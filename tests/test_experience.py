"""Experience API parity tests."""

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_experience_search_and_record(client: MockartyClient) -> None:
    search = respx.get(
        "http://localhost:5770/api/v1/autotester/context/knowledge/search"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "e1",
                        "kind": "pitfall",
                        "text": "retry",
                        "source": "run",
                        "provenance": "external",
                        "score": 1,
                    }
                ],
                "total": 1,
                "available": True,
                "engine": "bm25",
            },
        )
    )
    record = respx.post(
        "http://localhost:5770/api/v1/autotester/context/knowledge"
    ).mock(
        return_value=httpx.Response(
            200, json={"id": "e1", "kind": "pitfall", "provenance": "external"}
        )
    )
    assert (
        client.experience.search(query="retry", kinds=["pitfall"]).results[0].id == "e1"
    )
    assert search.calls.last.request.url.params["kinds"] == "pitfall"
    assert (
        client.experience.record(text="retry", source="run", kind="pitfall").id == "e1"
    )
    assert record.called


@pytest.mark.asyncio
@respx.mock
async def test_async_experience(base_url: str, api_key: str) -> None:
    respx.get(f"{base_url}/api/v1/autotester/context/knowledge/search").mock(
        return_value=httpx.Response(
            200, json={"results": [], "total": 0, "available": False, "engine": ""}
        )
    )
    async with AsyncMockartyClient(
        base_url=base_url, api_key=api_key, max_retries=0
    ) as client:
        assert (await client.experience.search(query="retry")).results == []
