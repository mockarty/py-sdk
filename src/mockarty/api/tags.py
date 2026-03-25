# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Tag management API resource."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.tags import Tag


class TagAPI(SyncAPIBase):
    """Synchronous Tag API resource."""

    def list(self) -> list[Tag]:
        """List all tags in the current namespace."""
        resp = self._request("GET", "/api/v1/tags")
        data = resp.json()
        if isinstance(data, list):
            return [Tag.model_validate(t) for t in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("tags") or []
            return [Tag.model_validate(t) for t in items]
        return []

    def create(self, name: str) -> Tag:
        """Create a new tag."""
        resp = self._request("POST", "/api/v1/tags", json={"name": name})
        return Tag.model_validate(resp.json())


class AsyncTagAPI(AsyncAPIBase):
    """Asynchronous Tag API resource."""

    async def list(self) -> list[Tag]:
        """List all tags in the current namespace."""
        resp = await self._request("GET", "/api/v1/tags")
        data = resp.json()
        if isinstance(data, list):
            return [Tag.model_validate(t) for t in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("tags") or []
            return [Tag.model_validate(t) for t in items]
        return []

    async def create(self, name: str) -> Tag:
        """Create a new tag."""
        resp = await self._request("POST", "/api/v1/tags", json={"name": name})
        return Tag.model_validate(resp.json())
