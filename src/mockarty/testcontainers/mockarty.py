# Copyright (c) 2026 Mockarty. All rights reserved.

"""``MockartyContainer`` -- testcontainers wrapper for ``mockarty/cli:latest-mock``.

The wrapper is intentionally thin: the container itself runs the real
``mockarty-cli mock serve`` process baked into the image. This module
just owns the docker lifecycle (pull, start, wait for ``/health``,
stop) and exposes ergonomic admin URLs + ``apply`` / ``reset`` helpers
so existing WireMock / Mockarty-native test bodies port over without
changes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

# ---------------------------------------------------------------------------
# Public constants -- exported via __init__ so the surface stays self-
# documenting and "one-import" for users.
# ---------------------------------------------------------------------------

DEFAULT_IMAGE = "mockarty/cli:latest-mock"
MOCK_PORT = 8080
METRICS_PORT = 9090
STUBS_MOUNT = "/data/stubs"

FORMAT_AUTO = "auto"
FORMAT_WIREMOCK = "wiremock"
FORMAT_MOCKARTY = "mockarty"
FORMAT_MOCKOON = "mockoon"

_VALID_FORMATS = frozenset(
    {FORMAT_AUTO, FORMAT_WIREMOCK, FORMAT_MOCKARTY, FORMAT_MOCKOON}
)


def _lazy_docker_container() -> Any:
    """Import :class:`testcontainers.core.container.DockerContainer` lazily.

    The :mod:`testcontainers` package is an optional dependency, so we
    fail with a friendly message only when the user actually tries to
    instantiate a container -- importing :mod:`mockarty.testcontainers`
    alone never crashes on a slim production install.
    """
    try:
        from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - exercised via runtime import check
        raise ImportError(
            "mockarty.testcontainers requires the optional `testcontainers` "
            "package. Install with: pip install 'mockarty[testcontainers]' "
            "or `pip install testcontainers`."
        ) from exc
    return DockerContainer


# ---------------------------------------------------------------------------
# MockartyContainer
# ---------------------------------------------------------------------------


class MockartyContainer:
    """Wraps a running ``mockarty/cli:latest-mock`` instance.

    Designed for use as a context manager::

        with MockartyContainer() as c:
            c.apply(stub)
            ...

    All optional knobs flow through builder-style ``with_*`` methods so
    new options drop in without touching call-sites (mirrors the Go
    SDK's functional options).

    The class does NOT subclass :class:`DockerContainer` -- it
    composes one so the import remains lazy.
    """

    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        *,
        fmt: str = FORMAT_AUTO,
        stub_files: Optional[Iterable[str]] = None,
        env: Optional[dict[str, str]] = None,
        cmd: Optional[Iterable[str]] = None,
    ) -> None:
        if not image or not image.strip():
            raise ValueError("MockartyContainer: image must not be empty")
        if fmt not in _VALID_FORMATS:
            raise ValueError(
                f"MockartyContainer: unknown format {fmt!r} "
                f"(valid: {sorted(_VALID_FORMATS)})"
            )

        self._image: str = image.strip()
        self._format: str = fmt
        self._stub_files: list[Path] = [Path(p).resolve() for p in (stub_files or [])]
        self._env: dict[str, str] = dict(env or {})
        self._cmd: list[str] = list(cmd or [])
        self._container: Optional[Any] = None

    # ----- builder methods (functional-options analogue) ------------------

    def with_image(self, image: str) -> "MockartyContainer":
        if not image or not image.strip():
            raise ValueError("MockartyContainer: image must not be empty")
        self._image = image.strip()
        return self

    def with_format(self, fmt: str) -> "MockartyContainer":
        if fmt not in _VALID_FORMATS:
            raise ValueError(
                f"MockartyContainer: unknown format {fmt!r} "
                f"(valid: {sorted(_VALID_FORMATS)})"
            )
        self._format = fmt
        return self

    def with_stub_file(self, host_path: str | os.PathLike[str]) -> "MockartyContainer":
        p = Path(host_path)
        if not str(p).strip():
            raise ValueError("MockartyContainer: stub file path must not be empty")
        self._stub_files.append(p.resolve())
        return self

    def with_env(self, key: str, value: str) -> "MockartyContainer":
        if not key or not key.strip():
            raise ValueError("MockartyContainer: env key must not be empty")
        self._env[key] = value
        return self

    def with_cmd(self, *args: str) -> "MockartyContainer":
        self._cmd = list(args)
        return self

    # ----- lifecycle ------------------------------------------------------

    def start(self) -> "MockartyContainer":
        DockerContainer = _lazy_docker_container()
        c = DockerContainer(self._image)
        c = c.with_exposed_ports(MOCK_PORT, METRICS_PORT)
        c = c.with_env("MOCKARTY_STUB_FORMAT", self._format)
        for k, v in self._env.items():
            c = c.with_env(k, v)
        for stub in self._stub_files:
            c = c.with_volume_mapping(str(stub), f"{STUBS_MOUNT}/{stub.name}", "ro")
        if self._cmd:
            c = c.with_command(" ".join(self._cmd))

        c.start()
        self._wait_for_health(c)
        self._container = c
        return self

    def stop(self) -> None:
        """Stop and remove the container. Idempotent."""
        if self._container is not None:
            try:
                self._container.stop()
            finally:
                self._container = None

    def __enter__(self) -> "MockartyContainer":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ----- endpoint URLs --------------------------------------------------

    def url(self) -> str:
        c = self._require_started()
        host = c.get_container_host_ip()
        port = c.get_exposed_port(MOCK_PORT)
        return f"http://{host}:{port}"

    def wiremock_url(self) -> str:
        return self.url().rstrip("/") + "/__admin"

    def mockarty_url(self) -> str:
        return self.url().rstrip("/") + "/api/v1"

    def metrics_url(self) -> str:
        c = self._require_started()
        host = c.get_container_host_ip()
        port = c.get_exposed_port(METRICS_PORT)
        return f"http://{host}:{port}"

    # ----- admin operations ----------------------------------------------

    def apply(self, stub: Any) -> None:
        """Register one Mockarty-native stub via ``POST /api/v1/mocks``.

        Accepts anything :mod:`json`-serialisable -- a ``dict``, a
        :class:`mockarty.models.Mock`, or a generated dataclass with
        ``model_dump()``.
        """
        if stub is None:
            raise ValueError("MockartyContainer.apply: stub must not be None")
        payload = self._to_json(stub)
        self._post(self.mockarty_url() + "/mocks", payload)

    def reset(self) -> None:
        """Wipe every applied stub + request history on the container.

        Maps to the WireMock-compatible ``POST /__admin/reset`` which
        the CLI image also wires to its Mockarty internals.
        """
        self._post(self.wiremock_url() + "/reset", None)

    def logs(self) -> str:
        """Return the container stdout+stderr as a single string."""
        c = self._require_started()
        out, err = c.get_logs()

        def _decode(b: Any) -> str:
            if b is None:
                return ""
            if isinstance(b, bytes):
                return b.decode("utf-8", errors="replace")
            return str(b)

        return _decode(out) + _decode(err)

    # ----- internals ------------------------------------------------------

    def _require_started(self) -> Any:
        if self._container is None:
            raise RuntimeError("MockartyContainer has not been started yet")
        return self._container

    def _wait_for_health(self, container: Any) -> None:
        """Block until ``/health`` on the metrics port returns 200."""
        import time
        import urllib.error
        import urllib.request

        host = container.get_container_host_ip()
        port = container.get_exposed_port(METRICS_PORT)
        url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + 60.0
        last_err: Optional[BaseException] = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2.0) as resp:  # noqa: S310
                    if 200 <= resp.status < 300:
                        return
            except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
                last_err = exc
            time.sleep(0.5)
        raise TimeoutError(
            f"MockartyContainer: /health never returned 200 within 60s "
            f"(last error: {last_err!r})"
        )

    @staticmethod
    def _to_json(stub: Any) -> bytes:
        # Support pydantic v2 dataclass-y objects without a hard import.
        if hasattr(stub, "model_dump"):
            stub = stub.model_dump(exclude_none=True)
        elif hasattr(stub, "dict") and callable(stub.dict):  # pydantic v1
            stub = stub.dict(exclude_none=True)
        return json.dumps(stub).encode("utf-8")

    @staticmethod
    def _post(url: str, body: Optional[bytes]) -> None:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(  # noqa: S310
            url,
            data=body if body else b"",
            method="POST",
        )
        if body:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:  # noqa: S310
                if resp.status >= 400:
                    raise RuntimeError(
                        f"MockartyContainer: POST {url} returned {resp.status}"
                    )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(
                f"MockartyContainer: POST {url} returned {exc.code}: {detail.strip()}"
            ) from exc
