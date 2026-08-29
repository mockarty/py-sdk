"""Managed Cloud instance API parity tests."""

import httpx
import asyncio
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_instances_lifecycle_and_one_time_bootstrap(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/cloud/instances"
    create = respx.post(base).mock(return_value=httpx.Response(201, json={
        "instance": {"id": "instance-1"},
        "bootstrap": {"available": True, "password": "one-time", "one_time": True},
    }))
    respx.get(base, params={"workspace_id": "space-1"}).mock(return_value=httpx.Response(200, json={"instances": []}))
    respx.get(f"{base}/instance-1").mock(return_value=httpx.Response(200, json={"instance": {"id": "instance-1"}}))
    stop = respx.post(f"{base}/instance-1/stop").mock(return_value=httpx.Response(202, json={}))
    respx.post(f"{base}/instance-1/start").mock(return_value=httpx.Response(202, json={}))
    respx.delete(f"{base}/instance-1").mock(return_value=httpx.Response(202, json={}))

    result = client.cloud_instances.create("space-1", "Managed", "create-1")
    assert result["bootstrap"]["password"] == "one-time"
    assert create.calls.last.request.headers["Idempotency-Key"] == "create-1"
    assert client.cloud_instances.list("space-1")["instances"] == []
    assert client.cloud_instances.get("instance-1")["id"] == "instance-1"
    client.cloud_instances.stop("instance-1", "stop-1")
    client.cloud_instances.start("instance-1", "start-1")
    client.cloud_instances.delete("instance-1", "delete-1")
    assert stop.calls.last.request.headers["Idempotency-Key"] == "stop-1"


@respx.mock
def test_async_cloud_instances_create_uses_exact_contract(base_url: str, api_key: str) -> None:
    route = respx.post(f"{base_url}/api/v1/cloud/instances").mock(
        return_value=httpx.Response(201, json={"instance": {"id": "instance-2"}})
    )
    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            result = await client.cloud_instances.create("space-2", "Async", "create-2")
            assert result["instance"]["id"] == "instance-2"

    asyncio.run(run())
    assert route.calls.last.request.headers["Idempotency-Key"] == "create-2"
