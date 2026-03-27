# Copyright (c) 2026 Mockarty. All rights reserved.

"""Proxy API resource for forwarding requests through Mockarty."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class ProxyAPI(SyncAPIBase):
    """Synchronous Proxy API resource."""

    def http(self, request: dict[str, Any]) -> dict[str, Any]:
        """Proxy an HTTP request through Mockarty."""
        resp = self._request("POST", "/api/v1/proxy/http", json=request)
        return resp.json()

    def soap(self, request: dict[str, Any]) -> dict[str, Any]:
        """Proxy a SOAP request through Mockarty."""
        resp = self._request("POST", "/api/v1/proxy/soap", json=request)
        return resp.json()

    def grpc(self, request: dict[str, Any]) -> dict[str, Any]:
        """Proxy a gRPC request through Mockarty."""
        resp = self._request("POST", "/api/v1/proxy/grpc", json=request)
        return resp.json()


class AsyncProxyAPI(AsyncAPIBase):
    """Asynchronous Proxy API resource."""

    async def http(self, request: dict[str, Any]) -> dict[str, Any]:
        """Proxy an HTTP request through Mockarty."""
        resp = await self._request("POST", "/api/v1/proxy/http", json=request)
        return resp.json()

    async def soap(self, request: dict[str, Any]) -> dict[str, Any]:
        """Proxy a SOAP request through Mockarty."""
        resp = await self._request("POST", "/api/v1/proxy/soap", json=request)
        return resp.json()

    async def grpc(self, request: dict[str, Any]) -> dict[str, Any]:
        """Proxy a gRPC request through Mockarty."""
        resp = await self._request("POST", "/api/v1/proxy/grpc", json=request)
        return resp.json()
