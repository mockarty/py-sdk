# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Operator-only Mockarty Cloud cabinet OAuth provider registry."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _payload(client_id: str, client_secret_ref: str, expected_revision: int, enabled: bool) -> dict[str, Any]:
    if not client_id or expected_revision < 0:
        raise ValueError("client_id and a non-negative expected_revision are required")
    return {"client_id": client_id, "client_secret_ref": client_secret_ref,
            "expected_revision": expected_revision, "enabled": enabled}


class CloudOAuthProvidersAPI(SyncAPIBase):
    def list(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/cloud/operator/oauth/providers").json()
        return data.get("providers", []) if isinstance(data, dict) else []

    def update(self, provider: str, *, client_id: str, client_secret_ref: str = "",
               expected_revision: int = 0, enabled: bool = False,
               idempotency_key: str) -> dict[str, Any]:
        if not provider or not idempotency_key:
            raise ValueError("provider and idempotency_key are required")
        return self._request("PUT", f"/api/v1/cloud/operator/oauth/providers/{quote(provider, safe='')}",
                             json=_payload(client_id, client_secret_ref, expected_revision, enabled),
                             headers={"Idempotency-Key": idempotency_key}).json()


class AsyncCloudOAuthProvidersAPI(AsyncAPIBase):
    async def list(self) -> list[dict[str, Any]]:
        data = (await self._request("GET", "/api/v1/cloud/operator/oauth/providers")).json()
        return data.get("providers", []) if isinstance(data, dict) else []

    async def update(self, provider: str, *, client_id: str, client_secret_ref: str = "",
                     expected_revision: int = 0, enabled: bool = False,
                     idempotency_key: str) -> dict[str, Any]:
        if not provider or not idempotency_key:
            raise ValueError("provider and idempotency_key are required")
        return (await self._request("PUT", f"/api/v1/cloud/operator/oauth/providers/{quote(provider, safe='')}",
                                    json=_payload(client_id, client_secret_ref, expected_revision, enabled),
                                    headers={"Idempotency-Key": idempotency_key})).json()
