"""Cloud customer and operator product-surface contract tests."""

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_customer_and_operations_canonical_routes(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/cloud"
    routes = [
        respx.get(f"{base}/spaces/space%2F1/loyalty/redemptions", params={"cursor": "next", "limit": 25}),
        respx.post(f"{base}/spaces/space%2F1/loyalty/redemptions"),
        respx.get(f"{base}/spaces/space%2F1/support/cases", params={"cursor": "cursor", "limit": 20, "status": "open"}),
        respx.post(f"{base}/spaces/space%2F1/support/cases"),
        respx.get(f"{base}/spaces/space%2F1/support/cases/case%2F1"),
        respx.post(f"{base}/spaces/space%2F1/support/cases/case%2F1/messages"),
        respx.get(f"{base}/risk/cases/risk%2F1/appeal"),
        respx.post(f"{base}/risk/cases/risk%2F1/appeal"),
        respx.get(f"{base}/operator/support/cases", params={"cursor": "op-next", "limit": 50, "status": "open"}),
        respx.get(f"{base}/operator/support/cases/case%2F1"),
        respx.post(f"{base}/operator/support/cases/case%2F1/messages"),
        respx.post(f"{base}/operator/support/cases/case%2F1/assign"),
        respx.post(f"{base}/operator/support/cases/case%2F1/transition"),
        respx.get(f"{base}/operator/analytics/product", params={"days": 30}),
        respx.patch(f"{base}/spaces/space%2F1"),
    ]
    for route in routes:
        route.mock(return_value=httpx.Response(200, json={}))

    customer = client.cloud_customer
    customer.list_loyalty_redemptions("space/1", "next", 25)
    customer.redeem_loyalty("space/1", "WELCOME", "RU", "redeem-1")
    customer.list_support_cases("space/1", "open", "cursor", 20)
    customer.open_support_case("space/1", "Help", "billing", "normal", "Please help", "case-1")
    customer.get_support_case("space/1", "case/1")
    customer.reply_support_case("space/1", "case/1", "Reply", "reply-1")
    customer.get_risk_appeal("risk/1")
    customer.submit_risk_appeal("risk/1", "This decision needs review", "appeal-1")
    operations = client.cloud_operations
    operations.list_support_cases("open", "op-next", 50)
    operations.get_support_case("case/1")
    operations.reply_support_case("case/1", "Operator reply", "customer", "op-reply-1")
    operations.assign_support_case("case/1", "user/1", 7)
    operations.transition_support_case("case/1", "resolved", 8)
    operations.product_analytics(30)
    client.cloud_spaces.rename("space/1", "Renamed", '"space-r7"', "rename-1")

    assert all(route.called for route in routes)
    assert routes[7].calls.last.request.headers["Idempotency-Key"] == "appeal-1"
    assert routes[14].calls.last.request.headers["If-Match"] == '"space-r7"'
    assert routes[14].calls.last.request.headers["Idempotency-Key"] == "rename-1"


def test_cloud_product_analytics_rejects_unsupported_window(client: MockartyClient) -> None:
    for days in (0, 91):
        with pytest.raises(ValueError, match="between 1 and 90"):
            client.cloud_operations.product_analytics(days)


@pytest.mark.asyncio
@respx.mock
async def test_async_cloud_customer_and_operations_canonical_routes() -> None:
    base = "http://localhost:5770/api/v1/cloud"
    routes = [
        respx.get(f"{base}/spaces/space%2F1/loyalty/redemptions", params={"cursor": "next", "limit": 25}),
        respx.post(f"{base}/spaces/space%2F1/loyalty/redemptions"),
        respx.get(f"{base}/spaces/space%2F1/support/cases", params={"cursor": "cursor", "limit": 20, "status": "open"}),
        respx.post(f"{base}/spaces/space%2F1/support/cases"),
        respx.get(f"{base}/spaces/space%2F1/support/cases/case%2F1"),
        respx.post(f"{base}/spaces/space%2F1/support/cases/case%2F1/messages"),
        respx.get(f"{base}/risk/cases/risk%2F1/appeal"),
        respx.post(f"{base}/risk/cases/risk%2F1/appeal"),
        respx.get(f"{base}/operator/support/cases", params={"cursor": "op-next", "limit": 50, "status": "open"}),
        respx.get(f"{base}/operator/support/cases/case%2F1"),
        respx.post(f"{base}/operator/support/cases/case%2F1/messages"),
        respx.post(f"{base}/operator/support/cases/case%2F1/assign"),
        respx.post(f"{base}/operator/support/cases/case%2F1/transition"),
        respx.get(f"{base}/operator/analytics/product", params={"days": 30}),
        respx.patch(f"{base}/spaces/space%2F1"),
    ]
    for route in routes:
        route.mock(return_value=httpx.Response(200, json={}))

    async with AsyncMockartyClient(base_url="http://localhost:5770", api_key="cloud-token", max_retries=0) as client:
        customer = client.cloud_customer
        await customer.list_loyalty_redemptions("space/1", "next", 25)
        await customer.redeem_loyalty("space/1", "WELCOME", "RU", "redeem-1")
        await customer.list_support_cases("space/1", "open", "cursor", 20)
        await customer.open_support_case("space/1", "Help", "billing", "normal", "Please help", "case-1")
        await customer.get_support_case("space/1", "case/1")
        await customer.reply_support_case("space/1", "case/1", "Reply", "reply-1")
        await customer.get_risk_appeal("risk/1")
        await customer.submit_risk_appeal("risk/1", "This decision needs review", "appeal-1")
        operations = client.cloud_operations
        await operations.list_support_cases("open", "op-next", 50)
        await operations.get_support_case("case/1")
        await operations.reply_support_case("case/1", "Operator reply", "customer", "op-reply-1")
        await operations.assign_support_case("case/1", "user/1", 7)
        await operations.transition_support_case("case/1", "resolved", 8)
        await operations.product_analytics(30)
        await client.cloud_spaces.rename("space/1", "Renamed", '"space-r7"', "rename-1")

    assert all(route.called for route in routes)
    assert routes[7].calls.last.request.headers["Idempotency-Key"] == "appeal-1"
    assert routes[14].calls.last.request.headers["If-Match"] == '"space-r7"'


@pytest.mark.asyncio
async def test_async_cloud_product_analytics_rejects_unsupported_window() -> None:
    async with AsyncMockartyClient(base_url="http://127.0.0.1:1", max_retries=0) as client:
        for days in (0, 91):
            with pytest.raises(ValueError, match="between 1 and 90"):
                await client.cloud_operations.product_analytics(days)
