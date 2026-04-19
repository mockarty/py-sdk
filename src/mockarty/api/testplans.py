# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test Plans API — master orchestrator for functional / fuzz / chaos / load
/ contract runs.

See docs/research/TEST_PLANS_ARCHITECTURE_2026-04-19.md for the full spec.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, BinaryIO, Iterator, Optional
from urllib.parse import quote

import httpx

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.errors import MockartyAPIError, MockartyError
from mockarty.models.testplan import (
    AdHocRunResponse,
    AllureReport,
    CreateAdHocRunRequest,
    PatchPlanRequest,
    PlanRunStatus,
    RunEvent,
    Schedule,
    TestPlan,
    TestPlanRun,
    Webhook,
)


_BASE = "/api/v1/test-plans"


def _ns_base(namespace: str) -> str:
    """Build the namespace-scoped API prefix used by the TP-6b endpoints."""
    return f"/api/v1/namespaces/{quote(namespace, safe='')}"


def _plan_ref(plan_ref: str) -> str:
    """Normalize and URL-escape a plan UUID / numeric-id for path insertion."""
    key = _normalize_id(plan_ref)
    return quote(key, safe="")


def _etag_from_plan(plan: TestPlan) -> str:
    """Derive the RFC 7232 strong validator the server expects.

    The server emits ``"<updatedAt unix-ms>"`` (with literal quotes). The
    plan model carries ``updated_at`` as an ISO-8601 string; convert it to
    unix milliseconds. Returns an empty string when ``updated_at`` is
    absent — callers must handle the fallback (e.g. pass an explicit
    ``if_match`` or re-fetch).
    """
    if not plan.updated_at:
        return ""
    # Parse ISO-8601 (accepts both ``Z`` suffix and ``+00:00`` offsets).
    try:
        from datetime import datetime

        raw = plan.updated_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        millis = int(dt.timestamp() * 1000)
        return f'"{millis}"'
    except (ValueError, TypeError):
        return ""


class TestPlanError(MockartyError):
    """Base exception for Test Plan operations."""


class PlanNotFoundError(TestPlanError):
    """Raised when a plan lookup 404s."""


class RunFailedError(TestPlanError):
    """Raised by wait_for_run when the run finishes failed."""


class RunCancelledError(TestPlanError):
    """Raised by wait_for_run when the run was cancelled."""


class WebhookDeliveryError(TestPlanError):
    """Raised by test_webhook when the server reports a failed ping."""


class PreconditionFailedError(TestPlanError):
    """Raised by :meth:`TestPlansAPI.patch` on HTTP 412 (If-Match mismatch).

    Callers should re-fetch the plan, reconcile their local state with
    the server's updated_at, and retry the patch with the fresh etag.

    Attributes:
        message: Server-supplied human-readable reason.
        request_id: Correlation ID from the ``X-Request-Id`` header.
    """

    def __init__(self, message: str, request_id: Optional[str] = None) -> None:
        self.message = message
        self.request_id = request_id
        super().__init__(message)


def _normalize_id(id_or_numeric: str) -> str:
    """Strip the ``#`` prefix used in UI copy-to-clipboard strings."""
    s = (id_or_numeric or "").strip()
    if s.startswith("#"):
        s = s[1:]
    if not s:
        raise ValueError("plan id must not be empty")
    return s


def _parse_sse_stream(
    response: httpx.Response,
) -> Iterator[RunEvent]:
    """Sync generator that yields RunEvents from a text/event-stream body."""
    event: str = ""
    data_lines: list[str] = []
    for raw in response.iter_lines():
        if raw == "":
            if event or data_lines:
                payload = "\n".join(data_lines)
                parsed: Optional[dict[str, Any]] = None
                if payload:
                    try:
                        parsed = json.loads(payload)
                    except json.JSONDecodeError:
                        parsed = {"_raw": payload}
                yield RunEvent(kind=event, data=parsed)
            event = ""
            data_lines = []
            continue
        if raw.startswith(":"):
            continue
        if raw.startswith("event:"):
            event = raw[len("event:") :].strip()
        elif raw.startswith("data:"):
            data_lines.append(raw[len("data:") :].strip())


