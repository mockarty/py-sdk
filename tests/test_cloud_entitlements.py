"""Committed Cloud entitlement projection parity tests."""

import asyncio

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_entitlements_get_explicit_space(client: MockartyClient) -> None:
    route = respx.get(
        "http://localhost:5770/api/v1/cloud/entitlements", params={"space_id": "space-1"}
    ).mock(return_value=httpx.Response(200, json={"revision": 7, "digest": "abc", "snapshot": {"plan": "team"}}))
    assert client.cloud_entitlements.get("space-1")["snapshot"]["plan"] == "team"
    assert route.called
    with pytest.raises(ValueError, match="space_id"):
        client.cloud_entitlements.get(" ")


@respx.mock
def test_async_cloud_entitlements_get_explicit_space(base_url: str, api_key: str) -> None:
    route = respx.get(
        f"{base_url}/api/v1/cloud/entitlements", params={"space_id": "space-1"}
    ).mock(return_value=httpx.Response(200, json={"revision": 7, "snapshot": {"plan": "team"}}))
    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            assert (await client.cloud_entitlements.get("space-1"))["revision"] == 7

    asyncio.run(run())
    assert route.called
