# Copyright (c) 2026 Mockarty. All rights reserved.

"""Base classes for sync and async API resources."""

from __future__ import annotations

from typing import Any

import httpx

from mockarty._base_client import raise_for_status, serialize_body, wrap_transport_error


class SyncAPIBase:
    """Base class for synchronous API resource groups."""

    def __init__(self, client: httpx.Client, namespace: str) -> None:
        self._client = client
        self._namespace = namespace

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request and raise on errors."""
        kwargs: dict[str, Any] = {"params": params}
        if json is not None:
            kwargs["json"] = serialize_body(json)
        if content is not None:
            kwargs["content"] = content
        if headers:
            kwargs["headers"] = headers

        try:
            response = self._client.request(method, path, **kwargs)
        except Exception as exc:
            wrap_transport_error(exc)

        raise_for_status(response)
        return response


class AsyncAPIBase:
    """Base class for asynchronous API resource groups."""

    def __init__(self, client: httpx.AsyncClient, namespace: str) -> None:
        self._client = client
        self._namespace = namespace

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        """Execute an async HTTP request and raise on errors."""
        kwargs: dict[str, Any] = {"params": params}
        if json is not None:
            kwargs["json"] = serialize_body(json)
        if content is not None:
            kwargs["content"] = content
        if headers:
            kwargs["headers"] = headers

        try:
            response = await self._client.request(method, path, **kwargs)
        except Exception as exc:
            wrap_transport_error(exc)

        raise_for_status(response)
        return response
