# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Pydantic models for Mockarty API objects."""

from mockarty.models.common import (
    ErrorResponse,
    HealthResponse,
    MockLogs,
    Page,
    RequestLog,
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
from mockarty.models.store import (
    DeleteFromStoreRequest,
    StoreData,
    StoreEntry,
)
from mockarty.models.tags import Tag
from mockarty.models.templates import TemplateFile
from mockarty.models.testrun import TestRun
from mockarty.models.undefined import UndefinedRequest

__all__ = [
    # Condition models
    "AssertAction",
    "Condition",
    # Common models
    "ErrorResponse",
    "HealthResponse",
    "MockLogs",
    "Page",
    "RequestLog",
    # Contract models
    "Contract",
    "ContractConfig",
    "ContractResult",
    "ContractValidationRequest",
    "ContractValidationResult",
    "ContractViolation",
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
    # Tag models
    "Tag",
    # Template models
    "TemplateFile",
    # Test run models
    "TestRun",
    # Undefined request models
    "UndefinedRequest",
]
