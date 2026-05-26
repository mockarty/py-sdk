# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Helper mapping Tester report → ExternalRunsAPI.report kwargs.

Mirrors ``sdk/go-sdk/tester/external_run.go`` so test suites that ship
to TCM via either SDK use the same field semantics.

Example::

    from mockarty import MockartyClient
    from mockarty.tester import Tester
    from mockarty.tester.external_run import to_report_kwargs

    with MockartyClient(base_url="http://...") as client, Tester(...) as t:
        t.http().get("/me").expect_status(200)

        client.external_runs.report(
            **to_report_kwargs(t, case_name="me-endpoint", auto_create=True),
            namespace="qa",
        )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .tester import StepRecord, Tester


def to_report_kwargs(
    t: Tester,
    *,
    case_id: Optional[str] = None,
    case_name: Optional[str] = None,
    full_name: Optional[str] = None,
    test_display_name: Optional[str] = None,
    plan_id: Optional[str] = None,
    plan_run_id: Optional[str] = None,
    framework: Optional[str] = None,
    framework_version: Optional[str] = None,
    auto_create: bool = False,
    claim_case_ownership: bool = False,
    labels: Optional[dict[str, str]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Materialise the Tester's report into a kwargs dict ready to splat
    into :meth:`mockarty.api.external_runs.ExternalRunsAPI.report`.

    Every :class:`StepRecord` becomes one step entry; Protocol / Method /
    URL / StatusOrCode land under ``metadata`` so the server's UI can
    surface them without a schema migration.
    """
    report = t.report()
    steps: list[dict[str, Any]] = []
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms = 0

    if report:
        first = report[0]
        last = report[-1]
        if first.started_at:
            started_at = _to_iso(first.started_at)
        if last.ended_at:
            finished_at = _to_iso(last.ended_at)
            if first.started_at:
                duration_ms = int((last.ended_at - first.started_at) * 1000)

        for r in report:
            steps.append(_step_dict(r))

    status = "passed" if t.ok() else "failed"
    error = None
    if status == "failed":
        errs = t.errors()
        error = errs[0] if errs else None

    out: dict[str, Any] = {
        "status": status,
        "case_id": case_id,
        "case_name": case_name,
        "full_name": full_name,
        "test_display_name": test_display_name,
        "plan_id": plan_id,
        "framework": framework or "mockarty-tester-py",
        "framework_version": framework_version,
        "auto_create": auto_create,
        "claim_case_ownership": claim_case_ownership,
        "labels": labels,
        "metadata": metadata,
        "duration_ms": duration_ms,
        "started_at": started_at,
        "finished_at": finished_at,
        "steps": steps or None,
        "error": error,
    }
    # plan_run_id is supported by some report() implementations; only
    # include it when set to avoid a TypeError on older signatures.
    if plan_run_id is not None:
        out["plan_run_id"] = plan_run_id
    # Drop None entries so downstream report() receives only what we
    # actually mean to set (matches the SDK's idiomatic keyword shape).
    return {k: v for k, v in out.items() if v is not None}


def _step_dict(r: StepRecord) -> dict[str, Any]:
    step: dict[str, Any] = {
        "name": r.name,
        "status": "passed" if not r.failures else "failed",
        "metadata": _step_metadata(r),
    }
    if r.started_at:
        step["startedAt"] = _to_iso(r.started_at)
    if r.ended_at:
        step["finishedAt"] = _to_iso(r.ended_at)
        if r.started_at:
            step["durationMs"] = int((r.ended_at - r.started_at) * 1000)
    if r.failures:
        # Join with "; " so a single-line UI shows the first failure.
        step["error"] = "; ".join(r.failures)
    return step


def _step_metadata(r: StepRecord) -> dict[str, Any]:
    m: dict[str, Any] = {"protocol": r.protocol, "method": r.method}
    if r.url:
        m["url"] = r.url
    if r.status_or_code:
        m["statusOrCode"] = r.status_or_code
    return m


def _to_iso(ts: float) -> str:
    """Convert a Unix timestamp (float seconds) to RFC3339 UTC."""
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    )
