# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mockarty Python SDK -- Official client for the Mockarty multi-protocol mock server.

Quick start::

    from mockarty import MockartyClient, MockBuilder, AssertAction

    with MockartyClient(base_url="http://localhost:5770") as client:
        mock = (
            MockBuilder.http("/api/users/:id", "GET")
            .id("user-get")
            .respond(200, body={"id": "$.pathParam.id", "name": "$.fake.FirstName"})
            .build()
        )
        result = client.mocks.create(mock)
        print(f"Created mock: {result.mock.id}")
"""

from __future__ import annotations

from mockarty.api.agent_tasks import AgentTaskAPI, AsyncAgentTaskAPI
from mockarty.api.autonomous_missions import AsyncAutonomousMissionsAPI, AutonomousMissionsAPI
from mockarty.api.chaos import AsyncChaosAPI, ChaosAPI
from mockarty.api.discovery import (
    AsyncDiscoveryAPI,
    DiscoveryAPI,
    DiscoveryCase,
    SyncResult,
)
from mockarty.api.economics import AsyncEconomicsAPI, EconomicsAPI
from mockarty.api.entity_search import AsyncEntitySearchAPI, EntitySearchAPI
from mockarty.api.environments import AsyncEnvironmentAPI, EnvironmentAPI
from mockarty.api.experience import AsyncExperienceAPI, ExperienceAPI
from mockarty.api.external_runs import (
    EXTERNAL_RUN_SCHEMA_VERSION,
    EXTERNAL_STATUS_BROKEN,
    EXTERNAL_STATUS_CANCELLED,
    EXTERNAL_STATUS_FAILED,
    EXTERNAL_STATUS_PASSED,
    EXTERNAL_STATUS_SKIPPED,
    AsyncExternalRunsAPI,
    ExternalRunsAPI,
)
from mockarty.api.folders import AsyncFolderAPI, FolderAPI
from mockarty.api.llm_security import AsyncLLMSecurityAPI, LLMSecurityAPI
from mockarty.api.mcp import (
    AsyncMCPClient,
    MCPClient,
    MCPTool,
    MCPToolResult,
    MockartyMCPError,
)
from mockarty.api.namespace_settings import (
    AsyncNamespaceSettingsAPI,
    NamespaceSettingsAPI,
)
from mockarty.api.proxy import AsyncProxyAPI, ProxyAPI
from mockarty.api.stats import AsyncStatsAPI, StatsAPI
from mockarty.api.tags import AsyncTagAPI, TagAPI
from mockarty.api.testplans import (
    AsyncTestPlansAPI,
    PlanNotFoundError,
    PreconditionFailedError,
    RunCancelledError,
    RunFailedError,
    TestPlanError,
    TestPlansAPI,
    WebhookDeliveryError,
)
from mockarty.api.undefined import AsyncUndefinedAPI, UndefinedAPI
from mockarty.async_client import AsyncMockartyClient
from mockarty.builders.load_builder import LoadRequest, LoadTest
from mockarty.builders.mock_builder import MockBuilder, OneOfBuilder
from mockarty.builders.uitest_builder import UITest
from mockarty.client import MockartyClient
from mockarty.errors import (
    MockartyAPIError,
    MockartyConflictError,
    MockartyConnectionError,
    MockartyError,
    MockartyExternalError,
    MockartyForbiddenError,
    MockartyNotFoundError,
    MockartyRateLimitError,
    MockartyServerError,
    MockartyTaskError,
    MockartyTimeoutError,
    MockartyUnauthorizedError,
    MockartyUnavailableError,
    MockartyValidationError,
)
from mockarty.models.chaos import (
    AffectedResource,
    ChaosConnectionResult,
    ChaosEvent,
    ChaosExperiment,
    ChaosMetrics,
    ChaosOperatorStatus,
    ChaosPreset,
    ChaosProfile,
    ChaosReport,
    ChaosResults,
    ChaosSnapshot,
    FaultConfig,
    HealthCheckResult,
    InfraProfile,
    MetricsSnapshot,
    MinMaxAvg,
    PhaseMetrics,
    SafetyConfig,
    ScheduleConfig,
    SteadyState,
    SteadyStateCheck,
    TargetConfig,
    TimelineEvent,
)
from mockarty.models.common import (
    AbortCriterion,
    Collection,
    ErrorResponse,
    HealthResponse,
    MockLogs,
    Page,
    PerfComparison,
    PerfConfig,
    PerfOptions,
    PerfResult,
    PerfStage,
    PerfTask,
    RequestLog,
    TestRunResult,
)
from mockarty.models.autonomous_missions import (
    AutonomousMission,
    AutonomousMissionBudget,
    AutonomousMissionBudgetHint,
    AutonomousMissionContextRef,
    AutonomousMissionFlow,
    AutonomousMissionListResponse,
    AutonomousMissionSubmitRequest,
    AutonomousMissionSubmitResponse,
    MissionEffectiveSetting,
    MissionEffectiveSettings,
    MissionCancelRequest,
    MissionControlReceipt,
    MissionControlResponse,
    MissionStartRequest,
    MissionStartResponse,
    UnifiedMission,
)
from mockarty.models.condition import AssertAction, Condition
from mockarty.models.contexts import (
    GraphQLRequestContext,
    GrpcRequestContext,
    HttpRequestContext,
    KafkaRequestContext,
    MCPRequestContext,
    RabbitMQRequestContext,
    SmtpRequestContext,
    SoapRequestContext,
    SocketRequestContext,
    SSERequestContext,
)
from mockarty.models.contract import (
    Contract,
    ContractConfig,
    ContractResult,
    ContractValidationRequest,
    ContractValidationResult,
    ContractViolation,
)
from mockarty.models.economics import (
    LLMBudget,
    LLMBudgetList,
    LLMPrice,
    LLMPriceList,
    LLMUsageCost,
    LLMUsageForecast,
    LLMUsageGroup,
    LLMUsageOutcomeCost,
    LLMUsageReconciliation,
    LLMUsageRefund,
    LLMUsageReport,
    LLMUsageTotals,
    ResourcePrice,
    ResourcePriceList,
    ResourceUsageTotal,
)
from mockarty.models.entity_search import (
    ENTITY_SEARCH_DEFAULT_LIMIT,
    ENTITY_SEARCH_MAX_LIMIT,
    ENTITY_TYPE_CHAOS_EXPERIMENT,
    ENTITY_TYPE_CONTRACT_PACT,
    ENTITY_TYPE_FUZZ_CONFIG,
    ENTITY_TYPE_MOCK,
    ENTITY_TYPE_PERF_CONFIG,
    ENTITY_TYPE_TEST_PLAN,
    EntitySearchResponse,
    EntitySearchResult,
)
from mockarty.models.experience import (
    EXPERIENCE_KIND_DEFECT_ROOT_CAUSE,
    EXPERIENCE_KIND_MISSION_LESSON,
    EXPERIENCE_KIND_PITFALL,
    EXPERIENCE_KIND_PRODUCT_FACT,
    ExperienceItem,
    ExperienceRecordResponse,
    ExperienceReviewDetail,
    ExperienceReviewItem,
    ExperienceReviewMutation,
    ExperienceReviewPage,
    ExperienceReviewRelation,
    ExperienceReviewResponse,
    ExperienceSearchResponse,
)
from mockarty.models.folders import MockFolder
from mockarty.models.fuzzing import FuzzingConfig, FuzzingResult, FuzzingRun
from mockarty.models.generator import (
    GeneratorPreview,
    GeneratorRequest,
    GeneratorResponse,
)
from mockarty.models.imports import ImportResult
from mockarty.models.llm_security import (
    LLMSecurityDelegation,
    LLMSecurityEvent,
    LLMSecurityEventsResponse,
    LLMSecurityFinding,
    LLMSecurityPolicy,
    LLMSecurityPolicyDocument,
    LLMSecurityPolicyRequest,
    LLMSecurityPolicyResponse,
    LLMSecurityRestrictions,
    LLMSecuritySandboxRequest,
    LLMSecuritySandboxResponse,
    LLMSecuritySource,
)
from mockarty.models.mock import (
    Callback,
    ContentResponse,
    Extract,
    Mock,
    MockVersion,
    OneOf,
    Proxy,
    ResponseScript,
    SaveMockResponse,
)
from mockarty.models.recorder import RecorderEntry, RecorderSession
from mockarty.models.store import DeleteFromStoreRequest, StoreData, StoreEntry
from mockarty.models.testplan import (
    AdHocItem,
    AdHocRunResponse,
    AllureReport,
    CreateAdHocRunRequest,
    ItemSummary,
    PatchPlanRequest,
    PlanItemState,
    PlanRunStatus,
    RunEvent,
    Schedule,
    TestPlan,
    TestPlanItem,
    TestPlanRun,
    UnifiedItemResult,
    UnifiedReport,
    UnifiedReportCounts,
    Webhook,
)
from mockarty.models.testrun import TestRun
from mockarty.models.undefined import UndefinedRequest

__version__ = "0.3.0"

__all__ = [  # noqa: RUF022 - grouped by public API domain for discoverability
    # Clients
    "MockartyClient",
    "AsyncMockartyClient",
    "LLMSecurityAPI",
    "AsyncLLMSecurityAPI",
    "LLMSecurityDelegation",
    "LLMSecurityEvent",
    "LLMSecurityEventsResponse",
    "LLMSecurityFinding",
    "LLMSecurityPolicy",
    "LLMSecurityPolicyDocument",
    "LLMSecurityPolicyRequest",
    "LLMSecurityPolicyResponse",
    "LLMSecurityRestrictions",
    "LLMSecuritySandboxRequest",
    "LLMSecuritySandboxResponse",
    "LLMSecuritySource",
    "ExperienceAPI",
    "AsyncExperienceAPI",
    "EconomicsAPI",
    "AsyncEconomicsAPI",
    "LLMPrice",
    "LLMPriceList",
    "LLMBudget",
    "LLMBudgetList",
    "LLMUsageCost",
    "LLMUsageGroup",
    "LLMUsageForecast",
    "LLMUsageOutcomeCost",
    "LLMUsageReconciliation",
    "LLMUsageReport",
    "LLMUsageRefund",
    "LLMUsageTotals",
    "ResourcePrice",
    "ResourcePriceList",
    "ResourceUsageTotal",
    "ExperienceItem",
    "ExperienceSearchResponse",
    "ExperienceRecordResponse",
    "ExperienceReviewDetail",
    "ExperienceReviewItem",
    "ExperienceReviewMutation",
    "ExperienceReviewPage",
    "ExperienceReviewRelation",
    "ExperienceReviewResponse",
    "EXPERIENCE_KIND_MISSION_LESSON",
    "EXPERIENCE_KIND_PITFALL",
    "EXPERIENCE_KIND_PRODUCT_FACT",
    "EXPERIENCE_KIND_DEFECT_ROOT_CAUSE",
    # Builders
    "MockBuilder",
    "OneOfBuilder",
    "LoadTest",
    "UITest",
    "LoadRequest",
    # Core models
    "Mock",
    "MockVersion",
    "ContentResponse",
    "ResponseScript",
    "OneOf",
    "Proxy",
    "Callback",
    "Extract",
    "SaveMockResponse",
    # Conditions
    "Condition",
    "AssertAction",
    # Protocol contexts
    "HttpRequestContext",
    "GrpcRequestContext",
    "MCPRequestContext",
    "SocketRequestContext",
    "SoapRequestContext",
    "GraphQLRequestContext",
    "SSERequestContext",
    "KafkaRequestContext",
    "RabbitMQRequestContext",
    "SmtpRequestContext",
    # Common models
    "Page",
    "HealthResponse",
    "ErrorResponse",
    "RequestLog",
    "MockLogs",
    "Collection",
    "TestRunResult",
    "PerfConfig",
    "PerfTask",
    "PerfResult",
    "PerfComparison",
    # Store models
    "StoreEntry",
    "StoreData",
    "DeleteFromStoreRequest",
    # Generator models
    "GeneratorRequest",
    "GeneratorPreview",
    "GeneratorResponse",
    # Chaos models
    "AffectedResource",
    "ChaosConnectionResult",
    "ChaosEvent",
    "ChaosExperiment",
    "ChaosMetrics",
    "ChaosOperatorStatus",
    "ChaosPreset",
    "ChaosProfile",
    "ChaosReport",
    "ChaosResults",
    "ChaosSnapshot",
    "FaultConfig",
    "HealthCheckResult",
    "InfraProfile",
    "MetricsSnapshot",
    "MinMaxAvg",
    "PhaseMetrics",
    "SafetyConfig",
    "ScheduleConfig",
    "SteadyState",
    "SteadyStateCheck",
    "TargetConfig",
    "TimelineEvent",
    # Fuzzing models
    "FuzzingConfig",
    "FuzzingRun",
    "FuzzingResult",
    # Contract models
    "Contract",
    "ContractConfig",
    "ContractResult",
    "ContractValidationRequest",
    "ContractValidationResult",
    "ContractViolation",
    # Recorder models
    "RecorderSession",
    "RecorderEntry",
    # Import models
    "ImportResult",
    # Test run models
    "TestRun",
    # Performance config models
    "AbortCriterion",
    "PerfOptions",
    "PerfStage",
    # Test plan models
    "TestPlan",
    "TestPlanItem",
    "TestPlanRun",
    "PlanItemState",
    "PlanRunStatus",
    "Schedule",
    "Webhook",
    "RunEvent",
    "ItemSummary",
    # Test plan TP-6b models
    "PatchPlanRequest",
    "AdHocItem",
    "CreateAdHocRunRequest",
    "AdHocRunResponse",
    "AllureReport",
    "UnifiedReport",
    "UnifiedReportCounts",
    "UnifiedItemResult",
    # Folder models
    "MockFolder",
    # Undefined request models
    "UndefinedRequest",
    # API resource classes
    "ChaosAPI",
    "AsyncChaosAPI",
    "TagAPI",
    "AsyncTagAPI",
    "FolderAPI",
    "AsyncFolderAPI",
    "UndefinedAPI",
    "AsyncUndefinedAPI",
    "StatsAPI",
    "AsyncStatsAPI",
    "AgentTaskAPI",
    "AsyncAgentTaskAPI",
    "AsyncAutonomousMissionsAPI",
    "AutonomousMissionsAPI",
    "AutonomousMission",
    "AutonomousMissionBudget",
    "AutonomousMissionBudgetHint",
    "AutonomousMissionContextRef",
    "AutonomousMissionFlow",
    "AutonomousMissionListResponse",
    "AutonomousMissionSubmitRequest",
    "AutonomousMissionSubmitResponse",
    "MissionEffectiveSetting",
    "MissionEffectiveSettings",
    "MissionCancelRequest",
    "MissionControlReceipt",
    "MissionControlResponse",
    "MissionStartRequest",
    "MissionStartResponse",
    "UnifiedMission",
    "NamespaceSettingsAPI",
    "AsyncNamespaceSettingsAPI",
    "ProxyAPI",
    "AsyncProxyAPI",
    "EnvironmentAPI",
    "AsyncEnvironmentAPI",
    "EntitySearchAPI",
    "AsyncEntitySearchAPI",
    # Entity-search models + constants
    "EntitySearchResponse",
    "EntitySearchResult",
    "ENTITY_SEARCH_DEFAULT_LIMIT",
    "ENTITY_SEARCH_MAX_LIMIT",
    "ENTITY_TYPE_CHAOS_EXPERIMENT",
    "ENTITY_TYPE_CONTRACT_PACT",
    "ENTITY_TYPE_FUZZ_CONFIG",
    "ENTITY_TYPE_MOCK",
    "ENTITY_TYPE_PERF_CONFIG",
    "ENTITY_TYPE_TEST_PLAN",
    "TestPlansAPI",
    "AsyncTestPlansAPI",
    "ExternalRunsAPI",
    "AsyncExternalRunsAPI",
    # Discovery (test-inventory sync)
    "DiscoveryAPI",
    "AsyncDiscoveryAPI",
    "DiscoveryCase",
    "SyncResult",
    "EXTERNAL_RUN_SCHEMA_VERSION",
    "EXTERNAL_STATUS_PASSED",
    "EXTERNAL_STATUS_FAILED",
    "EXTERNAL_STATUS_BROKEN",
    "EXTERNAL_STATUS_SKIPPED",
    "EXTERNAL_STATUS_CANCELLED",
    # Test plan errors
    "TestPlanError",
    "PlanNotFoundError",
    "RunFailedError",
    "RunCancelledError",
    "WebhookDeliveryError",
    "PreconditionFailedError",
    # Errors
    "MockartyError",
    "MockartyAPIError",
    "MockartyValidationError",
    "MockartyNotFoundError",
    "MockartyUnauthorizedError",
    "MockartyForbiddenError",
    "MockartyConflictError",
    "MockartyRateLimitError",
    "MockartyServerError",
    "MockartyUnavailableError",
    "MockartyExternalError",
    "MockartyConnectionError",
    "MockartyTimeoutError",
    "MockartyTaskError",
    "MCPClient",
    "AsyncMCPClient",
    "MCPTool",
    "MCPToolResult",
    "MockartyMCPError",
]
