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
    """A running performance test task.

    Wire shape on POST /api/v1/perf/run is the single-field envelope
    ``{"taskId": "<uuid>"}``. We accept BOTH ``id`` and ``taskId`` as
    aliases so the model populates correctly regardless of which field
    a future server returns.
    """

    id: str = Field("", alias="taskId")
    status: str = ""
    created_at: Optional[str] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class PerfResult(BaseModel):
    """Result of a completed performance test.

    Mirrors ``runner.PerfTestResult`` on the server. ``task_id`` is the
    foreign key onto the originating perf task — use it to correlate a
    result with the value returned by ``PerfAPI.run()``. ``id`` is the
    result row's OWN UUID, distinct from ``task_id``.
    """

    id: str = ""
    task_id: Optional[str] = Field(None, alias="taskId")
    config_id: Optional[str] = Field(None, alias="configId")
    namespace: Optional[str] = None
    name: Optional[str] = None
    status: str = ""
    duration_ms: Optional[int] = Field(None, alias="durationMs")
    total_requests: Optional[int] = Field(None, alias="totalRequests")
    failed_requests: Optional[int] = Field(None, alias="failedRequests")
    total_vus: Optional[int] = Field(None, alias="totalVUs")
    started_at: Optional[str] = Field(None, alias="startedAt")
    completed_at: Optional[str] = Field(None, alias="completedAt")
    thresholds_passed: Optional[bool] = Field(None, alias="thresholdsPassed")
    thresholds_data: Optional[dict[str, Any]] = Field(None, alias="thresholdsData")
    metrics_data: Optional[dict[str, Any]] = Field(None, alias="metricsData")
    # Back-compat aliases (older servers / older code).
    metrics: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(None, alias="createdAt")
    finished_at: Optional[str] = Field(None, alias="finishedAt")

    model_config = {"populate_by_name": True, "extra": "ignore"}


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
