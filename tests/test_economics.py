"""LLM economics API parity tests."""

import json
from datetime import UTC, datetime

import httpx
import pytest
import respx

from mockarty import (
    AsyncMockartyClient,
    LLMBudget,
    LLMPrice,
    MockartyClient,
    ResourcePrice,
)


@respx.mock
def test_economics_price_book_and_usage(client: MockartyClient) -> None:
    append = respx.post("http://localhost:5770/api/v1/admin/llm-prices").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "price-1",
                "provider": "openai",
                "model": "gpt",
                "currency": "USD",
                "effectiveFrom": "2026-01-01T00:00:00Z",
                "inputMicrosPerMillion": 100000,
            },
        )
    )
    respx.get("http://localhost:5770/api/v1/admin/llm-prices").mock(
        return_value=httpx.Response(200, json={"prices": []})
    )
    respx.get("http://localhost:5770/api/v1/admin/llm-usage").mock(
        return_value=httpx.Response(
            200,
            json={
                "totals": {"calls": 3, "totalTokens": 9},
                "rows": [],
                "costs": [],
                "unpricedCalls": 1,
                "unpricedEvents": 2,
                "resourceTotals": [
                    {
                        "eventKind": "runner_seconds",
                        "unit": "seconds",
                        "events": 1,
                        "quantity": 12,
                    }
                ],
            },
        )
    )
    price = LLMPrice(
        provider="openai",
        model="gpt",
        currency="USD",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        input_micros_per_million=100000,
    )
    assert client.economics.append_price(price).id == "price-1"
    assert append.calls.last.request.content
    assert client.economics.list_prices(provider="openai").prices == []
    report = client.economics.get_usage(group_by="module", days=30)
    assert report.unpriced_calls == 1
    assert report.unpriced_events == 2
    assert report.resource_totals[0].quantity == 12


@respx.mock
def test_economics_resource_price_book(client: MockartyClient) -> None:
    payload = {
        "id": "resource-price-1",
        "eventKind": "tool_call",
        "provider": "mockarty-agent",
        "resource": "web_search",
        "unit": "calls",
        "currency": "USD",
        "providerMicrosPerUnit": 200,
        "customerMicrosPerUnit": 300,
        "effectiveFrom": "2026-08-20T00:00:00Z",
    }
    append = respx.post("http://localhost:5770/api/v1/admin/llm-prices").mock(
        return_value=httpx.Response(201, json=payload)
    )
    list_prices = respx.get("http://localhost:5770/api/v1/admin/llm-prices").mock(
        return_value=httpx.Response(200, json={"resourcePrices": [payload]})
    )
    price = ResourcePrice.model_validate(payload)

    assert client.economics.append_resource_price(price).id == "resource-price-1"
    assert json.loads(append.calls.last.request.content)["eventKind"] == "tool_call"
    prices = client.economics.list_resource_prices(
        event_kind="tool_call",
        provider="mockarty-agent",
        resource="web_search",
        unit="calls",
        limit=10,
    ).resource_prices
    assert prices == [price]
    assert list_prices.calls.last.request.url.params["eventKind"] == "tool_call"


@pytest.mark.parametrize(
    ("event_kind", "unit"),
    [("tool_call", "seconds"), ("runner_seconds", "calls"), ("unknown", "calls")],
)
def test_economics_resource_price_rejects_invalid_kind_unit(
    client: MockartyClient, event_kind: str, unit: str
) -> None:
    price = ResourcePrice(
        event_kind=event_kind,
        provider="mockarty",
        resource="resource",
        unit=unit,
        currency="USD",
        effective_from=datetime(2026, 8, 20, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="matching event kind/unit"):
        client.economics.append_resource_price(price)


@pytest.mark.asyncio
@respx.mock
async def test_async_economics(base_url: str, api_key: str) -> None:
    respx.get(f"{base_url}/api/v1/admin/llm-prices").mock(
        return_value=httpx.Response(200, json={"prices": []})
    )
    async with AsyncMockartyClient(
        base_url=base_url, api_key=api_key, max_retries=0
    ) as client:
        assert (await client.economics.list_prices()).prices == []


@pytest.mark.asyncio
@respx.mock
async def test_async_economics_resource_prices(base_url: str, api_key: str) -> None:
    route = respx.get(f"{base_url}/api/v1/admin/llm-prices").mock(
        return_value=httpx.Response(200, json={"resourcePrices": []})
    )
    async with AsyncMockartyClient(
        base_url=base_url, api_key=api_key, max_retries=0
    ) as client:
        result = await client.economics.list_resource_prices(
            event_kind="runner_seconds", unit="seconds"
        )
        assert result.resource_prices == []
        assert route.calls.last.request.url.params["eventKind"] == "runner_seconds"


@respx.mock
def test_economics_budgets(client: MockartyClient) -> None:
    now = datetime.now(UTC)
    budget = LLMBudget(
        namespace="team-a",
        scope_type="workspace",
        currency="USD",
        period_start=now,
        period_end=now.replace(year=now.year + 1),
    )
    create = respx.post("http://localhost:5770/api/v1/admin/llm-budgets").mock(
        return_value=httpx.Response(
            201,
            json={**budget.model_dump(mode="json", by_alias=True), "id": "budget-1"},
        )
    )
    respx.get("http://localhost:5770/api/v1/admin/llm-budgets").mock(
        return_value=httpx.Response(200, json={"budgets": []})
    )
    created = client.economics.create_budget(budget)
    assert created.id == "budget-1"
    assert create.calls.last.request.content
    assert client.economics.list_budgets(namespace="team-a", active=True).budgets == []


@respx.mock
def test_economics_statement_and_refund(client: MockartyClient) -> None:
    respx.get("http://localhost:5770/api/v1/admin/llm-usage/statement.csv").mock(
        return_value=httpx.Response(200, content=b"event_id,event_kind\ne1,llm_tokens\n")
    )
    respx.post("http://localhost:5770/api/v1/admin/llm-usage/e1/refund").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "r1",
                "createdAt": "2026-08-19T00:00:00Z",
                "originalEventId": "e1",
                "refundEventId": "e2",
                "reason": "invalid response",
            },
        )
    )
    assert b"llm_tokens" in client.economics.download_usage_statement(namespace="team-a")
    assert client.economics.refund_usage("e1", "invalid response").id == "r1"
