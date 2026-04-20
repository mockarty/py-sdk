# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the unified entity-search API (sync + async)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import (
    ENTITY_TYPE_MOCK,
    ENTITY_TYPE_TEST_PLAN,
    AsyncMockartyClient,
    EntitySearchResponse,
    MockartyClient,
)


# ---------------------------------------------------------------------------
# Synchronous
# ---------------------------------------------------------------------------


class TestEntitySearchSync:
    @respx.mock
    def test_search_builds_query(self, client: MockartyClient) -> None:
        route = respx.get("http://localhost:5770/api/v1/entity-search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "11111111-2222-3333-4444-555555555555",
                            "type": ENTITY_TYPE_TEST_PLAN,
                            "name": "smoke-suite",
                            "namespace": "production",
                            "createdAt": "2026-04-19T12:00:00Z",
                            "numericId": 42,
                        }
                    ],
                    "total": 1,
                },
            )
        )

        resp = client.entity_search.search(
            entity_type=ENTITY_TYPE_TEST_PLAN,
            namespace="production",
            query="smoke",
            limit=25,
            offset=5,
        )
        assert isinstance(resp, EntitySearchResponse)
        assert resp.total == 1
        assert len(resp.items) == 1
        item = resp.items[0]
        assert item.name == "smoke-suite"
        assert item.numeric_id == 42
        assert item.created_at == "2026-04-19T12:00:00Z"

        params = route.calls.last.request.url.params
        assert params["type"] == ENTITY_TYPE_TEST_PLAN
        assert params["namespace"] == "production"
        assert params["q"] == "smoke"
        assert params["limit"] == "25"
        assert params["offset"] == "5"

    @respx.mock
    def test_search_omits_zero_params(self, client: MockartyClient) -> None:
        route = respx.get("http://localhost:5770/api/v1/entity-search").mock(
            return_value=httpx.Response(200, json={"items": [], "total": 0})
        )

        client.entity_search.search(entity_type=ENTITY_TYPE_MOCK)

        params = route.calls.last.request.url.params
        assert params["type"] == ENTITY_TYPE_MOCK
        # Optional fields MUST be absent — not present-with-empty-value.
        for key in ("namespace", "q", "limit", "offset"):
            assert key not in params, f"expected {key!r} omitted"

    def test_search_requires_type(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError, match="entity_type is required"):
            client.entity_search.search(entity_type="   ")

    @respx.mock
    def test_search_normalises_missing_items(self, client: MockartyClient) -> None:
        # Server contract guarantees items is a list, but we still want callers
        # to never receive None — the Pydantic default_factory protects that.
        respx.get("http://localhost:5770/api/v1/entity-search").mock(
            return_value=httpx.Response(200, json={"total": 0})
        )
        resp = client.entity_search.search(entity_type=ENTITY_TYPE_MOCK)
        assert resp.items == []
        assert resp.total == 0


# ---------------------------------------------------------------------------
# Asynchronous
# ---------------------------------------------------------------------------


class TestEntitySearchAsync:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_search(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/api/v1/entity-search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                            "type": ENTITY_TYPE_MOCK,
                            "name": "users-mock",
                            "namespace": "test-ns",
                            "createdAt": "2026-04-20T08:00:00Z",
                        }
                    ],
                    "total": 1,
                },
            )
        )
        async with AsyncMockartyClient(
            base_url=base_url, api_key=api_key, namespace="test-ns", max_retries=0
        ) as c:
            resp = await c.entity_search.search(entity_type=ENTITY_TYPE_MOCK)
            assert resp.total == 1
            assert resp.items[0].numeric_id is None
