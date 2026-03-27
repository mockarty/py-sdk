# Copyright (c) 2026 Mockarty. All rights reserved.

"""Undefined requests API resource for unmatched traffic tracking."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.mock import Mock
from mockarty.models.undefined import UndefinedRequest


class UndefinedAPI(SyncAPIBase):
    """Synchronous Undefined Requests API resource."""

    def list(self) -> list[UndefinedRequest]:
        """List all undefined (unmatched) requests."""
        resp = self._request("GET", "/api/v1/undefined-requests")
        data = resp.json()
        if isinstance(data, list):
            return [UndefinedRequest.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("requests") or []
            return [UndefinedRequest.model_validate(r) for r in items]
        return []

    def ignore(self, request_id: str) -> None:
        """Mark an undefined request as ignored."""
        self._request("PATCH", f"/api/v1/undefined-requests/{request_id}/ignore")

    def delete(self, ids: list[str]) -> None:
        """Delete undefined requests by IDs."""
        self._request("DELETE", "/api/v1/undefined-requests", json={"ids": ids})

    def clear_all(self) -> None:
        """Delete all undefined requests."""
        self._request("DELETE", "/api/v1/undefined-requests/all")

    def create_mock(self, request_id: str) -> Mock:
        """Create a mock from an undefined request."""
        resp = self._request(
            "POST", f"/api/v1/undefined-requests/{request_id}/create-mock"
        )
        return Mock.model_validate(resp.json())


class AsyncUndefinedAPI(AsyncAPIBase):
    """Asynchronous Undefined Requests API resource."""

    async def list(self) -> list[UndefinedRequest]:
        """List all undefined (unmatched) requests."""
        resp = await self._request("GET", "/api/v1/undefined-requests")
        data = resp.json()
        if isinstance(data, list):
            return [UndefinedRequest.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("requests") or []
            return [UndefinedRequest.model_validate(r) for r in items]
        return []

    async def ignore(self, request_id: str) -> None:
        """Mark an undefined request as ignored."""
        await self._request("PATCH", f"/api/v1/undefined-requests/{request_id}/ignore")

    async def delete(self, ids: list[str]) -> None:
        """Delete undefined requests by IDs."""
        await self._request("DELETE", "/api/v1/undefined-requests", json={"ids": ids})

    async def clear_all(self) -> None:
        """Delete all undefined requests."""
        await self._request("DELETE", "/api/v1/undefined-requests/all")

    async def create_mock(self, request_id: str) -> Mock:
        """Create a mock from an undefined request."""
        resp = await self._request(
            "POST", f"/api/v1/undefined-requests/{request_id}/create-mock"
        )
        return Mock.model_validate(resp.json())
