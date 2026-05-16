# Copyright (c) 2026 Mockarty. All rights reserved.

"""Runner tests — verify submit / wait / stream / stop against a stub
HTTP client, and local_spawn against a subprocess mock.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from mockarty.fuzz import Mutator, Runner, Seed, Target, write_to
from mockarty.fuzz.runner import LocalSpawnResult


class _StubClient:
    """Records calls; returns canned JSON responses."""

    def __init__(self, responses: Optional[List[Dict[str, Any]]] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._responses = list(responses or [])
        self._idx = 0

    def _next(self) -> Dict[str, Any]:
        if self._idx >= len(self._responses):
            raise AssertionError(
                f"unexpected call (no more canned responses): {self.calls[-1]!r}"
            )
        r = self._responses[self._idx]
        self._idx += 1
        return r

    def post(self, url: str, json: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"method": "POST", "url": url, "json": json})
        return self._next()

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.calls.append({"method": "GET", "url": url, "params": params})
        return self._next()


def _target() -> Target:
    return (
        Target("t")
        .http_endpoint("GET", "/")
        .seeds([Seed("a", "{}")])
        .mutator(Mutator.JSON)
        .duration(timedelta(seconds=5))
    )


def test_submit_posts_to_run_endpoint_and_returns_id():
    client = _StubClient([{"id": "run-123"}])
    runner = Runner(client)
    job_id = runner.submit(_target())
    assert job_id == "run-123"
    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["url"] == "/api/v1/fuzzing/run"
    # the payload is the transpiled config
    assert client.calls[0]["json"]["name"] == "t"


def test_submit_accepts_run_id_field_too():
    client = _StubClient([{"runId": "alt-456"}])
    runner = Runner(client)
    assert runner.submit(_target()) == "alt-456"


def test_submit_raises_when_response_missing_id():
    client = _StubClient([{}])
    runner = Runner(client)
    with pytest.raises(RuntimeError):
        runner.submit(_target())


def test_submit_without_client_raises():
    runner = Runner(client=None)
    with pytest.raises(RuntimeError):
        runner.submit(_target())


def test_get_returns_result_and_inlines_findings():
    client = _StubClient(
        [
            {
                "id": "r",
                "status": "completed",
                "findings": [{"id": "f1", "category": "500_error", "severity": "high"}],
                "criticalFindings": 0,
                "highFindings": 1,
                "totalFindings": 1,
            }
        ]
    )
    runner = Runner(client)
    result = runner.get("r")
    assert result.id == "r"
    assert result.status == "completed"
    assert result.failed is True
    assert len(result.findings) == 1
    assert result.findings[0].id == "f1"
    assert result.findings[0].is_crash is True


def test_get_fetches_findings_separately_when_not_inlined():
    client = _StubClient(
        [
            {"id": "r", "status": "completed"},
            {"items": [{"id": "f1", "category": "sqli"}]},
        ]
    )
    runner = Runner(client)
    result = runner.get("r")
    assert len(result.findings) == 1
    assert result.findings[0].is_security is True
    # Verify the second call was to /findings with runId filter.
    assert client.calls[1]["url"] == "/api/v1/fuzzing/findings"
    assert client.calls[1]["params"] == {"runId": "r"}


def test_wait_polls_until_terminal():
    client = _StubClient(
        [
            {"id": "r", "status": "running"},
            {"id": "r", "status": "running"},
            {"id": "r", "status": "completed", "findings": []},
        ]
    )
    runner = Runner(client, poll_interval=0.001)
    result = runner.wait("r", timeout=5)
    assert result.status == "completed"


def test_wait_times_out():
    client = _StubClient(
        [
            {"id": "r", "status": "running", "findings": []},
        ]
        * 50
    )
    runner = Runner(client, poll_interval=0.01)
    with pytest.raises(TimeoutError):
        runner.wait("r", timeout=0.05)


def test_wait_rejects_non_positive_timeout():
    runner = Runner(_StubClient([]))
    with pytest.raises(ValueError):
        runner.wait("r", timeout=0)


def test_stream_yields_until_terminal():
    client = _StubClient(
        [
            {"id": "r", "status": "running", "findings": []},
            {"id": "r", "status": "running", "findings": []},
            {"id": "r", "status": "completed", "findings": []},
        ]
    )
    runner = Runner(client, poll_interval=0.001)
    snapshots = list(runner.stream("r"))
    assert len(snapshots) == 3
    assert snapshots[-1].status == "completed"


def test_stream_respects_max_iterations():
    client = _StubClient(
        [
            {"id": "r", "status": "running", "findings": []},
        ]
        * 5
    )
    runner = Runner(client, poll_interval=0.001)
    snapshots = list(runner.stream("r", max_iterations=2))
    assert len(snapshots) == 2


def test_stop_posts_to_stop_endpoint():
    client = _StubClient([{}])
    runner = Runner(client)
    runner.stop("r")
    assert client.calls[0]["url"] == "/api/v1/fuzzing/run/r/stop"


def test_local_spawn_invokes_cli_with_temp_config():
    target = _target()
    captured: List[List[str]] = []

    def fake_run(cmd, **kw):  # type: ignore[no-untyped-def]
        captured.append(list(cmd))
        # Verify the temp file exists and parses as our config.
        config_path = cmd[cmd.index("--config") + 1]
        payload = json.loads(Path(config_path).read_text())
        assert payload["name"] == "t"

        class _C:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return _C()

    with patch("subprocess.run", side_effect=fake_run):
        runner = Runner()
        result = runner.local_spawn(target, extra_args=["--quiet"])
    assert isinstance(result, LocalSpawnResult)
    assert result.succeeded
    assert result.returncode == 0
    # Verify the command structure.
    assert captured[0][:4] == ["mockarty-cli", "fuzz", "run", "--config"]
    assert "--quiet" in captured[0]
    # Temp file should be cleaned up since keep_config=False.
    assert result.config_path is None


def test_local_spawn_keep_config_retains_temp_file(tmp_path: Path):
    captured_path: List[str] = []

    def fake_run(cmd, **kw):  # type: ignore[no-untyped-def]
        path = cmd[cmd.index("--config") + 1]
        captured_path.append(path)

        class _C:
            returncode = 0
            stdout = ""
            stderr = ""

        return _C()

    with patch("subprocess.run", side_effect=fake_run):
        runner = Runner()
        result = runner.local_spawn(_target(), keep_config=True)
    assert result.config_path is not None
    assert result.config_path.exists()
    # Best-effort cleanup so we don't leak across test runs.
    try:
        result.config_path.unlink()
    except OSError:
        pass


def test_local_spawn_propagates_nonzero_exit():
    def fake_run(cmd, **kw):  # type: ignore[no-untyped-def]
        class _C:
            returncode = 2
            stdout = ""
            stderr = "boom"

        return _C()

    with patch("subprocess.run", side_effect=fake_run):
        runner = Runner()
        result = runner.local_spawn(_target())
    assert not result.succeeded
    assert result.returncode == 2
    assert result.stderr == "boom"


def test_local_spawn_passes_env():
    captured_env: Dict[str, str] = {}

    def fake_run(cmd, env=None, **kw):  # type: ignore[no-untyped-def]
        captured_env.update(env or {})

        class _C:
            returncode = 0
            stdout = ""
            stderr = ""

        return _C()

    with patch("subprocess.run", side_effect=fake_run):
        runner = Runner()
        runner.local_spawn(_target(), env={"FUZZ_SECRET": "xyz"})
    assert captured_env.get("FUZZ_SECRET") == "xyz"


def test_local_spawn_custom_cli_path():
    captured_cmd: List[List[str]] = []

    def fake_run(cmd, **kw):  # type: ignore[no-untyped-def]
        captured_cmd.append(list(cmd))

        class _C:
            returncode = 0
            stdout = ""
            stderr = ""

        return _C()

    with patch("subprocess.run", side_effect=fake_run):
        runner = Runner(cli_path="/opt/bin/mockarty-cli")
        runner.local_spawn(_target())
    assert captured_cmd[0][0] == "/opt/bin/mockarty-cli"


def test_write_to_creates_directory_and_dumps_json(tmp_path: Path):
    target = _target()
    out = write_to(target, tmp_path / "sub" / "cfg.json")
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["name"] == "t"


def test_runner_json_helper_handles_dict_and_httpx_like():
    # plain dict
    assert Runner._json({"x": 1}) == {"x": 1}

    class _R:
        def json(self):
            return {"y": 2}

    assert Runner._json(_R()) == {"y": 2}

    class _RList:
        def json(self):
            return [1, 2, 3]

    out = Runner._json(_RList())
    assert out == {"data": [1, 2, 3]}


def test_local_spawn_with_real_subprocess_against_true_binary():
    """Integration smoke: actually invoke `true` (always exits 0) via
    Runner.local_spawn — uses a real subprocess but a no-op binary.
    Skipped on platforms without /usr/bin/true.
    """
    true_path = "/usr/bin/true"
    if not Path(true_path).exists():
        pytest.skip("no /usr/bin/true on this platform")
    runner = Runner(cli_path=true_path)
    # `true` ignores args. We just want to verify the pipe / cleanup
    # flow works end-to-end against a real `subprocess.run`.
    result = runner.local_spawn(_target())
    assert result.succeeded
