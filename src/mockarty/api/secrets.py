# Copyright (c) 2026 Mockarty. All rights reserved.

"""Secrets Storage API resource (Phase A0 — centralised encrypted secrets)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class SecretsAPI(SyncAPIBase):
    """Synchronous Secrets Storage API.

    Surfaces namespace-scoped encrypted key/value stores. Decrypted
    values are only returned by ``get_entry`` and only when the caller's
    API key carries the ``secret:read`` permission.
    """

    # ── Stores ────────────────────────────────────────────────────────

    def list_stores(self) -> list[dict[str, Any]]:
        """Return every secret store in the client's namespace."""
        resp = self._request(
            "GET", "/api/v1/stores/secrets", params={"namespace": self._namespace}
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def create_store(
        self,
        name: str,
        *,
        description: str | None = None,
        backend: str = "software",
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Create a new secret store. ``backend`` is ``"software"`` or ``"vault"``."""
        body: dict[str, Any] = {
            "name": name,
            "backend": backend,
            "namespace": namespace or self._namespace,
        }
        if description is not None:
            body["description"] = description
        resp = self._request("POST", "/api/v1/stores/secrets", json=body)
        return resp.json()

    def get_store(self, store_id: str) -> dict[str, Any]:
        resp = self._request("GET", f"/api/v1/stores/secrets/{quote(store_id, safe='')}")
        return resp.json()

    def update_store(self, store_id: str, **fields: Any) -> dict[str, Any]:
        resp = self._request(
            "PUT", f"/api/v1/stores/secrets/{quote(store_id, safe='')}", json=fields
        )
        return resp.json()

    def delete_store(self, store_id: str) -> None:
        self._request("DELETE", f"/api/v1/stores/secrets/{quote(store_id, safe='')}")

    # ── Entries ───────────────────────────────────────────────────────

    def list_entries(self, store_id: str) -> list[dict[str, Any]]:
        """Return entry metadata (values are never included)."""
        resp = self._request(
            "GET", f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def create_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"key": key, "value": value}
        if description is not None:
            body["description"] = description
        resp = self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries",
            json=body,
        )
        return resp.json()

    def get_entry(self, store_id: str, key: str) -> dict[str, Any]:
        """Fetch the decrypted value. Requires ``secret:read`` permission."""
        resp = self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
        )
        return resp.json()

    def update_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"value": value}
        if description is not None:
            body["description"] = description
        resp = self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            json=body,
        )
        return resp.json()

    def rotate_entry(self, store_id: str, key: str) -> dict[str, Any]:
        """Generate a new random value, bumping the entry's version."""
        resp = self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}/rotate",
        )
        return resp.json()

    def delete_entry(self, store_id: str, key: str) -> None:
        self._request(
            "DELETE",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
        )

    # ── Vault integration ─────────────────────────────────────────────

    def configure_vault(self, config: dict[str, Any], namespace: str | None = None) -> None:
        ns = namespace or self._namespace
        self._request(
            "PUT",
            f"/api/v1/namespaces/{quote(ns, safe='')}/integrations/vault",
            json=config,
        )


class AsyncSecretsAPI(AsyncAPIBase):
    """Asynchronous Secrets Storage API (mirrors :class:`SecretsAPI`)."""

    async def list_stores(self) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET", "/api/v1/stores/secrets", params={"namespace": self._namespace}
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def create_store(
        self,
        name: str,
        *,
        description: str | None = None,
        backend: str = "software",
        namespace: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "backend": backend,
            "namespace": namespace or self._namespace,
        }
        if description is not None:
            body["description"] = description
        resp = await self._request("POST", "/api/v1/stores/secrets", json=body)
        return resp.json()

    async def get_store(self, store_id: str) -> dict[str, Any]:
        resp = await self._request(
            "GET", f"/api/v1/stores/secrets/{quote(store_id, safe='')}"
        )
        return resp.json()

    async def update_store(self, store_id: str, **fields: Any) -> dict[str, Any]:
        resp = await self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            json=fields,
        )
        return resp.json()

    async def delete_store(self, store_id: str) -> None:
        await self._request(
            "DELETE", f"/api/v1/stores/secrets/{quote(store_id, safe='')}"
        )

    async def list_entries(self, store_id: str) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET", f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def create_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"key": key, "value": value}
        if description is not None:
            body["description"] = description
        resp = await self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries",
            json=body,
        )
        return resp.json()

    async def get_entry(self, store_id: str, key: str) -> dict[str, Any]:
        resp = await self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
        )
        return resp.json()

    async def update_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"value": value}
        if description is not None:
            body["description"] = description
        resp = await self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            json=body,
        )
        return resp.json()

    async def rotate_entry(self, store_id: str, key: str) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}/rotate",
        )
        return resp.json()

    async def delete_entry(self, store_id: str, key: str) -> None:
        await self._request(
            "DELETE",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
        )

    async def configure_vault(
        self, config: dict[str, Any], namespace: str | None = None
    ) -> None:
        ns = namespace or self._namespace
        await self._request(
            "PUT",
            f"/api/v1/namespaces/{quote(ns, safe='')}/integrations/vault",
            json=config,
        )
