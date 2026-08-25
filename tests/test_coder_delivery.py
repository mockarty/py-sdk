import asyncio
import json

import httpx

import respx

from mockarty import AsyncMockartyClient, MockartyClient


def test_coder_delivery_routes_and_approval():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, dict(request.url.params)))
        if request.url.path.endswith("/approve"):
            assert json.loads(request.content) == {"approve": True}
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
    assert len(seen) == 7


@respx.mock
def test_async_coder_delivery_preserves_product_and_explicit_denial():
    start = respx.post("https://mockarty.test/api/v1/coder/missions").mock(
        return_value=httpx.Response(202, json={"id": "m1", "productId": "p1"})
    )
    deny = respx.post("https://mockarty.test/api/v1/coder/missions/m1/approve").mock(
        return_value=httpx.Response(200, json={"id": "m1", "approval": "denied"})
    )

    async def run():
        async with AsyncMockartyClient(base_url="https://mockarty.test", api_key="mk_test", namespace="team-a") as client:
            await client.coder_delivery.start_mission({"goal": "ship", "repoUrl": "https://git.test/app.git", "productId": "p1"})
            await client.coder_delivery.approve_mission("m1", False)

    asyncio.run(run())
    assert json.loads(start.calls.last.request.content)["productId"] == "p1"
    assert json.loads(deny.calls.last.request.content) == {"approve": False}
