# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Typed autonomous-mission intake and supervision payloads."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AutonomousMissionBudgetHint(BaseModel):
    usd_cap: float = 0.0
    tokens_total: int = 0
    tokens_per_day: int = 0

    @field_validator("usd_cap", "tokens_total", "tokens_per_day")
    @classmethod
    def validate_budget_value(cls, value: float | int) -> float | int:
        if value < 0 or not math.isfinite(float(value)):
            raise ValueError("budget values must be finite and non-negative")
        return value


class AutonomousMissionContextRef(BaseModel):
    kind: str
    value: str


class AutonomousMissionSubmitRequest(BaseModel):
    goal: str
    product_url: str = Field("", alias="productUrl")
    trace_id: str = Field("", alias="traceId")
    dedup_key: str = Field("", alias="dedupKey")
    mission_id: str = Field("", alias="missionId")
    autonomy: str = ""
    options: list[str] = Field(default_factory=list)
    context_refs: list[AutonomousMissionContextRef] = Field(default_factory=list, alias="contextRefs")
    budget: AutonomousMissionBudgetHint = Field(default_factory=AutonomousMissionBudgetHint)

    model_config = {"populate_by_name": True}

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("goal is required")
        return value

    @field_validator("autonomy")
    @classmethod
    def validate_autonomy(cls, value: str) -> str:
        if value not in {"", "recon", "propose", "auto"}:
            raise ValueError("autonomy must be recon, propose, or auto")
        return value


class AutonomousMissionSubmitResponse(BaseModel):
    mission_id: str = Field(alias="missionId")
    status: str

    model_config = {"populate_by_name": True}


class AutonomousMissionBudget(BaseModel):
    usd_cap: float = Field(0.0, alias="usdCap")
    tokens_total: int = Field(0, alias="tokensTotal")
    tokens_per_day: int = Field(0, alias="tokensPerDay")

    model_config = {"populate_by_name": True}


class AutonomousMission(BaseModel):
    lease_expires_at: datetime | None = Field(None, alias="leaseExpiresAt")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    id: str
    namespace: str = ""
    user_id: str = Field("", alias="userId")
    goal: str
    trace_id: str = Field("", alias="traceId")
    status: str
    autonomy: str = ""
    source: str = ""
    source_ref: str = Field("", alias="sourceRef")
    awaiting_question: str = Field("", alias="awaitingQuestion")
    awaiting_request_id: str = Field("", alias="awaitingRequestId")
    plan: str = ""
    lease_owner: str = Field("", alias="leaseOwner")
    context_refs: list[AutonomousMissionContextRef] = Field(default_factory=list, alias="contextRefs")
    options: list[str] = Field(default_factory=list)
    budget: AutonomousMissionBudget = Field(default_factory=AutonomousMissionBudget)
    spent_tokens: int = Field(0, alias="spentTokens")
    step_count: int = Field(0, alias="stepCount")
    step_in_progress: bool = Field(False, alias="stepInProgress")

    model_config = {"populate_by_name": True, "extra": "allow"}


class AutonomousMissionListResponse(BaseModel):
    missions: list[AutonomousMission] = Field(default_factory=list)
    total: int = 0


class AutonomousMissionFlow(BaseModel):
    source: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    mission: AutonomousMission

    model_config = {"extra": "allow"}


class MissionEffectiveSetting(BaseModel):
    key: str
    value: str
    layer: str
    builtin: str
    frozen: bool = False
    runtime_applied: bool = Field(alias="runtimeApplied")

    model_config = {"populate_by_name": True}


class MissionEffectiveSettings(BaseModel):
    namespace: str
    product_id: str = Field("", alias="productId")
    mission_id: str = Field("", alias="missionId")
    settings_digest: str = Field(alias="settingsDigest")
    settings: list[MissionEffectiveSetting] = Field(default_factory=list)
    count: int = 0

    model_config = {"populate_by_name": True}


class MissionStartRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    namespace: str = ""
    product_id: str = Field("", alias="productId")
    subject: str = ""
    kind: str = ""
    goal: str
    autonomy: str = ""
    origin_ref: str = Field("", alias="originRef")
    expected_settings_digest: str = Field("", alias="expectedSettingsDigest")
    chain: list[str] = Field(default_factory=list)
    budget_tokens_total: int = Field(0, alias="budgetTokensTotal")
    budget_tokens_per_day: int = Field(0, alias="budgetTokensPerDay")
    budget_usd_cap: float = Field(0.0, alias="budgetUsdCap")

    model_config = {"populate_by_name": True}

    @field_validator("goal")
    @classmethod
    def validate_unified_goal(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("goal is required")
        return value

    @field_validator("expected_settings_digest")
    @classmethod
    def validate_settings_digest(cls, value: str) -> str:
        value = value.strip()
        if value and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise ValueError("expected settings digest must be canonical sha256")
        return value

    @field_validator("budget_tokens_total", "budget_tokens_per_day", "budget_usd_cap")
    @classmethod
    def validate_unified_budget(cls, value: float | int) -> float | int:
        if value < 0 or not math.isfinite(float(value)):
            raise ValueError("budget values must be finite and non-negative")
        return value


class UnifiedMission(BaseModel):
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    closed_at: datetime | None = Field(None, alias="closedAt")
    data: dict[str, Any] = Field(default_factory=dict)
    id: str
    namespace: str
    product_id: str = Field("", alias="productId")
    subject: str = ""
    kind: str
    goal: str
    autonomy: str = ""
    created_by: str = Field("", alias="createdBy")
    closed_by: str = Field("", alias="closedBy")
    closed_reason: str = Field("", alias="closedReason")
    origin: str
    origin_ref: str = Field("", alias="originRef")
    status: str
    chain: list[dict[str, Any]] = Field(default_factory=list)
    budget_tokens_total: int = Field(0, alias="budgetTokensTotal")
    budget_tokens_per_day: int = Field(0, alias="budgetTokensPerDay")
    spent_tokens: int = Field(0, alias="spentTokens")
    budget_usd_cap: float = Field(0.0, alias="budgetUsdCap")
    step_count: int = Field(0, alias="stepCount")

    model_config = {"populate_by_name": True, "extra": "allow"}


class MissionStartResponse(BaseModel):
    mission: UnifiedMission
    created: bool
