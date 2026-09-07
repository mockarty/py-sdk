# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Namespace-scoped immutable Connection Authority lifecycle."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _base(namespace: str) -> str:
    if not namespace or namespace == "*":
        raise ValueError("a concrete namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/connections"


def _path(namespace: str, connection_id: str) -> str:
    if not connection_id:
        raise ValueError("connection_id is required")
    return f"{_base(namespace)}/{quote(connection_id, safe='')}"


def _body(descriptor: dict[str, Any], *, include_id: bool) -> dict[str, Any]:
    body = dict(descriptor)
    body.pop("namespace", None)
    body.pop("revision", None)
    if not include_id:
        body.pop("id", None)
    return body


class ConnectionAuthorityAPI(SyncAPIBase):
    """Create, rotate, inspect and revoke immutable connection revisions."""

    def create(self, descriptor: dict[str, Any], *, namespace: str | None = None) -> dict[str, Any]:
        ns = namespace or str(descriptor.get("namespace") or self._namespace)
        return dict(self._request("POST", _base(ns), json=_body(descriptor, include_id=True)).json() or {})

    def get_current(self, connection_id: str, *, namespace: str | None = None) -> dict[str, Any]:
        return dict(self._request("GET", _path(namespace or self._namespace, connection_id)).json() or {})

    def advance(self, connection_id: str, descriptor: dict[str, Any], expected_revision: int,
                *, namespace: str | None = None) -> dict[str, Any]:
        if expected_revision <= 0:
            raise ValueError("expected_revision must be positive")
        ns = namespace or str(descriptor.get("namespace") or self._namespace)
        return dict(self._request("PUT", _path(ns, connection_id),
                                  params={"expectedRevision": expected_revision},
                                  json=_body(descriptor, include_id=False)).json() or {})

    def revoke(self, connection_id: str, revision: int, *, namespace: str | None = None) -> None:
        if revision <= 0:
            raise ValueError("revision must be positive")
        self._request("DELETE", _path(namespace or self._namespace, connection_id), params={"revision": revision})


class AsyncConnectionAuthorityAPI(AsyncAPIBase):
    """Async parity for :class:`ConnectionAuthorityAPI`."""

    async def create(self, descriptor: dict[str, Any], *, namespace: str | None = None) -> dict[str, Any]:
        ns = namespace or str(descriptor.get("namespace") or self._namespace)
        return dict((await self._request("POST", _base(ns), json=_body(descriptor, include_id=True))).json() or {})

    async def get_current(self, connection_id: str, *, namespace: str | None = None) -> dict[str, Any]:
        return dict((await self._request("GET", _path(namespace or self._namespace, connection_id))).json() or {})

    async def advance(self, connection_id: str, descriptor: dict[str, Any], expected_revision: int,
                      *, namespace: str | None = None) -> dict[str, Any]:
        if expected_revision <= 0:
            raise ValueError("expected_revision must be positive")
        ns = namespace or str(descriptor.get("namespace") or self._namespace)
        response = await self._request("PUT", _path(ns, connection_id),
                                       params={"expectedRevision": expected_revision},
                                       json=_body(descriptor, include_id=False))
        return dict(response.json() or {})

    async def revoke(self, connection_id: str, revision: int, *, namespace: str | None = None) -> None:
        if revision <= 0:
            raise ValueError("revision must be positive")
        await self._request("DELETE", _path(namespace or self._namespace, connection_id), params={"revision": revision})
