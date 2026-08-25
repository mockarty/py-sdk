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
            200,
            json={
                "id": "e1",
                "kind": "pitfall",
                "provenance": "external",
                "state": "candidate",
                "reviewRequired": True,
            },
        )
    )
    assert (
        client.experience.search(query="retry", kinds=["pitfall"]).results[0].id == "e1"
    )
    assert search.calls.last.request.url.params["kinds"] == "pitfall"
    created = client.experience.record(text="retry", source="run", kind="pitfall")
    assert created.id == "e1"
    assert created.state == "candidate"
    assert created.review_required is True
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


@respx.mock
def test_experience_review_automation(client: MockartyClient) -> None:
    queue = respx.get(
        "http://localhost:5770/api/v1/autotester/context/knowledge/review"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"id": "k-1", "state": "candidate", "version": 1}],
                "nextCursor": "next",
            },
        )
    )
    detail = respx.get(
        "http://localhost:5770/api/v1/autotester/context/knowledge/review/k-1"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "item": {
                    "id": "k-1",
                    "state": "candidate",
                    "version": 1,
                    "metadata": {"instruction": "untrusted"},
                    "contentSha256": "abc123",
                },
                "relations": [],
                "history": [],
            },
        )
    )
    decide = respx.post(
        "http://localhost:5770/api/v1/autotester/context/knowledge/review/k-1"
    ).mock(
        return_value=httpx.Response(
            200, json={"item": {"id": "k-1", "state": "deleted", "version": 2}}
        )
    )

    page = client.experience.list_review(limit=20)
    assert page.items[0].id == "k-1"
    assert page.next_cursor == "next"
    assert queue.calls.last.request.url.params["state"] == "candidate"
    reviewed = client.experience.get_review("k-1").item
    assert reviewed.version == 1
    assert reviewed.metadata == {"instruction": "untrusted"}
    assert reviewed.content_sha256 == "abc123"
    assert detail.called
    result = client.experience.review(
        "k-1",
        decision="reject",
        expected_version=1,
        reason="unsupported",
        idempotency_key="review-1",
    )
    assert result.item.state == "deleted"
    assert decide.calls.last.request.read()
    assert decide.calls.last.request.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
@respx.mock
async def test_async_experience_review(base_url: str, api_key: str) -> None:
    route = respx.get(
        f"{base_url}/api/v1/autotester/context/knowledge/review"
    ).mock(return_value=httpx.Response(200, json={"items": [], "nextCursor": ""}))
    async with AsyncMockartyClient(
        base_url=base_url, api_key=api_key, max_retries=0
    ) as client:
        assert (await client.experience.list_review()).items == []
    assert route.called


def test_experience_review_validation(client: MockartyClient) -> None:
    with pytest.raises(ValueError, match="id is required"):
        client.experience.get_review(" ")
    with pytest.raises(ValueError, match="decision"):
        client.experience.review(
            "k-1",
            decision="approve",
            expected_version=1,
            reason="checked",
            idempotency_key="review-1",
        )
