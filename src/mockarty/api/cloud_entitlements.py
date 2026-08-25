# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Read-only committed Cloud entitlement projections.

The returned snapshot is unsigned inspection data, not an offline licence.
"""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _params(space_id: str) -> dict[str, str]:
    if not space_id or not space_id.strip():
        raise ValueError("space_id is required")
    return {"space_id": space_id}


class CloudEntitlementsAPI(SyncAPIBase):
    def get(self, space_id: str) -> dict[str, Any]:
        return self._request("GET", "/api/v1/cloud/entitlements", params=_params(space_id)).json()


class AsyncCloudEntitlementsAPI(AsyncAPIBase):
    async def get(self, space_id: str) -> dict[str, Any]:
        return (await self._request("GET", "/api/v1/cloud/entitlements", params=_params(space_id))).json()
