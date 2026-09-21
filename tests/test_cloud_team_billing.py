"""Read-only Team package and billing client contract."""

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_team_package_and_billing_reads(client: MockartyClient) -> None:
    packages = respx.get("http://localhost:5770/api/v1/cloud/team/packages",
                         params={"space_id": "personal-1"}).mock(
        return_value=httpx.Response(200, json={"packages": [{"seats": 5, "total_minor": 50000}]}))
    billing = respx.get("http://localhost:5770/api/v1/cloud/team/billing",
                        params={"space_id": "team-space-1"}).mock(
        return_value=httpx.Response(200, json={"billing": {"package_seats": 5, "reserved_seats": 1}}))
    with pytest.raises(ValueError):
        client.cloud_spaces.list_team_packages(" ")
    with pytest.raises(ValueError):
        client.cloud_spaces.get_team_billing("")
    assert client.cloud_spaces.list_team_packages("personal-1")[0]["total_minor"] == 50000
    assert client.cloud_spaces.get_team_billing("team-space-1")["reserved_seats"] == 1
    assert packages.call_count == billing.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_async_team_package_and_billing_reads(base_url: str, api_key: str) -> None:
    packages = respx.get(f"{base_url}/api/v1/cloud/team/packages",
                         params={"space_id": "personal-1"}).mock(
        return_value=httpx.Response(200, json={"packages": [{"seats": 10}]}))
    billing = respx.get(f"{base_url}/api/v1/cloud/team/billing",
                        params={"space_id": "team-space-1"}).mock(
        return_value=httpx.Response(200, json={"billing": {"package_seats": 10}}))
    async with AsyncMockartyClient(base_url=base_url, api_key=api_key) as client:
        assert (await client.cloud_spaces.list_team_packages("personal-1"))[0]["seats"] == 10
        assert (await client.cloud_spaces.get_team_billing("team-space-1"))["package_seats"] == 10
    assert packages.call_count == billing.call_count == 1
