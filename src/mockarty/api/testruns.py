# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test Run API resource for managing test execution history."""

from __future__ import annotations

from typing import Optional

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.testrun import TestRun


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
        resp = self._request("GET", "/api/v1/api-tester/test-runs", params=params or None)
        return _unwrap(resp.json())

    def list_by_mode(
        self,
        mode: str,
        reference_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[TestRun]:
        """Convenience wrapper: list runs for a specific execution mode."""
        return self.list(mode=mode, reference_id=reference_id, limit=limit, offset=offset)

    def get(self, run_id: str) -> TestRun:
        """Get a specific test run by ID."""
        resp = self._request("GET", f"/api/v1/api-tester/test-runs/{run_id}")
        return TestRun.model_validate(resp.json())

    def delete(self, run_id: str) -> None:
        """Delete a test run record."""
        self._request("DELETE", f"/api/v1/api-tester/test-runs/{run_id}")

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
