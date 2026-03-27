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
    created_at: Optional[int] = Field(None, alias="createdAt")
    updated_at: Optional[int] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


# Keep backward-compatible alias
Contract = ContractConfig


class ContractValidationRequest(BaseModel):
    """Request for contract validation operations."""

    spec: Optional[str] = None
    spec_url: Optional[str] = Field(None, alias="specUrl")
    namespace: Optional[str] = None
    mock_ids: Optional[list[str]] = Field(None, alias="mockIds")
    target_url: Optional[str] = Field(None, alias="targetUrl")
    payload: Optional[dict[str, Any]] = None

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
    validated_at: Optional[int] = Field(None, alias="validatedAt")

    model_config = {"populate_by_name": True}


class ContractResult(BaseModel):
    """A stored contract testing result."""

    id: Optional[str] = None
    config_id: Optional[str] = Field(None, alias="configId")
    status: Optional[str] = None
    violations: Optional[int] = None
    details: Optional[list[ContractViolation]] = None
    created_at: Optional[int] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}
