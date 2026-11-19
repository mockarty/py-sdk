# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Curated Cloud webhook lifecycle API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class CloudWebhooksAPI(SyncAPIBase):
    def list(self, workspace_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/cloud/webhooks", params={"workspace_id": workspace_id}).json()
        return data.get("webhooks", []) if isinstance(data, dict) else []

    def create(self, workspace_id: str, name: str, url: str, events: list[str],
               idempotency_key: str | None = None) -> dict[str, Any]:
        return self._request("POST", "/api/v1/cloud/webhooks", params={"workspace_id": workspace_id},
                             json={"name": name, "url": url, "events": events},
                             headers={"Idempotency-Key": idempotency_key} if idempotency_key else None).json()

    def create_with_idempotency_key(self, workspace_id: str, name: str, url: str,
                                    events: list[str], idempotency_key: str) -> dict[str, Any]:
        """Create a webhook with a CALLER-SUPPLIED key.

        This exists as its own method so the three SDKs expose the same name for
        the same capability: the Go SDK has no optional parameters, so the
        key-carrying create is a separate method there, and the parity gate
        compares METHOD NAMES. The SDK never invents the key — reuse it, with the
        identical body, to recover an ambiguous response instead of creating a
        second webhook.
        """
        if not idempotency_key:
            raise ValueError("mockarty: idempotency_key is required")
        return self.create(workspace_id, name, url, events, idempotency_key)

    def deactivate(self, workspace_id: str, webhook_id: str) -> None:
        self._request("DELETE", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}",
                      params={"workspace_id": workspace_id})

    def test(self, workspace_id: str, webhook_id: str) -> None:
        self._request("POST", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}/test",
                      params={"workspace_id": workspace_id}, json={})

    def list_deliveries(self, workspace_id: str, webhook_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 500:
            limit = 100
        data = self._request("GET", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}/deliveries",
                             params={"workspace_id": workspace_id, "limit": limit}).json()
        return data.get("deliveries", []) if isinstance(data, dict) else []

    def rotate_secret(self, workspace_id: str, webhook_id: str, idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        return self._request("POST", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}/rotate-secret",
                             params={"workspace_id": workspace_id}, json={},
                             headers={"Idempotency-Key": idempotency_key}).json()


class AsyncCloudWebhooksAPI(AsyncAPIBase):
    async def list(self, workspace_id: str) -> list[dict[str, Any]]:
        data = (await self._request("GET", "/api/v1/cloud/webhooks", params={"workspace_id": workspace_id})).json()
        return data.get("webhooks", []) if isinstance(data, dict) else []

    async def create(self, workspace_id: str, name: str, url: str, events: list[str],
                     idempotency_key: str | None = None) -> dict[str, Any]:
        return (await self._request("POST", "/api/v1/cloud/webhooks", params={"workspace_id": workspace_id},
                                    json={"name": name, "url": url, "events": events},
                                    headers={"Idempotency-Key": idempotency_key} if idempotency_key else None)).json()

    async def create_with_idempotency_key(self, workspace_id: str, name: str, url: str,
                                          events: list[str], idempotency_key: str) -> dict[str, Any]:
        """Async twin of the key-carrying create; see the sync docstring."""
        if not idempotency_key:
            raise ValueError("mockarty: idempotency_key is required")
        return await self.create(workspace_id, name, url, events, idempotency_key)

    async def deactivate(self, workspace_id: str, webhook_id: str) -> None:
        await self._request("DELETE", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}",
                            params={"workspace_id": workspace_id})

    async def test(self, workspace_id: str, webhook_id: str) -> None:
        await self._request("POST", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}/test",
                            params={"workspace_id": workspace_id}, json={})

    async def list_deliveries(self, workspace_id: str, webhook_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 500:
            limit = 100
        data = (await self._request("GET", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}/deliveries",
                                    params={"workspace_id": workspace_id, "limit": limit})).json()
        return data.get("deliveries", []) if isinstance(data, dict) else []

    async def rotate_secret(self, workspace_id: str, webhook_id: str, idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        return (await self._request("POST", f"/api/v1/cloud/webhooks/{quote(webhook_id, safe='')}/rotate-secret",
                                    params={"workspace_id": workspace_id}, json={},
                                    headers={"Idempotency-Key": idempotency_key})).json()
