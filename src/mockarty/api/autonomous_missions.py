# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Submit and supervise durable autonomous testing missions."""

from __future__ import annotations

from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.autonomous_missions import (
    AutonomousMission,
    AutonomousMissionFlow,
    AutonomousMissionListResponse,
    AutonomousMissionSubmitRequest,
    AutonomousMissionSubmitResponse,
    MissionEffectiveSettings,
    MissionStartRequest,
    MissionStartResponse,
)

_INTENTS_PATH = "/api/v1/autotester/intents"
_MISSIONS_PATH = "/api/v1/autotester/missions"
_UNIFIED_MISSIONS_PATH = "/api/v1/missions"


def _mission_path(mission_id: str) -> str:
    mission_id = (mission_id or "").strip()
    if not mission_id:
        raise ValueError("mission_id is required")
    return f"{_MISSIONS_PATH}/{quote(mission_id, safe='')}"


def _list_params(status: str, limit: int | None) -> dict[str, object]:
    params: dict[str, object] = {}
    if status := (status or "").strip():
        params["status"] = status
    if limit is not None:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        params["limit"] = limit
    return params


def _effective_settings_params(
    product_id: str, mission_id: str, run_window_minutes: int | None,
) -> dict[str, object]:
    params: dict[str, object] = {}
    if product_id := (product_id or "").strip():
        params["productId"] = product_id
    if mission_id := (mission_id or "").strip():
        params["missionId"] = mission_id
    if run_window_minutes is not None:
        if run_window_minutes < 1 or run_window_minutes > 20160:
            raise ValueError("run_window_minutes must be between 1 and 20160")
        params["runWindowMinutes"] = run_window_minutes
    return params


class AutonomousMissionsAPI(SyncAPIBase):
    def submit(self, request: AutonomousMissionSubmitRequest) -> AutonomousMissionSubmitResponse:
        resp = self._request("POST", _INTENTS_PATH, json=request.model_dump(by_alias=True, exclude_none=True))
        return AutonomousMissionSubmitResponse.model_validate(resp.json())

    def list(self, *, status: str = "", limit: int | None = None) -> AutonomousMissionListResponse:
        resp = self._request("GET", _MISSIONS_PATH, params=_list_params(status, limit))
        return AutonomousMissionListResponse.model_validate(resp.json())

    def get(self, mission_id: str) -> AutonomousMission:
        resp = self._request("GET", _mission_path(mission_id))
        return AutonomousMission.model_validate(resp.json())

    def get_flow(self, mission_id: str) -> AutonomousMissionFlow:
        resp = self._request("GET", _mission_path(mission_id) + "/flow")
        return AutonomousMissionFlow.model_validate(resp.json())

    def get_effective_settings(
        self, *, product_id: str = "", mission_id: str = "", run_window_minutes: int | None = None,
    ) -> MissionEffectiveSettings:
        resp = self._request(
            "GET", _UNIFIED_MISSIONS_PATH + "/settings/effective",
            params=_effective_settings_params(product_id, mission_id, run_window_minutes),
        )
        return MissionEffectiveSettings.model_validate(resp.json())

    def start(self, request: MissionStartRequest) -> MissionStartResponse:
        resp = self._request(
            "POST", _UNIFIED_MISSIONS_PATH,
            json=request.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True),
        )
        return MissionStartResponse.model_validate(resp.json())


class AsyncAutonomousMissionsAPI(AsyncAPIBase):
    async def submit(self, request: AutonomousMissionSubmitRequest) -> AutonomousMissionSubmitResponse:
        resp = await self._request("POST", _INTENTS_PATH, json=request.model_dump(by_alias=True, exclude_none=True))
        return AutonomousMissionSubmitResponse.model_validate(resp.json())

    async def list(self, *, status: str = "", limit: int | None = None) -> AutonomousMissionListResponse:
        resp = await self._request("GET", _MISSIONS_PATH, params=_list_params(status, limit))
        return AutonomousMissionListResponse.model_validate(resp.json())

    async def get(self, mission_id: str) -> AutonomousMission:
        resp = await self._request("GET", _mission_path(mission_id))
        return AutonomousMission.model_validate(resp.json())

    async def get_flow(self, mission_id: str) -> AutonomousMissionFlow:
        resp = await self._request("GET", _mission_path(mission_id) + "/flow")
        return AutonomousMissionFlow.model_validate(resp.json())

    async def get_effective_settings(
        self, *, product_id: str = "", mission_id: str = "", run_window_minutes: int | None = None,
    ) -> MissionEffectiveSettings:
        resp = await self._request(
            "GET", _UNIFIED_MISSIONS_PATH + "/settings/effective",
            params=_effective_settings_params(product_id, mission_id, run_window_minutes),
        )
        return MissionEffectiveSettings.model_validate(resp.json())

    async def start(self, request: MissionStartRequest) -> MissionStartResponse:
        resp = await self._request(
            "POST", _UNIFIED_MISSIONS_PATH,
            json=request.model_dump(by_alias=True, exclude_none=True, exclude_defaults=True),
        )
        return MissionStartResponse.model_validate(resp.json())
