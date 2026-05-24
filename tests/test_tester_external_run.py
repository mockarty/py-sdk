# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for Python Tester → ExternalRunsAPI mapping helper."""

from __future__ import annotations

import respx
import httpx

from mockarty.tester import Tester, to_report_kwargs


@respx.mock
def test_to_report_kwargs_happy_path():
    respx.get("http://api.test/users/42").respond(
        200, json={"id": 42, "name": "Alice"},
    )
    t = Tester(base_url="http://api.test")
    (t.http().get("/users/42")
        .expect_status(200)
        .expect_json_path("$.name", "Alice"))
    t.finish()

    kwargs = to_report_kwargs(
        t,
        case_name="users/get",
        test_display_name="GET /users/42",
        framework="custom-runner",
        labels={"suite": "smoke"},
        auto_create=True,
    )
    assert kwargs["status"] == "passed"
    assert kwargs["case_name"] == "users/get"
    assert kwargs["framework"] == "custom-runner"
    assert kwargs["auto_create"] is True
    assert kwargs["labels"] == {"suite": "smoke"}
    assert len(kwargs["steps"]) == 1
    step = kwargs["steps"][0]
    assert step["status"] == "passed"
    assert step["metadata"]["protocol"] == "http"
    assert step["metadata"]["method"] == "GET"
    assert step["metadata"]["statusOrCode"] == 200
    # ISO timestamps present
    assert kwargs["started_at"].endswith("Z")
    assert kwargs["finished_at"].endswith("Z")
    assert kwargs["duration_ms"] >= 0


@respx.mock
def test_to_report_kwargs_failure_carries_error():
    respx.get("http://api.test/").respond(500)
    t = Tester(base_url="http://api.test")
    t.http().get("/").expect_status(200)
    t.finish()
    kwargs = to_report_kwargs(t, case_name="x")
    assert kwargs["status"] == "failed"
    assert kwargs["error"]
    assert len(kwargs["steps"]) == 1
    assert kwargs["steps"][0]["status"] == "failed"
    assert "error" in kwargs["steps"][0]


def test_to_report_kwargs_empty_tester():
    t = Tester()
    t.finish()
    kwargs = to_report_kwargs(t, case_name="empty")
    assert kwargs["status"] == "passed"
    assert "steps" not in kwargs       # None dropped
    assert "started_at" not in kwargs  # None dropped
    assert kwargs["case_name"] == "empty"
    assert kwargs["framework"] == "mockarty-tester-py"  # default
    assert kwargs["duration_ms"] == 0


@respx.mock
def test_to_report_kwargs_multiple_failures_joined():
    respx.get("http://api.test/").respond(200, json={"id": 1})
    t = Tester(base_url="http://api.test")
    (t.http().get("/")
        .expect_status(204)
        .expect_json_path("$.id", 99)
        .expect_json_path("$.missing", "x"))
    t.finish()
    kwargs = to_report_kwargs(t, case_name="multi")
    assert kwargs["status"] == "failed"
    step = kwargs["steps"][0]
    assert "; " in step["error"]
    assert "expect_status" in step["error"]


def test_to_report_kwargs_plan_run_id_passthrough():
    t = Tester()
    t.finish()
    kwargs = to_report_kwargs(t, case_id="abc", plan_run_id="run-uuid")
    assert kwargs["plan_run_id"] == "run-uuid"
    assert kwargs["case_id"] == "abc"


def test_to_report_kwargs_labels_metadata_passthrough():
    t = Tester()
    t.finish()
    kwargs = to_report_kwargs(
        t,
        case_id="case-uuid",
        labels={"feature": "auth", "severity": "critical"},
        metadata={"git_sha": "abc123", "ci_url": "https://ci/build/42"},
        claim_case_ownership=True,
    )
    assert kwargs["labels"] == {"feature": "auth", "severity": "critical"}
    assert kwargs["metadata"]["git_sha"] == "abc123"
    assert kwargs["claim_case_ownership"] is True


# ── End-to-end: chain into existing ExternalRunsAPI.report ─────────────


@respx.mock
def test_to_report_kwargs_splat_into_report():
    """Prove the kwargs are accepted by the existing report() signature."""
    from mockarty import MockartyClient
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"runId": "rid"})

    respx.post(
        "http://api.test/api/v1/namespaces/qa/tcm/external-runs",
    ).mock(side_effect=handler)

    respx.get("http://api.test/probe").respond(200, json={"v": 1})

    t = Tester(base_url="http://api.test")
    t.http().get("/probe").expect_status(200)
    t.finish()

    client = MockartyClient(base_url="http://api.test", api_key="mk_test", namespace="qa")
    kwargs = to_report_kwargs(t, case_name="probe-case", auto_create=True)
    try:
        client.external_runs.report(**kwargs)
    finally:
        client.close()

    assert "probe-case" in captured["body"]
    assert '"status": "passed"' in captured["body"] or '"status":"passed"' in captured["body"]
