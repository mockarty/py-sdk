# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Namespace management API resource."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class NamespaceAPI(SyncAPIBase):
    """Synchronous Namespace API resource."""

    def create(self, name: str) -> None:
        """Create a new namespace."""
        self._request("POST", "/api/v1/namespaces", json={"name": name})

    def list(self) -> list[str]:
        """List all available namespaces."""
        resp = self._request("GET", "/api/v1/namespaces")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("namespaces") or data.get("items") or []
        return []

    # NOTE: namespace-level copy_mocks was removed — it POSTed to a
    # non-existent /api/v1/namespaces/copy-mocks route (404). The real,
    # server-backed operation is mocks.copy_to_namespace(mock_ids, target).


class AsyncNamespaceAPI(AsyncAPIBase):
    """Asynchronous Namespace API resource."""

    async def create(self, name: str) -> None:
        """Create a new namespace."""
        await self._request("POST", "/api/v1/namespaces", json={"name": name})

    async def list(self) -> list[str]:
        """List all available namespaces."""
        resp = await self._request("GET", "/api/v1/namespaces")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("namespaces") or data.get("items") or []
        return []

    # copy_mocks removed (phantom /namespaces/copy-mocks 404) — use
    # mocks.copy_to_namespace(mock_ids, target).
