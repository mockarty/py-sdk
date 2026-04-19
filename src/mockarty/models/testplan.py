# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test Plan models — master orchestrator for functional / fuzz / chaos /
load / contract runs.

See docs/research/TEST_PLANS_ARCHITECTURE_2026-04-19.md for the full spec.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


#: Canonical Test Plan item types accepted by the server. Mirrors
#: ``internal/testplan.AllItemTypes``. ``test_plan`` references another plan
#: by its ID — the server runs it as a child and maps the final status onto
#: the parent item. Cycles are rejected at save-time with a trace like
#: ``A → B → C → A``.
ITEM_TYPE_FUNCTIONAL = "functional"
ITEM_TYPE_LOAD = "load"
ITEM_TYPE_FUZZ = "fuzz"
ITEM_TYPE_CHAOS = "chaos"
ITEM_TYPE_CONTRACT = "contract"
ITEM_TYPE_TEST_PLAN = "test_plan"

ITEM_TYPES = (
    ITEM_TYPE_FUNCTIONAL,
    ITEM_TYPE_LOAD,
    ITEM_TYPE_FUZZ,
    ITEM_TYPE_CHAOS,
    ITEM_TYPE_CONTRACT,
    ITEM_TYPE_TEST_PLAN,
)


class TestPlanItem(BaseModel):
    """A single step within a Test Plan.

    ``resource_id`` points to the source entity — its type is determined by
    ``type`` (``functional``/``load``/``fuzz``/``chaos``/``contract``/
    ``test_plan``). ``test_plan`` items reference another plan by its ID and
    are executed as nested child runs.
    """

    __test__ = False  # pytest: not a test class

    model_config = ConfigDict(populate_by_name=True)

    order: int
    type: str
    resource_id: str = Field(alias="refId")
    name: Optional[str] = None
    depends_on: Optional[list[str]] = Field(default=None, alias="dependsOn")
    start_offset_ms: Optional[int] = Field(default=None, alias="startOffsetMs")
    delay_after_ms: Optional[int] = Field(default=None, alias="delayAfterMs")


class TestPlan(BaseModel):
    """A Test Plan — master orchestrator for heterogeneous runs."""

    __test__ = False  # pytest: not a test class

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    numeric_id: Optional[int] = Field(default=None, alias="numericId")
    namespace: str
    name: str
    description: Optional[str] = None
    schedule: Optional[str] = None  # legacy mode column
    items: list[TestPlanItem]
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    closed_at: Optional[str] = Field(default=None, alias="closedAt")
    created_by: Optional[str] = Field(default=None, alias="createdBy")


class PlanItemState(BaseModel):
    """State of one item within a running plan."""

    model_config = ConfigDict(populate_by_name=True)

    order: int
    type: str
    status: str
    error: Optional[str] = None
    skip_reason: Optional[str] = Field(default=None, alias="skipReason")
    run_id: Optional[str] = Field(default=None, alias="runId")
    started_at: Optional[str] = Field(default=None, alias="startedAt")
    completed_at: Optional[str] = Field(default=None, alias="completedAt")
    summary: Optional[dict[str, Any]] = None


class TestPlanRun(BaseModel):
    """Aggregate execution of a Test Plan."""

    __test__ = False  # pytest: not a test class

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    plan_id: Optional[str] = Field(default=None, alias="planId")
    namespace: Optional[str] = None
    status: Optional[str] = None
    triggered_by: Optional[str] = Field(default=None, alias="triggeredBy")
    report_url: Optional[str] = Field(default=None, alias="reportUrl")
    items_state: list[PlanItemState] = Field(default_factory=list, alias="itemsState")
    total_items: int = Field(default=0, alias="totalItems")
    completed_items: int = Field(default=0, alias="completedItems")
    failed_items: int = Field(default=0, alias="failedItems")
    started_at: Optional[str] = Field(default=None, alias="startedAt")
    completed_at: Optional[str] = Field(default=None, alias="completedAt")


class PlanRunStatus(BaseModel):
    """Compact status payload."""

    model_config = ConfigDict(populate_by_name=True)

    status: str
    total_items: int = Field(default=0, alias="totalItems")
    completed_items: int = Field(default=0, alias="completedItems")
    failed_items: int = Field(default=0, alias="failedItems")


class Schedule(BaseModel):
    """One firing rule for a Plan (cron / once / interval)."""

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    plan_id: Optional[str] = Field(default=None, alias="planId")
    kind: str  # cron / once / interval
    cron_expr: Optional[str] = Field(default=None, alias="cronExpr")
    run_at: Optional[str] = Field(default=None, alias="runAt")
    interval_seconds: Optional[int] = Field(default=None, alias="intervalSeconds")
    timezone: Optional[str] = "UTC"
    enabled: bool = True
    last_fired_at: Optional[str] = Field(default=None, alias="lastFiredAt")
    next_fire_at: Optional[str] = Field(default=None, alias="nextFireAt")


