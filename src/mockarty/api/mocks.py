# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Mock CRUD API resource."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.common import MockLogs, Page, RequestLog
from mockarty.models.mock import Mock, SaveMockResponse


class MockAPI(SyncAPIBase):
    """Synchronous Mock API resource."""

    def create(self, mock: Mock | dict[str, Any]) -> SaveMockResponse:
        """Create a new mock. Returns whether an existing mock was overwritten."""
        resp = self._request("POST", "/api/v1/mocks", json=mock)
        data = resp.json()
        return SaveMockResponse.model_validate(data)

    def get(self, mock_id: str) -> Mock:
        """Retrieve a mock by its ID."""
        resp = self._request("GET", f"/api/v1/mocks/{mock_id}")
        return Mock.model_validate(resp.json())

    def list(
        self,
        *,
        namespace: str | None = None,
        tags: list[str] | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Page[Mock]:
        """List mocks with optional filtering and pagination."""
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if namespace is not None:
            params["namespace"] = namespace
        if tags is not None:
            params["tags"] = ",".join(tags)
        if search is not None:
            params["search"] = search

        resp = self._request("GET", "/api/v1/mocks", params=params)
        data = resp.json()

        # The server returns a list of mocks; wrap in Page
        if isinstance(data, list):
            mocks = [Mock.model_validate(m) for m in data]
            return Page[Mock](items=mocks, total=len(mocks), offset=offset, limit=limit)

        # If server returns a paginated envelope, parse it
        if isinstance(data, dict):
            items = data.get("items") or data.get("mocks") or []
            mocks = [Mock.model_validate(m) for m in items]
            return Page[Mock](
                items=mocks,
                total=data.get("total", len(mocks)),
                offset=data.get("offset", offset),
                limit=data.get("limit", limit),
            )

        return Page[Mock](items=[], total=0, offset=offset, limit=limit)

    def update(self, mock_id: str, mock: Mock | dict[str, Any]) -> Mock:
        """Update a mock by re-creating it (full replacement)."""
        # Mockarty uses POST /api/v1/mocks with the same ID to update
        if isinstance(mock, dict):
            mock["id"] = mock_id
        else:
            mock.id = mock_id
        resp = self._request("POST", "/api/v1/mocks", json=mock)
        data = resp.json()
        result = SaveMockResponse.model_validate(data)
        return result.mock

    def patch(self, mock_id: str, patch: dict[str, Any]) -> Mock:
        """Partially update a mock. Sends only changed fields."""
        resp = self._request("PATCH", f"/api/v1/mocks/{mock_id}", json=patch)
        return Mock.model_validate(resp.json())

    def delete(self, mock_id: str) -> None:
        """Soft-delete a mock by ID."""
        self._request("DELETE", f"/api/v1/mocks/{mock_id}")

    def restore(self, mock_id: str) -> None:
        """Restore a previously soft-deleted mock."""
        self._request("POST", f"/api/v1/mocks/{mock_id}/restore")

    def purge(self, mock_id: str) -> None:
        """Permanently delete a mock (cannot be restored)."""
        self._request("DELETE", f"/api/v1/mocks/{mock_id}/purge")

    def batch_create(self, mocks: list[Mock | dict[str, Any]]) -> list[SaveMockResponse]:
        """Create multiple mocks in a single request."""
        results: list[SaveMockResponse] = []
        for mock in mocks:
            results.append(self.create(mock))
        return results

    def batch_delete(self, ids: list[str]) -> None:
        """Delete multiple mocks by their IDs."""
        self._request("DELETE", "/api/v1/mocks/batch", json={"ids": ids})

    def batch_restore(self, ids: list[str]) -> None:
        """Restore multiple soft-deleted mocks."""
        self._request("POST", "/api/v1/mocks/batch/restore", json={"ids": ids})

    def logs(self, mock_id: str, offset: int = 0, limit: int = 50) -> MockLogs:
        """Retrieve request logs for a specific mock."""
        resp = self._request(
            "GET",
            f"/api/v1/mocks/{mock_id}/logs",
            params={"offset": offset, "limit": limit},
        )
        data = resp.json()

        if isinstance(data, list):
            logs = [RequestLog.model_validate(entry) for entry in data]
            return MockLogs(logs=logs, total=len(logs))

        if isinstance(data, dict):
            raw_logs = data.get("logs") or data.get("items") or []
            logs = [RequestLog.model_validate(entry) for entry in raw_logs]
            return MockLogs(logs=logs, total=data.get("total", len(logs)))

        return MockLogs()

    def list_versions(self, mock_id: str) -> list[Mock]:
        """List all versions of a mock."""
        resp = self._request("GET", f"/api/v1/mocks/{mock_id}/versions")
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        return []

    def get_version(self, mock_id: str, version: int) -> Mock:
        """Get a specific version of a mock."""
        resp = self._request(
            "GET", f"/api/v1/mocks/{mock_id}/versions/{version}"
        )
        return Mock.model_validate(resp.json())

    def restore_version(self, mock_id: str, version: int) -> None:
        """Restore a mock to a specific version."""
        self._request(
            "POST", f"/api/v1/mocks/{mock_id}/versions/{version}/restore"
        )

    def delete_logs(self, mock_id: str) -> None:
        """Delete all request logs for a mock."""
        self._request("POST", f"/api/v1/mocks/{mock_id}/logs/delete")

    def copy_to_namespace(
        self, ids: list[str], target_namespace: str
    ) -> None:
        """Copy mocks to another namespace."""
        self._request(
            "POST",
            "/api/v1/mocks/copy-to-namespace",
            json={"ids": ids, "targetNamespace": target_namespace},
        )

    def move_to_folder(
        self, ids: list[str], folder_id: str | None
    ) -> None:
        """Move mocks to a folder."""
        self._request(
            "POST",
            "/api/v1/mocks/move-to-folder",
            json={"ids": ids, "folderId": folder_id},
        )

    def batch_update_tags(
        self, ids: list[str], tags: list[str]
    ) -> None:
        """Batch update tags for multiple mocks."""
        self._request(
            "PATCH",
            "/api/v1/mocks/batch/tags",
            json={"ids": ids, "tags": tags},
        )

    def versions(self, mock_id: str) -> list[Mock]:
        """Retrieve version history for a mock.

        .. deprecated:: Use :meth:`list_versions` instead.
        """
        return self.list_versions(mock_id)

    def chain(self, chain_id: str) -> list[Mock]:
        """Get all mocks in a chain by chain ID."""
        resp = self._request("GET", f"/api/v1/mocks/chains/{chain_id}")
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        return []

    def delete_chain(self, chain_id: str) -> None:
        """Delete all mocks in a chain."""
        self._request("DELETE", f"/api/v1/mocks/chains/{chain_id}")


class AsyncMockAPI(AsyncAPIBase):
    """Asynchronous Mock API resource."""

    async def create(self, mock: Mock | dict[str, Any]) -> SaveMockResponse:
        """Create a new mock."""
        resp = await self._request("POST", "/api/v1/mocks", json=mock)
        data = resp.json()
        return SaveMockResponse.model_validate(data)

    async def get(self, mock_id: str) -> Mock:
        """Retrieve a mock by its ID."""
        resp = await self._request("GET", f"/api/v1/mocks/{mock_id}")
        return Mock.model_validate(resp.json())

    async def list(
        self,
        *,
        namespace: str | None = None,
        tags: list[str] | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Page[Mock]:
        """List mocks with optional filtering and pagination."""
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if namespace is not None:
            params["namespace"] = namespace
        if tags is not None:
            params["tags"] = ",".join(tags)
        if search is not None:
            params["search"] = search

        resp = await self._request("GET", "/api/v1/mocks", params=params)
        data = resp.json()

        if isinstance(data, list):
            mocks = [Mock.model_validate(m) for m in data]
            return Page[Mock](items=mocks, total=len(mocks), offset=offset, limit=limit)

        if isinstance(data, dict):
            items = data.get("items") or data.get("mocks") or []
            mocks = [Mock.model_validate(m) for m in items]
            return Page[Mock](
                items=mocks,
                total=data.get("total", len(mocks)),
                offset=data.get("offset", offset),
                limit=data.get("limit", limit),
            )

        return Page[Mock](items=[], total=0, offset=offset, limit=limit)

    async def update(self, mock_id: str, mock: Mock | dict[str, Any]) -> Mock:
        """Update a mock by re-creating it."""
        if isinstance(mock, dict):
            mock["id"] = mock_id
        else:
            mock.id = mock_id
        resp = await self._request("POST", "/api/v1/mocks", json=mock)
        data = resp.json()
        result = SaveMockResponse.model_validate(data)
        return result.mock

    async def patch(self, mock_id: str, patch: dict[str, Any]) -> Mock:
        """Partially update a mock. Sends only changed fields."""
        resp = await self._request(
            "PATCH", f"/api/v1/mocks/{mock_id}", json=patch
        )
        return Mock.model_validate(resp.json())

    async def delete(self, mock_id: str) -> None:
        """Soft-delete a mock by ID."""
        await self._request("DELETE", f"/api/v1/mocks/{mock_id}")

    async def restore(self, mock_id: str) -> None:
        """Restore a previously soft-deleted mock."""
        await self._request("POST", f"/api/v1/mocks/{mock_id}/restore")

    async def purge(self, mock_id: str) -> None:
        """Permanently delete a mock."""
        await self._request("DELETE", f"/api/v1/mocks/{mock_id}/purge")

    async def batch_create(self, mocks: list[Mock | dict[str, Any]]) -> list[SaveMockResponse]:
        """Create multiple mocks."""
        results: list[SaveMockResponse] = []
        for mock in mocks:
            results.append(await self.create(mock))
        return results

    async def batch_delete(self, ids: list[str]) -> None:
        """Delete multiple mocks."""
        await self._request("DELETE", "/api/v1/mocks/batch", json={"ids": ids})

    async def batch_restore(self, ids: list[str]) -> None:
        """Restore multiple soft-deleted mocks."""
        await self._request("POST", "/api/v1/mocks/batch/restore", json={"ids": ids})

    async def logs(self, mock_id: str, offset: int = 0, limit: int = 50) -> MockLogs:
        """Retrieve request logs for a specific mock."""
        resp = await self._request(
            "GET",
            f"/api/v1/mocks/{mock_id}/logs",
            params={"offset": offset, "limit": limit},
        )
        data = resp.json()

        if isinstance(data, list):
            logs = [RequestLog.model_validate(entry) for entry in data]
            return MockLogs(logs=logs, total=len(logs))

        if isinstance(data, dict):
            raw_logs = data.get("logs") or data.get("items") or []
            logs = [RequestLog.model_validate(entry) for entry in raw_logs]
            return MockLogs(logs=logs, total=data.get("total", len(logs)))

        return MockLogs()

    async def list_versions(self, mock_id: str) -> list[Mock]:
        """List all versions of a mock."""
        resp = await self._request(
            "GET", f"/api/v1/mocks/{mock_id}/versions"
        )
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        return []

    async def get_version(self, mock_id: str, version: int) -> Mock:
        """Get a specific version of a mock."""
        resp = await self._request(
            "GET", f"/api/v1/mocks/{mock_id}/versions/{version}"
        )
        return Mock.model_validate(resp.json())

    async def restore_version(self, mock_id: str, version: int) -> None:
        """Restore a mock to a specific version."""
        await self._request(
            "POST", f"/api/v1/mocks/{mock_id}/versions/{version}/restore"
        )

    async def delete_logs(self, mock_id: str) -> None:
        """Delete all request logs for a mock."""
        await self._request("POST", f"/api/v1/mocks/{mock_id}/logs/delete")

    async def copy_to_namespace(
        self, ids: list[str], target_namespace: str
    ) -> None:
        """Copy mocks to another namespace."""
        await self._request(
            "POST",
            "/api/v1/mocks/copy-to-namespace",
            json={"ids": ids, "targetNamespace": target_namespace},
        )

    async def move_to_folder(
        self, ids: list[str], folder_id: str | None
    ) -> None:
        """Move mocks to a folder."""
        await self._request(
            "POST",
            "/api/v1/mocks/move-to-folder",
            json={"ids": ids, "folderId": folder_id},
        )

    async def batch_update_tags(
        self, ids: list[str], tags: list[str]
    ) -> None:
        """Batch update tags for multiple mocks."""
        await self._request(
            "PATCH",
            "/api/v1/mocks/batch/tags",
            json={"ids": ids, "tags": tags},
        )

    async def versions(self, mock_id: str) -> list[Mock]:
        """Retrieve version history for a mock.

        .. deprecated:: Use :meth:`list_versions` instead.
        """
        return await self.list_versions(mock_id)

    async def chain(self, chain_id: str) -> list[Mock]:
        """Get all mocks in a chain by chain ID."""
        resp = await self._request("GET", f"/api/v1/mocks/chains/{chain_id}")
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        return []

    async def delete_chain(self, chain_id: str) -> None:
        """Delete all mocks in a chain."""
        await self._request("DELETE", f"/api/v1/mocks/chains/{chain_id}")
