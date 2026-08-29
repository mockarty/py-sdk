# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Operator-only Cloud risk case and reversible enforcement API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _release_payload(revision: int, reason: str) -> dict[str, Any]:
    if revision < 1 or len(reason.strip()) < 3 or len(reason.strip()) > 512:
        raise ValueError("positive revision and release reason are required")
    return {"revision": revision, "reason": reason.strip()}


class CloudRiskAPI(SyncAPIBase):
    def list_cases(self, *, status: str = "", limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        data = self._request("GET", "/api/v1/cloud/operator/risk/cases", params=params).json()
        return data.get("cases", []) if isinstance(data, dict) else []

    def get_case(self, case_id: str) -> dict[str, Any]:
        if not case_id:
            raise ValueError("case_id is required")
        return self._request("GET", f"/api/v1/cloud/operator/risk/cases/{quote(case_id, safe='')}").json()

    def release_enforcement(self, case_id: str, enforcement_id: str, *, revision: int, reason: str) -> dict[str, Any]:
        if not case_id or not enforcement_id:
            raise ValueError("case_id and enforcement_id are required")
        path = (f"/api/v1/cloud/operator/risk/cases/{quote(case_id, safe='')}/enforcements/"
                f"{quote(enforcement_id, safe='')}/release")
        return self._request("POST", path, json=_release_payload(revision, reason)).json()


class AsyncCloudRiskAPI(AsyncAPIBase):
    async def list_cases(self, *, status: str = "", limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        data = (await self._request("GET", "/api/v1/cloud/operator/risk/cases", params=params)).json()
        return data.get("cases", []) if isinstance(data, dict) else []

    async def get_case(self, case_id: str) -> dict[str, Any]:
        if not case_id:
            raise ValueError("case_id is required")
        return (await self._request("GET", f"/api/v1/cloud/operator/risk/cases/{quote(case_id, safe='')}")).json()

    async def release_enforcement(self, case_id: str, enforcement_id: str, *, revision: int, reason: str) -> dict[str, Any]:
        if not case_id or not enforcement_id:
            raise ValueError("case_id and enforcement_id are required")
        path = (f"/api/v1/cloud/operator/risk/cases/{quote(case_id, safe='')}/enforcements/"
                f"{quote(enforcement_id, safe='')}/release")
        return (await self._request("POST", path, json=_release_payload(revision, reason))).json()
