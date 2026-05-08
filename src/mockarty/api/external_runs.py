# Copyright (c) 2026 Mockarty. All rights reserved.

"""External-run upload API for the Mockarty test framework.

Used by the pytest plugin (and direct callers) to ship a per-test
outcome — status, steps, captured stdout/stderr, small attachments — to
TCM as a synthetic case run, without invoking the orchestrator.

The wire shape is defined server-side in ``internal/testcase/external_run.go``
(``ExternalRunRequest``). This module is the typed Python facade. Field
names use camelCase to match the Go struct's JSON tags.
"""

from __future__ import annotations

import base64
from typing import Any, Iterable, Optional
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase

# Schema version this build of the SDK speaks. Server validates and
# returns 400 on mismatch — bumping it is a coordinated change with
# server + Java SDK.
EXTERNAL_RUN_SCHEMA_VERSION = 1

# Status values the framework can report. The server normalises into
# RunStatus (passed/failed/skipped/cancelled) on persist.
EXTERNAL_STATUS_PASSED = "passed"
EXTERNAL_STATUS_FAILED = "failed"
EXTERNAL_STATUS_BROKEN = "broken"
EXTERNAL_STATUS_SKIPPED = "skipped"
EXTERNAL_STATUS_CANCELLED = "cancelled"


def _ns_path(namespace: str) -> str:
    """Return the namespace-scoped /tcm/external-runs path.

    Namespaces are URL-quoted so a user-supplied value with slashes or
    other reserved characters cannot inject path segments — the server
    already validates the slug, but the SDK should be defensive.
    """
    if not namespace:
        raise ValueError("namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/tcm/external-runs"


def _build_attachments(
    attachments: Optional[Iterable[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Normalise attachments into the wire shape (``bodyB64`` + name + content type).

    Accepts either a list of dicts that already match the wire shape, or
    dicts with a ``body`` (bytes/str) field which we base64-encode here so
    callers don't have to think about encoding.
    """
    if not attachments:
        return []
    out: list[dict[str, Any]] = []
    for a in attachments:
        if not isinstance(a, dict) or not a.get("name"):
            raise ValueError("attachment requires a non-empty name")
        if "bodyB64" in a:
            entry = {
                "name": a["name"],
                "contentType": a.get("contentType", "application/octet-stream"),
                "bodyB64": a["bodyB64"],
            }
        else:
            body = a.get("body", b"")
            if isinstance(body, str):
                body = body.encode("utf-8")
            if not isinstance(body, (bytes, bytearray)):
                raise TypeError("attachment body must be bytes or str")
            entry = {
                "name": a["name"],
                "contentType": a.get("contentType", "application/octet-stream"),
                "bodyB64": base64.b64encode(body).decode("ascii"),
            }
        out.append(entry)
    return out


def _build_payload(
    *,
    status: str,
    case_id: Optional[str],
    case_name: Optional[str],
    plan_id: Optional[str],
    auto_create: bool,
    framework: Optional[str],
    framework_version: Optional[str],
    external_id: Optional[str],
    test_display_name: Optional[str],
    duration_ms: int,
    error: Optional[str],
    stdout: Optional[str],
    stderr: Optional[str],
    started_at: Optional[str],
    finished_at: Optional[str],
    labels: Optional[dict[str, str]],
    metadata: Optional[dict[str, Any]],
    steps: Optional[list[dict[str, Any]]],
    attachments: Optional[Iterable[dict[str, Any]]],
) -> dict[str, Any]:
    if not case_id and not case_name:
        raise ValueError("one of case_id / case_name is required")
    if auto_create and not case_name:
        raise ValueError("auto_create requires case_name")
    payload: dict[str, Any] = {
        "schemaVersion": EXTERNAL_RUN_SCHEMA_VERSION,
        "status": status,
        "autoCreate": bool(auto_create),
    }
    if case_id:
        payload["caseId"] = case_id
    if case_name:
        payload["caseName"] = case_name
    if plan_id:
        payload["planId"] = plan_id
    if framework:
        payload["framework"] = framework
    if framework_version:
        payload["frameworkVersion"] = framework_version
    if external_id:
        payload["externalId"] = external_id
    if test_display_name:
        payload["testDisplayName"] = test_display_name
    if duration_ms:
        payload["durationMs"] = int(duration_ms)
    if error:
        payload["error"] = error
    if stdout:
        payload["stdout"] = stdout
    if stderr:
        payload["stderr"] = stderr
    if started_at:
        payload["startedAt"] = started_at
    if finished_at:
        payload["finishedAt"] = finished_at
    if labels:
        payload["labels"] = dict(labels)
    if metadata:
        payload["metadata"] = dict(metadata)
    if steps:
        payload["steps"] = list(steps)
    norm_attachments = _build_attachments(attachments)
    if norm_attachments:
        payload["attachments"] = norm_attachments
    return payload


class ExternalRunsAPI(SyncAPIBase):
    """Sync client for ``/tcm/external-runs``."""

    def report(
        self,
        *,
        status: str,
        case_id: Optional[str] = None,
        case_name: Optional[str] = None,
        plan_id: Optional[str] = None,
        auto_create: bool = False,
        framework: Optional[str] = None,
        framework_version: Optional[str] = None,
        external_id: Optional[str] = None,
        test_display_name: Optional[str] = None,
        duration_ms: int = 0,
        error: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        steps: Optional[list[dict[str, Any]]] = None,
        attachments: Optional[Iterable[dict[str, Any]]] = None,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Persist a synthetic case run from an external test framework.

        Returns the JSON envelope from the server: ``run_id``, ``case_id``,
        ``case_name``, ``namespace``, ``status``, ``url``, ``resolved``.

        Defaults are tuned for the 80% case: pass ``case_id`` (UUID) or
        ``case_name`` plus ``status`` and the rest is optional.
        """
        ns = namespace or self._namespace
        body = _build_payload(
            status=status,
            case_id=case_id,
            case_name=case_name,
            plan_id=plan_id,
            auto_create=auto_create,
            framework=framework,
            framework_version=framework_version,
            external_id=external_id,
            test_display_name=test_display_name,
            duration_ms=duration_ms,
            error=error,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
            labels=labels,
            metadata=metadata,
            steps=steps,
            attachments=attachments,
        )
        resp = self._request("POST", _ns_path(ns), json=body)
        return resp.json() if resp.content else {}


class AsyncExternalRunsAPI(AsyncAPIBase):
    """Async counterpart of :class:`ExternalRunsAPI`."""

    async def report(
        self,
        *,
        status: str,
        case_id: Optional[str] = None,
        case_name: Optional[str] = None,
        plan_id: Optional[str] = None,
        auto_create: bool = False,
        framework: Optional[str] = None,
        framework_version: Optional[str] = None,
        external_id: Optional[str] = None,
        test_display_name: Optional[str] = None,
        duration_ms: int = 0,
        error: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        steps: Optional[list[dict[str, Any]]] = None,
        attachments: Optional[Iterable[dict[str, Any]]] = None,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body = _build_payload(
            status=status,
            case_id=case_id,
            case_name=case_name,
            plan_id=plan_id,
            auto_create=auto_create,
            framework=framework,
            framework_version=framework_version,
            external_id=external_id,
            test_display_name=test_display_name,
            duration_ms=duration_ms,
            error=error,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            finished_at=finished_at,
            labels=labels,
            metadata=metadata,
            steps=steps,
            attachments=attachments,
        )
        resp = await self._request("POST", _ns_path(ns), json=body)
        return resp.json() if resp.content else {}
