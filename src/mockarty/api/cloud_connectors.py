# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Operator-only Cloud platform connector lifecycle."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _connector_path(kind: str, provider: str, slot: str = "") -> str:
    key = (kind.strip().lower(), provider.strip().lower(), slot.strip().lower())
    valid = key in {
        ("smtp", "smtp", ""),
        ("oauth", "yandex", ""),
        ("oauth", "vk", ""),
        ("oauth", "github", ""),
        ("payment", "yookassa", "main"),
        ("payment", "stripe", "main"),
    }
    if not valid:
        raise ValueError("unsupported Cloud connector key")
    parts = [quote(value, safe="") for value in key if value]
    return "/api/v1/cloud/operator/connectors/" + "/".join(parts)


def _update_payload(*, config: dict[str, str], secrets: dict[str, str] | None,
                    clear_secrets: list[str] | None, expected_revision: int,
                    enabled: bool, default: bool) -> dict[str, Any]:
    if config is None or expected_revision < 1:
        raise ValueError("config and a positive expected_revision are required")
    return {"config": config, "secrets": secrets or {}, "clear_secrets": clear_secrets or [],
            "expected_revision": expected_revision, "enabled": enabled, "default": default}


class CloudConnectorsAPI(SyncAPIBase):
    def list(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/v1/cloud/operator/connectors").json()
        return data.get("connectors", []) if isinstance(data, dict) else []

    def update(self, kind: str, provider: str, *, slot: str = "", config: dict[str, str],
               secrets: dict[str, str] | None = None, clear_secrets: list[str] | None = None,
               expected_revision: int, enabled: bool = False, default: bool = False,
               idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        return self._request("PUT", _connector_path(kind, provider, slot),
                             json=_update_payload(config=config, secrets=secrets,
                                                  clear_secrets=clear_secrets,
                                                  expected_revision=expected_revision,
                                                  enabled=enabled, default=default),
                             headers={"Idempotency-Key": idempotency_key}).json()

    def test(self, kind: str, provider: str, *, slot: str = "", idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        return self._request("POST", _connector_path(kind, provider, slot) + "/test", json={},
                             headers={"Idempotency-Key": idempotency_key}).json()

    def revoke(self, version_id: str, *, idempotency_key: str) -> None:
        if not version_id or not idempotency_key:
            raise ValueError("version_id and idempotency_key are required")
        self._request("POST", "/api/v1/cloud/operator/connector-versions/" +
                      quote(version_id, safe="") + "/revoke", json={},
                      headers={"Idempotency-Key": idempotency_key})


class AsyncCloudConnectorsAPI(AsyncAPIBase):
    async def list(self) -> list[dict[str, Any]]:
        data = (await self._request("GET", "/api/v1/cloud/operator/connectors")).json()
        return data.get("connectors", []) if isinstance(data, dict) else []

    async def update(self, kind: str, provider: str, *, slot: str = "", config: dict[str, str],
                     secrets: dict[str, str] | None = None, clear_secrets: list[str] | None = None,
                     expected_revision: int, enabled: bool = False, default: bool = False,
                     idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        return (await self._request("PUT", _connector_path(kind, provider, slot),
                                    json=_update_payload(config=config, secrets=secrets,
                                                         clear_secrets=clear_secrets,
                                                         expected_revision=expected_revision,
                                                         enabled=enabled, default=default),
                                    headers={"Idempotency-Key": idempotency_key})).json()

    async def test(self, kind: str, provider: str, *, slot: str = "", idempotency_key: str) -> dict[str, Any]:
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        return (await self._request("POST", _connector_path(kind, provider, slot) + "/test", json={},
                                    headers={"Idempotency-Key": idempotency_key})).json()

    async def revoke(self, version_id: str, *, idempotency_key: str) -> None:
        if not version_id or not idempotency_key:
            raise ValueError("version_id and idempotency_key are required")
        await self._request("POST", "/api/v1/cloud/operator/connector-versions/" +
                            quote(version_id, safe="") + "/revoke", json={},
                            headers={"Idempotency-Key": idempotency_key})
