"""Administrator LLM usage and immutable price-book API."""

from __future__ import annotations

from datetime import datetime

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.economics import (
    LLMBudget,
    LLMBudgetList,
    LLMPrice,
    LLMPriceList,
    LLMUsageReport,
    LLMUsageRefund,
)

_PRICES_PATH = "/api/v1/admin/llm-prices"
_USAGE_PATH = "/api/v1/admin/llm-usage"
_BUDGETS_PATH = "/api/v1/admin/llm-budgets"


def _price_params(provider: str, model: str, limit: int | None) -> dict[str, object]:
    params: dict[str, object] = {}
    if provider.strip():
        params["provider"] = provider.strip()
    if model.strip():
        params["model"] = model.strip()
    if limit is not None and limit > 0:
        params["limit"] = limit
    return params


def _usage_params(group_by: str, days: int | None) -> dict[str, object]:
    params: dict[str, object] = {}
    if group_by:
        params["groupBy"] = group_by
    if days is not None and days > 0:
        params["days"] = days
    return params


def _statement_params(
    from_time: datetime | None,
    to_time: datetime | None,
    namespace: str,
    profile_id: str,
    limit: int | None,
) -> dict[str, object]:
    params: dict[str, object] = {}
    if from_time is not None:
        params["from"] = from_time.isoformat()
    if to_time is not None:
        params["to"] = to_time.isoformat()
    if namespace.strip():
        params["namespace"] = namespace.strip()
    if profile_id.strip():
        params["profileId"] = profile_id.strip()
    if limit is not None and limit > 0:
        params["limit"] = limit
    return params


def _validate_price(price: LLMPrice) -> None:
    if (
        not price.provider.strip()
        or not price.model.strip()
        or not price.currency.strip()
    ):
        raise ValueError("provider, model and currency are required")


def _validate_budget(budget: LLMBudget) -> None:
    if (
        not budget.namespace.strip()
        or not budget.scope_type.strip()
        or not budget.currency.strip()
    ):
        raise ValueError("namespace, scope and currency are required")
    if budget.period_end <= budget.period_start:
        raise ValueError("budget period end must be after its start")


class EconomicsAPI(SyncAPIBase):
    def list_prices(
        self, *, provider: str = "", model: str = "", limit: int | None = None
    ) -> LLMPriceList:
        response = self._request(
            "GET", _PRICES_PATH, params=_price_params(provider, model, limit)
        )
        return LLMPriceList.model_validate(response.json())

    def append_price(self, price: LLMPrice) -> LLMPrice:
        _validate_price(price)
        response = self._request(
            "POST",
            _PRICES_PATH,
            json=price.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return LLMPrice.model_validate(response.json())

    def get_usage(
        self, *, group_by: str = "profile", days: int | None = 30
    ) -> LLMUsageReport:
        response = self._request(
            "GET", _USAGE_PATH, params=_usage_params(group_by, days)
        )
        return LLMUsageReport.model_validate(response.json())

    def download_usage_statement(
        self,
        *,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        namespace: str = "",
        profile_id: str = "",
        limit: int | None = None,
    ) -> bytes:
        params = _statement_params(from_time, to_time, namespace, profile_id, limit)
        return self._request("GET", f"{_USAGE_PATH}/statement.csv", params=params).content

    def refund_usage(self, event_id: str, reason: str) -> LLMUsageRefund:
        if not event_id.strip() or len(reason.strip()) < 3:
            raise ValueError("event id and refund reason are required")
        response = self._request(
            "POST",
            f"{_USAGE_PATH}/{event_id.strip()}/refund",
            json={"reason": reason.strip()},
        )
        return LLMUsageRefund.model_validate(response.json())

    def list_budgets(
        self, *, namespace: str = "", active: bool = False, limit: int | None = None
    ) -> LLMBudgetList:
        params: dict[str, object] = {}
        if namespace.strip():
            params["namespace"] = namespace.strip()
        if active:
            params["active"] = True
        if limit is not None and limit > 0:
            params["limit"] = limit
        response = self._request("GET", _BUDGETS_PATH, params=params)
        return LLMBudgetList.model_validate(response.json())

    def create_budget(self, budget: LLMBudget) -> LLMBudget:
        _validate_budget(budget)
        response = self._request(
            "POST",
            _BUDGETS_PATH,
            json=budget.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return LLMBudget.model_validate(response.json())

    def update_budget(self, budget: LLMBudget) -> LLMBudget:
        _validate_budget(budget)
        if not budget.id.strip():
            raise ValueError("budget id is required")
        response = self._request(
            "PUT",
            f"{_BUDGETS_PATH}/{budget.id}",
            json=budget.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return LLMBudget.model_validate(response.json())


class AsyncEconomicsAPI(AsyncAPIBase):
    async def list_prices(
        self, *, provider: str = "", model: str = "", limit: int | None = None
    ) -> LLMPriceList:
        response = await self._request(
            "GET", _PRICES_PATH, params=_price_params(provider, model, limit)
        )
        return LLMPriceList.model_validate(response.json())

    async def append_price(self, price: LLMPrice) -> LLMPrice:
        _validate_price(price)
        response = await self._request(
            "POST",
            _PRICES_PATH,
            json=price.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return LLMPrice.model_validate(response.json())

    async def get_usage(
        self, *, group_by: str = "profile", days: int | None = 30
    ) -> LLMUsageReport:
        response = await self._request(
            "GET", _USAGE_PATH, params=_usage_params(group_by, days)
        )
        return LLMUsageReport.model_validate(response.json())

    async def download_usage_statement(
        self,
        *,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        namespace: str = "",
        profile_id: str = "",
        limit: int | None = None,
    ) -> bytes:
        params = _statement_params(from_time, to_time, namespace, profile_id, limit)
        response = await self._request("GET", f"{_USAGE_PATH}/statement.csv", params=params)
        return response.content

    async def refund_usage(self, event_id: str, reason: str) -> LLMUsageRefund:
        if not event_id.strip() or len(reason.strip()) < 3:
            raise ValueError("event id and refund reason are required")
        response = await self._request(
            "POST",
            f"{_USAGE_PATH}/{event_id.strip()}/refund",
            json={"reason": reason.strip()},
        )
        return LLMUsageRefund.model_validate(response.json())

    async def list_budgets(
        self, *, namespace: str = "", active: bool = False, limit: int | None = None
    ) -> LLMBudgetList:
        params: dict[str, object] = {}
        if namespace.strip():
            params["namespace"] = namespace.strip()
        if active:
            params["active"] = True
        if limit is not None and limit > 0:
            params["limit"] = limit
        response = await self._request("GET", _BUDGETS_PATH, params=params)
        return LLMBudgetList.model_validate(response.json())

    async def create_budget(self, budget: LLMBudget) -> LLMBudget:
        _validate_budget(budget)
        response = await self._request(
            "POST",
            _BUDGETS_PATH,
            json=budget.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return LLMBudget.model_validate(response.json())

    async def update_budget(self, budget: LLMBudget) -> LLMBudget:
        _validate_budget(budget)
        if not budget.id.strip():
            raise ValueError("budget id is required")
        response = await self._request(
            "PUT",
            f"{_BUDGETS_PATH}/{budget.id}",
            json=budget.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        return LLMBudget.model_validate(response.json())
