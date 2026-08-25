# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Namespace settings API resource for per-namespace user, cleanup, and webhook management."""

from __future__ import annotations

import uuid
from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class NamespaceSettingsAPI(SyncAPIBase):
    """Synchronous Namespace Settings API resource."""

    def get_autonomy_settings(self) -> dict[str, Any]:
        """Return autonomous-mission defaults for the configured namespace."""
        return self._request("GET", "/api/v1/autotester/settings").json()

    def save_autonomy_settings(
        self, settings: dict[str, Any], *, request_id: str | None = None
    ) -> dict[str, Any]:
        """Update defaults; reuse ``request_id`` after an ambiguous timeout."""
        loaded = self._request("GET", "/api/v1/autotester/settings")
        merged = loaded.json()
        merged.update(settings)
        etag = loaded.headers.get("ETag") or merged.get("etag", "")
        return self._request(
            "PUT", "/api/v1/autotester/settings", json=merged,
            headers={"Idempotency-Key": request_id or str(uuid.uuid4()), **({"If-Match": etag} if etag else {})},
        ).json()

    def clear_autonomy_retention(
        self, *, clear_event: bool = False, clear_payload: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Clear selected retention overrides so they inherit instance policy."""
        if not clear_event and not clear_payload:
            raise ValueError("at least one retention override must be selected")
        update: dict[str, Any] = {}
        if clear_event:
            update["journalEventRetentionDays"] = None
        if clear_payload:
            update["journalPayloadRetentionDays"] = None
        return self.save_autonomy_settings(update, request_id=request_id)

    def clear_autonomy_run_window(self, *, request_id: str | None = None) -> dict[str, Any]:
        """Clear the namespace wall override and inherit the effective policy."""
        return self.save_autonomy_settings({"runWindowMinutes": None}, request_id=request_id)

    # ── Users ──────────────────────────────────────────────────────────

    def list_users(self, namespace: str) -> list[dict[str, Any]]:
        """List users in a namespace."""
        resp = self._request("GET", f"/api/v1/namespaces/{namespace}/users")
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
            f"/api/v1/namespaces/{namespace}/users",
            json={"userId": user_id, "role": role},
        )
        return resp.json()

    def remove_user(self, namespace: str, user_id: str) -> None:
        """Remove a user from a namespace."""
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/users/{user_id}",
        )

    def update_user_role(
        self, namespace: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """Update a user's role in a namespace."""
        resp = self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/users/{user_id}/role",
            json={"role": role},
        )
        return resp.json()

    # ── Cleanup ────────────────────────────────────────────────────────

    def get_cleanup_policy(self, namespace: str) -> dict[str, Any]:
        """Get the cleanup policy for a namespace."""
        resp = self._request("GET", f"/api/v1/namespaces/{namespace}/cleanup-policy")
        return resp.json()

    def update_cleanup_policy(
        self, namespace: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the cleanup policy for a namespace."""
        resp = self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/cleanup-policy",
            json=policy,
        )
        return resp.json()

    # ── Webhooks ───────────────────────────────────────────────────────

    def list_webhooks(self, namespace: str) -> list[dict[str, Any]]:
        """List webhooks configured for a namespace."""
        resp = self._request("GET", f"/api/v1/namespaces/{namespace}/webhooks")
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
            f"/api/v1/namespaces/{namespace}/webhooks",
            json=webhook,
        )
        return resp.json()

    def delete_webhook(self, namespace: str, webhook_id: str) -> None:
        """Delete a webhook from a namespace."""
        self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/webhooks/{webhook_id}",
        )


class AsyncNamespaceSettingsAPI(AsyncAPIBase):
    """Asynchronous Namespace Settings API resource."""

    async def get_autonomy_settings(self) -> dict[str, Any]:
        """Return autonomous-mission defaults for the configured namespace."""
        return (await self._request("GET", "/api/v1/autotester/settings")).json()

    async def save_autonomy_settings(
        self, settings: dict[str, Any], *, request_id: str | None = None
    ) -> dict[str, Any]:
        """Update autonomy defaults without clearing omitted retention fields."""
        loaded = await self._request("GET", "/api/v1/autotester/settings")
        merged = loaded.json()
        merged.update(settings)
        etag = loaded.headers.get("ETag") or merged.get("etag", "")
        return (
            await self._request(
                "PUT", "/api/v1/autotester/settings", json=merged,
                headers={"Idempotency-Key": request_id or str(uuid.uuid4()), **({"If-Match": etag} if etag else {})},
            )
        ).json()

    async def clear_autonomy_retention(
        self, *, clear_event: bool = False, clear_payload: bool = False,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Clear selected retention overrides so they inherit instance policy."""
        if not clear_event and not clear_payload:
            raise ValueError("at least one retention override must be selected")
        update: dict[str, Any] = {}
        if clear_event:
            update["journalEventRetentionDays"] = None
        if clear_payload:
            update["journalPayloadRetentionDays"] = None
        return await self.save_autonomy_settings(update, request_id=request_id)

    async def clear_autonomy_run_window(self, *, request_id: str | None = None) -> dict[str, Any]:
        """Clear the namespace wall override and inherit the effective policy."""
        return await self.save_autonomy_settings({"runWindowMinutes": None}, request_id=request_id)

    # ── Users ──────────────────────────────────────────────────────────

    async def list_users(self, namespace: str) -> list[dict[str, Any]]:
        """List users in a namespace."""
        resp = await self._request("GET", f"/api/v1/namespaces/{namespace}/users")
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
            f"/api/v1/namespaces/{namespace}/users",
            json={"userId": user_id, "role": role},
        )
        return resp.json()

    async def remove_user(self, namespace: str, user_id: str) -> None:
        """Remove a user from a namespace."""
        await self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/users/{user_id}",
        )

    async def update_user_role(
        self, namespace: str, user_id: str, role: str
    ) -> dict[str, Any]:
        """Update a user's role in a namespace."""
        resp = await self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/users/{user_id}/role",
            json={"role": role},
        )
        return resp.json()

    # ── Cleanup ────────────────────────────────────────────────────────

    async def get_cleanup_policy(self, namespace: str) -> dict[str, Any]:
        """Get the cleanup policy for a namespace."""
        resp = await self._request(
            "GET", f"/api/v1/namespaces/{namespace}/cleanup-policy"
        )
        return resp.json()

    async def update_cleanup_policy(
        self, namespace: str, policy: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the cleanup policy for a namespace."""
        resp = await self._request(
            "PUT",
            f"/api/v1/namespaces/{namespace}/cleanup-policy",
            json=policy,
        )
        return resp.json()

    # ── Webhooks ───────────────────────────────────────────────────────

    async def list_webhooks(self, namespace: str) -> list[dict[str, Any]]:
        """List webhooks configured for a namespace."""
        resp = await self._request("GET", f"/api/v1/namespaces/{namespace}/webhooks")
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
            f"/api/v1/namespaces/{namespace}/webhooks",
            json=webhook,
        )
        return resp.json()

    async def delete_webhook(self, namespace: str, webhook_id: str) -> None:
        """Delete a webhook from a namespace."""
        await self._request(
            "DELETE",
            f"/api/v1/namespaces/{namespace}/webhooks/{webhook_id}",
        )
