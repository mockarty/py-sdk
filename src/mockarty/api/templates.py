# Copyright (c) 2026 Mockarty. All rights reserved.

"""Template API resource for managing payload templates.

Templates are file-backed payload bodies stored per-namespace. The server
treats them as opaque byte blobs keyed by file name:

  GET    /api/v1/templates                 — list file names
  GET    /api/v1/templates/:fileName       — download raw bytes
  POST   /api/v1/templates/:fileName       — upload raw bytes (body = content)
  DELETE /api/v1/templates/:fileName       — remove
"""

from __future__ import annotations

from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _encode_name(name: str) -> str:
    return quote(name, safe="")


class TemplateAPI(SyncAPIBase):
    """Synchronous Template API resource."""

    def list(
        self,
        namespace: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[str]:
        """List payload template file names in a namespace."""
        params: dict[str, str] = {}
        if namespace is not None:
            params["namespace"] = namespace
        if search is not None:
            params["search"] = search
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        resp = self._request("GET", "/api/v1/templates", params=params or None)
        data = resp.json()
        if isinstance(data, dict):
            items = data.get("templates") or data.get("items") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        return [str(t) for t in items if t]

    def get(self, name: str, namespace: str | None = None) -> bytes:
        """Download the raw bytes of a template file."""
        params = {"namespace": namespace} if namespace is not None else None
        resp = self._request(
            "GET", f"/api/v1/templates/{_encode_name(name)}", params=params
        )
        return resp.content

    def upload(
        self, name: str, content: bytes | str, namespace: str | None = None
    ) -> None:
        """Upload (or replace) a template file with raw body content."""
        body = content.encode("utf-8") if isinstance(content, str) else content
        params = {"namespace": namespace} if namespace is not None else None
        self._request(
            "POST",
            f"/api/v1/templates/{_encode_name(name)}",
            params=params,
            content=body,
        )

    def delete(self, name: str, namespace: str | None = None) -> None:
        """Delete a template file."""
        params = {"namespace": namespace} if namespace is not None else None
        self._request(
            "DELETE", f"/api/v1/templates/{_encode_name(name)}", params=params
        )


class AsyncTemplateAPI(AsyncAPIBase):
    """Asynchronous Template API resource."""

    async def list(
        self,
        namespace: str | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[str]:
        """List payload template file names in a namespace."""
        params: dict[str, str] = {}
        if namespace is not None:
            params["namespace"] = namespace
        if search is not None:
            params["search"] = search
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        resp = await self._request("GET", "/api/v1/templates", params=params or None)
        data = resp.json()
        if isinstance(data, dict):
            items = data.get("templates") or data.get("items") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        return [str(t) for t in items if t]

    async def get(self, name: str, namespace: str | None = None) -> bytes:
        """Download the raw bytes of a template file."""
        params = {"namespace": namespace} if namespace is not None else None
        resp = await self._request(
            "GET", f"/api/v1/templates/{_encode_name(name)}", params=params
        )
        return resp.content

    async def upload(
        self, name: str, content: bytes | str, namespace: str | None = None
    ) -> None:
        """Upload (or replace) a template file with raw body content."""
        body = content.encode("utf-8") if isinstance(content, str) else content
        params = {"namespace": namespace} if namespace is not None else None
        await self._request(
            "POST",
            f"/api/v1/templates/{_encode_name(name)}",
            params=params,
            content=body,
        )

    async def delete(self, name: str, namespace: str | None = None) -> None:
        """Delete a template file."""
        params = {"namespace": namespace} if namespace is not None else None
        await self._request(
            "DELETE", f"/api/v1/templates/{_encode_name(name)}", params=params
        )
