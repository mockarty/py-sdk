# Copyright (c) 2024-2026 Mockarty. All rights reserved.

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
from mockarty.api.environments import AsyncEnvironmentAPI, EnvironmentAPI
from mockarty.api.folders import AsyncFolderAPI, FolderAPI
from mockarty.api.namespace_settings import (
    AsyncNamespaceSettingsAPI,
    NamespaceSettingsAPI,
)
from mockarty.api.proxy import AsyncProxyAPI, ProxyAPI
from mockarty.api.stats import AsyncStatsAPI, StatsAPI
from mockarty.api.tags import AsyncTagAPI, TagAPI
from mockarty.api.undefined import AsyncUndefinedAPI, UndefinedAPI
from mockarty.async_client import AsyncMockartyClient
from mockarty.builders.mock_builder import MockBuilder, OneOfBuilder
from mockarty.client import MockartyClient
from mockarty.errors import (
    MockartyAPIError,
    MockartyConflictError,
    MockartyConnectionError,
    MockartyError,
    MockartyForbiddenError,
    MockartyNotFoundError,
    MockartyRateLimitError,
    MockartyServerError,
    MockartyTimeoutError,
    MockartyUnauthorizedError,
)
from mockarty.models.common import (
    Collection,
    ErrorResponse,
    HealthResponse,
    MockLogs,
    Page,
    PerfComparison,
    PerfConfig,
    PerfResult,
    PerfTask,
    RequestLog,
    TestRunResult,
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
from mockarty.models.folders import MockFolder
from mockarty.models.fuzzing import FuzzingConfig, FuzzingResult, FuzzingRun
from mockarty.models.generator import GeneratorPreview, GeneratorRequest, GeneratorResponse
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
from mockarty.models.store import DeleteFromStoreRequest, StoreData, StoreEntry
from mockarty.models.tags import Tag
from mockarty.models.templates import TemplateFile
from mockarty.models.testrun import TestRun
from mockarty.models.undefined import UndefinedRequest

__version__ = "0.1.0"

__all__ = [
    # Clients
    "MockartyClient",
    "AsyncMockartyClient",
    # Builders
    "MockBuilder",
    "OneOfBuilder",
    # Core models
    "Mock",
    "ContentResponse",
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
    # Template models
    "TemplateFile",
    # Import models
    "ImportResult",
    # Test run models
    "TestRun",
    # Tag models
    "Tag",
    # Folder models
    "MockFolder",
    # Undefined request models
    "UndefinedRequest",
    # API resource classes
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
    "NamespaceSettingsAPI",
    "AsyncNamespaceSettingsAPI",
    "ProxyAPI",
    "AsyncProxyAPI",
    "EnvironmentAPI",
    "AsyncEnvironmentAPI",
    # Errors
    "MockartyError",
    "MockartyAPIError",
    "MockartyNotFoundError",
    "MockartyUnauthorizedError",
    "MockartyForbiddenError",
    "MockartyConflictError",
    "MockartyRateLimitError",
    "MockartyServerError",
    "MockartyConnectionError",
    "MockartyTimeoutError",
]
