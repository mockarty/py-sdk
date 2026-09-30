import httpx
import pytest
from mockarty.errors import MockartyError


def response(request, mode="ok"):
    offset = int(request.url.params.get("offset", "0"))
    total = 2 if mode != "request-cap" else 101
    if mode == "changing-total" and offset:
        total = 3
    if mode == "oversized-total":
        total = 10001
    item = {"id": "same" if mode == "duplicate" else f"a{offset}", "namespace": "test-ns", "parentKind": "test_plan_run", "parentId": "run"}
    if mode == "foreign-owner":
        item["parentId"] = "foreign"
    items = [] if mode == "empty-more" else [item]
    page = {"items": items, "total": total, "offset": 1 if mode == "bad-offset" else offset, "limit": 500, "snapshot": "a" * 64, "hasMore": offset + len(items) < total}
    if mode == "missing-meta":
        del page["total"]
    if mode == "missing-snapshot":
        del page["snapshot"]
    if mode == "changed-snapshot" and offset:
        page["snapshot"] = "b" * 64
    return httpx.Response(200, json=page)


def test_launch_attachment_every_page(client, mock_api):
    route = mock_api.get("/api/v1/namespaces/test-ns/tcm/attachments").mock(side_effect=response)
    assert len(client.tcm.list_attachments("test_plan_run", "run")) == 2
    assert route.call_count == 2


@pytest.mark.parametrize("mode", ["duplicate", "empty-more", "changing-total", "bad-offset", "foreign-owner", "oversized-total", "missing-meta", "missing-snapshot", "changed-snapshot", "request-cap"])
def test_launch_attachment_reject_partial(client, mock_api, mode):
    mock_api.get("/api/v1/namespaces/test-ns/tcm/attachments").mock(side_effect=lambda request: response(request, mode))
    with pytest.raises(MockartyError):
        client.tcm.list_attachments("test_plan_run", "run")

@pytest.mark.parametrize("mode", ["ok", "duplicate", "empty-more", "changing-total", "bad-offset", "foreign-owner", "oversized-total", "missing-meta", "missing-snapshot", "changed-snapshot", "request-cap"])
def test_async_launch_attachment_pages(mode):
    import asyncio
    import respx
    from mockarty import AsyncMockartyClient

    async def journey():
        with respx.mock as router:
            route = router.get("http://test/api/v1/namespaces/test-ns/tcm/attachments").mock(side_effect=lambda request: response(request, mode))
            async with AsyncMockartyClient(base_url="http://test", namespace="test-ns") as client:
                if mode == "ok":
                    assert len(await client.tcm.list_attachments("test_plan_run", "run")) == 2
                    assert route.call_count == 2
                else:
                    with pytest.raises(MockartyError):
                        await client.tcm.list_attachments("test_plan_run", "run")
    asyncio.run(journey())


def test_async_launch_attachment_cancellation():
    import asyncio
    import respx
    from mockarty import AsyncMockartyClient

    async def journey():
        entered = asyncio.Event()
        async def paused(request):
            entered.set()
            await asyncio.Future()
        with respx.mock as router:
            router.get("http://test/api/v1/namespaces/test-ns/tcm/attachments").mock(side_effect=paused)
            async with AsyncMockartyClient(base_url="http://test", namespace="test-ns") as client:
                task = asyncio.create_task(client.tcm.list_attachments("test_plan_run", "run"))
                await entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
    asyncio.run(journey())
