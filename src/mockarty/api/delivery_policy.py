"""Administrator delivery-policy environment management."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


_BASE = "/api/v1/admin/delivery-policy/environments"


def _path(environment_id: str) -> str:
    if not environment_id or not environment_id.strip():
        raise ValueError("delivery-policy environment_id is required")
    return _BASE + "/" + quote(environment_id, safe="")


def _create_headers(idempotency_key: str) -> dict[str, str]:
    if not idempotency_key or not idempotency_key.strip():
        raise ValueError("delivery-policy idempotency_key is required")
    return {"Idempotency-Key": idempotency_key}


def _advance_headers(etag: str, idempotency_key: str) -> dict[str, str]:
    if not etag or not etag.strip():
        raise ValueError("delivery-policy ETag is required")
    return {"If-Match": etag, **_create_headers(idempotency_key)}


class DeliveryPolicyAPI(SyncAPIBase):
    def create(self, body: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._request("POST", _BASE, params={"namespace": self._namespace}, json=body, headers=_create_headers(idempotency_key)).json()

    def get(self, environment_id: str) -> dict[str, Any]:
        return self._request("GET", _path(environment_id), params={"namespace": self._namespace}).json()

    def list(self, status: str = "", cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params = {key: value for key, value in {"namespace": self._namespace, "status": status, "cursor": cursor, "limit": limit}.items() if value}
        return self._request("GET", _BASE, params=params).json()

    def advance(self, environment_id: str, body: dict[str, Any], etag: str, idempotency_key: str) -> dict[str, Any]:
        payload = dict(body)
        payload.pop("id", None)
        return self._request("PUT", _path(environment_id), params={"namespace": self._namespace}, json=payload, headers=_advance_headers(etag, idempotency_key)).json()

    def revoke(self, environment_id: str, etag: str) -> None:
        if not etag or not etag.strip():
            raise ValueError("delivery-policy ETag is required")
        self._request("DELETE", _path(environment_id), params={"namespace": self._namespace}, headers={"If-Match": etag})


class AsyncDeliveryPolicyAPI(AsyncAPIBase):
    async def create(self, body: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return (await self._request("POST", _BASE, params={"namespace": self._namespace}, json=body, headers=_create_headers(idempotency_key))).json()

    async def get(self, environment_id: str) -> dict[str, Any]:
        return (await self._request("GET", _path(environment_id), params={"namespace": self._namespace})).json()

    async def list(self, status: str = "", cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params = {key: value for key, value in {"namespace": self._namespace, "status": status, "cursor": cursor, "limit": limit}.items() if value}
        return (await self._request("GET", _BASE, params=params)).json()

    async def advance(self, environment_id: str, body: dict[str, Any], etag: str, idempotency_key: str) -> dict[str, Any]:
        payload = dict(body)
        payload.pop("id", None)
        return (await self._request("PUT", _path(environment_id), params={"namespace": self._namespace}, json=payload, headers=_advance_headers(etag, idempotency_key))).json()

    async def revoke(self, environment_id: str, etag: str) -> None:
        if not etag or not etag.strip():
            raise ValueError("delivery-policy ETag is required")
        await self._request("DELETE", _path(environment_id), params={"namespace": self._namespace}, headers={"If-Match": etag})
