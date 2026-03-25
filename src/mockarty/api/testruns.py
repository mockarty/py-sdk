# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Test Run API resource for managing test execution history."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.testrun import TestRun


class TestRunAPI(SyncAPIBase):
    """Synchronous Test Run API resource."""

    def list(self) -> list[TestRun]:
        """List all test runs."""
        resp = self._request("GET", "/api/v1/api-tester/test-runs")
        data = resp.json()
        if isinstance(data, list):
            return [TestRun.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("runs") or []
            return [TestRun.model_validate(r) for r in items]
        return []

    def get(self, run_id: str) -> TestRun:
        """Get a specific test run by ID."""
        resp = self._request("GET", f"/api/v1/api-tester/test-runs/{run_id}")
        return TestRun.model_validate(resp.json())

    def delete(self, run_id: str) -> None:
        """Delete a test run record."""
        self._request("DELETE", f"/api/v1/api-tester/test-runs/{run_id}")

    def list_by_collection(self, collection_id: str) -> list[TestRun]:
        """List test runs for a specific collection."""
        resp = self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}/test-runs"
        )
        data = resp.json()
        if isinstance(data, list):
            return [TestRun.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("runs") or []
            return [TestRun.model_validate(r) for r in items]
        return []


class AsyncTestRunAPI(AsyncAPIBase):
    """Asynchronous Test Run API resource."""

    async def list(self) -> list[TestRun]:
        """List all test runs."""
        resp = await self._request("GET", "/api/v1/api-tester/test-runs")
        data = resp.json()
        if isinstance(data, list):
            return [TestRun.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("runs") or []
            return [TestRun.model_validate(r) for r in items]
        return []

    async def get(self, run_id: str) -> TestRun:
        """Get a specific test run by ID."""
        resp = await self._request("GET", f"/api/v1/api-tester/test-runs/{run_id}")
        return TestRun.model_validate(resp.json())

    async def delete(self, run_id: str) -> None:
        """Delete a test run record."""
        await self._request("DELETE", f"/api/v1/api-tester/test-runs/{run_id}")

    async def list_by_collection(self, collection_id: str) -> list[TestRun]:
        """List test runs for a specific collection."""
        resp = await self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}/test-runs"
        )
        data = resp.json()
        if isinstance(data, list):
            return [TestRun.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("runs") or []
            return [TestRun.model_validate(r) for r in items]
        return []