class Webhook(BaseModel):
    """CI integration target for a Plan.

    ``secret`` is write-only — the server stores a bcrypt hash and never
    returns the plaintext again.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = None
    plan_id: Optional[str] = Field(default=None, alias="planId")
    url: str
    secret: Optional[str] = None  # write-only
    secret_hash: Optional[str] = Field(default=None, alias="secretHash")
    events: list[str]
    headers: Optional[dict[str, str]] = None
    timeout_ms: Optional[int] = Field(default=None, alias="timeoutMs")
    retry_count: Optional[int] = Field(default=None, alias="retryCount")
    retry_backoff_ms: Optional[int] = Field(default=None, alias="retryBackoffMs")
    enabled: bool = True
    last_called_at: Optional[str] = Field(default=None, alias="lastCalledAt")
    last_status: Optional[int] = Field(default=None, alias="lastStatus")


class RunEvent(BaseModel):
    """A single SSE event emitted by ``stream_run``."""

    kind: str  # run.started / run.completed / item.started / item.finished
    data: Optional[dict[str, Any]] = None


class ItemSummary(BaseModel):
    """Unified per-item report (maps 1:1 to internal/testplan.ItemSummary)."""

    status: str
    duration_ms: int = Field(default=0, alias="durationMs")
    started_at: Optional[str] = Field(default=None, alias="startedAt")
    finished_at: Optional[str] = Field(default=None, alias="finishedAt")
    steps: Optional[list[dict[str, Any]]] = None
    labels: Optional[dict[str, str]] = None
    parameters: Optional[dict[str, str]] = None
    attachments: Optional[list[dict[str, Any]]] = None
    metrics: Optional[dict[str, float]] = None


# ---------------------------------------------------------------------------
# TP-6b: PATCH + ad-hoc runs + namespace-scoped Allure report models
# ---------------------------------------------------------------------------


class PatchPlanRequest(BaseModel):
    """Partial-update payload for the namespace-scoped PATCH endpoint.

    Every field is optional. A field left unset (``None``) means "no change".
    Set a field to an empty string / ``False`` to overwrite the server's
    current value.

    ``schedule_cron`` accepts the same vocabulary as ``TestPlan.schedule``:
    empty string (FIFO), the sentinel modes ``parallel`` / ``dag``, or a
    5-/6-field cron expression.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    description: Optional[str] = None
    schedule_cron: Optional[str] = Field(default=None, alias="schedule_cron")
    enabled: Optional[bool] = None


class AdHocItem(BaseModel):
    """A single item in an ad-hoc run request.

    ``type`` accepts both the canonical short names (``functional``, ``load``,
    ``fuzz``, ``chaos``, ``contract``) AND the wider spec vocabulary
    (``collection``, ``perf_config``, ``fuzz_config``, ``chaos_experiment``,
    ``contract_config``).
    """

    model_config = ConfigDict(populate_by_name=True)

    type: str
    ref_id: str = Field(alias="ref_id")
    order: int = 0
    depends_on: Optional[list[str]] = Field(default=None, alias="depends_on")
    delay_after_ms: Optional[int] = Field(default=None, alias="delay_after_ms")


class CreateAdHocRunRequest(BaseModel):
    """POST ``/api/v1/namespaces/:ns/test-runs/ad-hoc`` payload.

    Schedule follows the same vocabulary as :class:`TestPlan.schedule`:
    empty (FIFO), ``parallel`` / ``dag`` sentinel, or cron expression.
    """

    __test__ = False  # pytest: not a test class

    model_config = ConfigDict(populate_by_name=True)

    items: list[AdHocItem]
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[str] = None


class AdHocRunResponse(BaseModel):
    """202 envelope returned by the ad-hoc run endpoint.

    ``links`` carries canonical follow-up URLs (self / status / cancel /
    report). Treat them as hints — downstream polling should use
    ``run_id`` with :meth:`TestPlansAPI.get_run`.
    """

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="run_id")
    plan_id: str = Field(alias="plan_id")
    status: str
    adhoc: bool = False
    links: Optional[dict[str, str]] = Field(default=None, alias="_links")


class AllureReport(BaseModel):
    """Decoded JSON shape returned by the namespace-scoped report endpoint.

    The server emits a loosely-typed envelope intentionally — new Allure
    fields roll out without SDK bumps. ``raw`` preserves the original
    bytes so callers can run a second decode pass with their own
    domain-specific types.
    """

    model_config = ConfigDict(populate_by_name=True)

    run_id: Optional[str] = Field(default=None, alias="runId")
    plan_id: Optional[str] = Field(default=None, alias="planId")
    status: Optional[str] = None
    items: list[ItemSummary] = Field(default_factory=list)
    summary: Optional[dict[str, Any]] = None
    labels: Optional[dict[str, str]] = None
    raw: Optional[bytes] = Field(default=None, exclude=True)
