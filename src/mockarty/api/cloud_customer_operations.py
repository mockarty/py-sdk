# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Customer-authorized and least-privilege operator Cloud product APIs."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _required(value: str, label: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{label} is required")
    return value


def _space_product_path(space_id: str, suffix: str) -> str:
    return "/api/v1/cloud/spaces/" + quote(_required(space_id, "space_id"), safe="") + suffix


def _entity_path(prefix: str, entity_id: str, label: str) -> str:
    return prefix + quote(_required(entity_id, label), safe="")


def _page(status: str = "", cursor: str = "", limit: int = 0) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if cursor:
        params["cursor"] = cursor
    if limit > 0:
        params["limit"] = limit
    if status:
        params["status"] = status
    return params


class CloudCustomerAPI(SyncAPIBase):
    def list_loyalty_redemptions(self, space_id: str, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return self._request("GET", _space_product_path(space_id, "/loyalty/redemptions"), params=_page(cursor=cursor, limit=limit)).json()

    def redeem_loyalty(self, space_id: str, code: str, region: str, idempotency_key: str) -> dict[str, Any]:
        body = {"code": code, "region": region, "idempotency_key": _required(idempotency_key, "idempotency_key")}
        return self._request("POST", _space_product_path(space_id, "/loyalty/redemptions"), json=body).json()

    def list_support_cases(self, space_id: str, status: str = "", cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return self._request("GET", _space_product_path(space_id, "/support/cases"), params=_page(status, cursor, limit)).json()

    def open_support_case(self, space_id: str, subject: str, category: str, priority: str, message: str, idempotency_key: str) -> dict[str, Any]:
        body = {"subject": subject, "category": category, "priority": priority, "message": message,
                "idempotency_key": _required(idempotency_key, "idempotency_key")}
        return self._request("POST", _space_product_path(space_id, "/support/cases"), json=body).json()

    def get_support_case(self, space_id: str, case_id: str) -> dict[str, Any]:
        path = _space_product_path(space_id, "/support/cases/") + quote(_required(case_id, "case_id"), safe="")
        return self._request("GET", path).json()

    def reply_support_case(self, space_id: str, case_id: str, body: str, idempotency_key: str) -> dict[str, Any]:
        path = _space_product_path(space_id, "/support/cases/") + quote(_required(case_id, "case_id"), safe="") + "/messages"
        return self._request("POST", path, json={"body": body, "visibility": "customer",
                                                  "idempotency_key": _required(idempotency_key, "idempotency_key")}).json()

    def get_risk_appeal(self, case_id: str) -> dict[str, Any]:
        return self._request("GET", _entity_path("/api/v1/cloud/risk/cases/", case_id, "case_id") + "/appeal").json()

    def submit_risk_appeal(self, case_id: str, reason: str, idempotency_key: str) -> dict[str, Any]:
        path = _entity_path("/api/v1/cloud/risk/cases/", case_id, "case_id") + "/appeal"
        return self._request("POST", path, json={"reason": reason},
                             headers={"Idempotency-Key": _required(idempotency_key, "idempotency_key")}).json()


class CloudOperationsAPI(SyncAPIBase):
    _SUPPORT = "/api/v1/cloud/operator/support/cases"

    def list_support_cases(self, status: str = "", cursor: str = "", limit: int = 50) -> dict[str, Any]:
        return self._request("GET", self._SUPPORT, params=_page(status, cursor, limit)).json()

    def get_support_case(self, case_id: str) -> dict[str, Any]:
        return self._request("GET", _entity_path(self._SUPPORT + "/", case_id, "case_id")).json()

    def reply_support_case(self, case_id: str, body: str, visibility: str, idempotency_key: str) -> dict[str, Any]:
        path = _entity_path(self._SUPPORT + "/", case_id, "case_id") + "/messages"
        return self._request("POST", path, json={"body": body, "visibility": visibility,
                                                  "idempotency_key": _required(idempotency_key, "idempotency_key")}).json()

    def assign_support_case(self, case_id: str, assignee_user_id: str, expected_generation: int) -> dict[str, Any]:
        path = _entity_path(self._SUPPORT + "/", case_id, "case_id") + "/assign"
        return self._request("POST", path, json={"assignee_user_id": assignee_user_id,
                                                  "expected_generation": expected_generation}).json()

    def transition_support_case(self, case_id: str, status: str, expected_generation: int) -> dict[str, Any]:
        path = _entity_path(self._SUPPORT + "/", case_id, "case_id") + "/transition"
        return self._request("POST", path, json={"status": status, "expected_generation": expected_generation}).json()

    def product_analytics(self, days: int = 30) -> dict[str, Any]:
        if days < 1 or days > 90:
            raise ValueError("days must be between 1 and 90")
        return self._request("GET", "/api/v1/cloud/operator/analytics/product", params={"days": days}).json()


class AsyncCloudCustomerAPI(AsyncAPIBase):
    async def list_loyalty_redemptions(self, space_id: str, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return (await self._request("GET", _space_product_path(space_id, "/loyalty/redemptions"), params=_page(cursor=cursor, limit=limit))).json()

    async def redeem_loyalty(self, space_id: str, code: str, region: str, idempotency_key: str) -> dict[str, Any]:
        body = {"code": code, "region": region, "idempotency_key": _required(idempotency_key, "idempotency_key")}
        return (await self._request("POST", _space_product_path(space_id, "/loyalty/redemptions"), json=body)).json()

    async def list_support_cases(self, space_id: str, status: str = "", cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return (await self._request("GET", _space_product_path(space_id, "/support/cases"), params=_page(status, cursor, limit))).json()

    async def open_support_case(self, space_id: str, subject: str, category: str, priority: str, message: str, idempotency_key: str) -> dict[str, Any]:
        body = {"subject": subject, "category": category, "priority": priority, "message": message,
                "idempotency_key": _required(idempotency_key, "idempotency_key")}
        return (await self._request("POST", _space_product_path(space_id, "/support/cases"), json=body)).json()

    async def get_support_case(self, space_id: str, case_id: str) -> dict[str, Any]:
        path = _space_product_path(space_id, "/support/cases/") + quote(_required(case_id, "case_id"), safe="")
        return (await self._request("GET", path)).json()

    async def reply_support_case(self, space_id: str, case_id: str, body: str, idempotency_key: str) -> dict[str, Any]:
        path = _space_product_path(space_id, "/support/cases/") + quote(_required(case_id, "case_id"), safe="") + "/messages"
        return (await self._request("POST", path, json={"body": body, "visibility": "customer",
                                                         "idempotency_key": _required(idempotency_key, "idempotency_key")})).json()

    async def get_risk_appeal(self, case_id: str) -> dict[str, Any]:
        return (await self._request("GET", _entity_path("/api/v1/cloud/risk/cases/", case_id, "case_id") + "/appeal")).json()

    async def submit_risk_appeal(self, case_id: str, reason: str, idempotency_key: str) -> dict[str, Any]:
        path = _entity_path("/api/v1/cloud/risk/cases/", case_id, "case_id") + "/appeal"
        return (await self._request("POST", path, json={"reason": reason},
                                    headers={"Idempotency-Key": _required(idempotency_key, "idempotency_key")})).json()


class AsyncCloudOperationsAPI(AsyncAPIBase):
    _SUPPORT = CloudOperationsAPI._SUPPORT

    async def list_support_cases(self, status: str = "", cursor: str = "", limit: int = 50) -> dict[str, Any]:
        return (await self._request("GET", self._SUPPORT, params=_page(status, cursor, limit))).json()

    async def get_support_case(self, case_id: str) -> dict[str, Any]:
        return (await self._request("GET", _entity_path(self._SUPPORT + "/", case_id, "case_id"))).json()

    async def reply_support_case(self, case_id: str, body: str, visibility: str, idempotency_key: str) -> dict[str, Any]:
        path = _entity_path(self._SUPPORT + "/", case_id, "case_id") + "/messages"
        return (await self._request("POST", path, json={"body": body, "visibility": visibility,
                                                         "idempotency_key": _required(idempotency_key, "idempotency_key")})).json()

    async def assign_support_case(self, case_id: str, assignee_user_id: str, expected_generation: int) -> dict[str, Any]:
        path = _entity_path(self._SUPPORT + "/", case_id, "case_id") + "/assign"
        return (await self._request("POST", path, json={"assignee_user_id": assignee_user_id,
                                                         "expected_generation": expected_generation})).json()

    async def transition_support_case(self, case_id: str, status: str, expected_generation: int) -> dict[str, Any]:
        path = _entity_path(self._SUPPORT + "/", case_id, "case_id") + "/transition"
        return (await self._request("POST", path, json={"status": status,
                                                         "expected_generation": expected_generation})).json()

    async def product_analytics(self, days: int = 30) -> dict[str, Any]:
        if days < 1 or days > 90:
            raise ValueError("days must be between 1 and 90")
        return (await self._request("GET", "/api/v1/cloud/operator/analytics/product", params={"days": days})).json()
