# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Operator-only durable Cloud refund recovery API.

The browser-session ``/api/v1/cloud/billing/refunds`` endpoint is intentionally
not exposed: starting a refund requires an interactive, action-bound step-up.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


_REASON_CODE = re.compile(r"[a-z0-9._:-]{2,64}\Z")
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:/@-]{1,128}\Z")


def _refunds_projection(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("refunds"), list):
        raise ValueError("operator refunds response is missing refunds")
    refunds: list[dict[str, Any]] = []
    for item in data["refunds"]:
        if (not isinstance(item, dict)
                or not isinstance(item.get("operation_id"), str) or not item["operation_id"]
                or type(item.get("generation")) is not int or item["generation"] < 0
                or not isinstance(item.get("status"), str) or not item["status"]
                or type(item.get("amount_minor")) is not int or item["amount_minor"] < 0
                or not isinstance(item.get("currency"), str) or not item["currency"]
                or not isinstance(item.get("provider"), str) or not item["provider"]):
            raise ValueError("operator refunds response contains an invalid refund projection")
        refunds.append(item)
    return refunds


def _resolution_payload(action: str, reason_code: str, generation: int,
                        idempotency_key: str) -> dict[str, Any]:
    if action not in {"reject", "retry"}:
        raise ValueError("action must be reject or retry")
    if generation < 0:
        raise ValueError("generation must be non-negative")
    if not _REASON_CODE.fullmatch(reason_code):
        raise ValueError("reason_code must contain 2-64 safe lowercase characters")
    # Validate without trimming or normalising: this exact caller-supplied value
    # is the replay authority sent in Idempotency-Key.
    if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
        raise ValueError("idempotency_key must contain 1-128 safe characters")
    return {"action": action, "reason_code": reason_code, "generation": generation}


def _resolution_path(operation_id: str) -> str:
    if not operation_id or operation_id.isspace():
        raise ValueError("operation_id is required")
    return f"/api/v1/cloud/operator/refunds/{quote(operation_id, safe='')}/resolve"


class CloudRefundsAPI(SyncAPIBase):
    """Resolve refunds held in ``operator_required`` without creating money success."""

    def list_refunds(self) -> list[dict[str, Any]]:
        """List redacted refunds; requires ``operator:commerce:write`` exactly."""
        response = self._request("GET", "/api/v1/cloud/operator/refunds")
        return _refunds_projection(response.json())

    def resolve_refund(self, operation_id: str, *, action: str, reason_code: str,
                       generation: int, idempotency_key: str) -> dict[str, Any]:
        payload = _resolution_payload(action, reason_code, generation, idempotency_key)
        return self._request("POST", _resolution_path(operation_id), json=payload,
                             headers={"Idempotency-Key": idempotency_key}).json()


class AsyncCloudRefundsAPI(AsyncAPIBase):
    """Asynchronous operator refund recovery API."""

    async def list_refunds(self) -> list[dict[str, Any]]:
        """List redacted refunds; requires ``operator:commerce:write`` exactly."""
        response = await self._request("GET", "/api/v1/cloud/operator/refunds")
        return _refunds_projection(response.json())

    async def resolve_refund(self, operation_id: str, *, action: str, reason_code: str,
                             generation: int, idempotency_key: str) -> dict[str, Any]:
        payload = _resolution_payload(action, reason_code, generation, idempotency_key)
        response = await self._request("POST", _resolution_path(operation_id), json=payload,
                                       headers={"Idempotency-Key": idempotency_key})
        return response.json()
