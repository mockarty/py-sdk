# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Typed autonomous-mission intake and supervision payloads."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator, StrictInt


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
        if value not in {"", "recon", "propose", "auto", "full"}:
            raise ValueError("autonomy must be recon, propose, auto, or full")
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


class MissionRevisionReference(BaseModel):
    """Exact target or artifact revision sealed into a mission brief."""

    kind: str
    id: str
    digest: str
    revision: int


class MissionStartRequest(BaseModel):
    """Goal-first mission input; kind/chain are legacy routing overrides."""

    data: dict[str, Any] = Field(default_factory=dict)
    namespace: str = ""
    product_id: str = Field("", alias="productId")
    subject: str = ""
    kind: str = ""
    goal: str
    autonomy: str = ""
    origin_ref: str = Field("", alias="originRef")
    expected_settings_digest: str = Field("", alias="expectedSettingsDigest")
    targets: list[MissionRevisionReference] = Field(default_factory=list)
    artifacts: list[MissionRevisionReference] = Field(default_factory=list)
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
    pins: list[MissionRevisionReference] = Field(default_factory=list)
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


class MissionCancelRequest(BaseModel):
    """Durable operator intent accepted by the unified cancel endpoint."""

    reason: str = ""
    idempotency_key: str = Field("", alias="idempotencyKey")

    model_config = {"populate_by_name": True}

    @field_validator("reason", "idempotency_key")
    @classmethod
    def trim_cancel_value(cls, value: str) -> str:
        return value.strip()


class MissionAnswerEntity(BaseModel):
    """Reference offered by the original question; never an authority grant."""

    kind: str
    id: str
    namespace: str = ""

    @model_validator(mode="after")
    def validate_reference(self) -> MissionAnswerEntity:
        for name, limit, required in (("kind", 64, True), ("id", 256, True), ("namespace", 256, False)):
            value = getattr(self, name).strip()
            if (required and not value) or len(value.encode("utf-8")) > limit:
                raise ValueError("entity requires bounded kind/id and optional namespace")
        return self


class MissionAnswerRequest(BaseModel):
    """Durable human input accepted while a mission waits for an answer."""

    answer: str = ""
    question_id: str = Field("", alias="questionId")
    revision: StrictInt = Field(0, ge=0, le=9223372036854775807)
    generation: StrictInt = Field(0, ge=0, le=9223372036854775807)
    text: str = ""
    selected: list[str] | None = None
    entity: MissionAnswerEntity | None = None
    idempotency_key: str = Field("", alias="idempotencyKey")

    model_config = {"populate_by_name": True}

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        value = value.strip()
        return value

    @model_validator(mode="after")
    def validate_captured_answer(self) -> MissionAnswerRequest:
        typed = bool(self.question_id or self.revision or self.generation or self.text or self.selected is not None or self.entity is not None)
        if not typed:
            if not self.answer:
                raise ValueError("answer or captured typed question answer is required")
            return self
        if self.answer:
            raise ValueError("do not mix legacy answer with typed fields")
        if not self.question_id.strip() or len(self.question_id.strip().encode("utf-8")) > 128 or self.revision <= 0:
            raise ValueError("captured questionId and positive revision are required")
        if not self.text.strip() and not self.selected and self.entity is None:
            raise ValueError("typed answer is empty")
        if len(self.text) > 4000 or any((ord(c) < 32 or 127 <= ord(c) <= 159) and c not in "\n\r\t" for c in self.text):
            raise ValueError("text exceeds 4000 characters or contains control characters")
        self.text.encode("utf-8")
        selected = self.selected or []
        normalized = [value.strip() for value in selected]
        if len(selected) > 32 or len(set(normalized)) != len(normalized) or any(not value or len(value.encode("utf-8")) > 128 for value in normalized):
            raise ValueError("selections must be unique, nonempty and bounded")
        return self

    @field_validator("idempotency_key")
    @classmethod
    def trim_answer_key(cls, value: str) -> str:
        return value.strip()


class MissionControlReceipt(BaseModel):
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    committed_at: datetime | None = Field(None, alias="committedAt")
    resolved_at: datetime | None = Field(None, alias="resolvedAt")
    id: str
    mission_id: str = Field(alias="missionId")
    idempotency_key: str = Field(alias="idempotencyKey")
    action: str
    phase: str
    outcome: str
    reason: str = ""
    resolution: str = ""
    resolved_by: str = Field("", alias="resolvedBy")
    resolution_reason: str = Field("", alias="resolutionReason")

    model_config = {"populate_by_name": True, "extra": "allow"}


class MissionExecutionBinding(BaseModel):
    """Durable public cancellation evidence for one exact child execution."""

    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    id: str
    node_id: str = Field(alias="nodeId")
    external_id: str = Field(alias="externalId")
    kind: str
    state: str
    graph_revision: int = Field(alias="graphRevision")
    generation: int
    cancel_epoch: int = Field(0, alias="cancelEpoch")
    delivery_count: int = Field(0, alias="deliveryCount")

    model_config = {"populate_by_name": True, "extra": "allow"}


class MissionControlResponse(BaseModel):
    error: dict[str, Any] | None = None
    mission: UnifiedMission
    control: MissionControlReceipt
    execution_bindings: list[MissionExecutionBinding] = Field(default_factory=list, alias="executionBindings")
    execution_bindings_available: bool = Field(False, alias="executionBindingsAvailable")
    pending: bool = False

    model_config = {"populate_by_name": True, "extra": "allow"}


class MissionArchiveEnvelope(BaseModel):
    """Portable digest-bound Mission, immutable Brief, and complete journal."""

    digest: str
    payload: dict[str, Any]

    @field_validator("digest")
    @classmethod
    def validate_archive_digest(cls, value: str) -> str:
        value = value.strip()
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise ValueError("digest must be canonical sha256")
        return value


class MissionArchiveRestoreResponse(BaseModel):
    id: str
    digest: str
    created: bool
