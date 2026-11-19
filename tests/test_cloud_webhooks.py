"""Curated Cloud webhook lifecycle parity tests."""

import httpx
import respx

from mockarty import MockartyClient


@respx.mock
def test_cloud_webhooks_lifecycle_and_one_time_rotation(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/cloud/webhooks"
    respx.get(base, params={"workspace_id": "space-a"}).mock(
        return_value=httpx.Response(200, json={"webhooks": [{"id": "hook-1"}]})
    )
    create = respx.post(base, params={"workspace_id": "space-a"}).mock(
        return_value=httpx.Response(201, json={"webhook": {"id": "hook-1"}, "secret": "whsec_once"})
    )
    rotate = respx.post(f"{base}/hook-1/rotate-secret", params={"workspace_id": "space-a"}).mock(
        return_value=httpx.Response(200, json={"webhook": {"id": "hook-1"}, "secret": "whsec_rotated"})
    )
    respx.post(f"{base}/hook-1/test", params={"workspace_id": "space-a"}).mock(
        return_value=httpx.Response(202, json={"status": "test_dispatched"})
    )
    respx.get(f"{base}/hook-1/deliveries", params={"workspace_id": "space-a", "limit": 100}).mock(
        return_value=httpx.Response(200, json={"deliveries": [{"id": "delivery-1"}]})
    )
    respx.delete(f"{base}/hook-1", params={"workspace_id": "space-a"}).mock(
        return_value=httpx.Response(204)
    )

    assert client.cloud_webhooks.list("space-a")[0]["id"] == "hook-1"
    created = client.cloud_webhooks.create("space-a", "Build events", "https://hooks.example/events", ["instance.created"], "create-retry-1")
    assert created["secret"] == "whsec_once"
    assert create.calls.last.request.content
    assert create.calls.last.request.headers["Idempotency-Key"] == "create-retry-1"
    assert client.cloud_webhooks.rotate_secret("space-a", "hook-1", "retry-1")["secret"] == "whsec_rotated"
    assert rotate.calls.last.request.headers["Idempotency-Key"] == "retry-1"
    client.cloud_webhooks.test("space-a", "hook-1")
    assert client.cloud_webhooks.list_deliveries("space-a", "hook-1", 999)[0]["id"] == "delivery-1"
    client.cloud_webhooks.deactivate("space-a", "hook-1")


def test_cloud_webhooks_rotation_requires_retry_identity(client: MockartyClient) -> None:
    try:
        client.cloud_webhooks.rotate_secret("space-a", "hook-1", "")
    except ValueError as exc:
        assert "idempotency_key" in str(exc)
    else:
        raise AssertionError("empty idempotency key accepted")


@respx.mock
def test_cloud_webhooks_named_idempotent_create_matches_the_go_sdk(client: MockartyClient) -> None:
    """The named key-carrying create is the method the Go SDK also exposes.

    Parity gate `scripts/sdk_parity_check.py` compares METHOD NAMES, so this
    wrapper must exist in all three SDKs; and it must carry the CALLER's key —
    an SDK-invented key would turn a retry into a second webhook.
    """
    base = "http://localhost:5770/api/v1/cloud/webhooks"
    create = respx.post(base, params={"workspace_id": "space-a"}).mock(
        return_value=httpx.Response(201, json={"webhook": {"id": "hook-1"}, "secret": "whsec_once"})
    )

    created = client.cloud_webhooks.create_with_idempotency_key(
        "space-a", "Build events", "https://hooks.example/events", ["instance.created"], "caller-key-7")
    assert created["secret"] == "whsec_once"
    assert create.calls.last.request.headers["Idempotency-Key"] == "caller-key-7"

    # An empty key is refused BEFORE any request: silently creating without one
    # would defeat the whole point of the idempotent path.
    respx.reset()
    try:
        client.cloud_webhooks.create_with_idempotency_key(
            "space-a", "Build events", "https://hooks.example/events", ["instance.created"], "")
    except ValueError as exc:
        assert "idempotency_key" in str(exc)
    else:  # pragma: no cover - the refusal is the contract
        raise AssertionError("an empty idempotency key must be refused")
