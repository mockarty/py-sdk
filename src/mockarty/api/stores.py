# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Store management API resource (Global and Chain stores)."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class StoreAPI(SyncAPIBase):
    """Synchronous Store API resource."""

    # ── Global Store ──────────────────────────────────────────────────

    def global_get(self) -> dict[str, Any]:
        """Retrieve the entire global store."""
        resp = self._request("GET", "/api/v1/stores/global")
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}

    def global_set(self, key: str, value: Any) -> None:
        """Set a key-value pair in the global store."""
        self._request("POST", "/api/v1/stores/global", json={key: value})

    def global_set_many(self, entries: dict[str, Any]) -> None:
        """Set multiple key-value pairs in the global store."""
        self._request("POST", "/api/v1/stores/global", json=entries)

    def global_delete(self, key: str) -> None:
        """Delete a key from the global store."""
        self._request("DELETE", "/api/v1/stores/global", json={"keys": [key]})

    def global_delete_many(self, keys: list[str]) -> None:
        """Delete multiple keys from the global store."""
        self._request("DELETE", "/api/v1/stores/global", json={"keys": keys})

    # ── Chain Store ───────────────────────────────────────────────────

    def chain_get(self, chain_id: str) -> dict[str, Any]:
        """Retrieve the chain store for a given chain ID."""
        resp = self._request("GET", f"/api/v1/stores/chain/{chain_id}")
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}

    def chain_set(self, chain_id: str, key: str, value: Any) -> None:
        """Set a key-value pair in a chain store."""
        self._request("POST", f"/api/v1/stores/chain/{chain_id}", json={key: value})

    def chain_set_many(self, chain_id: str, entries: dict[str, Any]) -> None:
        """Set multiple key-value pairs in a chain store."""
        self._request("POST", f"/api/v1/stores/chain/{chain_id}", json=entries)

    def chain_delete(self, chain_id: str, key: str) -> None:
        """Delete a key from a chain store."""
        self._request("DELETE", f"/api/v1/stores/chain/{chain_id}", json={"keys": [key]})

    def chain_delete_many(self, chain_id: str, keys: list[str]) -> None:
        """Delete multiple keys from a chain store."""
        self._request("DELETE", f"/api/v1/stores/chain/{chain_id}", json={"keys": keys})


class AsyncStoreAPI(AsyncAPIBase):
    """Asynchronous Store API resource."""

    # ── Global Store ──────────────────────────────────────────────────

    async def global_get(self) -> dict[str, Any]:
        """Retrieve the entire global store."""
        resp = await self._request("GET", "/api/v1/stores/global")
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}

    async def global_set(self, key: str, value: Any) -> None:
        """Set a key-value pair in the global store."""
        await self._request("POST", "/api/v1/stores/global", json={key: value})

    async def global_set_many(self, entries: dict[str, Any]) -> None:
        """Set multiple key-value pairs in the global store."""
        await self._request("POST", "/api/v1/stores/global", json=entries)

    async def global_delete(self, key: str) -> None:
        """Delete a key from the global store."""
        await self._request("DELETE", "/api/v1/stores/global", json={"keys": [key]})

    async def global_delete_many(self, keys: list[str]) -> None:
        """Delete multiple keys from the global store."""
        await self._request("DELETE", "/api/v1/stores/global", json={"keys": keys})

    # ── Chain Store ───────────────────────────────────────────────────

    async def chain_get(self, chain_id: str) -> dict[str, Any]:
        """Retrieve the chain store for a given chain ID."""
        resp = await self._request("GET", f"/api/v1/stores/chain/{chain_id}")
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {}

    async def chain_set(self, chain_id: str, key: str, value: Any) -> None:
        """Set a key-value pair in a chain store."""
        await self._request("POST", f"/api/v1/stores/chain/{chain_id}", json={key: value})

    async def chain_set_many(self, chain_id: str, entries: dict[str, Any]) -> None:
        """Set multiple key-value pairs in a chain store."""
        await self._request("POST", f"/api/v1/stores/chain/{chain_id}", json=entries)

    async def chain_delete(self, chain_id: str, key: str) -> None:
        """Delete a key from a chain store."""
        await self._request(
            "DELETE", f"/api/v1/stores/chain/{chain_id}", json={"keys": [key]}
        )

    async def chain_delete_many(self, chain_id: str, keys: list[str]) -> None:
        """Delete multiple keys from a chain store."""
        await self._request(
            "DELETE", f"/api/v1/stores/chain/{chain_id}", json={"keys": keys}
        )
