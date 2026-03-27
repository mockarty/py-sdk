# Copyright (c) 2026 Mockarty. All rights reserved.

"""Common models shared across the SDK: pagination, health, errors."""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Paginated list response from the API."""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50


class HealthResponse(BaseModel):
    """Response from the /health endpoint."""

    status: str = ""
    release_id: Optional[str] = Field(None, alias="releaseId")
    uptime: Optional[str] = None
    checks: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class ErrorResponse(BaseModel):
    """Standard error response from the API."""

    error: str = ""


class RequestLog(BaseModel):
    """A single request log entry."""

    id: Optional[str] = None
    called_at: Optional[str] = Field(None, alias="calledAt")
    req: Optional[Any] = None
    response: Optional[Any] = None

    model_config = {"populate_by_name": True}


class MockLogs(BaseModel):
    """Collection of request logs for a mock."""

    logs: list[RequestLog] = Field(default_factory=list)
    total: int = 0


class PerfConfig(BaseModel):
    """Performance test configuration."""

    name: Optional[str] = None
    script: Optional[str] = None
    vus: Optional[int] = None
    duration: Optional[str] = None
    stages: Optional[list[dict[str, Any]]] = None
    thresholds: Optional[dict[str, Any]] = None
    environment: Optional[dict[str, str]] = None

    model_config = {"populate_by_name": True}


class PerfTask(BaseModel):
    """A running performance test task."""

    id: str = ""
    status: str = ""
    created_at: Optional[str] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class PerfResult(BaseModel):
    """Result of a completed performance test."""

    id: str = ""
    name: Optional[str] = None
    status: str = ""
    metrics: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    finished_at: Optional[str] = Field(None, alias="finishedAt")
    duration_ms: Optional[int] = Field(None, alias="durationMs")

    model_config = {"populate_by_name": True}


class PerfComparison(BaseModel):
    """Comparison between multiple performance test results."""

    results: list[PerfResult] = Field(default_factory=list)
    diff: Optional[dict[str, Any]] = None


class Collection(BaseModel):
    """API Tester collection."""

    id: Optional[str] = None
    namespace: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    protocol: Optional[str] = None
    collection_type: Optional[str] = Field(None, alias="collectionType")
    is_shared: Optional[bool] = Field(None, alias="isShared")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class TestRunResult(BaseModel):
    """Result of executing a test collection."""

    id: Optional[str] = None
    status: str = ""
    total_tests: Optional[int] = Field(None, alias="totalTests")
    passed: Optional[int] = None
    failed: Optional[int] = None
    skipped: Optional[int] = None
    duration_ms: Optional[int] = Field(None, alias="durationMs")
    results: Optional[list[dict[str, Any]]] = None

    model_config = {"populate_by_name": True}
