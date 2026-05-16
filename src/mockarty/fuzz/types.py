# Copyright (c) 2026 Mockarty. All rights reserved.

"""Pydantic v2 models matching Mockarty's fuzz JSON config schema.

The models here are the single source of truth for what the transpiler
serialises. They mirror Go's ``internal/fuzzing/config.go`` field names
and casing (camelCase on the wire) so the admin server / CLI can
consume the JSON without an intermediate adapter.

Phase 1 covers the FuzzConfig + FuzzOptions + FuzzSeedRequest triple
that drives a single run. Schedules and quarantine entries are out of
scope here — those live on the existing ``mockarty.api.fuzzing``
HTTP surface.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Enums (string-typed for JSON-friendly serialisation) ───────────────


class Strategy(str, Enum):
    """Fuzzing strategy — drives which generators run.

    Mirrors Go's ``StrategyMutation`` / ``StrategySecurity`` /
    ``StrategySchemaAware`` / ``StrategyAll`` constants.
    """

    MUTATION = "mutation"
    SECURITY = "security"
    SCHEMA_AWARE = "schema_aware"
    ALL = "all"


class SourceType(str, Enum):
    """Where the seed corpus came from. Free-form on the server, but
    we surface the canonical values for IDE auto-complete.
    """

    MANUAL = "manual"
    OPENAPI = "openapi"
    CURL = "curl"
    COLLECTION = "collection"
    RECORDER = "recorder"
    MOCK = "mock"
    GRPC = "grpc"
    GRAPHQL = "graphql"


# ── Wire models ─────────────────────────────────────────────────────────


class FuzzSeedRequest(BaseModel):
    """One seed request inside the corpus.

    Mirrors Go's ``FuzzSeedRequest`` 1:1 — extra fields are dropped on
    serialise because the server doesn't accept unknown keys for some
    endpoints.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = ""
    method: str = "GET"
    url: str = ""
    path: str = ""
    body: str = ""
    content_type: str = Field(default="", alias="contentType")
    headers: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict, alias="queryParams")
    path_params: Dict[str, str] = Field(default_factory=dict, alias="pathParams")


class FuzzOptions(BaseModel):
    """Tunable engine options. Empty fields are dropped on dump so the
    JSON config stays small.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    max_duration: str = Field(default="", alias="maxDuration")
    timeout_per_req: str = Field(default="", alias="timeoutPerReq")
    max_requests: int = Field(default=0, alias="maxRequests")
    max_rps: int = Field(default=0, alias="maxRps")
    concurrency: int = 0
    mutation_depth: int = Field(default=0, alias="mutationDepth")
    follow_redirects: bool = Field(default=False, alias="followRedirects")
    stop_on_critical: bool = Field(default=False, alias="stopOnCritical")
    verify_findings: bool = Field(default=False, alias="verifyFindings")
    auth_header: str = Field(default="", alias="authHeader")
    custom_headers: Dict[str, str] = Field(default_factory=dict, alias="customHeaders")
    include_routes: List[str] = Field(default_factory=list, alias="includeRoutes")
    exclude_routes: List[str] = Field(default_factory=list, alias="excludeRoutes")
    status_code_alerts: List[int] = Field(
        default_factory=list, alias="statusCodeAlerts"
    )
    response_time_alert: int = Field(default=0, alias="responseTimeAlert")
    detect_patterns: List[str] = Field(default_factory=list, alias="detectPatterns")
    # gRPC
    grpc_address: str = Field(default="", alias="grpcAddress")
    grpc_services: List[str] = Field(default_factory=list, alias="grpcServices")
    grpc_methods: List[str] = Field(default_factory=list, alias="grpcMethods")
    grpc_use_tls: bool = Field(default=False, alias="grpcUseTls")
    # GraphQL
    graphql_endpoint: str = Field(default="", alias="graphqlEndpoint")
    graphql_path: str = Field(default="", alias="graphqlPath")
    # LLM
    llm_enabled: bool = Field(default=False, alias="llmEnabled")
    llm_profile_id: str = Field(default="", alias="llmProfileId")
    # Baseline
    baseline_run_id: str = Field(default="", alias="baselineRunId")


class FuzzConfig(BaseModel):
    """Top-level fuzz config — exactly the shape the server expects on
    ``POST /api/v1/fuzzing/run``.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = ""
    name: str = ""
    namespace: str = ""
    user_id: str = Field(default="", alias="userId")
    parent_id: Optional[str] = Field(default=None, alias="parentId")
    source_type: str = Field(default=SourceType.MANUAL.value, alias="sourceType")
    target_base_url: str = Field(default="", alias="targetBaseUrl")
    strategy: str = Strategy.ALL.value
    seed_requests: List[FuzzSeedRequest] = Field(
        default_factory=list, alias="seedRequests"
    )
    options: FuzzOptions = Field(default_factory=FuzzOptions)
    payload_categories: List[str] = Field(
        default_factory=list, alias="payloadCategories"
    )
    openapi_spec: Optional[str] = Field(default=None, alias="openapiSpec")
    sort_order: int = Field(default=0, alias="sortOrder")
    is_folder: bool = Field(default=False, alias="isFolder")

    # SDK-only fields (not in server FuzzConfig) — used by transpiler
    # to drive reporter selection / stop-on-finding behaviour.
    sdk_meta: Dict[str, Any] = Field(default_factory=dict, alias="_sdkMeta")
