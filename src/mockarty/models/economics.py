"""LLM usage economics and immutable price-book models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LLMPrice(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    effective_from: datetime = Field(alias="effectiveFrom")
    input_micros_per_million: int = Field(default=0, alias="inputMicrosPerMillion")
    output_micros_per_million: int = Field(default=0, alias="outputMicrosPerMillion")
    cache_read_micros_per_million: int = Field(
        default=0, alias="cacheReadMicrosPerMillion"
    )
    cache_write_micros_per_million: int = Field(
        default=0, alias="cacheWriteMicrosPerMillion"
    )
    provider: str
    model: str
    currency: str
    created_at: datetime | None = Field(default=None, alias="createdAt")
    id: str = ""
    source: str = ""


class LLMPriceList(BaseModel):
    prices: list[LLMPrice] = Field(default_factory=list)


class LLMUsageRefund(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    created_at: datetime = Field(alias="createdAt")
    original_event_id: str = Field(alias="originalEventId")
    refund_event_id: str = Field(alias="refundEventId")
    id: str
    actor_id: str = Field(default="", alias="actorId")
    namespace: str = ""
    reason: str


class LLMUsageTotals(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")
    total_tokens: int = Field(default=0, alias="totalTokens")
    calls: int = 0


class LLMUsageCost(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_cost_micros: int = Field(default=0, alias="providerCostMicros")
    platform_fee_micros: int = Field(default=0, alias="platformFeeMicros")
    markup_micros: int = Field(default=0, alias="markupMicros")
    tax_micros: int = Field(default=0, alias="taxMicros")
    discount_micros: int = Field(default=0, alias="discountMicros")
    customer_cost_micros: int = Field(default=0, alias="customerCostMicros")
    margin_micros: int = Field(default=0, alias="marginMicros")
    included_micros: int = Field(default=0, alias="includedMicros")
    prepaid_micros: int = Field(default=0, alias="prepaidMicros")
    overage_micros: int = Field(default=0, alias="overageMicros")
    byok_calls: int = Field(default=0, alias="byokCalls")
    calls: int = 0
    currency: str = ""


class LLMUsageGroup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")
    total_tokens: int = Field(default=0, alias="totalTokens")
    calls: int = 0
    key: str = ""
    label: str = ""


class LLMUsageForecast(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    observed_micros: int = Field(default=0, alias="observedMicros")
    daily_run_rate_micros: int = Field(default=0, alias="dailyRunRateMicros")
    projected_30_day_micros: int = Field(default=0, alias="projected30DayMicros")
    recent_24_hours_micros: int = Field(default=0, alias="recent24HoursMicros")
    prior_daily_micros: int = Field(default=0, alias="priorDailyMicros")
    recent_to_baseline_ratio: float = Field(default=0, alias="recentToBaselineRatio")
    currency: str = ""
    status: str = ""


class LLMUsageOutcomeCost(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider_cost_micros: int = Field(default=0, alias="providerCostMicros")
    customer_cost_micros: int = Field(default=0, alias="customerCostMicros")
    calls: int = 0
    outcome: str = ""
    currency: str = ""


class LLMUsageReconciliation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reserved: int = 0
    settled: int = 0
    released: int = 0
    expired: int = 0
    missing_usage_event: int = Field(default=0, alias="missingUsageEvent")
    orphan_usage_event: int = Field(default=0, alias="orphanUsageEvent")


class LLMUsageReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    totals: LLMUsageTotals = Field(default_factory=LLMUsageTotals)
    rows: list[LLMUsageGroup] = Field(default_factory=list)
    costs: list[LLMUsageCost] = Field(default_factory=list)
    forecast: list[LLMUsageForecast] = Field(default_factory=list)
    outcome_costs: list[LLMUsageOutcomeCost] = Field(
        default_factory=list, alias="outcomeCosts"
    )
    reconciliation: LLMUsageReconciliation = Field(
        default_factory=LLMUsageReconciliation
    )
    unpriced_calls: int = Field(default=0, alias="unpricedCalls")


class LLMBudget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period_start: datetime = Field(alias="periodStart")
    period_end: datetime = Field(alias="periodEnd")
    included_micros: int = Field(default=0, alias="includedMicros")
    prepaid_micros: int = Field(default=0, alias="prepaidMicros")
    soft_limit_micros: int = Field(default=0, alias="softLimitMicros")
    hard_limit_micros: int = Field(default=0, alias="hardLimitMicros")
    spent_micros: int = Field(default=0, alias="spentMicros")
    reserved_micros: int = Field(default=0, alias="reservedMicros")
    namespace: str
    scope_type: str = Field(alias="scopeType")
    currency: str
    scope_id: str = Field(default="", alias="scopeId")
    id: str = ""
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    overage_allowed: bool = Field(default=False, alias="overageAllowed")
    require_priced: bool = Field(default=True, alias="requirePriced")
    enabled: bool = True


class LLMBudgetList(BaseModel):
    budgets: list[LLMBudget] = Field(default_factory=list)
