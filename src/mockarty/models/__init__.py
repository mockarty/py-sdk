# Copyright (c) 2026 Mockarty. All rights reserved.

"""Pydantic models for Mockarty API objects."""

from mockarty.models.common import (
    ErrorResponse,
    HealthResponse,
    MockLogs,
    Page,
    RequestLog,
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
from mockarty.models.condition import AssertAction, Condition
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
    CheckCompatibilityRequest,
    Contract,
    ContractConfig,
    ContractResult,
    ContractValidationRequest,
    ContractValidationResult,
    ContractViolation,
    DriftDetectionRequest,
    PactMessageContent,
    PactMessageInteraction,
    PactProviderState,
    PactVerifyRequest,
    ValidatePayloadRequest,
)
from mockarty.models.folders import MockFolder
from mockarty.models.fuzzing import (
    FuzzingConfig,
    FuzzingResult,
    FuzzingRun,
    QuarantineEntry,
)
from mockarty.models.generator import (
    GeneratorPreview,
    GeneratorRequest,
    GeneratorResponse,
)
from mockarty.models.imports import ImportResult
from mockarty.models.mock import (
    Callback,
    ContentResponse,
    Extract,
    Mock,
    OneOf,
    Proxy,
    SaveMockResponse,
)
from mockarty.models.recorder import RecorderEntry, RecorderSession
from mockarty.models.store import (
    DeleteFromStoreRequest,
    StoreData,
    StoreEntry,
)
from mockarty.models.testrun import TestRun
from mockarty.models.undefined import UndefinedRequest

__all__ = [
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
    # Condition models
    "AssertAction",
    "Condition",
    # Entity-search models
    "ENTITY_SEARCH_DEFAULT_LIMIT",
    "ENTITY_SEARCH_MAX_LIMIT",
    "ENTITY_TYPE_CHAOS_EXPERIMENT",
    "ENTITY_TYPE_CONTRACT_PACT",
    "ENTITY_TYPE_FUZZ_CONFIG",
    "ENTITY_TYPE_MOCK",
    "ENTITY_TYPE_PERF_CONFIG",
    "ENTITY_TYPE_TEST_PLAN",
    "EntitySearchResponse",
    "EntitySearchResult",
    # Common models
    "ErrorResponse",
    "HealthResponse",
    "MockLogs",
    "Page",
    "RequestLog",
    # Contract models
    "CheckCompatibilityRequest",
    "Contract",
    "ContractConfig",
    "ContractResult",
    "ContractValidationRequest",
    "ContractValidationResult",
    "ContractViolation",
    "DriftDetectionRequest",
    "PactMessageContent",
    "PactMessageInteraction",
    "PactProviderState",
    "PactVerifyRequest",
    "ValidatePayloadRequest",
    # Context models
    "GraphQLRequestContext",
    "GrpcRequestContext",
    "HttpRequestContext",
    "KafkaRequestContext",
    "MCPRequestContext",
    "RabbitMQRequestContext",
    "SmtpRequestContext",
    "SoapRequestContext",
    "SocketRequestContext",
    "SSERequestContext",
    # Folder models
    "MockFolder",
    # Fuzzing models
    "FuzzingConfig",
    "FuzzingResult",
    "FuzzingRun",
    "QuarantineEntry",
    # Generator models
    "GeneratorPreview",
    "GeneratorRequest",
    "GeneratorResponse",
    # Import models
    "ImportResult",
    # Mock models
    "Callback",
    "ContentResponse",
    "Extract",
    "Mock",
    "OneOf",
    "Proxy",
    "SaveMockResponse",
    # Recorder models
    "RecorderEntry",
    "RecorderSession",
    # Store models
    "DeleteFromStoreRequest",
    "StoreData",
    "StoreEntry",
    # Test run models
    "TestRun",
    # Undefined request models
    "UndefinedRequest",
]
