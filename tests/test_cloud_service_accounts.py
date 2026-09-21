"""Cloud service-account management and workload route parity tests."""

import asyncio

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_service_accounts_management_and_workload(client: MockartyClient) -> None:
    management = "http://localhost:5770/api/v1/cloud/spaces/space-a/service-accounts"
    respx.get(management).mock(return_value=httpx.Response(200, json={"service_accounts": [], "capacity": {"remaining": 1}}))
    create = respx.post(management).mock(return_value=httpx.Response(201, json={"service_account": {"id": "sa"}}))
    machine = "http://localhost:5770/api/v1/cloud/service-account"
    respx.get(f"{machine}/self").mock(return_value=httpx.Response(200, json={"service_account": {"id": "sa"}}))
    workload = respx.post(f"{machine}/spaces/space-a/shared/projects").mock(
        return_value=httpx.Response(201, json={"id": "p1", "revision": 1}))

    assert client.cloud_service_accounts.list("space-a")["capacity"]["remaining"] == 1
    client.cloud_service_accounts.create("space-a", "ci", ["space.read"], "create-1")
    assert client.cloud_service_account.self()["service_account"]["id"] == "sa"
    client.cloud_service_account.create_project("space-a", "A", {}, "project-create-1")
    assert create.calls.last.request.headers["Idempotency-Key"] == "create-1"
    assert workload.calls.last.request.headers["Idempotency-Key"] == "project-create-1"
    assert "/service-account/spaces/" in workload.calls.last.request.url.path


def test_cloud_service_account_mutations_require_idempotency_key(client: MockartyClient) -> None:
    with pytest.raises(ValueError, match="idempotency_key"):
        client.cloud_service_accounts.create("space-a", "ci", ["space.read"], "")
    with pytest.raises(ValueError, match="idempotency_key"):
        client.cloud_service_account.create_project("space-a", "A", {}, "")


@respx.mock
def test_async_cloud_service_account_exact_surface(base_url: str, api_key: str) -> None:
    route = respx.get(f"{base_url}/api/v1/cloud/service-account/self").mock(
        return_value=httpx.Response(200, json={"credential_kind": "service_account"}))

    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            assert (await client.cloud_service_account.self())["credential_kind"] == "service_account"

    asyncio.run(run())
    assert route.called
