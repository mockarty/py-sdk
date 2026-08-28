"""Shared SaaS project CRUD parity tests."""

import httpx
import asyncio
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_shared_projects_crud(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/cloud/spaces/space-a/shared/projects"
    respx.get(base, params={"limit": 50}).mock(return_value=httpx.Response(200, json={"projects": [], "next_cursor": "", "has_more": False}))
    create = respx.post(base).mock(return_value=httpx.Response(201, json={"id": "p1", "name": "A", "body": {}, "revision": 1}))
    update = respx.put(f"{base}/p1").mock(return_value=httpx.Response(200, json={"id": "p1", "name": "B", "body": {}, "revision": 2}))
    delete = respx.delete(f"{base}/p1", params={"revision": 2}).mock(return_value=httpx.Response(204))
    assert client.cloud_shared_projects.list("space-a")["projects"] == []
    create_request_id = "11111111-1111-4111-8111-111111111111"
    assert client.cloud_shared_projects.create("space-a", "A", {}, request_id=create_request_id)["revision"] == 1
    assert client.cloud_shared_projects.update("space-a", "p1", "B", {}, 1)["revision"] == 2
    client.cloud_shared_projects.delete("space-a", "p1", 2)
    for route in (create, update, delete):
        assert route.called
        assert route.calls.last.request.headers["Authorization"].startswith("Bearer ")
        assert "X-API-Key" not in route.calls.last.request.headers
        assert route.calls.last.request.headers["X-Request-ID"]
    assert create.calls.last.request.headers["X-Request-ID"] == create_request_id


def test_cloud_shared_projects_rejects_noncanonical_request_id(client: MockartyClient) -> None:
    try:
        client.cloud_shared_projects.create("space-a", "A", {}, request_id="retry")
    except ValueError as exc:
        assert "canonical UUID" in str(exc)
    else:
        raise AssertionError("noncanonical request_id accepted")


@respx.mock
def test_async_cloud_shared_projects(base_url: str, api_key: str) -> None:
    base = f"{base_url}/api/v1/cloud/spaces/space-a/shared/projects"
    respx.get(base, params={"limit": 50}).mock(return_value=httpx.Response(200, json={"projects": [], "next_cursor": "", "has_more": False}))
    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            assert (await client.cloud_shared_projects.list("space-a"))["projects"] == []
    asyncio.run(run())
