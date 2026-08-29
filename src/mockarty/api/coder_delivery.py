# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Admitted coder repositories, delivery targets, and deploy missions."""

from __future__ import annotations

from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _mission_path(mission_id: str) -> str:
    mission_id = (mission_id or "").strip()
    if not mission_id:
        raise ValueError("mission_id is required")
    return "/api/v1/coder/missions/" + quote(mission_id, safe="")


def _deploy_reconciliation(outcome: str) -> dict[str, str]:
    outcome = (outcome or "").strip()
    if outcome not in {"applied", "not_applied"}:
        raise ValueError("outcome must be applied or not_applied")
    return {"outcome": outcome}


class CoderDeliveryAPI(SyncAPIBase):
    def get_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return self._request("GET", "/api/v1/coder/delivery-config", params=params).json()

    def put_config(self, config: dict) -> dict:
        return self._request("PUT", "/api/v1/coder/delivery-config", params={"namespace": self._namespace}, json=config).json()

    def delete_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return self._request("DELETE", "/api/v1/coder/delivery-config", params=params).json()

    def start_mission(self, request: dict) -> dict:
        if not str(request.get("goal", "")).strip() or not str(request.get("repoUrl", "")).strip():
            raise ValueError("goal and repoUrl are required")
        return self._request("POST", "/api/v1/coder/missions", params={"namespace": self._namespace}, json=request).json()

    def list_missions(self) -> list[dict]:
        body = self._request("GET", "/api/v1/coder/missions", params={"namespace": self._namespace}).json()
        return body.get("missions") or []

    def get_mission(self, mission_id: str) -> dict:
        return self._request("GET", _mission_path(mission_id), params={"namespace": self._namespace}).json()

    def approve_mission(self, mission_id: str, approve: bool) -> dict:
        return self._request("POST", _mission_path(mission_id) + "/approve", params={"namespace": self._namespace}, json={"approve": approve}).json()

    def reconcile_deploy(self, mission_id: str, outcome: str) -> dict:
        return self._request("POST", _mission_path(mission_id) + "/deploy-outcome", params={"namespace": self._namespace}, json=_deploy_reconciliation(outcome)).json()


class AsyncCoderDeliveryAPI(AsyncAPIBase):
    async def get_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return (await self._request("GET", "/api/v1/coder/delivery-config", params=params)).json()

    async def put_config(self, config: dict) -> dict:
        return (await self._request("PUT", "/api/v1/coder/delivery-config", params={"namespace": self._namespace}, json=config)).json()

    async def delete_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return (await self._request("DELETE", "/api/v1/coder/delivery-config", params=params)).json()

    async def start_mission(self, request: dict) -> dict:
        if not str(request.get("goal", "")).strip() or not str(request.get("repoUrl", "")).strip():
            raise ValueError("goal and repoUrl are required")
        return (await self._request("POST", "/api/v1/coder/missions", params={"namespace": self._namespace}, json=request)).json()

    async def list_missions(self) -> list[dict]:
        body = (await self._request("GET", "/api/v1/coder/missions", params={"namespace": self._namespace})).json()
        return body.get("missions") or []

    async def get_mission(self, mission_id: str) -> dict:
        return (await self._request("GET", _mission_path(mission_id), params={"namespace": self._namespace})).json()

    async def approve_mission(self, mission_id: str, approve: bool) -> dict:
        return (await self._request("POST", _mission_path(mission_id) + "/approve", params={"namespace": self._namespace}, json={"approve": approve})).json()

    async def reconcile_deploy(self, mission_id: str, outcome: str) -> dict:
        return (await self._request("POST", _mission_path(mission_id) + "/deploy-outcome", params={"namespace": self._namespace}, json=_deploy_reconciliation(outcome))).json()
