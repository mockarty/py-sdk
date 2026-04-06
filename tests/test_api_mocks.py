# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for MockAPI and other API resources with respx-mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient, MockBuilder, AssertAction
from mockarty.models.common import HealthResponse
from mockarty.models.mock import Mock, SaveMockResponse


# ── MockAPI CRUD ──────────────────────────────────────────────────────


class TestMockAPICreate:
    """Test mock creation via the API."""

    @respx.mock
    def test_create_from_model(self, client: MockartyClient) -> None:
        """Create a mock from a Mock model instance."""
        respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "overwritten": False,
                    "mock": {
                        "id": "new-mock",
                        "http": {"route": "/test", "httpMethod": "GET"},
                        "response": {"statusCode": 200, "payload": "ok"},
                    },
                },
            )
        )

        mock = Mock(
            id="new-mock",
            http={"route": "/test", "httpMethod": "GET"},
            response={"statusCode": 200, "payload": "ok"},
        )
        result = client.mocks.create(mock)

        assert isinstance(result, SaveMockResponse)
        assert result.overwritten is False
        assert result.mock.id == "new-mock"

    @respx.mock
    def test_create_from_dict(self, client: MockartyClient) -> None:
        """Create a mock from a plain dict."""
        respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "overwritten": False,
                    "mock": {"id": "dict-mock"},
                },
            )
        )

        result = client.mocks.create({"id": "dict-mock"})
        assert result.mock.id == "dict-mock"

    @respx.mock
    def test_create_from_builder(self, client: MockartyClient) -> None:
        """Create a mock built with MockBuilder."""
        respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "overwritten": False,
                    "mock": {
                        "id": "builder-mock",
                        "http": {"route": "/api/hello", "httpMethod": "GET"},
                        "response": {"statusCode": 200, "payload": {"msg": "hello"}},
                    },
                },
            )
        )

        mock = (
            MockBuilder.http("/api/hello", "GET")
            .id("builder-mock")
            .respond(200, body={"msg": "hello"})
            .build()
        )
        result = client.mocks.create(mock)
        assert result.mock.id == "builder-mock"

    @respx.mock
    def test_create_returns_overwritten(self, client: MockartyClient) -> None:
        """Server indicates when an existing mock was overwritten."""
        respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "overwritten": True,
                    "mock": {"id": "existing"},
                },
            )
        )

        result = client.mocks.create({"id": "existing"})
        assert result.overwritten is True


class TestMockAPIGet:
    """Test mock retrieval."""

    @respx.mock
    def test_get_by_id(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/mocks/my-mock").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "my-mock",
                    "http": {"route": "/api/test", "httpMethod": "GET"},
                    "response": {"statusCode": 200},
                    "tags": ["test"],
                },
            )
        )

        mock = client.mocks.get("my-mock")
        assert mock.id == "my-mock"
        assert mock.http.route == "/api/test"
        assert mock.tags == ["test"]


class TestMockAPIList:
    """Test mock listing."""

    @respx.mock
    def test_list_returns_array(self, client: MockartyClient) -> None:
        """Server returns a plain JSON array of mocks."""
        respx.get("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "mock-1", "http": {"route": "/a"}},
                    {"id": "mock-2", "http": {"route": "/b"}},
                ],
            )
        )

        page = client.mocks.list()
        assert len(page.items) == 2
        assert page.items[0].id == "mock-1"
        assert page.items[1].id == "mock-2"
        assert page.total == 2

    @respx.mock
    def test_list_returns_paginated(self, client: MockartyClient) -> None:
        """Server returns a paginated envelope."""
        respx.get("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [{"id": "mock-1"}],
                    "total": 50,
                    "offset": 10,
                    "limit": 20,
                },
            )
        )

        page = client.mocks.list(offset=10, limit=20)
        assert len(page.items) == 1
        assert page.total == 50

    @respx.mock
    def test_list_with_filters(self, client: MockartyClient) -> None:
        """Query parameters are correctly passed."""
        route = respx.get("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(200, json=[])
        )

        client.mocks.list(
            namespace="production",
            tags=["orders", "v2"],
            search="user",
            offset=5,
            limit=25,
        )

        assert route.called
        request = route.calls.last.request
        assert "namespace=production" in str(request.url)
        assert "tags=orders%2Cv2" in str(request.url) or "tags=orders,v2" in str(request.url)
        assert "search=user" in str(request.url)


