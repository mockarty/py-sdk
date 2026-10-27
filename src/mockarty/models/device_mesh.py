# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Typed device-mesh payloads: devices, grants, commands and receipts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MeshDevice(BaseModel):
    """One machine, phone or runner in the mesh.

    Presence is derived from the heartbeat, so ``state`` reads ``offline`` for a
    device that stopped reporting without anything being deleted.
    """

    heartbeat_at: datetime | None = Field(None, alias="heartbeatAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    created_at: datetime | None = Field(None, alias="createdAt")
    labels: dict[str, str] = Field(default_factory=dict)
    device_id: str = Field("", alias="deviceId")
    namespace: str = ""
    kind: str = ""
    state: str = ""
    owner_user_id: str = Field("", alias="ownerUserId")
    capabilities: list[str] = Field(default_factory=list)


class MeshGrant(BaseModel):
    """An owner's decision to lend a device for a set of capabilities."""

    created_at: datetime | None = Field(None, alias="createdAt")
    device_id: str = Field("", alias="deviceId")
    namespace: str = ""
    grantee_user_id: str = Field("", alias="granteeUserId")
    capabilities: list[str] = Field(default_factory=list)


class MeshCommand(BaseModel):
    """One piece of work, bound to a device or unbound with a placement reason."""

    queued_at: datetime | None = Field(None, alias="queuedAt")
    claimed_at: datetime | None = Field(None, alias="claimedAt")
    started_at: datetime | None = Field(None, alias="startedAt")
    finished_at: datetime | None = Field(None, alias="finishedAt")
    lease_expires_at: datetime | None = Field(None, alias="leaseExpiresAt")
    payload: Any = None
    id: str = ""
    namespace: str = ""
    kind: str = ""
    state: str = ""
    target_device_id: str = Field("", alias="targetDeviceId")
    lease_owner: str = Field("", alias="leaseOwner")
    placement_reason: str = Field("", alias="placementReason")
    result_summary: str = Field("", alias="resultSummary")
    result_ref: str = Field("", alias="resultRef")
    failure_reason: str = Field("", alias="failureReason")
    required_capabilities: list[str] = Field(default_factory=list, alias="requiredCapabilities")


class MeshSubmitResult(BaseModel):
    """The submit answer. ``replayed`` distinguishes a retry from a new placement."""

    command: MeshCommand
    replayed: bool = False


class MeshExecutionReport(BaseModel):
    """The durable receipt of a finished command."""

    recorded_at: datetime | None = Field(None, alias="recordedAt")
    started_at: datetime | None = Field(None, alias="startedAt")
    finished_at: datetime | None = Field(None, alias="finishedAt")
    id: str = ""
    ref: str = ""
    namespace: str = ""
    device_id: str = Field("", alias="deviceId")
    submitter_user_id: str = Field("", alias="submitterUserId")
    state: str = ""
    summary: str = ""
    failure_code: str = Field("", alias="failureCode")
    report_kind: str = Field("", alias="reportKind")
    subject_id: str = Field("", alias="subjectId")


class MeshDeviceList(BaseModel):
    devices: list[MeshDevice] = Field(default_factory=list)


class MeshReportList(BaseModel):
    reports: list[MeshExecutionReport] = Field(default_factory=list)
