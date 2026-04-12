# Copyright (c) 2026 Mockarty. All rights reserved.

"""Contract testing models for API contract validation."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ContractConfig(BaseModel):
    """A contract testing configuration."""

    id: Optional[str] = None
    name: Optional[str] = None
    spec: Optional[str] = None
    spec_url: Optional[str] = Field(None, alias="specUrl")
    target_url: Optional[str] = Field(None, alias="targetUrl")
    namespace: Optional[str] = None
    schedule: Optional[str] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


# Keep backward-compatible alias
Contract = ContractConfig


class ContractValidationRequest(BaseModel):
    """Request for validate-mocks and verify-provider operations."""

    spec_content: Optional[str] = Field(None, alias="specContent")
    spec_url: Optional[str] = Field(None, alias="specUrl")
    spec_type: Optional[str] = Field(None, alias="specType")
    content_type: Optional[str] = Field(None, alias="contentType")
    base_url: Optional[str] = Field(None, alias="baseUrl")
    namespace: Optional[str] = None
    mock_ids: Optional[list[str]] = Field(None, alias="mockIds")
    tags: Optional[list[str]] = None
    headers: Optional[dict[str, str]] = None
    timeout: Optional[int] = None

    model_config = {"populate_by_name": True}


class CheckCompatibilityRequest(BaseModel):
    """Request for backwards-compatibility checking between two spec versions."""

    old_spec_content: str = Field(alias="oldSpecContent")
    old_content_type: Optional[str] = Field(None, alias="oldContentType")
    new_spec_content: str = Field(alias="newSpecContent")
    new_content_type: Optional[str] = Field(None, alias="newContentType")

    model_config = {"populate_by_name": True}


class ValidatePayloadRequest(BaseModel):
    """Request for single payload validation against a spec schema."""

    payload: Any
    spec_content: str = Field(alias="specContent")
    content_type: Optional[str] = Field(None, alias="contentType")
    spec_url: Optional[str] = Field(None, alias="specUrl")
    endpoint: str
    status_code: str = Field(alias="statusCode")

    model_config = {"populate_by_name": True}


class DriftDetectionRequest(BaseModel):
    """Request for drift detection between mocks and live service."""

    base_url: str = Field(alias="baseUrl")
    headers: Optional[dict[str, str]] = None
    namespace: Optional[str] = None
    mock_ids: Optional[list[str]] = Field(None, alias="mockIds")
    tags: Optional[list[str]] = None
    timeout: Optional[int] = None

    model_config = {"populate_by_name": True}


class PactVerifyRequest(BaseModel):
    """Request for pact provider verification."""

    pact_id: Optional[str] = Field(None, alias="pactId")
    pact_content: Optional[str] = Field(None, alias="pactContent")
    provider_base_url: str = Field(alias="providerBaseUrl")
    provider_state_url: Optional[str] = Field(None, alias="providerStateUrl")
    message_callback_url: Optional[str] = Field(None, alias="messageCallbackUrl")
    headers: Optional[dict[str, str]] = None
    timeout: Optional[int] = None

    model_config = {"populate_by_name": True}


class ContractViolation(BaseModel):
    """A single violation found during contract validation."""

    path: Optional[str] = None
    message: Optional[str] = None
    severity: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None


class ContractValidationResult(BaseModel):
    """Result of a contract validation run."""

    id: Optional[str] = None
    contract_id: Optional[str] = Field(None, alias="contractId")
    status: Optional[str] = None
    violations: Optional[int] = None
    details: Optional[list[ContractViolation]] = None
    validated_at: Optional[str] = Field(None, alias="validatedAt")

    model_config = {"populate_by_name": True}


class ContractResult(BaseModel):
    """A stored contract testing result."""

    id: Optional[str] = None
    config_id: Optional[str] = Field(None, alias="configId")
    status: Optional[str] = None
    violations: Optional[int] = None
    details: Optional[list[ContractViolation]] = None
    created_at: Optional[str] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class PactProviderState(BaseModel):
    """A provider state required by a message interaction."""

    name: str
    params: Optional[dict[str, Any]] = None


class PactMessageContent(BaseModel):
    """A single request or response body inside a synchronous message
    interaction. For asynchronous messages only `contents`/`metadata` apply."""

    contents: Optional[Any] = None
    metadata: Optional[dict[str, Any]] = None


class PactMessageInteraction(BaseModel):
    """An async or sync message interaction from a v4 pact file.

    Async messages populate `contents` + `metadata`. Synchronous messages
    additionally populate `response` with one or more reply variants.
    """

    type: Optional[str] = None
    description: str
    provider_states: Optional[list[PactProviderState]] = Field(
        None, alias="providerStates"
    )
    contents: Optional[Any] = None
    metadata: Optional[dict[str, Any]] = None
    response: Optional[list[PactMessageContent]] = None

    model_config = {"populate_by_name": True}
