# Copyright (c) 2026 Mockarty. All rights reserved.

"""Namespace settings API resource for per-namespace user, cleanup, and webhook management."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class NamespaceSettingsAPI(SyncAPIBase):
    """Synchronous Namespace Settings API resource."""

    # ── Users ──────────────────────────────────────────────────────────

    def list_users(self, namespace: str) -> list[dict[str, Any]]:
        """List users in a namespace."""
        resp = self._request("GET", f"/api/v1/namespaces/{namespace}/settings/users")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("users") or []
        return []

    def add_user(self, namespace: str, user_id: str, role: str) -> dict[str, Any]:
        """Add a user to a namespace with a given role."""
        resp = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/settings/users",
            json={"userId": user_id, "role": role},
        )
        return resp.json()

    def remove_user(self, namespace: str, user_id: str) -> None:
        """Remove a user from a namespace."""
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/settings/users/{user_id}",
        )

    def update_user_role(
        self, namespace: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """Update a user's role in a namespace."""
        resp = self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/settings/users/{user_id}",
            json={"role": role},
        )
        return resp.json()

    # ── Cleanup ────────────────────────────────────────────────────────

    def get_cleanup_policy(self, namespace: str) -> dict[str, Any]:
        """Get the cleanup policy for a namespace."""
        resp = self._request("GET", f"/api/v1/namespaces/{namespace}/settings/cleanup")
        return resp.json()

    def update_cleanup_policy(
        self, namespace: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the cleanup policy for a namespace."""
        resp = self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/settings/cleanup",
            json=policy,
        )
        return resp.json()

    # ── Webhooks ───────────────────────────────────────────────────────

    def list_webhooks(self, namespace: str) -> list[dict[str, Any]]:
        """List webhooks configured for a namespace."""
        resp = self._request("GET", f"/api/v1/namespaces/{namespace}/settings/webhooks")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("webhooks") or []
        return []

    def create_webhook(self, namespace: str, webhook: dict[str, Any]) -> dict[str, Any]:
        """Create a webhook for a namespace."""
        resp = self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/settings/webhooks",
            json=webhook,
        )
        return resp.json()

    def delete_webhook(self, namespace: str, webhook_id: str) -> None:
        """Delete a webhook from a namespace."""
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/settings/webhooks/{webhook_id}",
        )


class AsyncNamespaceSettingsAPI(AsyncAPIBase):
    """Asynchronous Namespace Settings API resource."""

    # ── Users ──────────────────────────────────────────────────────────

    async def list_users(self, namespace: str) -> list[dict[str, Any]]:
        """List users in a namespace."""
        resp = await self._request(
            "GET", f"/api/v1/namespaces/{namespace}/settings/users"
        )
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("users") or []
        return []

    async def add_user(self, namespace: str, user_id: str, role: str) -> dict[str, Any]:
        """Add a user to a namespace with a given role."""
        resp = await self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/settings/users",
            json={"userId": user_id, "role": role},
        )
        return resp.json()

    async def remove_user(self, namespace: str, user_id: str) -> None:
        """Remove a user from a namespace."""
        await self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/settings/users/{user_id}",
        )

    async def update_user_role(
        self, namespace: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """Update a user's role in a namespace."""
        resp = await self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/settings/users/{user_id}",
            json={"role": role},
        )
        return resp.json()

    # ── Cleanup ────────────────────────────────────────────────────────

    async def get_cleanup_policy(self, namespace: str) -> dict[str, Any]:
        """Get the cleanup policy for a namespace."""
        resp = await self._request(
            "GET", f"/api/v1/namespaces/{namespace}/settings/cleanup"
        )
        return resp.json()

    async def update_cleanup_policy(
        self, namespace: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the cleanup policy for a namespace."""
        resp = await self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/settings/cleanup",
            json=policy,
        )
        return resp.json()

    # ── Webhooks ───────────────────────────────────────────────────────

    async def list_webhooks(self, namespace: str) -> list[dict[str, Any]]:
        """List webhooks configured for a namespace."""
        resp = await self._request(
            "GET", f"/api/v1/namespaces/{namespace}/settings/webhooks"
        )
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("webhooks") or []
        return []

    async def create_webhook(
        self, namespace: str, webhook: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a webhook for a namespace."""
        resp = await self._request(
            "POST",
            f"/api/v1/namespaces/{namespace}/settings/webhooks",
            json=webhook,
        )
        return resp.json()

    async def delete_webhook(self, namespace: str, webhook_id: str) -> None:
        """Delete a webhook from a namespace."""
        await self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/settings/webhooks/{webhook_id}",
        )
