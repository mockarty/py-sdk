# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

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
import uuid
from typing import Any, Iterable, Optional
from urllib.parse import quote

from mockarty.ci_job_context import CICallback, CI_CONTEXT_ENVIRONMENT, load_ci_job_context, prepare_ci_report
from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.api._allure_media import collect_media, read_source

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


def _lifecycle_path(namespace: str) -> str:
    """Return the namespace-scoped streaming-lifecycle base path."""
    return _ns_path(namespace) + "/lifecycle"


def _revision_headers(revision: int) -> dict[str, str]:
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ValueError("revision must be a positive integer")
    return {"If-Match": f'"{revision}"'}


def _multipart_attachment(name: str, data: bytes) -> tuple[bytes, str]:
    if not isinstance(name, str) or not name or "\r" in name or "\n" in name:
        raise ValueError("attachment name must be non-empty and single-line")
    if not isinstance(data, bytes):
        raise TypeError("attachment data must be bytes")
    boundary = "mockarty-" + uuid.uuid4().hex
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{escaped}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + data + suffix, f"multipart/form-data; boundary={boundary}"


def _build_attachments(
    attachments: Optional[Iterable[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Normalise attachments into the wire shape (``bodyB64`` + name + content type).

    Accepts inline ``bodyB64`` or ``body`` (bytes/str), or a server-issued
    ``blobUri`` from a prior upload. References are passed to the server for
    namespace validation; the SDK never downloads them.
    """
    if not attachments:
        return []
    out: list[dict[str, Any]] = []
    for a in attachments:
        if not isinstance(a, dict) or not a.get("name"):
            raise ValueError("attachment requires a non-empty name")
        if "blobUri" in a:
            uri = a["blobUri"]
            if not isinstance(uri, str) or not uri.strip():
                raise ValueError("blobUri must be a non-empty server-issued reference")
            if "body" in a or "bodyB64" in a:
                raise ValueError("blobUri and inline attachment bodies are mutually exclusive")
            entry = {
                "name": a["name"],
                "contentType": a.get("contentType", "application/octet-stream"),
                "blobUri": uri,
            }
        elif "bodyB64" in a:
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
    plan_run_id: Optional[str] = None,
    test_case_id: Optional[str] = None,
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
    parameters: Optional[dict[str, str]] = None,
    metadata: Optional[dict[str, Any]],
    steps: Optional[list[dict[str, Any]]],
    attachments: Optional[Iterable[dict[str, Any]]],
    full_name: Optional[str] = None,
    case_description: Optional[str] = None,
    case_expected_result: Optional[str] = None,
    custom_fields: Optional[list[dict[str, Any]]] = None,
    claim_case_ownership: bool = False,
) -> dict[str, Any]:
    if not case_id and not case_name and not os.environ.get(CI_CONTEXT_ENVIRONMENT):
        raise ValueError("one of case_id / case_name is required")
    if auto_create and not case_name and not os.environ.get(CI_CONTEXT_ENVIRONMENT):
        raise ValueError("auto_create requires case_name")
    payload: dict[str, Any] = {
        "schemaVersion": EXTERNAL_RUN_SCHEMA_VERSION,
        "status": status,
        "autoCreate": bool(auto_create),
    }
    if case_id:
        payload["caseId"] = case_id
    if test_case_id:
        # Author-pinned identity (Allure testCaseId / @allure.id). Distinct
        # from caseId (Mockarty's internal UUID): the server tries testCaseId
        # BEFORE fullName/name when resolving the case (migration 402).
        payload["testCaseId"] = test_case_id
    if case_name:
        payload["caseName"] = case_name
    if plan_id:
        payload["planId"] = plan_id
    if plan_run_id:
        payload["planRunId"] = plan_run_id
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
    if parameters:
        payload["parameters"] = dict(parameters)
    if metadata:
        payload["metadata"] = dict(metadata)
    if steps:
        payload["steps"] = list(steps)
    if full_name:
        payload["fullName"] = full_name
    if case_description:
        payload["caseDescription"] = case_description
    if case_expected_result:
        payload["caseExpectedResult"] = case_expected_result
    if custom_fields:
        payload["customFields"] = [dict(f) for f in custom_fields]
    if claim_case_ownership:
        payload["claimCaseOwnership"] = True
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
        test_case_id: Optional[str] = None,
        case_name: Optional[str] = None,
        plan_id: Optional[str] = None,
        plan_run_id: Optional[str] = None,
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
        parameters: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        steps: Optional[list[dict[str, Any]]] = None,
        attachments: Optional[Iterable[dict[str, Any]]] = None,
        namespace: Optional[str] = None,
        full_name: Optional[str] = None,
        case_description: Optional[str] = None,
        case_expected_result: Optional[str] = None,
        custom_fields: Optional[list[dict[str, Any]]] = None,
        claim_case_ownership: bool = False,
        ci_context: CICallback | None = None,
    ) -> dict[str, Any]:
        """Persist a synthetic case run from an external test framework.

        Returns the JSON envelope from the server: ``run_id``, ``case_id``,
        ``case_name``, ``namespace``, ``status``, ``url``, ``resolved``.

        Defaults are tuned for the 80% case: pass ``case_id`` (UUID) or
        ``case_name`` plus ``status`` and the rest is optional.

        Mockarty extension fields (Mockarty extensions beyond the Allure base):

        - ``full_name``           — deterministic test identifier
          ("package.Class::test[param=value]") for duplicate-prevention
          across parallel CI workers. Migration 321 introduced the
          ``test_cases.external_full_name`` column + partial unique
          index that backs this.
        - ``case_description``    — Markdown description stamped on
          case auto-create (or overwrite when ``claim_case_ownership``).
        - ``case_expected_result``— review-workflow's expected-result
          clause (Mockarty's primary differentiator vs Allure).
        - ``custom_fields``       — list of ``{type, name, value}``
          triplets persisted to ``test_cases.custom_fields_json``.
        - ``claim_case_ownership``— when True, the receiver overwrites
          existing Description / ExpectedResult / CustomFields on
          every upload so the code annotation is source-of-truth.
          Default False preserves manual UI edits.
        """
        ns = namespace or self._namespace
        body = _build_payload(
            status=status,
            case_id=case_id,
            test_case_id=test_case_id,
            case_name=case_name,
            plan_id=plan_id,
            plan_run_id=plan_run_id,
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
            parameters=parameters,
            metadata=metadata,
            steps=steps,
            attachments=attachments,
            full_name=full_name,
            case_description=case_description,
            case_expected_result=case_expected_result,
            custom_fields=custom_fields,
            claim_case_ownership=claim_case_ownership,
        )
        body = prepare_ci_report(ns, body, ci_context)
        resp = self._request("POST", _ns_path(ns), json=body)
        return resp.json() if resp.content else {}

    def complete_group(self, callback: CICallback, status: str, *, namespace: str | None = None) -> dict[str, Any]:
        """Finish a selected job after uploads; the receiver checks all missing items."""
        wire = callback.to_wire(completion=True)
        if status not in ("passed", "failed", "cancelled"):
            raise ValueError("invalid selected CI completion status")
        ns = namespace or self._namespace
        path = _ns_path(ns).removesuffix("/external-runs") + f"/ci-launches/{wire['launchId']}/groups/{wire['groupId']}/complete"
        resp = self._request("POST", path, json={"callback": wire, "status": status})
        return resp.json() if resp.content else {}

    def report_batch(
        self,
        runs: list[dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """POST a batch of external-run results in one round-trip.

        Wraps ``POST /api/v1/namespaces/:ns/tcm/external-runs/batch`` —
        the fan-in endpoint for CI scripts that produce many results
        per pipeline. Each item in ``runs`` is a payload dict (same
        shape ``report()`` builds; pass results from ``_build_payload``
        helpers or construct manually).

        The server caps the batch at 100 items per call (see
        ``MaxBatchExternalRuns`` in
        ``internal/webui/tcm_external_run_batch_handler.go``); larger
        sets must be chunked by the caller. Even when N items fail
        the server returns 200 with per-row errors — the caller
        inspects ``response["results"][i]`` to correlate.

        Returns the raw server envelope:
        ``{"results": [{"index": N, "result": {...}} | {"error": "..."}],
        "counts": {"total": int, "passed": int, "failed": int}}``.
        """
        if not runs:
            raise ValueError("runs must be a non-empty list")
        ns = namespace or self._namespace
        body = {"runs": [prepare_ci_report(ns, run) for run in runs]}
        path = _ns_path(ns) + "/batch"
        resp = self._request("POST", path, json=body)
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
        Returns the list of server responses (one per result). Nested step
        media is included; container fixtures are not imported. Media is
        validated before any POST: 256 KiB/file, 1 MiB and 32 sources/result,
        32 MiB/batch, 64 levels and 5000 steps/result. Missing/unsafe media
        always raises, including when ``on_error="warn"``.

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

    # -- streaming lifecycle -------------------------------------------------

    def start_run(
        self, run: dict[str, Any], *, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Open a streaming external run and return its server view (with the
        run ``id`` to feed :meth:`append_steps` / :meth:`finish_run`).

        Unlike :meth:`report` (one-shot upload of a finished run), the lifecycle
        API reports incrementally: ``start_run`` → ``append_steps`` (repeatedly)
        → ``finish_run``. ``run`` accepts ``name``, ``full_name``, ``framework``,
        ``suite_id``, ``external_id``, ``test_case_id``, ``tags``, ``environment``.
        """
        ns = namespace or self._namespace
        resp = self._request("POST", _lifecycle_path(ns), json=run)
        return resp.json()

    def append_steps(
        self,
        run_id: str,
        steps: list[dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Stream one or more steps into an open run. Each step accepts
        ``step_key``, ``name``, ``status``, ``message``, ``stack_trace``,
        ``parent_key``, ``duration_ms``, ``parameters``."""
        ns = namespace or self._namespace
        resp = self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/steps",
            json={"steps": steps},
        )
        return resp.json()

    def append_steps_at_revision(
        self,
        run_id: str,
        revision: int,
        steps: list[dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Stream steps only while ``revision`` remains current."""
        ns = namespace or self._namespace
        resp = self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/steps",
            json={"steps": steps},
            headers=_revision_headers(revision),
        )
        return resp.json()

    def upload_attachment(
        self, run_id: str, name: str, data: bytes, *, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Upload one attachment through the legacy unfenced lane."""
        return self._upload_attachment(run_id, 0, name, data, namespace=namespace)

    def upload_attachment_at_revision(
        self,
        run_id: str,
        revision: int,
        name: str,
        data: bytes,
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Upload one attachment only while ``revision`` remains current."""
        _revision_headers(revision)
        return self._upload_attachment(
            run_id, revision, name, data, namespace=namespace
        )

    def _upload_attachment(
        self,
        run_id: str,
        revision: int,
        name: str,
        data: bytes,
        *,
        namespace: Optional[str],
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        content, content_type = _multipart_attachment(name, data)
        headers = {"Content-Type": content_type}
        if revision > 0:
            headers.update(_revision_headers(revision))
        resp = self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/attachments",
            content=content,
            headers=headers,
        )
        return resp.json()

    def finish_run(
        self,
        run_id: str,
        status: str,
        *,
        summary: str = "",
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Close an open run; the returned view carries the resolved TCM
        case/run ids the ingest matched or created."""
        ns = namespace or self._namespace
        body: dict[str, Any] = {"status": status}
        if summary:
            body["summary"] = summary
        resp = self._request(
            "POST", f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/finish", json=body
        )
        return resp.json()

    def finish_run_at_revision(
        self,
        run_id: str,
        revision: int,
        status: str,
        *,
        summary: str = "",
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Finish only the accumulated projection identified by ``revision``."""
        ns = namespace or self._namespace
        body: dict[str, Any] = {"status": status}
        if summary:
            body["summary"] = summary
        resp = self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/finish",
            json=body,
            headers=_revision_headers(revision),
        )
        return resp.json()

    def get_run(
        self, run_id: str, *, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Fetch the current view of a streaming run."""
        ns = namespace or self._namespace
        resp = self._request("GET", f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}")
        return resp.json()

    def list_runs(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        """List streaming runs in the namespace."""
        ns = namespace or self._namespace
        resp = self._request("GET", _lifecycle_path(ns))
        data = resp.json()
        return data.get("runs", []) if isinstance(data, dict) else []


class AsyncExternalRunsAPI(AsyncAPIBase):
    """Async counterpart of :class:`ExternalRunsAPI`."""

    async def report(
        self,
        *,
        status: str,
        case_id: Optional[str] = None,
        test_case_id: Optional[str] = None,
        case_name: Optional[str] = None,
        plan_id: Optional[str] = None,
        plan_run_id: Optional[str] = None,
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
        parameters: Optional[dict[str, str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        steps: Optional[list[dict[str, Any]]] = None,
        attachments: Optional[Iterable[dict[str, Any]]] = None,
        namespace: Optional[str] = None,
        full_name: Optional[str] = None,
        case_description: Optional[str] = None,
        case_expected_result: Optional[str] = None,
        custom_fields: Optional[list[dict[str, Any]]] = None,
        claim_case_ownership: bool = False,
        ci_context: CICallback | None = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body = _build_payload(
            status=status,
            case_id=case_id,
            test_case_id=test_case_id,
            case_name=case_name,
            plan_id=plan_id,
            plan_run_id=plan_run_id,
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
            parameters=parameters,
            metadata=metadata,
            steps=steps,
            attachments=attachments,
            full_name=full_name,
            case_description=case_description,
            case_expected_result=case_expected_result,
            custom_fields=custom_fields,
            claim_case_ownership=claim_case_ownership,
        )
        body = prepare_ci_report(ns, body, ci_context)
        resp = await self._request("POST", _ns_path(ns), json=body)
        return resp.json() if resp.content else {}

    async def complete_group(self, callback: CICallback, status: str, *, namespace: str | None = None) -> dict[str, Any]:
        """Finish a selected job after uploads; the receiver checks all missing items."""
        wire = callback.to_wire(completion=True)
        if status not in ("passed", "failed", "cancelled"):
            raise ValueError("invalid selected CI completion status")
        ns = namespace or self._namespace
        path = _ns_path(ns).removesuffix("/external-runs") + f"/ci-launches/{wire['launchId']}/groups/{wire['groupId']}/complete"
        resp = await self._request("POST", path, json={"callback": wire, "status": status})
        return resp.json() if resp.content else {}

    async def report_batch(
        self,
        runs: list[dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Async counterpart of :meth:`ExternalRunsAPI.report_batch`."""
        if not runs:
            raise ValueError("runs must be a non-empty list")
        ns = namespace or self._namespace
        body = {"runs": [prepare_ci_report(ns, run) for run in runs]}
        path = _ns_path(ns) + "/batch"
        resp = await self._request("POST", path, json=body)
        return resp.json() if resp.content else {}

    # -- streaming lifecycle -------------------------------------------------

    async def start_run(
        self, run: dict[str, Any], *, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Async counterpart of :meth:`ExternalRunsAPI.start_run`."""
        ns = namespace or self._namespace
        resp = await self._request("POST", _lifecycle_path(ns), json=run)
        return resp.json()

    async def append_steps(
        self,
        run_id: str,
        steps: list[dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Async counterpart of :meth:`ExternalRunsAPI.append_steps`."""
        ns = namespace or self._namespace
        resp = await self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/steps",
            json={"steps": steps},
        )
        return resp.json()

    async def append_steps_at_revision(
        self,
        run_id: str,
        revision: int,
        steps: list[dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fenced async counterpart of
        :meth:`ExternalRunsAPI.append_steps_at_revision`."""
        ns = namespace or self._namespace
        resp = await self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/steps",
            json={"steps": steps},
            headers=_revision_headers(revision),
        )
        return resp.json()

    async def upload_attachment(
        self, run_id: str, name: str, data: bytes, *, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Async upload through the legacy unfenced lane."""
        return await self._upload_attachment(run_id, 0, name, data, namespace=namespace)

    async def upload_attachment_at_revision(
        self,
        run_id: str,
        revision: int,
        name: str,
        data: bytes,
        *,
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Async fenced attachment upload."""
        _revision_headers(revision)
        return await self._upload_attachment(
            run_id, revision, name, data, namespace=namespace
        )

    async def _upload_attachment(
        self,
        run_id: str,
        revision: int,
        name: str,
        data: bytes,
        *,
        namespace: Optional[str],
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        content, content_type = _multipart_attachment(name, data)
        headers = {"Content-Type": content_type}
        if revision > 0:
            headers.update(_revision_headers(revision))
        resp = await self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/attachments",
            content=content,
            headers=headers,
        )
        return resp.json()

    async def finish_run(
        self,
        run_id: str,
        status: str,
        *,
        summary: str = "",
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Async counterpart of :meth:`ExternalRunsAPI.finish_run`."""
        ns = namespace or self._namespace
        body: dict[str, Any] = {"status": status}
        if summary:
            body["summary"] = summary
        resp = await self._request(
            "POST", f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/finish", json=body
        )
        return resp.json()

    async def finish_run_at_revision(
        self,
        run_id: str,
        revision: int,
        status: str,
        *,
        summary: str = "",
        namespace: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fenced async counterpart of
        :meth:`ExternalRunsAPI.finish_run_at_revision`."""
        ns = namespace or self._namespace
        body: dict[str, Any] = {"status": status}
        if summary:
            body["summary"] = summary
        resp = await self._request(
            "POST",
            f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}/finish",
            json=body,
            headers=_revision_headers(revision),
        )
        return resp.json()

    async def get_run(
        self, run_id: str, *, namespace: Optional[str] = None
    ) -> dict[str, Any]:
        """Async counterpart of :meth:`ExternalRunsAPI.get_run`."""
        ns = namespace or self._namespace
        resp = await self._request(
            "GET", f"{_lifecycle_path(ns)}/{quote(run_id, safe='')}"
        )
        return resp.json()

    async def list_runs(
        self, *, namespace: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Async counterpart of :meth:`ExternalRunsAPI.list_runs`."""
        ns = namespace or self._namespace
        resp = await self._request("GET", _lifecycle_path(ns))
        data = resp.json()
        return data.get("runs", []) if isinstance(data, dict) else []


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

    job=load_ci_job_context(os.environ[CI_CONTEXT_ENVIRONMENT]) if os.environ.get(CI_CONTEXT_ENVIRONMENT) else None
    ns=namespace or api._namespace
    if job is not None and job.namespace!=ns:
        raise ValueError("invalid or unmatched selected CI context")
    if not os.path.isdir(directory):
        raise FileNotFoundError(f"allure-results directory not found: {directory}")
    out: list[dict[str, Any]] = []
    skipped: list[str] = []
    pattern = os.path.join(directory, "*-result.json")
    paths = sorted(glob.glob(pattern))
    prepared = []
    media_bytes = 0
    selected_items=set()
    for path in paths:
        try:
            doc = json.loads(read_source(directory, os.path.basename(path), 10 << 20))
        except Exception as exc:
            if on_error == "raise":
                raise
            skipped.append(f"{os.path.basename(path)}: {exc}")
            _warnings.warn(
                f"mockarty: failed to read {path}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
        if job is not None:
            labels={}
            for label in doc.get("labels") or []:
                if isinstance(label,dict) and "name" in label and "value" in label:
                    labels[str(label["name"])]=str(label["value"])
            if not job._matches_report({"externalId":doc.get("uuid"),"testCaseId":_resolve_test_case_id(doc,labels),"fullName":doc.get("fullName")}):
                continue
        kwargs = allure_result_to_external_payload(
            doc,
            directory=directory,
            plan_id=plan_id,
            framework=framework,
            auto_create=auto_create,
        )
        media_bytes += sum(len(a["body"]) for a in kwargs.get("attachments") or [])
        if media_bytes > 32 << 20:
            raise ValueError("allure: batch attachments exceed 32 MiB")
        if namespace:
            kwargs["namespace"] = namespace
        if job is not None:
            wire=_build_payload(case_id=None,framework_version=None,stdout=None,stderr=None,started_at=None,finished_at=None,**{k:v for k,v in kwargs.items() if k!="namespace"})
            pinned=prepare_ci_report(ns,wire)
            uid=pinned["ciContext"]["itemUid"]
            if uid in selected_items:
                raise ValueError("invalid or unmatched selected CI context")
            selected_items.add(uid)
        prepared.append((path, kwargs))
    if job is not None and (not prepared or skipped):
        raise ValueError("selected Allure preflight did not produce a complete result set")
    for path, kwargs in prepared:
        try:
            out.append(api.report(**kwargs))
        except Exception as exc:
            if on_error == "raise":
                raise
            skipped.append(f"{os.path.basename(path)}: {exc}")
            _warnings.warn(
                f"mockarty: upload failed for {path}: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
    if skipped:
        # "warn" keeps going past a bad file, but the caller must still learn
        # that N results never reached Mockarty — returning only the successes
        # made a half-lost upload indistinguishable from a clean one.
        raise AllureUploadPartialError(uploaded=len(out), skipped=skipped, results=out)
    if not paths:
        raise AllureUploadEmptyError(
            f"no *-result.json in {directory} — nothing was reported to Mockarty"
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
    in the same dir under ``<uuid>-attachment.<ext>``). Recursive step media
    is retained with source paths. Missing or unsafe media fails preflight.
    """
    name = doc.get("name") or doc.get("fullName") or "unnamed"
    full_name = doc.get("fullName")
    # An absent status means we never observed an outcome — it is NOT a pass.
    # The server's status vocabulary includes "broken" (an assertion failure and
    # a test that blew up are different findings, and both Allure TestOps and
    # Test IT report them separately), so it is carried through rather than
    # flattened onto "failed".
    status_raw = (doc.get("status") or "").strip().lower()
    if status_raw == "error":
        status_raw = "broken"
    if status_raw not in ("passed", "failed", "broken", "skipped", "cancelled"):
        status_raw = "broken"
    wire_status = status_raw
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
    steps, attachments, paths, _ = collect_media(doc, directory)
    metadata = {"allureFullName": full_name} if full_name else {}
    if paths:
        metadata["allureAttachmentPaths"] = paths
    return {
        "status": wire_status,
        # Allure's testCaseId (@allure.id) is the author-pinned identity, NOT
        # Mockarty's internal case UUID — map it to test_case_id so the server
        # resolves by it (tried before fullName/name). Mapping it to case_id
        # made every upload look up a non-existent UUID.
        "test_case_id": _resolve_test_case_id(doc, labels),
        "case_name": name,
        "plan_id": plan_id,
        # Honour the caller's auto_create regardless of testCaseId: the server
        # only creates when resolution (testCaseId → fullName → name) misses,
        # so this never produces duplicates.
        "auto_create": auto_create,
        "framework": framework,
        "external_id": doc.get("uuid"),
        "test_display_name": name,
        "duration_ms": duration_ms,
        "error": err,
        "labels": labels or None,
        # fullName is a first-class resolution key (migration 321), not just
        # display metadata — send it as full_name AND keep the metadata mirror.
        "full_name": full_name,
        "metadata": metadata or None,
        "steps": steps or None,
        "attachments": attachments or None,
    }


def _resolve_test_case_id(doc: dict[str, Any], labels: dict[str, str]) -> Optional[str]:
    """Resolve the author-pinned identity of an Allure result.

    Allure's own field is ``testCaseId``. Allure TestOps adapters express
    ``@AllureId(123)`` as the ``AS_ID`` label instead, so a suite migrated from
    TestOps carried its identity somewhere this translator never looked — every
    upload looked new and the autotest-to-case link was lost. Mirrors the
    server-side ``allure.ResolveTestCaseID`` and the CLI, which must stay in
    lockstep with this function.
    """
    pinned = (doc.get("testCaseId") or "").strip()
    if pinned:
        return pinned
    for name, value in (labels or {}).items():
        if str(name).strip().lower() in ("as_id", "allure_id", "allureid"):
            value = (value or "").strip()
            if value:
                return value
    return None


class AllureUploadEmptyError(RuntimeError):
    """Raised when an allure-results directory contains no results at all.

    A CI step that finds nothing to upload means the test run produced nothing;
    returning an empty list turned that into a silently green pipeline.
    """


class AllureUploadPartialError(RuntimeError):
    """Raised when some results of a directory upload never reached Mockarty.

    ``results`` carries the responses that DID land, so a caller that wants
    best-effort semantics can still use them after catching this.
    """

    def __init__(
        self,
        uploaded: int,
        skipped: list[str],
        results: list[dict[str, Any]],
    ) -> None:
        super().__init__(
            f"mockarty: {uploaded} result(s) uploaded, "
            f"{len(skipped)} not reported: {'; '.join(skipped)}"
        )
        self.uploaded = uploaded
        self.skipped = skipped
        self.results = results
