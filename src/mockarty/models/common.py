# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Common models shared across the SDK: pagination, health, errors."""

from __future__ import annotations

import json
from typing import Any, Generic, Optional, TypeVar

from pydantic import AliasChoices, BaseModel, Field

T = TypeVar("T")


class _ForwardCompatibleModel(BaseModel):
    """Preserve future fields without letting extras shadow typed fields.

    Pydantic's ``extra='allow'`` map is intentionally mutable. Its default
    serializer lets an entry such as ``parentId`` replace an omitted typed
    field and drops unknown ``null`` values when ``exclude_none=True``. Saved
    perf configs need the inverse contract: typed names and aliases are always
    reserved, while genuinely unknown values round-trip losslessly.
    """

    model_config = {"populate_by_name": True, "extra": "allow"}

    @classmethod
    def _protected_json_names(cls) -> set[str]:
        names: set[str] = set()
        for field_name, field in cls.model_fields.items():
            names.add(field_name)
            for alias in (field.alias, field.serialization_alias):
                if isinstance(alias, str):
                    names.add(alias)
            validation_alias = field.validation_alias
            if isinstance(validation_alias, str):
                names.add(validation_alias)
            elif isinstance(validation_alias, AliasChoices):
                names.update(choice for choice in validation_alias.choices if isinstance(choice, str))
        return names

    @staticmethod
    def _safe_copy_value(value: Any) -> Any:
        if isinstance(value, _ForwardCompatibleModel):
            return value._safe_copy_for_dump()
        if isinstance(value, list):
            return [_ForwardCompatibleModel._safe_copy_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(_ForwardCompatibleModel._safe_copy_value(item) for item in value)
        if isinstance(value, dict):
            return {
                key: _ForwardCompatibleModel._safe_copy_value(item)
                for key, item in value.items()
            }
        return value

    def _safe_copy_for_dump(self) -> _ForwardCompatibleModel:
        copied = self.model_copy(deep=False)
        for field_name in type(self).model_fields:
            if field_name in copied.__dict__:
                copied.__dict__[field_name] = self._safe_copy_value(
                    copied.__dict__[field_name]
                )
        protected = type(self)._protected_json_names()
        protected_casefold = {name.casefold() for name in protected}
        extras = {
            key: self._safe_copy_value(value)
            for key, value in (self.__pydantic_extra__ or {}).items()
            if isinstance(key, str) and key.casefold() not in protected_casefold
        }
        object.__setattr__(copied, "__pydantic_extra__", extras)
        return copied

    @classmethod
    def _remove_typed_none(
        cls,
        model: _ForwardCompatibleModel,
        payload: dict[str, Any],
        by_alias: bool,
    ) -> None:
        for field_name, field in type(model).model_fields.items():
            key = field_name
            if by_alias:
                key = field.serialization_alias or field.alias or field_name
            value = getattr(model, field_name)
            if value is None:
                payload.pop(key, None)
                continue
            encoded = payload.get(key)
            if isinstance(value, _ForwardCompatibleModel) and isinstance(encoded, dict):
                cls._remove_typed_none(value, encoded, by_alias)
            elif isinstance(value, (list, tuple)) and isinstance(encoded, list):
                for item, encoded_item in zip(value, encoded):
                    if isinstance(item, _ForwardCompatibleModel) and isinstance(
                        encoded_item, dict
                    ):
                        cls._remove_typed_none(item, encoded_item, by_alias)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        exclude_none = bool(kwargs.pop("exclude_none", False))
        by_alias = bool(kwargs.get("by_alias", False))
        safe = self._safe_copy_for_dump()
        payload = BaseModel.model_dump(safe, exclude_none=False, **kwargs)
        if exclude_none:
            self._remove_typed_none(safe, payload, by_alias)
        return payload

    def model_dump_json(self, **kwargs: Any) -> str:
        indent = kwargs.pop("indent", None)
        ensure_ascii = bool(kwargs.pop("ensure_ascii", False))
        payload = self.model_dump(mode="json", **kwargs)
        separators = None if indent is not None else (",", ":")
        return json.dumps(
            payload,
            ensure_ascii=ensure_ascii,
            indent=indent,
            separators=separators,
        )


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


class PerfStage(_ForwardCompatibleModel):
    """One virtual-user or arrival-rate ramp stage in a saved perf profile."""

    duration: str = ""
    target: int = 0
    target_rps: Optional[int] = Field(default=None, alias="targetRPS")


class AbortCriterion(_ForwardCompatibleModel):
    """An automatic stop condition for a performance run."""

    metric: str = ""
    stat: str = ""
    condition: str = ""
    value: float = 0.0
    enabled: bool = False
    duration: Optional[str] = None
    name: Optional[str] = None


class PerfOptions(_ForwardCompatibleModel):
    """Typed ``options`` envelope for a saved performance configuration."""

    thresholds: Optional[dict[str, list[str]]] = None
    duration: Optional[str] = None
    stages: Optional[list[PerfStage]] = None
    abort_criteria: Optional[list[AbortCriterion]] = Field(default=None, alias="abortCriteria")
    start_at_unix_ms: Optional[int] = Field(default=None, alias="startAtUnixMs")
    vus: Optional[int] = None
    iterations: Optional[int] = None
    rps: Optional[int] = None
    max_vus: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("maxVUs", "maxVus"),
        serialization_alias="maxVUs",
    )
    arrival_rate: Optional[bool] = Field(default=None, alias="arrivalRate")
    graceful_stop: Optional[str] = Field(default=None, alias="gracefulStop")
    graceful_ramp_down: Optional[str] = Field(default=None, alias="gracefulRampDown")
    metrics_push: Optional[list[str]] = Field(default=None, alias="metricsPush")
    metrics_push_interval: Optional[str] = Field(default=None, alias="metricsPushInterval")
    emit_histograms: Optional[bool] = Field(default=None, alias="emitHistograms")


class PerfConfig(_ForwardCompatibleModel):
    """Performance test configuration.

    ``id`` / ``namespace`` / timestamps are populated by the server on
    create/get/list (POST/GET /api/v1/perf-configs) and are required to
    address a saved config via get_config / update_config / delete_config.
    They are optional on the request side so a caller can still build a
    config inline for perf.run().
    """

    id: Optional[str] = None
    namespace: Optional[str] = None
    name: Optional[str] = None
    script: Optional[str] = None
    options: Optional[PerfOptions] = None
    collection_id: Optional[str] = Field(default=None, alias="collectionId")
    parent_id: Optional[str] = Field(default=None, alias="parentId")
    user_id: Optional[str] = Field(default=None, alias="userId")
    sort_order: int = Field(default=0, alias="sortOrder")
    is_folder: bool = Field(default=False, alias="isFolder")
    vus: Optional[int] = None
    duration: Optional[str] = None
    stages: Optional[list[dict[str, Any]]] = None
    thresholds: Optional[dict[str, Any]] = None
    environment: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")


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
