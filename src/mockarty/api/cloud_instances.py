# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Dedicated Mockarty Cloud instance lifecycle."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _required(**values: str) -> None:
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(f"required value is empty: {', '.join(missing)}")


class CloudInstancesAPI(SyncAPIBase):
    def list(self, workspace_id: str) -> dict[str, Any]:
        _required(workspace_id=workspace_id)
        return self._request("GET", "/api/v1/cloud/instances", params={"workspace_id": workspace_id}).json()

    def get(self, instance_id: str) -> dict[str, Any]:
        _required(instance_id=instance_id)
        data = self._request("GET", f"/api/v1/cloud/instances/{quote(instance_id, safe='')}").json()
        return data.get("instance", {}) if isinstance(data, dict) else {}

    def create(self, workspace_id: str, name: str, idempotency_key: str) -> dict[str, Any]:
        """Admit an instance and return the bootstrap password on the first response only."""
        _required(workspace_id=workspace_id, name=name, idempotency_key=idempotency_key)
        return self._request("POST", "/api/v1/cloud/instances",
                             json={"workspace_id": workspace_id, "name": name},
                             headers={"Idempotency-Key": idempotency_key}).json()

    def delete(self, instance_id: str, idempotency_key: str) -> None:
        self._mutate("DELETE", instance_id, "", idempotency_key)

    def start(self, instance_id: str, idempotency_key: str) -> None:
        self._mutate("POST", instance_id, "start", idempotency_key)

    def stop(self, instance_id: str, idempotency_key: str) -> None:
        self._mutate("POST", instance_id, "stop", idempotency_key)

    def _mutate(self, method: str, instance_id: str, action: str, idempotency_key: str) -> None:
        _required(instance_id=instance_id, idempotency_key=idempotency_key)
        path = f"/api/v1/cloud/instances/{quote(instance_id, safe='')}"
        if action:
            path += f"/{action}"
        self._request(method, path, headers={"Idempotency-Key": idempotency_key})


class AsyncCloudInstancesAPI(AsyncAPIBase):
    async def list(self, workspace_id: str) -> dict[str, Any]:
        _required(workspace_id=workspace_id)
        return (await self._request("GET", "/api/v1/cloud/instances", params={"workspace_id": workspace_id})).json()

    async def get(self, instance_id: str) -> dict[str, Any]:
        _required(instance_id=instance_id)
        data = (await self._request("GET", f"/api/v1/cloud/instances/{quote(instance_id, safe='')}")).json()
        return data.get("instance", {}) if isinstance(data, dict) else {}

    async def create(self, workspace_id: str, name: str, idempotency_key: str) -> dict[str, Any]:
        _required(workspace_id=workspace_id, name=name, idempotency_key=idempotency_key)
        return (await self._request("POST", "/api/v1/cloud/instances",
                                    json={"workspace_id": workspace_id, "name": name},
                                    headers={"Idempotency-Key": idempotency_key})).json()

    async def delete(self, instance_id: str, idempotency_key: str) -> None:
        await self._mutate("DELETE", instance_id, "", idempotency_key)

    async def start(self, instance_id: str, idempotency_key: str) -> None:
        await self._mutate("POST", instance_id, "start", idempotency_key)

    async def stop(self, instance_id: str, idempotency_key: str) -> None:
        await self._mutate("POST", instance_id, "stop", idempotency_key)

    async def _mutate(self, method: str, instance_id: str, action: str, idempotency_key: str) -> None:
        _required(instance_id=instance_id, idempotency_key=idempotency_key)
        path = f"/api/v1/cloud/instances/{quote(instance_id, safe='')}"
        if action:
            path += f"/{action}"
        await self._request(method, path, headers={"Idempotency-Key": idempotency_key})
