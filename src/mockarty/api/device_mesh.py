# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Lend machines to a workspace and place work on them.

Two rules the server enforces and this API keeps visible: only a device's owner
can lend it, and claim/report belong to the executing device. ``submit`` reports
whether an idempotency key replayed, so a pipeline can tell a fresh placement
from a repeat.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from mockarty.api._base import SyncAPIBase
from mockarty.models.device_mesh import (
    MeshCommand,
    MeshDevice,
    MeshDeviceList,
    MeshGrant,
    MeshReportList,
    MeshSubmitResult,
)


def _mesh_path(namespace: str) -> str:
    namespace = (namespace or "").strip()
    if not namespace:
        raise ValueError("namespace is required for the device mesh")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/device-mesh"


def _required(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


class DeviceMeshAPI(SyncAPIBase):
    """Devices, grants, commands, receipts and the operator drain."""

    def list_devices(self, *, namespace: str = "") -> list[MeshDevice]:
        resp = self._request("GET", _mesh_path(namespace or self._namespace) + "/devices")
        return MeshDeviceList.model_validate(resp.json()).devices

    def create_grant(
        self, device_id: str, grantee_user_id: str, *,
        capabilities: list[str] | None = None, namespace: str = "",
    ) -> MeshGrant:
        base = _mesh_path(namespace or self._namespace)
        body: dict[str, Any] = {"granteeUserId": _required(grantee_user_id, "grantee_user_id")}
        if capabilities:
            body["capabilities"] = capabilities
        resp = self._request(
            "POST", f"{base}/devices/{quote(_required(device_id, 'device_id'), safe='')}/grants", json=body,
        )
        return MeshGrant.model_validate(resp.json())

    def revoke_grant(self, device_id: str, grantee_user_id: str, *, namespace: str = "") -> None:
        base = _mesh_path(namespace or self._namespace)
        self._request(
            "DELETE",
            f"{base}/devices/{quote(_required(device_id, 'device_id'), safe='')}"
            f"/grants/{quote(_required(grantee_user_id, 'grantee_user_id'), safe='')}",
        )

    def submit(
        self, *, kind: str, payload: Any = None, idempotency_key: str,
        target_device_id: str = "", required_capabilities: list[str] | None = None,
        target_labels: dict[str, str] | None = None, namespace: str = "",
    ) -> MeshSubmitResult:
        base = _mesh_path(namespace or self._namespace)
        body: dict[str, Any] = {
            "kind": _required(kind, "kind"),
            "idempotencyKey": _required(idempotency_key, "idempotency_key"),
        }
        if payload is not None:
            body["payload"] = payload
        if required_capabilities:
            body["requiredCapabilities"] = required_capabilities
        if (target_device_id or "").strip():
            body["targetDeviceId"] = target_device_id.strip()
        if target_labels:
            body["targetLabels"] = target_labels
        resp = self._request("POST", f"{base}/commands", json=body)
        return MeshSubmitResult.model_validate(resp.json())

    def get_command(self, command_id: str, *, namespace: str = "") -> MeshCommand:
        base = _mesh_path(namespace or self._namespace)
        resp = self._request("GET", f"{base}/commands/{quote(_required(command_id, 'command_id'), safe='')}")
        return MeshCommand.model_validate(resp.json())

    def report(
        self, command_id: str, *, device_id: str, state: str,
        result_summary: str = "", result_ref: str = "", failure_reason: str = "",
        namespace: str = "",
    ) -> MeshCommand:
        base = _mesh_path(namespace or self._namespace)
        body: dict[str, Any] = {"state": _required(state, "state")}
        if result_summary:
            body["resultSummary"] = result_summary
        if result_ref:
            body["resultRef"] = result_ref
        if failure_reason:
            body["failureReason"] = failure_reason
        path = (
            f"{base}/commands/{quote(_required(command_id, 'command_id'), safe='')}/report"
            f"?deviceId={quote(_required(device_id, 'device_id'), safe='')}"
        )
        resp = self._request("POST", path, json=body)
        return MeshCommand.model_validate(resp.json())

    def list_reports(self, command_id: str, *, namespace: str = "") -> list[Any]:
        base = _mesh_path(namespace or self._namespace)
        path = f"{base}/reports?commandId={quote(_required(command_id, 'command_id'), safe='')}"
        resp = self._request("GET", path)
        return MeshReportList.model_validate(resp.json()).reports

    def set_drain(
        self, device_id: str, *, draining: bool, reason: str = "", namespace: str = "",
    ) -> MeshDevice:
        base = _mesh_path(namespace or self._namespace)
        body: dict[str, Any] = {"draining": bool(draining)}
        if reason:
            body["reason"] = reason
        resp = self._request(
            "POST", f"{base}/devices/{quote(_required(device_id, 'device_id'), safe='')}/drain", json=body,
        )
        return MeshDevice.model_validate(resp.json())


def payload_json(value: Any) -> str:
    """Render a command payload the way the server expects it."""
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
