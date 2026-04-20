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

#: Typed plan-level execution strategies. Mirrors the server's
#: ``testplan.ExecutionMode*`` constants (introduced in migration 077).
EXECUTION_MODE_FIFO = "fifo"
EXECUTION_MODE_PARALLEL = "parallel"
EXECUTION_MODE_DAG = "dag"

EXECUTION_MODES = (
    EXECUTION_MODE_FIFO,
    EXECUTION_MODE_PARALLEL,
    EXECUTION_MODE_DAG,
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
    schedule: Optional[str] = None  # legacy mode column (kept for backward-compat)
    # Typed execution mode introduced in migration 077. One of "fifo" /
    # "parallel" / "dag". Empty defers to ExecutionMode auto-detect on
    # the server (Gates → DAG, otherwise FIFO).
    execution_mode: Optional[str] = Field(default=None, alias="executionMode")
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

    ``execution_mode`` is the typed, post-077 successor — pass ``"fifo"``,
    ``"parallel"`` or ``"dag"``. Prefer it over the schedule_cron sentinel
    forms; cron expressions still belong in ``schedule_cron``.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    description: Optional[str] = None
    schedule_cron: Optional[str] = Field(default=None, alias="schedule_cron")
    execution_mode: Optional[str] = Field(default=None, alias="execution_mode")
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


class UnifiedReportCounts(BaseModel):
    """Per-status item tallies in a :class:`UnifiedReport`."""

    model_config = ConfigDict(populate_by_name=True)

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    broken: int = 0


class UnifiedItemResult(BaseModel):
    """One result entry inside a :class:`UnifiedReport`.

    Mirrors ``internal/testplan.AllureResult``. Unknown fields round-trip
    through :attr:`UnifiedReport.raw` for callers who need them.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: Optional[str] = None
    uuid: Optional[str] = None
    history_id: Optional[str] = Field(default=None, alias="historyId")
    full_name: Optional[str] = Field(default=None, alias="fullName")
    description: Optional[str] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    status_details: Optional[dict[str, Any]] = Field(default=None, alias="statusDetails")
    labels: Optional[list[dict[str, Any]]] = None
    parameters: Optional[list[dict[str, Any]]] = None
    attachments: Optional[list[dict[str, Any]]] = None
    start: Optional[int] = None
    stop: Optional[int] = None


class UnifiedReport(BaseModel):
    """Native Mockarty-shape report served by the ``.unified.json`` endpoint.

    The server serialises the same fields for every language SDK (Go /
    Python / Java). ``raw`` preserves the wire bytes so callers can decode
    into custom types if the server adds new fields before the SDK is
    updated.
    """

    __test__ = False  # pytest: not a test class

    model_config = ConfigDict(populate_by_name=True)

    started_at: Optional[str] = Field(default=None, alias="startedAt")
    plan_name: Optional[str] = Field(default=None, alias="planName")
    run_id: Optional[str] = Field(default=None, alias="runId")
    results: list[UnifiedItemResult] = Field(default_factory=list)
    counts: UnifiedReportCounts = Field(default_factory=UnifiedReportCounts)
    generated_at: Optional[int] = Field(default=None, alias="generatedAt")
    duration_ms: Optional[int] = Field(default=None, alias="durationMs")
    raw: Optional[bytes] = Field(default=None, exclude=True)


# -----------------------------------------------------------------------------
# Compare runs (Phase-4 task #82)
# -----------------------------------------------------------------------------


class CompareItemSide(BaseModel):
    """Per-run snapshot of a single item in a compare result."""

    model_config = ConfigDict(populate_by_name=True)

    started_at: Optional[str] = Field(default=None, alias="startedAt")
    completed_at: Optional[str] = Field(default=None, alias="completedAt")
    status: Optional[str] = None
    skip_reason: Optional[str] = Field(default=None, alias="skipReason")
    error: Optional[str] = None
    duration_ms: int = Field(default=0, alias="durationMs")
    attempts: int = 0
    present: bool = False


class CompareItemDiff(BaseModel):
    """Per-item delta classification.

    ``regression_type`` is one of ``unchanged``, ``pass_to_fail``,
    ``fail_to_pass``, ``skipped_to_ran``, ``ran_to_skipped``,
    ``fail_to_fail``, ``pass_to_pass``, ``added``, ``removed``.
    """

    model_config = ConfigDict(populate_by_name=True)

    regression_type: str = Field(default="unchanged", alias="regressionType")
    duration_delta_ms: int = Field(default=0, alias="durationDeltaMs")
    status_changed: bool = Field(default=False, alias="statusChanged")
    is_regression: bool = Field(default=False, alias="isRegression")
    is_improvement: bool = Field(default=False, alias="isImprovement")
    duration_worsened: bool = Field(default=False, alias="durationWorsened")


class CompareItem(BaseModel):
    """One row in the compare diff (state on each side + delta)."""

    model_config = ConfigDict(populate_by_name=True)

    a: CompareItemSide = Field(default_factory=CompareItemSide)
    b: CompareItemSide = Field(default_factory=CompareItemSide)
    diff: CompareItemDiff = Field(default_factory=CompareItemDiff)
    type: Optional[str] = None
    name: Optional[str] = None
    item_uid: str = Field(alias="itemUid")


class CompareRunSide(BaseModel):
    """Per-run envelope (counts, duration, plan name)."""

    model_config = ConfigDict(populate_by_name=True)

    started_at: Optional[str] = Field(default=None, alias="startedAt")
    completed_at: Optional[str] = Field(default=None, alias="completedAt")
    plan_name: Optional[str] = Field(default=None, alias="planName")
    status: Optional[str] = None
    namespace: Optional[str] = None
    id: Optional[str] = None
    plan_id: Optional[str] = Field(default=None, alias="planId")
    plan_numeric_id: int = Field(default=0, alias="planNumericId")
    total_items: int = Field(default=0, alias="totalItems")
    completed_items: int = Field(default=0, alias="completedItems")
    failed_items: int = Field(default=0, alias="failedItems")
    passed_items: int = Field(default=0, alias="passedItems")
    skipped_items: int = Field(default=0, alias="skippedItems")
    duration_ms: int = Field(default=0, alias="durationMs")


class CompareItemRef(BaseModel):
    """Compact pointer to an item used in summary added/removed lists."""

    model_config = ConfigDict(populate_by_name=True)

    type: Optional[str] = None
    name: Optional[str] = None
    item_uid: str = Field(alias="itemUid")


class CompareSummary(BaseModel):
    """Aggregate counters — useful when CI just wants a single number."""

    model_config = ConfigDict(populate_by_name=True)

    added_items: list[CompareItemRef] = Field(default_factory=list, alias="addedItems")
    removed_items: list[CompareItemRef] = Field(default_factory=list, alias="removedItems")
    total_a: int = Field(default=0, alias="totalA")
    total_b: int = Field(default=0, alias="totalB")
    pass_to_fail: int = Field(default=0, alias="passToFail")
    fail_to_pass: int = Field(default=0, alias="failToPass")
    skipped_to_ran: int = Field(default=0, alias="skippedToRan")
    ran_to_skipped: int = Field(default=0, alias="ranToSkipped")
    regressions: int = 0
    improvements: int = 0
    unchanged_items: int = Field(default=0, alias="unchangedItems")
    different_plans: bool = Field(default=False, alias="differentPlans")


class CompareResult(BaseModel):
    """Full diff envelope returned by GET /test-plans/runs/compare."""

    model_config = ConfigDict(populate_by_name=True)

    run_a: CompareRunSide = Field(default_factory=CompareRunSide, alias="runA")
    run_b: CompareRunSide = Field(default_factory=CompareRunSide, alias="runB")
    items: list[CompareItem] = Field(default_factory=list)
    summary: CompareSummary = Field(default_factory=CompareSummary)
