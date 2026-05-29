# Copyright (c) 2026 Mockarty. All rights reserved.

"""Secrets Storage API resource (Phase A0 — centralised encrypted secrets).

Server wire shapes (admin webui handlers):

    GET    /api/v1/stores/secrets                       → {"stores": [...], ...}
    POST   /api/v1/stores/secrets                       → {"store":  {...}}
    GET    /api/v1/stores/secrets/:id                   → {"store":  {...}}
    PUT    /api/v1/stores/secrets/:id                   → {"store":  {...}}
    DELETE /api/v1/stores/secrets/:id                   → {"message": "...", "id": ...}

    GET    /stores/secrets/:id/entries                  → {"entries": [...], ...}
    POST   /stores/secrets/:id/entries                  → {"entry":   <flat dict>}
    GET    /stores/secrets/:id/entries/:k               → <flat dict>   (NO envelope)
    PUT    /stores/secrets/:id/entries/:k               → {"message": "...", "id": "..."}
    POST   /stores/secrets/:id/entries/:k/rotate        → {"message": "...", "id": "..."}
    DELETE /stores/secrets/:id/entries/:k               → {"message": "..."}

The SDK unwraps the ``store`` / ``stores`` / ``entry`` / ``entries`` envelopes
before returning so callers see the inner object directly. Every entry-level
call threads ``?namespace=<X>`` because the handlers read NS from the query
string only — a body-level ``namespace`` field is silently ignored.

Valid backend values: ``inline`` (default, local AES-GCM via KeyStore),
``vault``, ``aws_sm``, ``gcp_sm``, ``azure_kv``, ``custom_api``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _unwrap_one(payload: Any, key: str) -> dict[str, Any]:
    """Return ``payload[key]`` when present, else the payload itself.

    Defensive against future server shape changes (if a handler stops
    wrapping its single-item responses, the SDK keeps working).
    """
    if isinstance(payload, dict) and key in payload and isinstance(payload[key], dict):
        return payload[key]
    return payload if isinstance(payload, dict) else {}


def _unwrap_list(payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and key in payload and isinstance(payload[key], list):
        return payload[key]
    return payload if isinstance(payload, list) else []


class SecretsAPI(SyncAPIBase):
    """Synchronous Secrets Storage API.

    Surfaces namespace-scoped encrypted key/value stores. Decrypted
    values are only returned by ``get_entry`` and only when the caller's
    API key carries the ``secret:read`` permission.
    """

    # ── Stores ────────────────────────────────────────────────────────

    def list_stores(self, namespace: str | None = None) -> list[dict[str, Any]]:
        """Return every secret store in the given namespace (or the client's
        default if ``namespace`` is omitted)."""
        ns = namespace or self._namespace
        resp = self._request("GET", "/api/v1/stores/secrets", params={"namespace": ns})
        return _unwrap_list(resp.json(), "stores")

    def create_store(
        self,
        name: str,
        *,
        description: str | None = None,
        backend: str = "inline",
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Create a new secret store.

        ``backend`` is one of ``inline`` | ``vault`` | ``aws_sm`` | ``gcp_sm``
        | ``azure_kv`` | ``custom_api``. Default ``inline`` uses local
        AES-GCM via the admin node's KeyStore.
        """
        ns = namespace or self._namespace
        body: dict[str, Any] = {"name": name, "backend": backend}
        if description is not None:
            body["description"] = description
        resp = self._request(
            "POST",
            "/api/v1/stores/secrets",
            params={"namespace": ns},
            json=body,
        )
        return _unwrap_one(resp.json(), "store")

    def get_store(
        self, store_id: str, *, namespace: str | None = None
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        resp = self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            params={"namespace": ns},
        )
        return _unwrap_one(resp.json(), "store")

    def update_store(
        self, store_id: str, *, namespace: str | None = None, **fields: Any
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        resp = self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            params={"namespace": ns},
            json=fields,
        )
        return _unwrap_one(resp.json(), "store")

    def delete_store(self, store_id: str, *, namespace: str | None = None) -> None:
        ns = namespace or self._namespace
        self._request(
            "DELETE",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            params={"namespace": ns},
        )

    # ── Entries ───────────────────────────────────────────────────────

    def list_entries(
        self, store_id: str, *, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """Return entry metadata (values are never included)."""
        ns = namespace or self._namespace
        resp = self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries",
            params={"namespace": ns},
        )
        return _unwrap_list(resp.json(), "entries")

    def create_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body: dict[str, Any] = {"key": key, "value": value}
        if description is not None:
            body["description"] = description
        resp = self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries",
            params={"namespace": ns},
            json=body,
        )
        return _unwrap_one(resp.json(), "entry")

    def get_entry(
        self, store_id: str, key: str, *, namespace: str | None = None
    ) -> dict[str, Any]:
        """Fetch the decrypted value. Requires ``secret:read`` permission.

        The server returns a flat dict (NOT enveloped) on this endpoint.
        """
        ns = namespace or self._namespace
        resp = self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            params={"namespace": ns},
        )
        data = resp.json()
        return data if isinstance(data, dict) else {}

    def update_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body: dict[str, Any] = {"value": value}
        if description is not None:
            body["description"] = description
        resp = self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            params={"namespace": ns},
            json=body,
        )
        return resp.json() if hasattr(resp, "json") else {}

    def rotate_entry(
        self,
        store_id: str,
        key: str,
        new_value: str,
        *,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Replace the entry's value with ``new_value``, bumping its version.

        Server wire shape requires ``{value: ...}`` in the body — older SDK
        builds posted nil and rotate calls 400'd with 'invalid request
        payload'. The new value is mandatory.
        """
        if not new_value:
            raise ValueError("rotate_entry: new_value is required")
        ns = namespace or self._namespace
        resp = self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}/rotate",
            params={"namespace": ns},
            json={"value": new_value},
        )
        return resp.json() if hasattr(resp, "json") else {}

    def delete_entry(
        self, store_id: str, key: str, *, namespace: str | None = None
    ) -> None:
        ns = namespace or self._namespace
        self._request(
            "DELETE",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            params={"namespace": ns},
        )

    # ── Vault integration ─────────────────────────────────────────────

    def configure_vault(
        self, config: dict[str, Any], namespace: str | None = None
    ) -> None:
        ns = namespace or self._namespace
        self._request(
            "PUT",
            f"/api/v1/namespaces/{quote(ns, safe='')}/integrations/vault",
            json=config,
        )


class AsyncSecretsAPI(AsyncAPIBase):
    """Asynchronous Secrets Storage API (mirrors :class:`SecretsAPI`)."""

    async def list_stores(self, namespace: str | None = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request(
            "GET", "/api/v1/stores/secrets", params={"namespace": ns}
        )
        return _unwrap_list(resp.json(), "stores")

    async def create_store(
        self,
        name: str,
        *,
        description: str | None = None,
        backend: str = "inline",
        namespace: str | None = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body: dict[str, Any] = {"name": name, "backend": backend}
        if description is not None:
            body["description"] = description
        resp = await self._request(
            "POST",
            "/api/v1/stores/secrets",
            params={"namespace": ns},
            json=body,
        )
        return _unwrap_one(resp.json(), "store")

    async def get_store(
        self, store_id: str, *, namespace: str | None = None
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        resp = await self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            params={"namespace": ns},
        )
        return _unwrap_one(resp.json(), "store")

    async def update_store(
        self, store_id: str, *, namespace: str | None = None, **fields: Any
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        resp = await self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            params={"namespace": ns},
            json=fields,
        )
        return _unwrap_one(resp.json(), "store")

    async def delete_store(
        self, store_id: str, *, namespace: str | None = None
    ) -> None:
        ns = namespace or self._namespace
        await self._request(
            "DELETE",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}",
            params={"namespace": ns},
        )

    async def list_entries(
        self, store_id: str, *, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries",
            params={"namespace": ns},
        )
        return _unwrap_list(resp.json(), "entries")

    async def create_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body: dict[str, Any] = {"key": key, "value": value}
        if description is not None:
            body["description"] = description
        resp = await self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries",
            params={"namespace": ns},
            json=body,
        )
        return _unwrap_one(resp.json(), "entry")

    async def get_entry(
        self, store_id: str, key: str, *, namespace: str | None = None
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        resp = await self._request(
            "GET",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            params={"namespace": ns},
        )
        data = resp.json()
        return data if isinstance(data, dict) else {}

    async def update_entry(
        self,
        store_id: str,
        key: str,
        value: str,
        *,
        description: str | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        ns = namespace or self._namespace
        body: dict[str, Any] = {"value": value}
        if description is not None:
            body["description"] = description
        resp = await self._request(
            "PUT",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            params={"namespace": ns},
            json=body,
        )
        return resp.json() if hasattr(resp, "json") else {}

    async def rotate_entry(
        self,
        store_id: str,
        key: str,
        new_value: str,
        *,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        """Async mirror of ``SecretsAPI.rotate_entry`` — see sync docstring."""
        if not new_value:
            raise ValueError("rotate_entry: new_value is required")
        ns = namespace or self._namespace
        resp = await self._request(
            "POST",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}/rotate",
            params={"namespace": ns},
            json={"value": new_value},
        )
        return resp.json() if hasattr(resp, "json") else {}

    async def delete_entry(
        self, store_id: str, key: str, *, namespace: str | None = None
    ) -> None:
        ns = namespace or self._namespace
        await self._request(
            "DELETE",
            f"/api/v1/stores/secrets/{quote(store_id, safe='')}/entries/{quote(key, safe='')}",
            params={"namespace": ns},
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
