# Copyright (c) 2026 Mockarty. All rights reserved.

"""Result + Finding parser tests."""

from __future__ import annotations

from datetime import datetime

from mockarty.fuzz import Finding, Result


def test_finding_parses_canonical_payload():
    f = Finding.from_dict(
        {
            "id": "f1",
            "runId": "r1",
            "title": "SQL injection",
            "description": "panic in handler",
            "category": "sqli",
            "severity": "high",
            "requestMethod": "POST",
            "requestUrl": "https://api/login",
            "requestBody": '{"u":"\' OR 1=1"}',
            "responseStatus": 500,
            "responseTimeMs": 1200,
            "mutationApplied": "sqli-classic",
            "originalSeedId": "valid",
            "triagedStatus": "new",
            "reproducible": True,
            "reproduceCount": 3,
            "requestHeaders": {"X": "y"},
            "responseHeaders": {"Z": "w"},
        }
    )
    assert f.id == "f1"
    assert f.run_id == "r1"
    assert f.title == "SQL injection"
    assert f.category == "sqli"
    assert f.severity == "high"
    assert f.response_status == 500
    assert f.reproducible is True
    assert f.is_security is True
    assert f.is_crash is False


def test_finding_handles_missing_fields():
    f = Finding.from_dict({})
    assert f.id == ""
    assert f.response_status == 0
    assert f.reproducible is None


def test_finding_handles_none_numeric_fields():
    f = Finding.from_dict({"responseStatus": None, "responseTimeMs": None})
    assert f.response_status == 0
    assert f.response_time_ms == 0


def test_finding_crash_categories():
    for cat in ("500_error", "timeout", "empty_response"):
        assert Finding.from_dict({"category": cat}).is_crash is True
    assert Finding.from_dict({"category": "sqli"}).is_crash is False


def test_finding_security_categories():
    for cat in ("sqli", "xss", "ssrf", "ldap_injection", "idor"):
        assert Finding.from_dict({"category": cat}).is_security is True
    assert Finding.from_dict({"category": "500_error"}).is_security is False


def test_finding_preserves_raw_for_forward_compat():
    f = Finding.from_dict({"futureField": 42, "id": "x"})
    assert f.raw["futureField"] == 42


def test_result_parses_canonical_payload():
    r = Result.from_dict(
        {
            "id": "run-1",
            "configId": "cfg-1",
            "configName": "login-flow",
            "namespace": "default",
            "status": "completed",
            "strategy": "all",
            "startedAt": "2026-05-16T10:00:00Z",
            "completedAt": "2026-05-16T10:05:00Z",
            "durationMs": 300_000,
            "totalRequests": 1000,
            "totalFindings": 2,
            "criticalFindings": 0,
            "highFindings": 1,
            "mediumFindings": 1,
            "lowFindings": 0,
            "infoFindings": 0,
            "networkErrorCount": 0,
            "findings": [
                {"id": "f1", "severity": "high", "category": "sqli"},
                {"id": "f2", "severity": "medium", "category": "xss"},
            ],
        }
    )
    assert r.id == "run-1"
    assert r.status == "completed"
    assert r.duration_ms == 300_000
    assert r.high_findings == 1
    assert isinstance(r.started_at, datetime)
    assert r.completed_at.isoformat().startswith("2026-05-16T10:05:00")
    assert len(r.findings) == 2


def test_result_passed_property():
    assert (
        Result.from_dict({"status": "completed", "criticalFindings": 0}).passed is True
    )
    assert Result.from_dict({"status": "completed", "highFindings": 1}).failed is True
    assert Result.from_dict({"status": "running"}).failed is True


def test_result_handles_invalid_datetime_gracefully():
    r = Result.from_dict({"startedAt": "garbage"})
    assert r.started_at is None


def test_result_handles_empty_startedat():
    r = Result.from_dict({"startedAt": ""})
    assert r.started_at is None


def test_result_drops_non_dict_findings_entries():
    r = Result.from_dict({"findings": [{"id": "f1"}, "not-a-dict", None]})
    assert len(r.findings) == 1
    assert r.findings[0].id == "f1"
