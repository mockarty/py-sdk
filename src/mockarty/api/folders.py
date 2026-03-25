# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Mock folder management API resource."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.folders import MockFolder


class FolderAPI(SyncAPIBase):
    """Synchronous Folder API resource."""

    def list(self) -> list[MockFolder]:
        """List all mock folders."""
        resp = self._request("GET", "/api/v1/mock-folders")
        data = resp.json()
        if isinstance(data, list):
            return [MockFolder.model_validate(f) for f in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("folders") or []
            return [MockFolder.model_validate(f) for f in items]
        return []

    def create(self, folder: MockFolder | dict[str, Any]) -> MockFolder:
        """Create a new mock folder."""
        resp = self._request("POST", "/api/v1/mock-folders", json=folder)
        return MockFolder.model_validate(resp.json())

    def update(self, folder_id: str, folder: MockFolder | dict[str, Any]) -> MockFolder:
        """Update an existing mock folder."""
        resp = self._request("PUT", f"/api/v1/mock-folders/{folder_id}", json=folder)
        return MockFolder.model_validate(resp.json())

    def delete(self, folder_id: str) -> None:
        """Delete a mock folder."""
        self._request("DELETE", f"/api/v1/mock-folders/{folder_id}")

    def move(self, folder_id: str, parent_id: str | None) -> MockFolder:
        """Move a folder to a new parent."""
        resp = self._request(
            "PATCH",
            f"/api/v1/mock-folders/{folder_id}/move",
            json={"parentId": parent_id},
        )
        return MockFolder.model_validate(resp.json())


class AsyncFolderAPI(AsyncAPIBase):
    """Asynchronous Folder API resource."""

    async def list(self) -> list[MockFolder]:
        """List all mock folders."""
        resp = await self._request("GET", "/api/v1/mock-folders")
        data = resp.json()
        if isinstance(data, list):
            return [MockFolder.model_validate(f) for f in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("folders") or []
            return [MockFolder.model_validate(f) for f in items]
        return []

    async def create(self, folder: MockFolder | dict[str, Any]) -> MockFolder:
        """Create a new mock folder."""
        resp = await self._request("POST", "/api/v1/mock-folders", json=folder)
        return MockFolder.model_validate(resp.json())

    async def update(
        self, folder_id: str, folder: MockFolder | dict[str, Any]
    ) -> MockFolder:
        """Update an existing mock folder."""
        resp = await self._request(
            "PUT", f"/api/v1/mock-folders/{folder_id}", json=folder
        )
        return MockFolder.model_validate(resp.json())

    async def delete(self, folder_id: str) -> None:
        """Delete a mock folder."""
        await self._request("DELETE", f"/api/v1/mock-folders/{folder_id}")

    async def move(self, folder_id: str, parent_id: str | None) -> MockFolder:
        """Move a folder to a new parent."""
        resp = await self._request(
            "PATCH",
            f"/api/v1/mock-folders/{folder_id}/move",
            json={"parentId": parent_id},
        )
        return MockFolder.model_validate(resp.json())
