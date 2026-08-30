# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Operator-only Mockarty Cloud cabinet OAuth provider registry."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _payload(client_id: str, client_secret: str, client_secret_ref: str,
             expected_revision: int, enabled: bool, clear_secret: bool) -> dict[str, Any]:
    if not client_id or expected_revision < 1:
        raise ValueError("client_id and a positive expected_revision are required")
    if client_secret and client_secret_ref:
        raise ValueError("client_secret and client_secret_ref are mutually exclusive")
    if client_secret_ref:
        if not client_secret_ref.startswith("env://") or len(client_secret_ref) == len("env://"):
            raise ValueError("client_secret_ref must use env://NAME")
        client_secret = os.environ.get(client_secret_ref[len("env://"):], "")
        if not client_secret:
            raise ValueError("referenced client secret environment variable is empty or unset")
    if clear_secret and client_secret:
        raise ValueError("client_secret and clear_secret are mutually exclusive")
    return {"client_id": client_id, "client_secret": client_secret,
            "expected_revision": expected_revision, "enabled": enabled,
            "clear_secret": clear_secret}


class CloudOAuthProvidersAPI(SyncAPIBase):
    def list(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/cloud/operator/oauth/providers").json()
        return data.get("providers", []) if isinstance(data, dict) else []

    def update(self, provider: str, *, client_id: str, client_secret: str = "",
               client_secret_ref: str = "", expected_revision: int = 0,
               enabled: bool = False, clear_secret: bool = False,
               idempotency_key: str) -> dict[str, Any]:
        if not provider or not idempotency_key:
            raise ValueError("provider and idempotency_key are required")
        return self._request("PUT", f"/api/v1/cloud/operator/oauth/providers/{quote(provider, safe='')}",
                             json=_payload(client_id, client_secret, client_secret_ref,
                                           expected_revision, enabled, clear_secret),
                             headers={"Idempotency-Key": idempotency_key}).json()


class AsyncCloudOAuthProvidersAPI(AsyncAPIBase):
    async def list(self) -> list[dict[str, Any]]:
        data = (await self._request("GET", "/api/v1/cloud/operator/oauth/providers")).json()
        return data.get("providers", []) if isinstance(data, dict) else []

    async def update(self, provider: str, *, client_id: str, client_secret: str = "",
                     client_secret_ref: str = "", expected_revision: int = 0,
                     enabled: bool = False, clear_secret: bool = False,
                     idempotency_key: str) -> dict[str, Any]:
        if not provider or not idempotency_key:
            raise ValueError("provider and idempotency_key are required")
        return (await self._request("PUT", f"/api/v1/cloud/operator/oauth/providers/{quote(provider, safe='')}",
                                    json=_payload(client_id, client_secret, client_secret_ref,
                                                  expected_revision, enabled, clear_secret),
                                    headers={"Idempotency-Key": idempotency_key})).json()
