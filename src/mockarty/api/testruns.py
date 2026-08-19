# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Test Run API resource for managing test execution history."""

from __future__ import annotations

from typing import Optional

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.testrun import TestRun

# Aggregate report formats (POST /test-runs/reports/aggregate). This is the
# stateless replacement for the persistent merge surface removed server-side
# in migration 100 — recomputed per call, no parent row.
AGGREGATE_REPORT_FORMAT_UNIFIED = "unified"
AGGREGATE_REPORT_FORMAT_MARKDOWN = "markdown"
AGGREGATE_REPORT_FORMAT_HTML = "html"
AGGREGATE_REPORT_FORMAT_JUNIT = "junit"

# Aggregated report formats supported by the unified per-run endpoint
# ``/api-tester/test-runs/:id/report`` (backlog #67 foundation). Works for
# every mode (functional / load / fuzz / chaos / contract / merged).
TEST_RUN_REPORT_FORMAT_ALLURE_ZIP = "allure_zip"
TEST_RUN_REPORT_FORMAT_ALLURE_JSON = "allure_json"
TEST_RUN_REPORT_FORMAT_JUNIT = "junit"
TEST_RUN_REPORT_FORMAT_MARKDOWN = "markdown"
TEST_RUN_REPORT_FORMAT_UNIFIED_JSON = "unified_json"
TEST_RUN_REPORT_FORMAT_HTML = "html"


def _build_query(
    mode: Optional[str],
    reference_id: Optional[str],
    limit: Optional[int],
    offset: Optional[int],
) -> dict[str, str]:
    """Build the list-test-runs query params (migration 033 unified filters)."""
    q: dict[str, str] = {}
    if mode:
        q["mode"] = mode
    if reference_id:
        q["referenceId"] = reference_id
    if limit and limit > 0:
        q["limit"] = str(limit)
    if offset and offset > 0:
        q["offset"] = str(offset)
    return q


def _unwrap(data: object) -> list[TestRun]:
    """Decode either a bare list or an envelope {runs:[...]} / {items:[...]}."""
    if isinstance(data, list):
        return [TestRun.model_validate(r) for r in data]
    if isinstance(data, dict):
        items = data.get("items") or data.get("runs") or []
        return [TestRun.model_validate(r) for r in items]
    return []


class TestRunAPI(SyncAPIBase):
    """Synchronous Test Run API resource."""

    def list(
        self,
        mode: Optional[str] = None,
        reference_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestRun]:
        """List test runs with optional mode/reference filters (migration 033)."""
        params = _build_query(mode, reference_id, limit, offset)
        resp = self._request(
            "GET", "/api/v1/api-tester/test-runs", params=params or None
        )
        return _unwrap(resp.json())

    def list_by_mode(
        self,
        mode: str,
        reference_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestRun]:
        """Convenience wrapper: list runs for a specific execution mode."""
        return self.list(
            mode=mode, reference_id=reference_id, limit=limit, offset=offset
        )

    def get(self, run_id: str) -> TestRun:
        """Get a specific test run by ID."""
        resp = self._request("GET", f"/api/v1/api-tester/test-runs/{run_id}")
        return TestRun.model_validate(resp.json())

    def delete(self, run_id: str) -> None:
        """Delete a test run record."""
        self._request("DELETE", f"/api/v1/api-tester/test-runs/{run_id}")

    def get_test_run_report(
        self,
        run_id: str,
        format: str = TEST_RUN_REPORT_FORMAT_UNIFIED_JSON,
    ) -> bytes:
        """Fetch the aggregated report for a test run (backlog #67).

        Works for every mode (functional, load, fuzz, chaos, contract,
        merged). ``format`` must be one of the ``TEST_RUN_REPORT_FORMAT_*``
        constants. Returns the raw response bytes — callers decode JSON /
        write to file as appropriate.
        """
        fmt = format or TEST_RUN_REPORT_FORMAT_UNIFIED_JSON
        resp = self._request(
            "GET",
            f"/api/v1/api-tester/test-runs/{run_id}/report",
            params={"format": fmt},
        )
        return resp.content

    def list_by_collection(self, collection_id: str) -> list[TestRun]:
        """List test runs filtered by collection ID (client-side filter)."""
        all_runs = self.list()
        return [
            r for r in all_runs if getattr(r, "collection_id", None) == collection_id
        ]

    def list_active(self) -> list[TestRun]:
        """List active (pending/running) test runs in the current namespace.

        Polled by the UI Runs Tray; useful for CI gating on parallel runs.
        """
        resp = self._request("GET", "/api/v1/test-runs/active")
        return _unwrap(resp.json())

    # ── Merged test runs (T-12 / backlog #55) ──────────────────────────
    #
    # Aggregate report: a stateless report over several run IDs. Replaces the
    # removed persistent merge surface — nothing is created server-side.

    def aggregate_runs_report(
        self,
        run_ids: list[str],
        format: str = AGGREGATE_REPORT_FORMAT_UNIFIED,
        name: Optional[str] = None,
    ) -> bytes:
        """Build a transient release-ready aggregate report.

        No entity is persisted; the server streams the requested format back
        for download. ``format`` accepts ``AGGREGATE_REPORT_FORMAT_HTML``
        (self-contained, print-to-PDF), ``AGGREGATE_REPORT_FORMAT_UNIFIED``
        (JSON envelope), ``AGGREGATE_REPORT_FORMAT_MARKDOWN``, or
        ``AGGREGATE_REPORT_FORMAT_JUNIT`` (CI-ingest XML).
        """
        if not run_ids:
            raise ValueError("run_ids must be a non-empty list")
        fmt = format or AGGREGATE_REPORT_FORMAT_UNIFIED
        body: dict = {"run_ids": list(run_ids)}
        if name:
            body["name"] = name
        resp = self._request(
            "POST",
            "/api/v1/test-runs/reports/aggregate",
            params={"format": fmt},
            json=body,
        )
        return resp.content

    def cancel(self, run_id: str) -> None:
        """Cancel a running test run. Parity: Go/Java cancel."""
        self._request("POST", f"/api/v1/api-tester/test-runs/{run_id}/cancel")

    def export(self, run_id: str, format: str) -> bytes:
        """Export a test run's report as bytes. Parity: Go/Java export."""
        resp = self._request(
            "GET", f"/api/v1/api-tester/test-runs/{run_id}/export", params={"format": format}
        )
        return resp.content

    def import_report(self, report: dict[str, Any]) -> TestRun:
        """Import a test-run report. Parity: Go/Java importReport."""
        resp = self._request("POST", "/api/v1/api-tester/reports/import", json=report)
        return TestRun.model_validate(resp.json())


