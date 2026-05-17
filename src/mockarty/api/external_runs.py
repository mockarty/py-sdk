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
import glob
import json
import os
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

    def upload_allure_dir(
        self,
        directory: str,
        *,
        namespace: Optional[str] = None,
        plan_id: Optional[str] = None,
        framework: str = "allure",
        auto_create: bool = True,
        on_error: str = "warn",
    ) -> list[dict[str, Any]]:
        """Read an ``allure-results`` directory and POST each result.

        Reads every ``*-result.json`` file produced by either
        ``allure-pytest`` or our :class:`mockarty.allure_writer.AllureResultsWriter`,
        translates it into an external-run payload, and posts to TCM.
        Returns the list of server responses (one per result).

        Args:
            directory: filesystem path to the ``allure-results`` dir.
            namespace: target Mockarty namespace (falls back to client default).
            plan_id: optional plan id to associate every uploaded run with.
            framework: ``framework`` label on the wire (default ``allure``).
            auto_create: when True, missing cases are created server-side.
            on_error: ``warn`` (default) logs + continues; ``raise`` re-raises.
        """
        return _upload_allure_dir_impl(
            self,
            directory,
            namespace=namespace,
            plan_id=plan_id,
            framework=framework,
            auto_create=auto_create,
            on_error=on_error,
        )


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


# ── Allure → external-run translator ────────────────────────────────────


def _upload_allure_dir_impl(
    api: Any,
    directory: str,
    *,
    namespace: Optional[str],
    plan_id: Optional[str],
    framework: str,
    auto_create: bool,
    on_error: str,
) -> list[dict[str, Any]]:
    """Shared implementation between Sync/Async ExternalRunsAPI.

    Iterates the directory, translates each result JSON via
    :func:`allure_result_to_external_payload`, then calls
    :meth:`ExternalRunsAPI.report`. Caller controls error policy.
    """
    import warnings as _warnings

    if not os.path.isdir(directory):
        raise FileNotFoundError(f"allure-results directory not found: {directory}")
    out: list[dict[str, Any]] = []
    pattern = os.path.join(directory, "*-result.json")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as exc:
            if on_error == "raise":
                raise
            _warnings.warn(
                f"mockarty: failed to read {path}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        kwargs = allure_result_to_external_payload(
            doc,
            directory=directory,
            plan_id=plan_id,
            framework=framework,
            auto_create=auto_create,
        )
        if namespace:
            kwargs["namespace"] = namespace
        try:
            out.append(api.report(**kwargs))
        except Exception as exc:
            if on_error == "raise":
                raise
            _warnings.warn(
                f"mockarty: upload failed for {path}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
    return out


def allure_result_to_external_payload(
    doc: dict[str, Any],
    *,
    directory: str,
    plan_id: Optional[str],
    framework: str,
    auto_create: bool,
) -> dict[str, Any]:
    """Translate an Allure-2 TestResult dict into kwargs for ``report()``.

    Reads attachment sources off the filesystem (Allure attachments live
    in the same dir under ``<uuid>-attachment.<ext>``). Skips an
    attachment whose source is missing rather than failing the upload.
    """
    name = doc.get("name") or doc.get("fullName") or "unnamed"
    full_name = doc.get("fullName")
    status_raw = (doc.get("status") or "passed").lower()
    if status_raw not in ("passed", "failed", "broken", "skipped"):
        status_raw = "failed"
    # Server enum doesn't know "broken"; map to "failed".
    wire_status = "failed" if status_raw == "broken" else status_raw
    start = doc.get("start")
    stop = doc.get("stop")
    duration_ms = int(stop) - int(start) if (start and stop) else 0
    err = None
    sd = doc.get("statusDetails") or {}
    if sd.get("message"):
        err = sd["message"]
        if sd.get("trace"):
            err = f"{err}\n{sd['trace']}"
    # Labels → flat dict keyed by label name (last wins for duplicates).
    labels = {}
    for lab in doc.get("labels") or []:
        try:
            labels[str(lab["name"])] = str(lab["value"])
        except Exception:
            continue
    # Steps → wire shape (name + status + error).
    steps: list[dict[str, Any]] = []
    for s in doc.get("steps") or []:
        s_status = (s.get("status") or "passed").lower()
        if s_status == "broken":
            s_status = "failed"
        sd_s = s.get("statusDetails") or {}
        steps.append(
            {
                "name": s.get("name", ""),
                "status": s_status
                if s_status in ("passed", "failed", "skipped", "broken")
                else "failed",
                "error": sd_s.get("message"),
            }
        )
    # Attachments → load body bytes from filesystem.
    attachments: list[dict[str, Any]] = []
    for a in doc.get("attachments") or []:
        src = a.get("source")
        if not src:
            continue
        path = os.path.join(directory, src)
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            continue
        attachments.append(
            {
                "name": a.get("name") or src,
                "body": body,
                "contentType": a.get("type") or "application/octet-stream",
            }
        )
    return {
        "status": wire_status,
        "case_id": doc.get("testCaseId"),
        "case_name": name,
        "plan_id": plan_id,
        "auto_create": auto_create if not doc.get("testCaseId") else False,
        "framework": framework,
        "external_id": doc.get("uuid"),
        "test_display_name": name,
        "duration_ms": duration_ms,
        "error": err,
        "labels": labels or None,
        "metadata": {"allureFullName": full_name} if full_name else None,
        "steps": steps or None,
        "attachments": attachments or None,
    }
