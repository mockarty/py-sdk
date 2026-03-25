# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Health check API resource."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.common import HealthResponse


class HealthAPI(SyncAPIBase):
    """Synchronous Health API resource."""

    def check(self) -> HealthResponse:
        """Perform a comprehensive health check."""
        resp = self._request("GET", "/health")
        return HealthResponse.model_validate(resp.json())

    def live(self) -> bool:
        """Check if the server is alive (liveness probe).

        Returns True if the server responds, False otherwise.
        """
        try:
            resp = self._request("GET", "/health/live")
            return resp.is_success
        except Exception:
            return False

    def ready(self) -> bool:
        """Check if the server is ready to accept traffic (readiness probe).

        Returns True if the server is ready, False otherwise.
        """
        try:
            resp = self._request("GET", "/health/ready")
            return resp.is_success
        except Exception:
            return False


class AsyncHealthAPI(AsyncAPIBase):
    """Asynchronous Health API resource."""

    async def check(self) -> HealthResponse:
        """Perform a comprehensive health check."""
        resp = await self._request("GET", "/health")
        return HealthResponse.model_validate(resp.json())

    async def live(self) -> bool:
        """Check if the server is alive (liveness probe)."""
        try:
            resp = await self._request("GET", "/health/live")
            return resp.is_success
        except Exception:
            return False

    async def ready(self) -> bool:
        """Check if the server is ready to accept traffic (readiness probe)."""
        try:
            resp = await self._request("GET", "/health/ready")
            return resp.is_success
        except Exception:
            return False
