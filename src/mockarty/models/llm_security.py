"""Layered prompt-security management models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LLMSecurityPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    surface_actions: dict[str, str] = Field(
        default_factory=dict, alias="surfaceActions"
    )
    rule_ids: list[str] = Field(default_factory=list, alias="ruleIds")
    blocked_capabilities: list[str] = Field(
        default_factory=list, alias="blockedCapabilities"
    )
    mode: str = ""
    enabled: bool | None = None
    fail_closed: bool | None = Field(default=None, alias="failClosed")
    max_input_bytes: int = Field(default=0, alias="maxInputBytes")
    max_output_bytes: int = Field(default=0, alias="maxOutputBytes")
    max_decoded_bytes: int = Field(default=0, alias="maxDecodedBytes")
    block_threshold: int = Field(default=0, alias="blockThreshold")
    redact_threshold: int = Field(default=0, alias="redactThreshold")
    max_findings: int = Field(default=0, alias="maxFindings")
    max_decode_candidates: int = Field(default=0, alias="maxDecodeCandidates")
    max_decode_depth: int = Field(default=0, alias="maxDecodeDepth")


class LLMSecurityDelegation(BaseModel):
    layers: list[str] = Field(default_factory=list)
    kind: str
    key: str
    item: str = ""


class LLMSecurityPolicyDocument(BaseModel):
    value: LLMSecurityPolicy | None = None
    additions: dict[str, list[str]] = Field(default_factory=dict)
    denies: dict[str, list[str]] = Field(default_factory=dict)
    allows: dict[str, list[str]] = Field(default_factory=dict)
    caps: dict[str, float] = Field(default_factory=dict)
    delegations: list[LLMSecurityDelegation] = Field(default_factory=list)


class LLMSecuritySource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    layer: str
    scope_id: str = Field(alias="scopeId")
    actor_id: str = Field(default="", alias="actorId")
    revision: int = 0


class LLMSecurityRestrictions(BaseModel):
    denies: dict[str, dict[str, object]] = Field(default_factory=dict)
    caps: dict[str, object] = Field(default_factory=dict)
    relaxations: list[dict[str, object]] = Field(default_factory=list)


class LLMSecurityPolicyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    effective: LLMSecurityPolicy
    document: LLMSecurityPolicyDocument = Field(
        default_factory=LLMSecurityPolicyDocument
    )
    restrictions: LLMSecurityRestrictions = Field(
        default_factory=LLMSecurityRestrictions
    )
    applied: list[LLMSecuritySource] = Field(default_factory=list)
    mode: str
    layer: str
    namespace: str = ""
    revision: int = 0
    active: bool = False
    local: bool = False
    delivery_deferred: bool = Field(default=False, alias="deliveryDeferred")


class LLMSecurityPolicyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document: LLMSecurityPolicyDocument
    mode: str = "merge"
    active: bool | None = None
    expected_revision: int = Field(default=0, alias="expectedRevision", ge=0)


class LLMSecuritySandboxRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(min_length=1)
    document: LLMSecurityPolicyDocument | None = None
    mode: str = ""
    surface: str = "input"
    trust_class: str = Field(default="user", alias="trustClass")
    active: bool | None = None
    expected_revision: int = Field(default=0, alias="expectedRevision", ge=0)


class LLMSecurityFinding(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rule_id: str = Field(alias="ruleId")
    category: str
    path: str
    fingerprint: str
    score: int
    start: int
    end: int
    decoded_depth: int = Field(default=0, alias="decodedDepth")
    normalized: bool = False


class LLMSecuritySandboxResponse(BaseModel):
    findings: list[LLMSecurityFinding] = Field(default_factory=list)
    decision: str
    mode: str
    score: int
    truncated: bool = False


class LLMSecurityEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    created_at: datetime = Field(alias="createdAt")
    mode: str
    source: str
    namespace: str = ""
    rule_id: str = Field(alias="ruleId")
    profile_id: str = Field(default="", alias="profileId")
    category: str
    decision: str
    surface: str
    trust_class: str = Field(alias="trustClass")
    fingerprint: str = ""
    correlation_id: str = Field(default="", alias="correlationId")
    id: int
    latency_us: int = Field(alias="latencyUs")
    policy_revision: int = Field(alias="policyRevision")
    matches: int
    score: int
    truncated: bool = False


class LLMSecurityEventsResponse(BaseModel):
    events: list[LLMSecurityEvent] = Field(default_factory=list)
