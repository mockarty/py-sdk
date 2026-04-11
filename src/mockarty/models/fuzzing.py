# Copyright (c) 2026 Mockarty. All rights reserved.

"""Fuzzing models for API security and reliability testing."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class FuzzingConfig(BaseModel):
    """Configuration for a fuzzing test."""

    id: Optional[str] = None
    name: Optional[str] = None
    namespace: Optional[str] = None
    target_base_url: Optional[str] = Field(None, alias="targetBaseUrl")
    source_type: Optional[str] = Field(None, alias="sourceType")
    strategy: Optional[str] = None
    payload_categories: Optional[list[str]] = Field(None, alias="payloadCategories")
    seed_requests: Optional[Any] = Field(None, alias="seedRequests")
    options: Optional[Any] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class FuzzingRun(BaseModel):
    """A running fuzzing test instance."""

    id: Optional[str] = None
    status: Optional[str] = None


class FuzzingResult(BaseModel):
    """Result of a completed fuzzing test."""

    id: Optional[str] = None
    config_id: Optional[str] = Field(None, alias="configId")
    namespace: Optional[str] = None
    status: Optional[str] = None
    strategy: Optional[str] = None
    total_requests: Optional[int] = Field(None, alias="totalRequests")
    total_findings: Optional[int] = Field(None, alias="totalFindings")
    critical_findings: Optional[int] = Field(None, alias="criticalFindings")
    high_findings: Optional[int] = Field(None, alias="highFindings")
    medium_findings: Optional[int] = Field(None, alias="mediumFindings")
    low_findings: Optional[int] = Field(None, alias="lowFindings")
    info_findings: Optional[int] = Field(None, alias="infoFindings")
    started_at: Optional[str] = Field(None, alias="startedAt")
    completed_at: Optional[str] = Field(None, alias="completedAt")
    duration_ms: Optional[int] = Field(None, alias="durationMs")

    model_config = {"populate_by_name": True}


class QuarantineEntry(BaseModel):
    """A quarantine rule for suppressing known false-positive fuzzing findings."""

    id: Optional[str] = None
    namespace: Optional[str] = None
    fingerprint: Optional[str] = None
    category: Optional[str] = None
    endpoint_pattern: Optional[str] = Field(None, alias="endpointPattern")
    title: Optional[str] = None
    reason: Optional[str] = None
    source_finding_id: Optional[str] = Field(None, alias="sourceFindingId")
    created_by: Optional[str] = Field(None, alias="createdBy")
    created_at: Optional[str] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}
