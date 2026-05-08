# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the external-runs SDK API.

Covers payload-builder validation + transport happy/error paths via
respx mocking. The aim is to confirm the wire shape matches what the Go
service expects without standing up a live server.
"""

from __future__ import annotations

import base64

import httpx
import pytest
import respx

from mockarty import EXTERNAL_RUN_SCHEMA_VERSION, MockartyClient
from mockarty.api.external_runs import _build_attachments, _build_payload


# ── _build_payload ──────────────────────────────────────────────────────


def test_build_payload_minimum_fields():
    body = _build_payload(
        status="passed",
        case_id="case-1",
        case_name=None,
        plan_id=None,
        auto_create=False,
        framework=None,
        framework_version=None,
        external_id=None,
        test_display_name=None,
        duration_ms=0,
        error=None,
        stdout=None,
        stderr=None,
        started_at=None,
        finished_at=None,
        labels=None,
        metadata=None,
        steps=None,
        attachments=None,
    )
    assert body == {
        "schemaVersion": EXTERNAL_RUN_SCHEMA_VERSION,
        "status": "passed",
        "autoCreate": False,
        "caseId": "case-1",
    }


def test_build_payload_full_shape():
    body = _build_payload(
        status="failed",
        case_id=None,
        case_name="login flow",
        plan_id="plan-7",
        auto_create=True,
        framework="pytest",
        framework_version="8.4.2",
        external_id="tests/test_x.py::test_y",
        test_display_name="test_y",
        duration_ms=1234,
        error="AssertionError",
        stdout="x",
        stderr="y",
        started_at="2026-05-09T10:00:00Z",
        finished_at="2026-05-09T10:00:01Z",
        labels={"env": "ci"},
        metadata={"build": "42"},
        steps=[{"name": "step1", "status": "passed"}],
        attachments=[{"name": "a", "body": b"hi"}],
    )
    assert body["caseName"] == "login flow"
    assert body["autoCreate"] is True
    assert body["framework"] == "pytest"
    assert body["frameworkVersion"] == "8.4.2"
    assert body["externalId"] == "tests/test_x.py::test_y"
    assert body["labels"] == {"env": "ci"}
    assert body["steps"] == [{"name": "step1", "status": "passed"}]
    # Attachment body got base64-encoded.
    assert body["attachments"][0]["bodyB64"] == base64.b64encode(b"hi").decode()


def test_build_payload_requires_case_identifier():
    with pytest.raises(ValueError, match="case_id"):
        _build_payload(
            status="passed",
            case_id=None,
            case_name=None,
            plan_id=None,
            auto_create=False,
            framework=None,
            framework_version=None,
            external_id=None,
            test_display_name=None,
            duration_ms=0,
            error=None,
            stdout=None,
            stderr=None,
            started_at=None,
            finished_at=None,
            labels=None,
            metadata=None,
            steps=None,
            attachments=None,
        )


def test_build_payload_auto_create_requires_name():
    with pytest.raises(ValueError, match="auto_create requires case_name"):
        _build_payload(
            status="passed",
            case_id="x",
            case_name=None,
            plan_id=None,
            auto_create=True,
            framework=None,
            framework_version=None,
            external_id=None,
            test_display_name=None,
            duration_ms=0,
            error=None,
            stdout=None,
            stderr=None,
            started_at=None,
            finished_at=None,
            labels=None,
            metadata=None,
            steps=None,
            attachments=None,
        )


# ── _build_attachments ──────────────────────────────────────────────────


def test_build_attachments_encodes_bytes():
    out = _build_attachments([{"name": "x", "body": b"abc"}])
    assert out[0]["bodyB64"] == base64.b64encode(b"abc").decode()
    assert out[0]["contentType"] == "application/octet-stream"


def test_build_attachments_encodes_str_as_utf8():
    out = _build_attachments([{"name": "x", "body": "hello"}])
    assert base64.b64decode(out[0]["bodyB64"]) == b"hello"


def test_build_attachments_passes_through_existing_b64():
    pre_b64 = base64.b64encode(b"already").decode()
    out = _build_attachments([{"name": "x", "bodyB64": pre_b64}])
    assert out[0]["bodyB64"] == pre_b64


def test_build_attachments_rejects_missing_name():
    with pytest.raises(ValueError):
        _build_attachments([{"body": b"x"}])


def test_build_attachments_rejects_non_byte_body():
    with pytest.raises(TypeError):
        _build_attachments([{"name": "x", "body": 123}])


def test_build_attachments_empty_returns_empty_list():
    assert _build_attachments(None) == []
    assert _build_attachments([]) == []


# ── Transport ──────────────────────────────────────────────────────────


@respx.mock
def test_external_runs_report_posts_correct_path_and_body():
    route = respx.post("http://localhost:5770/api/v1/namespaces/qa/tcm/external-runs").mock(
        return_value=httpx.Response(
            200,
            json={
                "runId": "run-uuid",
                "caseId": "case-uuid",
                "caseName": "login",
                "namespace": "qa",
                "status": "passed",
                "url": "/ui/tcm/case-runs/run-uuid",
                "resolved": "uuid",
                "startedAt": "2026-05-09T10:00:00Z",
            },
        )
    )

    with MockartyClient(base_url="http://localhost:5770", namespace="qa") as client:
        result = client.external_runs.report(
            status="passed",
            case_id="case-uuid",
            framework="pytest",
            external_id="t::y",
        )

    assert route.called
    assert result["runId"] == "run-uuid"
    assert result["resolved"] == "uuid"
    body = route.calls[0].request.read()
    import json

    parsed = json.loads(body)
    assert parsed["caseId"] == "case-uuid"
    assert parsed["framework"] == "pytest"
    assert parsed["schemaVersion"] == EXTERNAL_RUN_SCHEMA_VERSION


@respx.mock
def test_external_runs_report_namespace_override():
    route = respx.post("http://localhost:5770/api/v1/namespaces/other-ns/tcm/external-runs").mock(
        return_value=httpx.Response(200, json={})
    )
    with MockartyClient(base_url="http://localhost:5770", namespace="qa") as client:
        client.external_runs.report(
            status="passed",
            case_id="x",
            namespace="other-ns",
        )
    assert route.called
