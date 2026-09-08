import asyncio
import json

import httpx
import pytest

import respx

from mockarty import AsyncMockartyClient, MockartyClient


def test_upload_mission_material_multipart():
    def handler(request):
        assert request.url.path == "/api/v1/missions/materials"
        assert request.url.params["productId"] == "p & one"
        assert request.url.params["namespace"] == "team"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert b'filename="design.txt"' in request.content
        assert b"navy palette" in request.content
        return httpx.Response(201, json={"reference": {"kind": "mission_material", "id": "mat1"}})
    with MockartyClient(base_url="https://mockarty.test", api_key="mk_test", namespace="team") as client:
        client._http._transport = httpx.MockTransport(handler)
        assert client.coder_delivery.upload_mission_material("p & one", "design.txt", b"navy palette")["reference"]["id"] == "mat1"
        with pytest.raises(ValueError):
            client.coder_delivery.upload_mission_material("", "design.txt", b"content")
        with pytest.raises(ValueError, match="64 KiB"):
            client.coder_delivery.upload_mission_material("p", "design.txt", b"a" * (64 * 1024 + 1), "text/plain")


def test_coder_delivery_routes_and_approval():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, dict(request.url.params)))
        if request.url.path.endswith("/approve"):
            assert json.loads(request.content) == {"approve": True}
        if request.url.path.endswith("/deploy-outcome"):
            assert json.loads(request.content) == {"outcome": "not_applied"}
        if request.url.path.endswith("/add"):
            body = json.loads(request.content)
            assert body["tasks"][0]["requiredChecks"][0]["args"] == ["go", "test", "./..."]
        return httpx.Response(200, json={"id": "m1", "missions": []})

    client = MockartyClient(base_url="https://mockarty.test", api_key="mk_test", namespace="team-a")
    client._http._transport = httpx.MockTransport(handler)
    api = client.coder_delivery
    api.get_config(product_id="p1")
    api.put_config({"targets": [{"name": "prod", "approval": "approval"}]})
    api.delete_config(product_id="p1")
    api.start_mission({"goal": "ship", "repoUrl": "https://git.test/app.git"})
    api.list_missions()
    api.get_mission("m1")
    api.approve_mission("m1", True)
    api.add_to_mission("m1", {"tasks": [{"prompt": "add tests", "requiredChecks": [{"name": "unit", "args": ["go", "test", "./..."]}]}]})
    api.reconcile_deploy("m1", "not_applied")
    api.observability_sources()
    api.query_observability({"source": "prometheus", "expression": "up", "correlation": {"missionId": "m1"}})
    assert len(seen) == 11
    assert seen[-2] == ("GET", "/api/v1/observability/sources", {"namespace": "team-a"})
    assert seen[-1] == ("POST", "/api/v1/observability/query", {"namespace": "team-a"})


@respx.mock
def test_async_coder_delivery_preserves_product_and_explicit_denial():
    start = respx.post("https://mockarty.test/api/v1/coder/missions").mock(
        return_value=httpx.Response(202, json={"id": "m1", "productId": "p1"})
    )
    deny = respx.post("https://mockarty.test/api/v1/coder/missions/m1/approve").mock(
        return_value=httpx.Response(200, json={"id": "m1", "approval": "denied"})
    )
    add = respx.post("https://mockarty.test/api/v1/coder/missions/m1/add").mock(
        return_value=httpx.Response(200, json={"id": "m1"})
    )
    sources = respx.get("https://mockarty.test/api/v1/observability/sources").mock(
        return_value=httpx.Response(200, json={"contractVersion": "mockarty.observability-query/v1", "sources": []})
    )

    async def run():
        async with AsyncMockartyClient(base_url="https://mockarty.test", api_key="mk_test", namespace="team-a") as client:
            await client.coder_delivery.start_mission({"goal": "ship", "repoUrl": "https://git.test/app.git", "productId": "p1"})
            await client.coder_delivery.approve_mission("m1", False)
            await client.coder_delivery.add_to_mission("m1", {"prompts": ["add tests"]})
            await client.coder_delivery.observability_sources()

    asyncio.run(run())
    assert json.loads(start.calls.last.request.content)["productId"] == "p1"
    assert json.loads(deny.calls.last.request.content) == {"approve": False}
    assert json.loads(add.calls.last.request.content) == {"prompts": ["add tests"]}
    assert sources.calls.last.request.url.params["namespace"] == "team-a"


def test_coder_deploy_reconciliation_requires_explicit_outcome():
    client = MockartyClient(base_url="https://mockarty.test", api_key="mk_test", namespace="team-a")
    try:
        with pytest.raises(ValueError, match="applied or not_applied"):
            client.coder_delivery.reconcile_deploy("m1", "")
        with pytest.raises(ValueError, match="source and expression"):
            client.coder_delivery.query_observability({"source": "prometheus"})
    finally:
        client.close()
