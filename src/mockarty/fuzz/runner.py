# Copyright (c) 2026 Mockarty. All rights reserved.

"""Runner — thin REST + subprocess wrapper around the admin server.

Three execution modes:

1. :meth:`Runner.submit` — POST the transpiled config to
   ``/api/v1/fuzzing/run`` and return a ``JobID`` immediately.
2. :meth:`Runner.wait` — poll ``/api/v1/fuzzing/results/{id}`` until
   the status reaches a terminal state.
3. :meth:`Runner.local_spawn` — write the JSON config to a temp file
   and invoke ``mockarty-cli fuzz run`` via subprocess. Useful for
   air-gapped CI runners that don't have HTTP reach to the admin
   server.

The SDK does NOT execute fuzz mutations in-process — see
``feedback_sdk_thin_layer.md``. We only describe and dispatch.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Protocol, TYPE_CHECKING, Union

from mockarty.fuzz.result import Finding, Result

if TYPE_CHECKING:  # pragma: no cover
    from mockarty.fuzz.dsl import Target

# Terminal fuzz-run statuses — anything outside this set is "still going".
_TERMINAL = {
    "completed",
    "success",
    "passed",
    "failed",
    "stopped",
    "error",
    "cancelled",
}


class _HttpClient(Protocol):
    """Minimal HTTP surface the runner depends on.

    We accept anything quack-typed: the project's own
    :class:`mockarty.client.MockartyClient`, the ``httpx.Client`` it
    wraps, a hand-rolled stub in tests, etc. Only ``request``-style
    methods we touch are required.
    """

    def post(self, url: str, json: Dict[str, Any]) -> Any: ...  # noqa: E704

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any: ...  # noqa: E704


JobID = str


class Runner:
    """Dispatcher for fuzz runs.

    Usage::

        from mockarty.client import MockartyClient
        from mockarty.fuzz import Runner

        client = MockartyClient(base_url="https://mockarty.local", token="t")
        runner = Runner(client)

        job_id = runner.submit(target)
        result = runner.wait(job_id, timeout=600)
        assert result.passed, f"crashes: {len(result.findings)}"
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        *,
        cli_path: str = "mockarty-cli",
        poll_interval: float = 2.0,
    ) -> None:
        # Accept either a raw httpx-style client (with .post/.get) or a
        # :class:`mockarty.client.MockartyClient` (where we unwrap to
        # the inner httpx client). Stubs are accepted as-is when they
        # implement the .post/.get protocol.
        if client is not None and not (
            hasattr(client, "post") and hasattr(client, "get")
        ):
            inner = getattr(client, "_http", None)
            if inner is not None and hasattr(inner, "post") and hasattr(inner, "get"):
                client = inner
        self._client = client
        self._cli_path = cli_path
        self._poll_interval = max(0.1, float(poll_interval))

    # ── HTTP-backed flows ────────────────────────────────────────

    def submit(self, target: "Target") -> JobID:
        """POST the transpiled config; return the run id."""

        if self._client is None:
            raise RuntimeError(
                "Runner has no HTTP client — pass MockartyClient(...) to "
                "Runner(...) or use .local_spawn() instead"
            )
        payload = target.to_json()
        resp = self._client.post("/api/v1/fuzzing/run", json=payload)
        data = self._json(resp)
        run_id = str(data.get("id") or data.get("runId") or "")
        if not run_id:
            raise RuntimeError(f"server response missing 'id'/'runId' field: {data!r}")
        return run_id

    def get(self, job_id: JobID) -> Result:
        """Fetch the current result snapshot for ``job_id``.

        When the response payload omits the ``findings`` key entirely
        (i.e. the server splits them onto the separate findings
        endpoint), we fetch them lazily. An explicit empty list is
        respected as "no findings" so polling doesn't double-hit.
        """

        if self._client is None:
            raise RuntimeError("Runner has no HTTP client")
        resp = self._client.get(f"/api/v1/fuzzing/results/{job_id}")
        data = self._json(resp)
        result = Result.from_dict(data)
        if "findings" not in data:
            # The server didn't inline the findings array — fetch via
            # the dedicated endpoint. Skipped when the response payload
            # explicitly sets ``findings: []``.
            result.findings = self._fetch_findings(job_id)
        return result

    def wait(
        self,
        job_id: JobID,
        *,
        timeout: float = 600.0,
        poll_interval: Optional[float] = None,
    ) -> Result:
        """Poll until the run reaches a terminal state or ``timeout``
        elapses. Raises :class:`TimeoutError` on timeout.
        """

        if timeout <= 0:
            raise ValueError("timeout must be positive")
        interval = poll_interval or self._poll_interval
        deadline = time.monotonic() + timeout
        last: Optional[Result] = None
        while time.monotonic() < deadline:
            last = self.get(job_id)
            if last.status in _TERMINAL:
                return last
            time.sleep(interval)
        raise TimeoutError(
            f"fuzz run {job_id} did not reach terminal state in {timeout}s "
            f"(last status: {last.status if last else 'unknown'})"
        )

    def stream(
        self,
        job_id: JobID,
        *,
        poll_interval: Optional[float] = None,
        max_iterations: Optional[int] = None,
    ) -> Iterator[Result]:
        """Yield :class:`Result` snapshots until the run terminates.

        Implemented as polling (not SSE) so it works against any admin
        server build — the server's SSE channel can be wired later
        without changing this interface.
        """

        interval = poll_interval or self._poll_interval
        seen = 0
        while max_iterations is None or seen < max_iterations:
            snap = self.get(job_id)
            yield snap
            seen += 1
            if snap.status in _TERMINAL:
                return
            time.sleep(interval)

    def stop(self, job_id: JobID) -> None:
        """Best-effort cancel of a running fuzz job."""

        if self._client is None:
            raise RuntimeError("Runner has no HTTP client")
        self._client.post(f"/api/v1/fuzzing/run/{job_id}/stop", json={})

    # ── Subprocess flow ──────────────────────────────────────────

    def local_spawn(
        self,
        target: "Target",
        *,
        cli_path: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        keep_config: bool = False,
    ) -> "LocalSpawnResult":
        """Write the config to a temp file and invoke ``mockarty-cli``.

        The CLI is invoked with ``fuzz run --config <path>`` plus any
        ``extra_args``. The default ``cli_path`` (``mockarty-cli``)
        assumes the binary is on PATH; override per call when running
        from a custom installation.
        """

        payload = target.to_json()
        cli = cli_path or self._cli_path

        # NamedTemporaryFile with delete=False because we close it
        # before subprocess invocation (Windows quirk) and clean up
        # ourselves in the finally block.
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", prefix="mockarty-fuzz-", delete=False
        )
        try:
            json.dump(payload, tmp, indent=2, sort_keys=True)
            tmp.flush()
            tmp.close()
            cmd = [cli, "fuzz", "run", "--config", tmp.name]
            if extra_args:
                cmd.extend(extra_args)
            proc_env = dict(os.environ)
            if env:
                proc_env.update(env)
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=proc_env,
                timeout=timeout,
                check=False,
            )
            return LocalSpawnResult(
                command=cmd,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                config_path=Path(tmp.name) if keep_config else None,
            )
        finally:
            if not keep_config:
                try:
                    os.unlink(tmp.name)
                except OSError:  # pragma: no cover — defensive
                    pass

    # ── Internals ────────────────────────────────────────────────

    def _fetch_findings(self, job_id: JobID) -> List[Finding]:
        """Hit the findings list endpoint with ``runId`` filter."""

        if self._client is None:
            return []
        try:
            resp = self._client.get(
                "/api/v1/fuzzing/findings", params={"runId": job_id}
            )
        except Exception:
            return []
        data = self._json(resp)
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            items = [d for d in data if isinstance(d, dict)]
        elif isinstance(data, dict):
            items = [
                d
                for d in (data.get("items") or data.get("findings") or [])
                if isinstance(d, dict)
            ]
        return [Finding.from_dict(item) for item in items]

    @staticmethod
    def _json(resp: Any) -> Dict[str, Any]:
        """Best-effort response-to-dict adapter.

        Supports httpx-style ``.json()`` and dict-typed responses from
        stubs / mocks. When the underlying response carries an HTTP
        error status we delegate to the shared error mapper so callers
        observe typed SDK exceptions (e.g.
        :class:`mockarty.errors.MockartyValidationError` for 400 with
        ``code=validation``) instead of a raw ``RuntimeError`` later
        on missing-field paths.
        """

        if isinstance(resp, dict):
            return resp
        # httpx.Response carries .is_success + .json(); when it isn't
        # successful we hand it to the SDK error mapper to keep typed
        # error parity with the rest of the API surface.
        if getattr(resp, "is_success", True) is False:
            # Imported lazily to avoid a circular dep on _base_client.
            from mockarty._base_client import raise_for_status

            raise_for_status(resp)  # always raises
        if hasattr(resp, "json"):
            data = resp.json()
            if isinstance(data, dict):
                return data
            return {"data": data}
        return {"raw": resp}


class LocalSpawnResult:
    """Outcome of :meth:`Runner.local_spawn` — captures the subprocess
    output so callers can stash logs / assert on exit codes.
    """

    __slots__ = ("command", "returncode", "stdout", "stderr", "config_path")

    def __init__(
        self,
        *,
        command: List[str],
        returncode: int,
        stdout: str,
        stderr: str,
        config_path: Optional[Path] = None,
    ) -> None:
        self.command = list(command)
        self.returncode = int(returncode)
        self.stdout = stdout
        self.stderr = stderr
        self.config_path = config_path

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0

    def __repr__(self) -> str:
        return (
            f"LocalSpawnResult(returncode={self.returncode}, "
            f"command={self.command[:2]!r}...)"
        )


__all__ = ["JobID", "LocalSpawnResult", "Runner"]


def write_to(target: "Target", path: Union[str, os.PathLike[str]]) -> Path:
    """Write a target's transpiled config to ``path`` as JSON.

    Convenience helper for CLI workflows: ``mockarty-cli fuzz run
    --config $(target.write_to(...))``. The directory is created on
    demand.
    """

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(target.to_json(), f, indent=2, sort_keys=True)
    return out
