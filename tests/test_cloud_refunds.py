from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_refunds_resolve_refund_exact_contract() -> None:
    route = respx.post("https://cloud.test/api/v1/cloud/operator/refunds/refund%2F1/resolve").mock(
        return_value=httpx.Response(200, json={
            "refund": {"operation_id": "refund/1", "status": "accepted", "generation": 5},
            "replayed": True,
            "request_id": "req-1",
        })
    )
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    result = client.cloud_refunds.resolve_refund(
        "refund/1", action="retry", reason_code="provider_recovery_retry",
        generation=4, idempotency_key="refund-resolution:exact-1",
    )
    request = route.calls.last.request
    assert result["refund"]["generation"] == 5
    assert request.headers["Idempotency-Key"] == "refund-resolution:exact-1"
    assert request.content == b'{"action":"retry","reason_code":"provider_recovery_retry","generation":4}'


@respx.mock
@pytest.mark.asyncio
async def test_async_cloud_refunds_resolve_refund_exact_contract() -> None:
    route = respx.post("https://cloud.test/api/v1/cloud/operator/refunds/op-1/resolve").mock(
        return_value=httpx.Response(200, json={"refund": {"operation_id": "op-1", "status": "rejected"}})
    )
    async with AsyncMockartyClient(base_url="https://cloud.test", max_retries=0) as client:
        result = await client.cloud_refunds.resolve_refund(
            "op-1", action="reject", reason_code="provider_definitive_reject",
            generation=2, idempotency_key="refund-resolution@exact-2",
        )
    assert result["refund"]["status"] == "rejected"
    assert route.calls.last.request.headers["Idempotency-Key"] == "refund-resolution@exact-2"


@pytest.mark.parametrize(
    ("operation_id", "action", "reason_code", "generation", "idempotency_key"),
    [
        ("", "reject", "provider_reject", 0, "refund-1"),
        (" ", "reject", "provider_reject", 0, "refund-1"),
        ("op-1", "succeeded", "operator_says_paid", 0, "refund-1"),
        ("op-1", "reject", "Customer said no", 0, "refund-1"),
        ("op-1", "retry", "provider_retry", -1, "refund-1"),
        ("op-1", "retry", "provider_retry", 0, " refund-1 "),
    ],
)
def test_cloud_refunds_reject_unsafe_resolution(
    operation_id: str, action: str, reason_code: str, generation: int, idempotency_key: str,
) -> None:
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    with pytest.raises(ValueError):
        client.cloud_refunds.resolve_refund(
            operation_id, action=action, reason_code=reason_code,
            generation=generation, idempotency_key=idempotency_key,
        )


def test_cloud_refunds_does_not_expose_interactive_self_service_creation() -> None:
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    assert not hasattr(client.cloud_refunds, "request_refund")
    assert not hasattr(client.cloud_refunds, "create_refund")