class TestMockAPIUpdate:
    """Test mock update."""

    @respx.mock
    def test_update_sets_id(self, client: MockartyClient) -> None:
        """Update injects the mock_id into the payload."""
        route = respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={"overwritten": True, "mock": {"id": "upd-1"}},
            )
        )

        mock = Mock(http={"route": "/updated"})
        client.mocks.update("upd-1", mock)

        assert route.called
        assert mock.id == "upd-1"


class TestMockAPIDelete:
    """Test mock deletion."""

    @respx.mock
    def test_delete(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/mocks/del-1").mock(
            return_value=httpx.Response(200, json={"status": "deleted"})
        )

        client.mocks.delete("del-1")
        assert route.called

    @respx.mock
    def test_restore(self, client: MockartyClient) -> None:
        route = respx.post("http://localhost:5770/api/v1/mocks/res-1/restore").mock(
            return_value=httpx.Response(200, json={"status": "restored"})
        )

        client.mocks.restore("res-1")
        assert route.called

    @respx.mock
    def test_purge(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/mocks/purge-1/purge").mock(
            return_value=httpx.Response(200, json={"status": "purged"})
        )

        client.mocks.purge("purge-1")
        assert route.called


class TestMockAPILogs:
    """Test mock log retrieval."""

    @respx.mock
    def test_logs_as_list(self, client: MockartyClient) -> None:
        """Server returns a plain list of log entries."""
        respx.get("http://localhost:5770/api/v1/mocks/log-mock/logs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "l1", "calledAt": "2024-01-01T00:00:00Z", "req": {"method": "GET"}},
                    {"id": "l2", "calledAt": "2024-01-01T00:01:00Z", "req": {"method": "POST"}},
                ],
            )
        )

        logs = client.mocks.logs("log-mock")
        assert len(logs.logs) == 2
        assert logs.logs[0].id == "l1"

    @respx.mock
    def test_logs_as_envelope(self, client: MockartyClient) -> None:
        """Server returns a logs envelope with total."""
        respx.get("http://localhost:5770/api/v1/mocks/log-mock/logs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "logs": [{"id": "l1"}],
                    "total": 100,
                },
            )
        )

        logs = client.mocks.logs("log-mock")
        assert len(logs.logs) == 1
        assert logs.total == 100


class TestMockAPIChain:
    """Test chain operations."""

    @respx.mock
    def test_get_chain(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/mocks/chains/chain-1").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "step-1", "chainId": "chain-1"},
                    {"id": "step-2", "chainId": "chain-1"},
                ],
            )
        )

        mocks = client.mocks.chain("chain-1")
        assert len(mocks) == 2
        assert mocks[0].chain_id == "chain-1"

    @respx.mock
    def test_delete_chain(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/mocks/chains/chain-1").mock(
            return_value=httpx.Response(200)
        )
        client.mocks.delete_chain("chain-1")
        assert route.called


class TestMockAPIBatch:
    """Test batch operations."""

    @respx.mock
    def test_batch_create(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200,
                json={"overwritten": False, "mock": {"id": "batch-mock"}},
            )
        )

        results = client.mocks.batch_create([
            {"id": "b1"},
            {"id": "b2"},
        ])
        assert len(results) == 2

    @respx.mock
    def test_batch_delete(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/mocks/batch").mock(
            return_value=httpx.Response(200)
        )

        client.mocks.batch_delete(["d1", "d2", "d3"])
        assert route.called


# ── NamespaceAPI ──────────────────────────────────────────────────────


class TestNamespaceAPI:
    @respx.mock
    def test_create_namespace(self, client: MockartyClient) -> None:
        route = respx.post("http://localhost:5770/api/v1/namespaces").mock(
            return_value=httpx.Response(200)
        )
        client.namespaces.create("new-ns")
        assert route.called

    @respx.mock
    def test_list_namespaces_array(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/namespaces").mock(
            return_value=httpx.Response(
                200, json=["sandbox", "production", "staging"]
            )
        )
        ns = client.namespaces.list()
        assert ns == ["sandbox", "production", "staging"]

    @respx.mock
    def test_list_namespaces_envelope(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/namespaces").mock(
            return_value=httpx.Response(
                200, json={"namespaces": ["ns1", "ns2"]}
            )
        )
        ns = client.namespaces.list()
        assert ns == ["ns1", "ns2"]