class AsyncTestRunAPI(AsyncAPIBase):
    """Asynchronous Test Run API resource."""

    async def list(
        self,
        mode: Optional[str] = None,
        reference_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestRun]:
        """List test runs with optional mode/reference filters (migration 033)."""
        params = _build_query(mode, reference_id, limit, offset)
        resp = await self._request(
            "GET", "/api/v1/api-tester/test-runs", params=params or None
        )
        return _unwrap(resp.json())

    async def list_by_mode(
        self,
        mode: str,
        reference_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestRun]:
        """Convenience wrapper: list runs for a specific execution mode."""
        return await self.list(
            mode=mode, reference_id=reference_id, limit=limit, offset=offset
        )

    async def get(self, run_id: str) -> TestRun:
        """Get a specific test run by ID."""
        resp = await self._request("GET", f"/api/v1/api-tester/test-runs/{run_id}")
        return TestRun.model_validate(resp.json())

    async def delete(self, run_id: str) -> None:
        """Delete a test run record."""
        await self._request("DELETE", f"/api/v1/api-tester/test-runs/{run_id}")

    async def get_test_run_report(
        self,
        run_id: str,
        format: str = TEST_RUN_REPORT_FORMAT_UNIFIED_JSON,
    ) -> bytes:
        """Fetch the aggregated report for a test run (backlog #67)."""
        fmt = format or TEST_RUN_REPORT_FORMAT_UNIFIED_JSON
        resp = await self._request(
            "GET",
            f"/api/v1/api-tester/test-runs/{run_id}/report",
            params={"format": fmt},
        )
        return resp.content

    async def list_by_collection(self, collection_id: str) -> list[TestRun]:
        """List test runs filtered by collection ID (client-side filter)."""
        all_runs = await self.list()
        return [
            r for r in all_runs if getattr(r, "collection_id", None) == collection_id
        ]

    async def list_active(self) -> list[TestRun]:
        """List active (pending/running) test runs in the current namespace."""
        resp = await self._request("GET", "/api/v1/test-runs/active")
        return _unwrap(resp.json())

    # Aggregate report (stateless; replaces the removed merge surface).

    async def aggregate_runs_report(
        self,
        run_ids: list[str],
        format: str = AGGREGATE_REPORT_FORMAT_UNIFIED,
        name: Optional[str] = None,
    ) -> bytes:
        """Async twin of the transient aggregate-report endpoint."""
        if not run_ids:
            raise ValueError("run_ids must be a non-empty list")
        fmt = format or AGGREGATE_REPORT_FORMAT_UNIFIED
        body: dict = {"run_ids": list(run_ids)}
        if name:
            body["name"] = name
        resp = await self._request(
            "POST",
            "/api/v1/test-runs/reports/aggregate",
            params={"format": fmt},
            json=body,
        )
        return resp.content

    async def cancel(self, run_id: str) -> None:
        """Cancel a running test run. Parity: Go/Java cancel."""
        await self._request("POST", f"/api/v1/api-tester/test-runs/{run_id}/cancel")

    async def export(self, run_id: str, format: str) -> bytes:
        """Export a test run's report as bytes. Parity: Go/Java export."""
        resp = await self._request(
            "GET", f"/api/v1/api-tester/test-runs/{run_id}/export", params={"format": format}
        )
        return resp.content

    async def import_report(self, report: dict[str, Any]) -> TestRun:
        """Import a test-run report. Parity: Go/Java importReport."""
        resp = await self._request("POST", "/api/v1/api-tester/reports/import", json=report)
        return TestRun.model_validate(resp.json())
