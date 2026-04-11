# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tag management API resource."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class TagAPI(SyncAPIBase):
    """Synchronous Tag API resource.

    Tags are stored as a flat list of strings attached to mocks.
    The server returns them as plain string values, not objects.
    """

    def list(self, namespace: str | None = None) -> list[str]:
        """List all tags in the given namespace (or the client's default)."""
        params: dict[str, str] = {}
        if namespace is not None:
            params["namespace"] = namespace
        resp = self._request("GET", "/api/v1/tags", params=params or None)
        data = resp.json()
        if isinstance(data, list):
            return [str(t) for t in data if t]
        if isinstance(data, dict):
            items = data.get("tags") or data.get("items") or []
            return [str(t) for t in items if t]
        return []

    def create(self, name: str, namespace: str | None = None) -> str:
        """Register a tag so it appears in autocomplete before being used on a mock."""
        body: dict[str, str] = {"tag": name}
        if namespace is not None:
            body["namespace"] = namespace
        resp = self._request("POST", "/api/v1/tags", json=body)
        data = resp.json() if resp.content else {}
        if isinstance(data, dict) and isinstance(data.get("tag"), str):
            return data["tag"]
        return name


class AsyncTagAPI(AsyncAPIBase):
    """Asynchronous Tag API resource."""

    async def list(self, namespace: str | None = None) -> list[str]:
        """List all tags in the given namespace (or the client's default)."""
        params: dict[str, str] = {}
        if namespace is not None:
            params["namespace"] = namespace
        resp = await self._request("GET", "/api/v1/tags", params=params or None)
        data = resp.json()
        if isinstance(data, list):
            return [str(t) for t in data if t]
        if isinstance(data, dict):
            items = data.get("tags") or data.get("items") or []
            return [str(t) for t in items if t]
        return []

    async def create(self, name: str, namespace: str | None = None) -> str:
        """Register a tag so it appears in autocomplete before being used on a mock."""
        body: dict[str, str] = {"tag": name}
        if namespace is not None:
            body["namespace"] = namespace
        resp = await self._request("POST", "/api/v1/tags", json=body)
        data = resp.json() if resp.content else {}
        if isinstance(data, dict) and isinstance(data.get("tag"), str):
            return data["tag"]
        return name
