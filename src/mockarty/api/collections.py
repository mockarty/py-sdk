# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Collection (API Tester) API resource."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.common import Collection, TestRunResult


class CollectionAPI(SyncAPIBase):
    """Synchronous Collection API resource."""

    def list(self) -> list[Collection]:
        """List all test collections."""
        resp = self._request("GET", "/api/v1/api-tester/collections")
        data = resp.json()
        if isinstance(data, list):
            return [Collection.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("collections") or []
            return [Collection.model_validate(c) for c in items]
        return []

    def get(self, collection_id: str) -> Collection:
        """Get a single collection by ID."""
        resp = self._request("GET", f"/api/v1/api-tester/collections/{collection_id}")
        return Collection.model_validate(resp.json())

    def execute(self, collection_id: str) -> TestRunResult:
        """Execute all tests in a collection."""
        resp = self._request(
            "POST", f"/api/v1/api-tester/collections/{collection_id}/run"
        )
        return TestRunResult.model_validate(resp.json())

    def execute_multiple(self, ids: list[str]) -> TestRunResult:
        """Execute tests from multiple collections."""
        resp = self._request(
            "POST",
            "/api/v1/api-tester/collections/run-multiple",
            json={"collectionIds": ids},
        )
        return TestRunResult.model_validate(resp.json())

    def export(self, collection_id: str) -> bytes:
        """Export a collection as a downloadable archive."""
        resp = self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}/export"
        )
        return resp.content


class AsyncCollectionAPI(AsyncAPIBase):
    """Asynchronous Collection API resource."""

    async def list(self) -> list[Collection]:
        """List all test collections."""
        resp = await self._request("GET", "/api/v1/api-tester/collections")
        data = resp.json()
        if isinstance(data, list):
            return [Collection.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("collections") or []
            return [Collection.model_validate(c) for c in items]
        return []

    async def get(self, collection_id: str) -> Collection:
        """Get a single collection by ID."""
        resp = await self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}"
        )
        return Collection.model_validate(resp.json())

    async def execute(self, collection_id: str) -> TestRunResult:
        """Execute all tests in a collection."""
        resp = await self._request(
            "POST", f"/api/v1/api-tester/collections/{collection_id}/run"
        )
        return TestRunResult.model_validate(resp.json())

    async def execute_multiple(self, ids: list[str]) -> TestRunResult:
        """Execute tests from multiple collections."""
        resp = await self._request(
            "POST",
            "/api/v1/api-tester/collections/run-multiple",
            json={"collectionIds": ids},
        )
        return TestRunResult.model_validate(resp.json())

    async def export(self, collection_id: str) -> bytes:
        """Export a collection as a downloadable archive."""
        resp = await self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}/export"
        )
        return resp.content
