# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

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
            "POST", f"/api/v1/api-tester/collections/{collection_id}/execute"
        )
        return TestRunResult.model_validate(resp.json())

    def execute_multiple(self, ids: list[str]) -> TestRunResult:
        """Execute tests from multiple collections."""
        resp = self._request(
            "POST",
            "/api/v1/api-tester/collections/execute-multiple",
            json={"collectionIds": ids},
        )
        return TestRunResult.model_validate(resp.json())

    def export(self, collection_id: str) -> bytes:
        """Export a collection as a downloadable archive."""
        resp = self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}/export"
        )
        return resp.content

    def create(self, collection: Collection | dict) -> Collection:
        """Create a new test collection. Parity: Go Create / Java create."""
        resp = self._request("POST", "/api/v1/api-tester/collections", json=collection)
        return Collection.model_validate(resp.json())

    def update(self, collection_id: str, collection: Collection | dict) -> Collection:
        """Update a collection by ID. Parity: Go Update / Java update."""
        resp = self._request(
            "PUT", f"/api/v1/api-tester/collections/{collection_id}", json=collection
        )
        return Collection.model_validate(resp.json())

    def delete(self, collection_id: str) -> None:
        """Delete a collection by ID. Parity: Go Delete / Java delete."""
        self._request("DELETE", f"/api/v1/api-tester/collections/{collection_id}")

    def duplicate(self, collection_id: str) -> Collection:
        """Duplicate a collection by ID. Parity: Go Duplicate / Java duplicate."""
        resp = self._request(
            "POST", f"/api/v1/api-tester/collections/{collection_id}/duplicate"
        )
        return Collection.model_validate(resp.json())

    def batch_delete(self, ids: list[str]) -> None:
        """Delete multiple collections by ID. Parity: Go BatchDelete / Java batchDelete."""
        self._request("DELETE", "/api/v1/api-tester/collections/batch", json={"ids": ids})


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
            "POST", f"/api/v1/api-tester/collections/{collection_id}/execute"
        )
        return TestRunResult.model_validate(resp.json())

    async def execute_multiple(self, ids: list[str]) -> TestRunResult:
        """Execute tests from multiple collections."""
        resp = await self._request(
            "POST",
            "/api/v1/api-tester/collections/execute-multiple",
            json={"collectionIds": ids},
        )
        return TestRunResult.model_validate(resp.json())

    async def export(self, collection_id: str) -> bytes:
        """Export a collection as a downloadable archive."""
        resp = await self._request(
            "GET", f"/api/v1/api-tester/collections/{collection_id}/export"
        )
        return resp.content

    async def create(self, collection: Collection | dict) -> Collection:
        """Create a new test collection. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/collections", json=collection)
        return Collection.model_validate(resp.json())

    async def update(self, collection_id: str, collection: Collection | dict) -> Collection:
        """Update a collection by ID. Parity: Go/Java."""
        resp = await self._request(
            "PUT", f"/api/v1/api-tester/collections/{collection_id}", json=collection
        )
        return Collection.model_validate(resp.json())

    async def delete(self, collection_id: str) -> None:
        """Delete a collection by ID. Parity: Go/Java."""
        await self._request("DELETE", f"/api/v1/api-tester/collections/{collection_id}")

    async def duplicate(self, collection_id: str) -> Collection:
        """Duplicate a collection by ID. Parity: Go/Java."""
        resp = await self._request(
            "POST", f"/api/v1/api-tester/collections/{collection_id}/duplicate"
        )
        return Collection.model_validate(resp.json())

    async def batch_delete(self, ids: list[str]) -> None:
        """Delete multiple collections by ID. Parity: Go/Java."""
        await self._request("DELETE", "/api/v1/api-tester/collections/batch", json={"ids": ids})