# ── StoreAPI ──────────────────────────────────────────────────────────


class TestStoreAPI:
    @respx.mock
    def test_global_get(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/stores/global").mock(
            return_value=httpx.Response(200, json={"counter": 42, "flag": True})
        )
        data = client.stores.global_get()
        assert data["counter"] == 42
        assert data["flag"] is True

    @respx.mock
    def test_global_set(self, client: MockartyClient) -> None:
        route = respx.post("http://localhost:5770/api/v1/stores/global").mock(
            return_value=httpx.Response(200)
        )
        client.stores.global_set("counter", 100)
        assert route.called

    @respx.mock
    def test_global_delete(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/stores/global/counter").mock(
            return_value=httpx.Response(200)
        )
        client.stores.global_delete("counter")
        assert route.called

    @respx.mock
    def test_chain_get(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/stores/chain/ch-1").mock(
            return_value=httpx.Response(200, json={"step": "processing"})
        )
        data = client.stores.chain_get("ch-1")
        assert data["step"] == "processing"

    @respx.mock
    def test_chain_set(self, client: MockartyClient) -> None:
        route = respx.post("http://localhost:5770/api/v1/stores/chain/ch-1").mock(
            return_value=httpx.Response(200)
        )
        client.stores.chain_set("ch-1", "step", "done")
        assert route.called

    @respx.mock
    def test_chain_delete(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/stores/chain/ch-1/step").mock(
            return_value=httpx.Response(200)
        )
        client.stores.chain_delete("ch-1", "step")
        assert route.called

    @respx.mock
    def test_global_set_many(self, client: MockartyClient) -> None:
        route = respx.post("http://localhost:5770/api/v1/stores/global").mock(
            return_value=httpx.Response(200)
        )
        client.stores.global_set_many({"a": 1, "b": 2})
        assert route.call_count == 2

    @respx.mock
    def test_global_delete_many(self, client: MockartyClient) -> None:
        route_a = respx.delete("http://localhost:5770/api/v1/stores/global/a").mock(
            return_value=httpx.Response(200)
        )
        route_b = respx.delete("http://localhost:5770/api/v1/stores/global/b").mock(
            return_value=httpx.Response(200)
        )
        client.stores.global_delete_many(["a", "b"])
        assert route_a.called
        assert route_b.called


# ── HealthAPI ─────────────────────────────────────────────────────────


class TestHealthAPI:
    @respx.mock
    def test_health_check(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/health").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "ok",
                    "releaseId": "1.2.3",
                    "uptime": "5h30m",
                },
            )
        )
        health = client.health.check()
        assert isinstance(health, HealthResponse)
        assert health.status == "ok"
        assert health.release_id == "1.2.3"

    @respx.mock
    def test_live_returns_true(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/health/live").mock(
            return_value=httpx.Response(200)
        )
        assert client.health.live() is True

    @respx.mock
    def test_live_returns_false_on_error(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/health/live").mock(
            return_value=httpx.Response(503)
        )
        assert client.health.live() is False

    @respx.mock
    def test_ready_returns_true(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/health/ready").mock(
            return_value=httpx.Response(200)
        )
        assert client.health.ready() is True

    @respx.mock
    def test_ready_returns_false_on_error(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/health/ready").mock(
            return_value=httpx.Response(503)
        )
        assert client.health.ready() is False


# ── Request header verification ───────────────────────────────────────


class TestRequestHeaders:
    """Verify that the client sends the correct headers on every request."""

    @respx.mock
    def test_auth_header_sent(self, client: MockartyClient) -> None:
        """Authorization header is sent on API calls."""
        route = respx.get("http://localhost:5770/health").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client.health.check()

        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer mk_test_key_12345"

    @respx.mock
    def test_namespace_header_sent(self, client: MockartyClient) -> None:
        """X-Namespace header is sent on API calls."""
        route = respx.get("http://localhost:5770/health").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client.health.check()

        request = route.calls.last.request
        assert request.headers["X-Namespace"] == "test-ns"

    @respx.mock
    def test_content_type_header_sent(self, client: MockartyClient) -> None:
        """Content-Type header is sent on API calls."""
        route = respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(
                200, json={"overwritten": False, "mock": {"id": "x"}}
            )
        )
        client.mocks.create({"id": "x"})

        request = route.calls.last.request
        assert "application/json" in request.headers["Content-Type"]
