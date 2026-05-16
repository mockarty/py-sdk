# Copyright (c) 2026 Mockarty. All rights reserved.

"""End-to-end example test — exercises the full DSL surface.

Mirrors the README quick-start so the example is always live. Runs
against an in-memory stub HTTP client so no admin server is required.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from mockarty.fuzz import (
    AssertNoCrash,
    AssertResponseTimeUnder,
    AssertStatus,
    Mutator,
    Runner,
    Seed,
    Target,
    write_to,
)


class _StubClient:
    def __init__(self, queue: List[Dict[str, Any]]):
        self._queue = list(queue)

    def post(self, url: str, json: Dict[str, Any]) -> Dict[str, Any]:
        return self._queue.pop(0)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._queue.pop(0)


def test_full_dsl_pattern_end_to_end():
    """Build a complete target, transpile, submit via stub, wait."""

    target = (
        Target("login-flow")
        .description("Stress-test login endpoint")
        .http_endpoint("POST", "/api/v1/login", base_url="https://api.example.com")
        .seeds(
            [
                Seed("valid", '{"username":"admin","password":"secret"}'),
                Seed("missing-pw", '{"username":"admin"}'),
                Seed("unicode", '{"name":"Привет"}'),
            ]
        )
        .mutator(Mutator.JSON)
        .mutator(Mutator.SQLI)
        .duration(timedelta(minutes=5))
        .timeout_per_request(timedelta(seconds=10))
        .max_requests(5000)
        .concurrency(16)
        .stop_on_finding(True)
        .auth_header("Bearer test-token")
        .custom_headers({"X-Tenant": "acme"})
        .reporter("allure")
        .reporter("junit")
        .assertion(AssertStatus(range(200, 300)))
        .assertion(AssertNoCrash())
        .assertion(AssertResponseTimeUnder(timedelta(milliseconds=500)))
    )

    payload = target.to_json()

    # ── verify the JSON has every section ──
    assert payload["name"] == "login-flow"
    assert payload["targetBaseUrl"] == "https://api.example.com"
    assert len(payload["seedRequests"]) == 3
    assert "json" in payload["payloadCategories"]
    assert "sqli" in payload["payloadCategories"]
    assert payload["options"]["maxDuration"] == "5m"
    assert payload["options"]["timeoutPerReq"] == "10s"
    assert payload["options"]["maxRequests"] == 5000
    assert payload["options"]["concurrency"] == 16
    assert payload["options"]["stopOnCritical"] is True
    assert payload["options"]["authHeader"] == "Bearer test-token"
    assert payload["options"]["customHeaders"] == {"X-Tenant": "acme"}
    assert payload["_sdkMeta"]["reporters"] == ["allure", "junit"]
    assert len(payload["_sdkMeta"]["assertions"]) == 3

    # ── submit + wait via stub ──
    stub = _StubClient(
        [
            {"id": "run-1"},
            {
                "id": "run-1",
                "status": "completed",
                "totalRequests": 5000,
                "totalFindings": 0,
                "findings": [],
            },
        ]
    )
    runner = Runner(stub, poll_interval=0.001)
    job_id = runner.submit(target)
    result = runner.wait(job_id, timeout=5)
    assert job_id == "run-1"
    assert result.passed
    assert result.total_requests == 5000


def test_local_spawn_pattern_writes_config_and_invokes_cli(tmp_path):
    """Mirror the air-gapped CI pattern from the README."""

    target = (
        Target("smoke")
        .http_endpoint("GET", "/health")
        .mutator(Mutator.JSON)
        .duration(timedelta(seconds=30))
    )

    captured_cmd: List[List[str]] = []
    captured_config: List[Dict[str, Any]] = []

    def fake_run(cmd, **kw):
        captured_cmd.append(list(cmd))
        config_path = cmd[cmd.index("--config") + 1]
        captured_config.append(json.loads(open(config_path).read()))

        class _C:
            returncode = 0
            stdout = "fuzz ok"
            stderr = ""

        return _C()

    with patch("subprocess.run", side_effect=fake_run):
        runner = Runner()
        spawn = runner.local_spawn(target, extra_args=["--report", "allure"])

    assert spawn.succeeded
    assert spawn.stdout == "fuzz ok"
    assert captured_cmd[0][:4] == ["mockarty-cli", "fuzz", "run", "--config"]
    assert "--report" in captured_cmd[0]
    assert captured_config[0]["name"] == "smoke"


def test_write_to_helper_dumps_canonical_json(tmp_path):
    target = Target("w").http_endpoint("GET", "/").mutator(Mutator.JSON)
    out = write_to(target, tmp_path / "fuzz.json")
    payload = json.loads(out.read_text())
    assert payload["name"] == "w"
    # write_to sorts keys → top level is alphabetical.
    text = out.read_text()
    # name comes after _sdkMeta alphabetically; sort_keys=True implies
    # _sdkMeta appears before name (underscore sorts before letters).
    assert text.index("_sdkMeta") < text.index('"name"')


def test_pytest_factory_fixture_pre_names_target(
    mockarty_fuzz_target_factory,
):
    """Verify the pytest fixture wires up properly."""

    t = mockarty_fuzz_target_factory()
    assert t.name == "test_pytest_factory_fixture_pre_names_target"


def test_pytest_factory_accepts_override(
    mockarty_fuzz_target_factory,
):
    t = mockarty_fuzz_target_factory("custom-name")
    assert t.name == "custom-name"


def test_pytest_runner_fixture_returns_runner(mockarty_fuzz_runner):
    """The fixture always yields a :class:`Runner` instance; whether
    HTTP-capable or local-spawn-only depends on the project's setup
    (presence of a ``mockarty_client`` fixture).
    """
    assert mockarty_fuzz_runner is not None
    assert isinstance(mockarty_fuzz_runner, Runner)


def test_runner_without_client_raises_on_submit():
    runner = Runner(client=None)
    with pytest.raises(RuntimeError):
        runner.submit(Target("x").http_endpoint("GET", "/"))


# The fuzz pytest fixtures (mockarty_fuzz_target_factory, etc.) are
# made available to this module via tests/conftest_fuzz.py imported
# from tests/conftest.py.
