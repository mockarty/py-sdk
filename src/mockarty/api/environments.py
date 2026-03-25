# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Environments API resource for API Tester environment management."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class EnvironmentAPI(SyncAPIBase):
    """Synchronous Environment API resource."""

    def list(self) -> list[dict[str, Any]]:
        """List all environments."""
        resp = self._request("GET", "/api/v1/api-tester/environments")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("environments") or []
        return []

    def get_active(self) -> dict[str, Any]:
        """Get the currently active environment."""
        resp = self._request("GET", "/api/v1/api-tester/environments/active")
        return resp.json()

    def get(self, env_id: str) -> dict[str, Any]:
        """Get an environment by ID."""
        resp = self._request(
            "GET", f"/api/v1/api-tester/environments/{env_id}"
        )
        return resp.json()

    def create(self, env: dict[str, Any]) -> dict[str, Any]:
        """Create a new environment."""
        resp = self._request(
            "POST", "/api/v1/api-tester/environments", json=env
        )
        return resp.json()

    def update(self, env_id: str, env: dict[str, Any]) -> dict[str, Any]:
        """Update an existing environment."""
        resp = self._request(
            "PUT", f"/api/v1/api-tester/environments/{env_id}", json=env
        )
        return resp.json()

    def delete(self, env_id: str) -> None:
        """Delete an environment."""
        self._request(
            "DELETE", f"/api/v1/api-tester/environments/{env_id}"
        )

    def activate(self, env_id: str) -> None:
        """Activate an environment."""
        self._request(
            "POST", f"/api/v1/api-tester/environments/{env_id}/activate"
        )


class AsyncEnvironmentAPI(AsyncAPIBase):
    """Asynchronous Environment API resource."""

    async def list(self) -> list[dict[str, Any]]:
        """List all environments."""
        resp = await self._request("GET", "/api/v1/api-tester/environments")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("environments") or []
        return []

    async def get_active(self) -> dict[str, Any]:
        """Get the currently active environment."""
        resp = await self._request(
            "GET", "/api/v1/api-tester/environments/active"
        )
        return resp.json()

    async def get(self, env_id: str) -> dict[str, Any]:
        """Get an environment by ID."""
        resp = await self._request(
            "GET", f"/api/v1/api-tester/environments/{env_id}"
        )
        return resp.json()

    async def create(self, env: dict[str, Any]) -> dict[str, Any]:
        """Create a new environment."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/environments", json=env
        )
        return resp.json()

    async def update(
        self, env_id: str, env: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing environment."""
        resp = await self._request(
            "PUT", f"/api/v1/api-tester/environments/{env_id}", json=env
        )
        return resp.json()

    async def delete(self, env_id: str) -> None:
        """Delete an environment."""
        await self._request(
            "DELETE", f"/api/v1/api-tester/environments/{env_id}"
        )

    async def activate(self, env_id: str) -> None:
        """Activate an environment."""
        await self._request(
            "POST", f"/api/v1/api-tester/environments/{env_id}/activate"
        )