async def _parse_sse_stream_async(
    response: httpx.Response,
) -> AsyncIterator[RunEvent]:
    """Async generator yielding RunEvents from an async HTTP response."""
    event: str = ""
    data_lines: list[str] = []
    async for raw in response.aiter_lines():
        if raw == "":
            if event or data_lines:
                payload = "\n".join(data_lines)
                parsed: Optional[dict[str, Any]] = None
                if payload:
                    try:
                        parsed = json.loads(payload)
                    except json.JSONDecodeError:
                        parsed = {"_raw": payload}
                yield RunEvent(kind=event, data=parsed)
            event = ""
            data_lines = []
            continue
        if raw.startswith(":"):
            continue
        if raw.startswith("event:"):
            event = raw[len("event:") :].strip()
        elif raw.startswith("data:"):
            data_lines.append(raw[len("data:") :].strip())


# ---------------------------------------------------------------------------
# Sync API
# ---------------------------------------------------------------------------


class TestPlansAPI(SyncAPIBase):
    """Synchronous Test Plans API."""

    # ── CRUD ──────────────────────────────────────────────────────────

    def create(self, plan: TestPlan) -> TestPlan:
        """Create a new Test Plan."""
        if not plan.namespace:
            plan.namespace = self._namespace
        resp = self._request(
            "POST", _BASE, json=plan.model_dump(by_alias=True, exclude_none=True)
        )
        return TestPlan.model_validate(resp.json())

    def get(self, id_or_numeric: str) -> TestPlan:
        """Fetch a plan by UUID or numeric_id (``#1042`` / ``1042``)."""
        key = _normalize_id(id_or_numeric)
        try:
            resp = self._request("GET", f"{_BASE}/{key}")
        except MockartyAPIError as err:
            if err.status_code == 404:
                raise PlanNotFoundError(f"test plan {key!r} not found") from err
            raise
        return TestPlan.model_validate(resp.json())

    def update(self, plan_id: str, plan: TestPlan) -> TestPlan:
        """Full-replace update (PUT)."""
        if not plan.namespace:
            plan.namespace = self._namespace
        plan.id = plan_id
        resp = self._request(
            "PUT",
            f"{_BASE}/{plan_id}",
            json=plan.model_dump(by_alias=True, exclude_none=True),
        )
        return TestPlan.model_validate(resp.json())

    def delete(self, plan_id: str) -> None:
        """Soft-delete a plan."""
        self._request("DELETE", f"{_BASE}/{plan_id}")

    def list(
        self,
        namespace: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestPlan]:
        """List plans matching the filters."""
        params: dict[str, str] = {}
        ns = namespace or self._namespace
        if ns:
            params["namespace"] = ns
        if status:
            params["status"] = status
        if limit and limit > 0:
            params["limit"] = str(limit)
        if offset and offset > 0:
            params["offset"] = str(offset)
        resp = self._request("GET", _BASE, params=params or None)
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [TestPlan.model_validate(p) for p in items]

    # ── Runs ──────────────────────────────────────────────────────────

    def run(
        self,
        id_or_numeric: str,
        items: Optional[list[int]] = None,
        mode: Optional[str] = None,
    ) -> TestPlanRun:
        """Trigger a Plan run."""
        key = _normalize_id(id_or_numeric)
        body: dict[str, Any] = {}
        if items:
            body["items"] = items
        if mode:
            body["mode"] = mode
        resp = self._request("POST", f"{_BASE}/{key}/run", json=body or None)
        payload = resp.json()
        return TestPlanRun(
            id=payload.get("runId"),
            plan_id=payload.get("planId"),
            status=payload.get("status"),
        )

    def get_run(self, run_id: str) -> TestPlanRun:
        resp = self._request("GET", f"{_BASE}/runs/{run_id}")
        return TestPlanRun.model_validate(resp.json())

    def get_run_status(self, run_id: str) -> PlanRunStatus:
        resp = self._request("GET", f"{_BASE}/runs/{run_id}/status")
        return PlanRunStatus.model_validate(resp.json())

    def cancel_run(self, run_id: str) -> None:
        self._request("POST", f"{_BASE}/runs/{run_id}/cancel")

    def list_runs(
        self, plan_id: str, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> list[TestPlanRun]:
        params: dict[str, str] = {}
        if limit and limit > 0:
            params["limit"] = str(limit)
        if offset and offset > 0:
            params["offset"] = str(offset)
        resp = self._request("GET", f"{_BASE}/{plan_id}/runs", params=params or None)
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [TestPlanRun.model_validate(r) for r in items]

    def wait_for_run(
        self,
        run_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None,
    ) -> TestPlanRun:
        """Poll until the run reaches a terminal state.

        Raises ``RunFailedError`` / ``RunCancelledError`` on non-pass terminal
        status so CI jobs can ``except`` and exit non-zero.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            run = self.get_run(run_id)
            if run.status == "completed":
                return run
            if run.status == "failed":
                raise RunFailedError(f"run {run_id} failed")
            if run.status == "cancelled":
                raise RunCancelledError(f"run {run_id} cancelled")
            if deadline is not None and time.monotonic() >= deadline:
                return run
            time.sleep(poll_interval)

    def stream_run(self, run_id: str) -> Iterator[RunEvent]:
        """Subscribe to the SSE stream of a run. Yields RunEvent until EOF."""
        with self._client.stream(
            "GET", f"{_BASE}/runs/{run_id}/stream", headers={"Accept": "text/event-stream"}
        ) as response:
            response.raise_for_status()
            yield from _parse_sse_stream(response)

    def get_report(self, run_id: str, format: str = "allure") -> bytes:
        resp = self._request(
            "GET", f"{_BASE}/runs/{run_id}/report", params={"format": format}
        )
        return resp.content

    def download_report_zip(self, run_id: str, dest: BinaryIO) -> None:
        with self._client.stream(
            "GET", f"{_BASE}/runs/{run_id}/report.zip", headers={"Accept": "application/zip"}
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                dest.write(chunk)

    # ── Schedules ─────────────────────────────────────────────────────

    def add_schedule(self, plan_id: str, schedule: Schedule) -> Schedule:
        resp = self._request(
            "POST",
            f"{_BASE}/{plan_id}/schedules",
            json=schedule.model_dump(by_alias=True, exclude_none=True),
        )
        return Schedule.model_validate(resp.json())

    def list_schedules(self, plan_id: str) -> list[Schedule]:
        resp = self._request("GET", f"{_BASE}/{plan_id}/schedules")
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [Schedule.model_validate(s) for s in items]

    def update_schedule(
        self, plan_id: str, schedule_id: str, schedule: Schedule
    ) -> Schedule:
        resp = self._request(
            "PATCH",
            f"{_BASE}/{plan_id}/schedules/{schedule_id}",
            json=schedule.model_dump(by_alias=True, exclude_none=True),
        )
        return Schedule.model_validate(resp.json())

    def delete_schedule(self, plan_id: str, schedule_id: str) -> None:
        self._request("DELETE", f"{_BASE}/{plan_id}/schedules/{schedule_id}")

    # ── Webhooks ──────────────────────────────────────────────────────

    def add_webhook(self, plan_id: str, webhook: Webhook) -> Webhook:
        resp = self._request(
            "POST",
            f"{_BASE}/{plan_id}/webhooks",
            json=webhook.model_dump(by_alias=True, exclude_none=True),
        )
        return Webhook.model_validate(resp.json())

    def list_webhooks(self, plan_id: str) -> list[Webhook]:
        resp = self._request("GET", f"{_BASE}/{plan_id}/webhooks")
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [Webhook.model_validate(w) for w in items]

    def update_webhook(
        self, plan_id: str, webhook_id: str, webhook: Webhook
    ) -> Webhook:
        resp = self._request(
            "PATCH",
            f"{_BASE}/{plan_id}/webhooks/{webhook_id}",
            json=webhook.model_dump(by_alias=True, exclude_none=True),
        )
        return Webhook.model_validate(resp.json())

    def delete_webhook(self, plan_id: str, webhook_id: str) -> None:
        self._request("DELETE", f"{_BASE}/{plan_id}/webhooks/{webhook_id}")

    def test_webhook(self, plan_id: str, webhook_id: str) -> None:
        """Ping a webhook server-side. Raises WebhookDeliveryError on failure."""
        resp = self._request(
            "POST", f"{_BASE}/{plan_id}/webhooks/{webhook_id}/test"
        )
        body = resp.json() if resp.content else {}
        if not body.get("success", False):
            msg = body.get("error") or f"status={body.get('status')}"
            raise WebhookDeliveryError(f"webhook {webhook_id!r}: {msg}")

    # ── TP-6b: namespace-scoped endpoints ─────────────────────────────

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Pick an explicit namespace or fall back to the client default."""
        ns = (namespace or self._namespace or "").strip()
        if not ns:
            raise ValueError("namespace is required for this endpoint")
        return ns

    def patch(
        self,
        plan_ref: str,
        request: PatchPlanRequest,
        *,
        if_match: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> TestPlan:
        """Partially update a plan via the namespace-scoped PATCH endpoint.

        Uses ``PATCH /api/v1/namespaces/:namespace/test-plans/:idOrNumericID``
        and requires an RFC 7232 strong validator in the ``If-Match`` header.

        Behaviour:
          - ``if_match`` is the ``ETag`` value from a prior Get / Create /
            Patch. When omitted the SDK performs a pre-fetch to obtain the
            current ``updated_at`` and formats a fresh etag — safe for
            one-shot CLI tooling, vulnerable to lost updates under
            concurrency. Always pass an explicit ``if_match`` from a known
            snapshot in multi-writer scenarios.
          - On HTTP 412 raises :class:`PreconditionFailedError` so CI / tools
            can catch it, re-fetch, and retry with the new etag.

        Args:
            plan_ref: Plan UUID or numeric id (``#42`` / ``42`` both work).
            request: Partial update payload. Must set at least one field.
            if_match: Strong-validator etag. Auto-fetched when omitted.
            namespace: Target namespace. Falls back to the client default.

        Returns:
            The updated :class:`TestPlan` as returned by the server.

        Raises:
            ValueError: When ``plan_ref`` is empty or no field is set.
            PreconditionFailedError: On HTTP 412 etag mismatch.
            MockartyAPIError: For any other non-2xx response.
        """
        key = _plan_ref(plan_ref)
        ns = self._resolve_namespace(namespace)

        body = request.model_dump(by_alias=True, exclude_none=True)
        if not body:
            raise ValueError("patch requires at least one field")

        etag = (if_match or "").strip()
        if not etag:
            current = self.get(plan_ref)
            etag = _etag_from_plan(current)

        path = f"{_ns_base(ns)}/test-plans/{key}"
        try:
            resp = self._request(
                "PATCH", path, json=body, headers={"If-Match": etag}
            )
        except MockartyAPIError as err:
            if err.status_code == 412:
                raise PreconditionFailedError(
                    err.message or "If-Match does not match current plan version",
                    request_id=err.request_id,
                ) from err
            raise
        return TestPlan.model_validate(resp.json())

    def create_ad_hoc_run(
        self,
        request: CreateAdHocRunRequest,
        *,
        namespace: Optional[str] = None,
    ) -> AdHocRunResponse:
        """Dispatch an ad-hoc master run (hidden plan + run in one call).

        Uses ``POST /api/v1/namespaces/:namespace/test-runs/ad-hoc``. The
        server provisions a ``adhoc=true`` plan row, seeds per-item pending
        state, and dispatches the orchestrator in a detached goroutine —
        returning 202 with ``{run_id, plan_id, status, _links}``.

        Polling: use :meth:`get_run`, :meth:`wait_for_run`, or
        :meth:`stream_run` against the returned ``run_id``.

        Orchestrator availability: single-binary / SQLite deployments
        without the orchestrator wired reject with 503 — see the
        ``Admin Panel → Orchestrator`` status.

        Args:
            request: Ad-hoc run specification (items + optional name /
                description / schedule).
            namespace: Target namespace. Falls back to the client default.

        Returns:
            :class:`AdHocRunResponse` with ``run_id``, ``plan_id`` and
            optional ``_links``.
        """
        if not request.items:
            raise ValueError("CreateAdHocRunRequest requires at least one item")
        ns = self._resolve_namespace(namespace)
        path = f"{_ns_base(ns)}/test-runs/ad-hoc"
        resp = self._request(
            "POST",
            path,
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return AdHocRunResponse.model_validate(resp.json())

    def get_run_report(
        self,
        plan_ref: str,
        run_id: str,
        *,
        namespace: Optional[str] = None,
    ) -> AllureReport:
        """Fetch the merged Allure JSON report for a namespace-scoped run.

        Uses ``GET /api/v1/namespaces/:namespace/test-plans/:planRef/runs/:runId/report``.

        The raw JSON body is preserved in :attr:`AllureReport.raw` so
        callers can run a second decode pass with domain-specific types —
        the server's schema is loosely typed on purpose so new Allure
        fields roll out without SDK bumps.

        Args:
            plan_ref: Plan UUID or numeric id.
            run_id: Run UUID.
            namespace: Target namespace. Falls back to the client default.

        Returns:
            :class:`AllureReport` with best-effort decoded fields + raw bytes.
        """
        key = _plan_ref(plan_ref)
        if not (run_id or "").strip():
            raise ValueError("run_id must not be empty")
        ns = self._resolve_namespace(namespace)
        path = (
            f"{_ns_base(ns)}/test-plans/{key}/runs/{quote(run_id, safe='')}/report"
        )
        resp = self._request("GET", path)
        body = resp.json() if resp.content else {}
        report = AllureReport.model_validate(body) if body else AllureReport()
        report.raw = resp.content
        return report

    def get_run_report_zip(
        self,
        plan_ref: str,
        run_id: str,
        dest: BinaryIO,
        *,
        namespace: Optional[str] = None,
    ) -> None:
        """Stream the Allure ZIP archive for a namespace-scoped run into ``dest``.

        Uses ``GET /api/v1/namespaces/:namespace/test-plans/:planRef/runs/:runId/report.zip``.

        The caller owns ``dest`` (any binary file-like object). The SDK
        streams chunks directly so the archive never lands fully in
        memory — suitable for multi-MB Allure reports.

        Args:
            plan_ref: Plan UUID or numeric id.
            run_id: Run UUID.
            dest: Open binary writer; the archive is streamed chunk-by-chunk.
            namespace: Target namespace. Falls back to the client default.
        """
        key = _plan_ref(plan_ref)
        if not (run_id or "").strip():
            raise ValueError("run_id must not be empty")
        ns = self._resolve_namespace(namespace)
        path = (
            f"{_ns_base(ns)}/test-plans/{key}"
            f"/runs/{quote(run_id, safe='')}/report.zip"
        )
        with self._client.stream(
            "GET", path, headers={"Accept": "application/zip"}
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                dest.write(chunk)


# ---------------------------------------------------------------------------
# Async API
# ---------------------------------------------------------------------------


class AsyncTestPlansAPI(AsyncAPIBase):
    """Asynchronous Test Plans API."""

    async def create(self, plan: TestPlan) -> TestPlan:
        if not plan.namespace:
            plan.namespace = self._namespace
        resp = await self._request(
            "POST", _BASE, json=plan.model_dump(by_alias=True, exclude_none=True)
        )
        return TestPlan.model_validate(resp.json())

    async def get(self, id_or_numeric: str) -> TestPlan:
        key = _normalize_id(id_or_numeric)
        try:
            resp = await self._request("GET", f"{_BASE}/{key}")
        except MockartyAPIError as err:
            if err.status_code == 404:
                raise PlanNotFoundError(f"test plan {key!r} not found") from err
            raise
        return TestPlan.model_validate(resp.json())

    async def update(self, plan_id: str, plan: TestPlan) -> TestPlan:
        if not plan.namespace:
            plan.namespace = self._namespace
        plan.id = plan_id
        resp = await self._request(
            "PUT",
            f"{_BASE}/{plan_id}",
            json=plan.model_dump(by_alias=True, exclude_none=True),
        )
        return TestPlan.model_validate(resp.json())

    async def delete(self, plan_id: str) -> None:
        await self._request("DELETE", f"{_BASE}/{plan_id}")

    async def list(
        self,
        namespace: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestPlan]:
        params: dict[str, str] = {}
        ns = namespace or self._namespace
        if ns:
            params["namespace"] = ns
        if status:
            params["status"] = status
        if limit and limit > 0:
            params["limit"] = str(limit)
        if offset and offset > 0:
            params["offset"] = str(offset)
        resp = await self._request("GET", _BASE, params=params or None)
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [TestPlan.model_validate(p) for p in items]

    async def run(
        self,
        id_or_numeric: str,
        items: Optional[list[int]] = None,
        mode: Optional[str] = None,
    ) -> TestPlanRun:
        key = _normalize_id(id_or_numeric)
        body: dict[str, Any] = {}
        if items:
            body["items"] = items
        if mode:
            body["mode"] = mode
        resp = await self._request("POST", f"{_BASE}/{key}/run", json=body or None)
        payload = resp.json()
        return TestPlanRun(
            id=payload.get("runId"),
            plan_id=payload.get("planId"),
            status=payload.get("status"),
        )

    async def get_run(self, run_id: str) -> TestPlanRun:
        resp = await self._request("GET", f"{_BASE}/runs/{run_id}")
        return TestPlanRun.model_validate(resp.json())

    async def get_run_status(self, run_id: str) -> PlanRunStatus:
        resp = await self._request("GET", f"{_BASE}/runs/{run_id}/status")
        return PlanRunStatus.model_validate(resp.json())

    async def cancel_run(self, run_id: str) -> None:
        await self._request("POST", f"{_BASE}/runs/{run_id}/cancel")

    async def list_runs(
        self, plan_id: str, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> list[TestPlanRun]:
        params: dict[str, str] = {}
        if limit and limit > 0:
            params["limit"] = str(limit)
        if offset and offset > 0:
            params["offset"] = str(offset)
        resp = await self._request(
            "GET", f"{_BASE}/{plan_id}/runs", params=params or None
        )
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [TestPlanRun.model_validate(r) for r in items]

    async def wait_for_run(
        self,
        run_id: str,
        poll_interval: float = 2.0,
        timeout: Optional[float] = None,
    ) -> TestPlanRun:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            run = await self.get_run(run_id)
            if run.status == "completed":
                return run
            if run.status == "failed":
                raise RunFailedError(f"run {run_id} failed")
            if run.status == "cancelled":
                raise RunCancelledError(f"run {run_id} cancelled")
            if deadline is not None and time.monotonic() >= deadline:
                return run
            await asyncio.sleep(poll_interval)

    async def stream_run(self, run_id: str) -> AsyncIterator[RunEvent]:
        """Subscribe to the SSE stream of a run. Yields RunEvents."""
        async with self._client.stream(
            "GET",
            f"{_BASE}/runs/{run_id}/stream",
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            async for ev in _parse_sse_stream_async(response):
                yield ev

    async def get_report(self, run_id: str, format: str = "allure") -> bytes:
        resp = await self._request(
            "GET", f"{_BASE}/runs/{run_id}/report", params={"format": format}
        )
        return resp.content

    async def download_report_zip(self, run_id: str, dest: BinaryIO) -> None:
        async with self._client.stream(
            "GET",
            f"{_BASE}/runs/{run_id}/report.zip",
            headers={"Accept": "application/zip"},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                dest.write(chunk)

    async def add_schedule(self, plan_id: str, schedule: Schedule) -> Schedule:
        resp = await self._request(
            "POST",
            f"{_BASE}/{plan_id}/schedules",
            json=schedule.model_dump(by_alias=True, exclude_none=True),
        )
        return Schedule.model_validate(resp.json())

    async def list_schedules(self, plan_id: str) -> list[Schedule]:
        resp = await self._request("GET", f"{_BASE}/{plan_id}/schedules")
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [Schedule.model_validate(s) for s in items]

    async def update_schedule(
        self, plan_id: str, schedule_id: str, schedule: Schedule
    ) -> Schedule:
        resp = await self._request(
            "PATCH",
            f"{_BASE}/{plan_id}/schedules/{schedule_id}",
            json=schedule.model_dump(by_alias=True, exclude_none=True),
        )
        return Schedule.model_validate(resp.json())

    async def delete_schedule(self, plan_id: str, schedule_id: str) -> None:
        await self._request("DELETE", f"{_BASE}/{plan_id}/schedules/{schedule_id}")

    async def add_webhook(self, plan_id: str, webhook: Webhook) -> Webhook:
        resp = await self._request(
            "POST",
            f"{_BASE}/{plan_id}/webhooks",
            json=webhook.model_dump(by_alias=True, exclude_none=True),
        )
        return Webhook.model_validate(resp.json())

    async def list_webhooks(self, plan_id: str) -> list[Webhook]:
        resp = await self._request("GET", f"{_BASE}/{plan_id}/webhooks")
        body = resp.json()
        items = body.get("items", []) if isinstance(body, dict) else body
        return [Webhook.model_validate(w) for w in items]

    async def update_webhook(
        self, plan_id: str, webhook_id: str, webhook: Webhook
    ) -> Webhook:
        resp = await self._request(
            "PATCH",
            f"{_BASE}/{plan_id}/webhooks/{webhook_id}",
            json=webhook.model_dump(by_alias=True, exclude_none=True),
        )
        return Webhook.model_validate(resp.json())

    async def delete_webhook(self, plan_id: str, webhook_id: str) -> None:
        await self._request("DELETE", f"{_BASE}/{plan_id}/webhooks/{webhook_id}")

    async def test_webhook(self, plan_id: str, webhook_id: str) -> None:
        resp = await self._request(
            "POST", f"{_BASE}/{plan_id}/webhooks/{webhook_id}/test"
        )
        body = resp.json() if resp.content else {}
        if not body.get("success", False):
            msg = body.get("error") or f"status={body.get('status')}"
            raise WebhookDeliveryError(f"webhook {webhook_id!r}: {msg}")

    # ── TP-6b: namespace-scoped endpoints (async) ─────────────────────

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        ns = (namespace or self._namespace or "").strip()
        if not ns:
            raise ValueError("namespace is required for this endpoint")
        return ns

    async def patch(
        self,
        plan_ref: str,
        request: PatchPlanRequest,
        *,
        if_match: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> TestPlan:
        """Async twin of :meth:`TestPlansAPI.patch`."""
        key = _plan_ref(plan_ref)
        ns = self._resolve_namespace(namespace)

        body = request.model_dump(by_alias=True, exclude_none=True)
        if not body:
            raise ValueError("patch requires at least one field")

        etag = (if_match or "").strip()
        if not etag:
            current = await self.get(plan_ref)
            etag = _etag_from_plan(current)

        path = f"{_ns_base(ns)}/test-plans/{key}"
        try:
            resp = await self._request(
                "PATCH", path, json=body, headers={"If-Match": etag}
            )
        except MockartyAPIError as err:
            if err.status_code == 412:
                raise PreconditionFailedError(
                    err.message or "If-Match does not match current plan version",
                    request_id=err.request_id,
                ) from err
            raise
        return TestPlan.model_validate(resp.json())

    async def create_ad_hoc_run(
        self,
        request: CreateAdHocRunRequest,
        *,
        namespace: Optional[str] = None,
    ) -> AdHocRunResponse:
        """Async twin of :meth:`TestPlansAPI.create_ad_hoc_run`."""
        if not request.items:
            raise ValueError("CreateAdHocRunRequest requires at least one item")
        ns = self._resolve_namespace(namespace)
        path = f"{_ns_base(ns)}/test-runs/ad-hoc"
        resp = await self._request(
            "POST",
            path,
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        return AdHocRunResponse.model_validate(resp.json())

    async def get_run_report(
        self,
        plan_ref: str,
        run_id: str,
        *,
        namespace: Optional[str] = None,
    ) -> AllureReport:
        """Async twin of :meth:`TestPlansAPI.get_run_report`."""
        key = _plan_ref(plan_ref)
        if not (run_id or "").strip():
            raise ValueError("run_id must not be empty")
        ns = self._resolve_namespace(namespace)
        path = (
            f"{_ns_base(ns)}/test-plans/{key}/runs/{quote(run_id, safe='')}/report"
        )
        resp = await self._request("GET", path)
        body = resp.json() if resp.content else {}
        report = AllureReport.model_validate(body) if body else AllureReport()
        report.raw = resp.content
        return report

    async def get_run_report_zip(
        self,
        plan_ref: str,
        run_id: str,
        dest: BinaryIO,
        *,
        namespace: Optional[str] = None,
    ) -> None:
        """Async twin of :meth:`TestPlansAPI.get_run_report_zip`."""
        key = _plan_ref(plan_ref)
        if not (run_id or "").strip():
            raise ValueError("run_id must not be empty")
        ns = self._resolve_namespace(namespace)
        path = (
            f"{_ns_base(ns)}/test-plans/{key}"
            f"/runs/{quote(run_id, safe='')}/report.zip"
        )
        async with self._client.stream(
            "GET", path, headers={"Accept": "application/zip"}
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                dest.write(chunk)
