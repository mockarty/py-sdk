# Copyright (c) 2026 Mockarty. All rights reserved.

"""Stats API resource for system statistics and status."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class StatsAPI(SyncAPIBase):
    """Synchronous Stats API resource."""

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        resp = self._request("GET", "/api/v1/stats")
        return resp.json()

    def get_counts(self) -> dict[str, Any]:
        """Get resource counts (mocks, namespaces, etc.)."""
        resp = self._request("GET", "/api/v1/counts")
        return resp.json()

    def get_status(self) -> dict[str, Any]:
        """Get system status information."""
        resp = self._request("GET", "/api/v1/status")
        return resp.json()

    def get_features(self) -> dict[str, Any]:
        """Get available feature flags."""
        resp = self._request("GET", "/api/v1/features")
        return resp.json()


class AsyncStatsAPI(AsyncAPIBase):
    """Asynchronous Stats API resource."""

    async def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        resp = await self._request("GET", "/api/v1/stats")
        return resp.json()

    async def get_counts(self) -> dict[str, Any]:
        """Get resource counts (mocks, namespaces, etc.)."""
        resp = await self._request("GET", "/api/v1/counts")
        return resp.json()

    async def get_status(self) -> dict[str, Any]:
        """Get system status information."""
        resp = await self._request("GET", "/api/v1/status")
        return resp.json()

    async def get_features(self) -> dict[str, Any]:
        """Get available feature flags."""
        resp = await self._request("GET", "/api/v1/features")
        return resp.json()
