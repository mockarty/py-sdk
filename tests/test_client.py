# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for MockartyClient initialization, configuration, and error handling."""

from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import pytest
import respx

from mockarty import (
    AsyncMockartyClient,
    MockartyClient,
)
from mockarty.errors import (
    MockartyAPIError,
    MockartyConflictError,
    MockartyForbiddenError,
    MockartyNotFoundError,
    MockartyRateLimitError,
    MockartyServerError,
    MockartyUnauthorizedError,
)


# ── Client creation ──────────────────────────────────────────────────


class TestClientCreation:
    """Test client creation with various configurations."""

    def test_default_base_url(self) -> None:
        """Client uses localhost:5770 by default."""
        client = MockartyClient()
        assert client.base_url == "http://localhost:5770"
        client.close()

    def test_custom_base_url(self) -> None:
        """Client respects a custom base URL."""
        client = MockartyClient(base_url="http://my-server:8080")
        assert client.base_url == "http://my-server:8080"
        client.close()

    def test_base_url_trailing_slash_stripped(self) -> None:
        """Trailing slash is removed from base URL."""
        client = MockartyClient(base_url="http://my-server:8080/")
        assert client.base_url == "http://my-server:8080"
        client.close()

    def test_default_namespace(self) -> None:
        """Default namespace is 'sandbox'."""
        client = MockartyClient()
        assert client.namespace == "sandbox"
        client.close()

    def test_custom_namespace(self) -> None:
        """Client respects a custom namespace."""
        client = MockartyClient(namespace="production")
        assert client.namespace == "production"
        client.close()

    def test_namespace_setter(self) -> None:
        """Namespace can be changed after creation."""
        client = MockartyClient()
        client.namespace = "staging"
        assert client.namespace == "staging"
        client.close()


class TestClientEnvVars:
    """Test environment variable fallback."""

    def test_base_url_from_env(self) -> None:
        """Client reads MOCKARTY_BASE_URL from environment."""
        with patch.dict(os.environ, {"MOCKARTY_BASE_URL": "http://env-server:9999"}):
            client = MockartyClient()
            assert client.base_url == "http://env-server:9999"
            client.close()

    def test_api_key_from_env(self) -> None:
        """Client reads MOCKARTY_API_KEY from environment."""
        with patch.dict(os.environ, {"MOCKARTY_API_KEY": "mk_env_key_xyz"}):
            client = MockartyClient()
            assert client._api_key == "mk_env_key_xyz"
            client.close()

    def test_explicit_overrides_env(self) -> None:
        """Explicit arguments take precedence over env vars."""
        with patch.dict(
            os.environ,
            {"MOCKARTY_BASE_URL": "http://env:1", "MOCKARTY_API_KEY": "env-key"},
        ):
            client = MockartyClient(
                base_url="http://explicit:2", api_key="explicit-key"
            )
            assert client.base_url == "http://explicit:2"
            assert client._api_key == "explicit-key"
            client.close()


class TestClientHeaders:
    """Test that the correct headers are set on the HTTP client."""

    def test_auth_header_when_key_provided(self) -> None:
        """Authorization header is set when api_key is provided."""
        client = MockartyClient(api_key="my-key")
        assert client._http.headers["Authorization"] == "Bearer my-key"
        client.close()

    def test_no_auth_header_when_no_key(self) -> None:
        """No Authorization header when api_key is None."""
        with patch.dict(os.environ, {}, clear=True):
            # Ensure env var doesn't leak in
            os.environ.pop("MOCKARTY_API_KEY", None)
            client = MockartyClient()
            assert "Authorization" not in client._http.headers
            client.close()

    def test_namespace_header(self) -> None:
        """X-Namespace header matches the configured namespace."""
        client = MockartyClient(namespace="my-ns")
        assert client._http.headers["X-Namespace"] == "my-ns"
        client.close()

    def test_content_type_header(self) -> None:
        """Content-Type is set to application/json."""
        client = MockartyClient()
        assert client._http.headers["Content-Type"] == "application/json"
        client.close()


class TestContextManager:
    """Test context manager protocol."""

    def test_sync_context_manager(self) -> None:
        """Sync client works as a context manager."""
        with MockartyClient() as client:
            assert isinstance(client, MockartyClient)
        # After exiting, the client should be closed (no assertion possible
        # without inspecting internals, but it should not raise)

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Async client works as an async context manager."""
        async with AsyncMockartyClient() as client:
            assert isinstance(client, AsyncMockartyClient)


class TestAPIResources:
    """Test that API resource properties return the correct types."""

    def test_mocks_property(self, client: MockartyClient) -> None:
        """mocks property returns MockAPI."""
        from mockarty.api.mocks import MockAPI

        assert isinstance(client.mocks, MockAPI)

    def test_namespaces_property(self, client: MockartyClient) -> None:
        """namespaces property returns NamespaceAPI."""
        from mockarty.api.namespaces import NamespaceAPI

        assert isinstance(client.namespaces, NamespaceAPI)

    def test_stores_property(self, client: MockartyClient) -> None:
        """stores property returns StoreAPI."""
        from mockarty.api.stores import StoreAPI

        assert isinstance(client.stores, StoreAPI)

    def test_collections_property(self, client: MockartyClient) -> None:
        """collections property returns CollectionAPI."""
        from mockarty.api.collections import CollectionAPI

        assert isinstance(client.collections, CollectionAPI)

    def test_perf_property(self, client: MockartyClient) -> None:
        """perf property returns PerfAPI."""
        from mockarty.api.perf import PerfAPI

        assert isinstance(client.perf, PerfAPI)

    def test_health_property(self, client: MockartyClient) -> None:
        """health property returns HealthAPI."""
        from mockarty.api.health import HealthAPI

        assert isinstance(client.health, HealthAPI)

    def test_resources_cached(self, client: MockartyClient) -> None:
        """API resource instances are cached (same object on repeated access)."""
        assert client.mocks is client.mocks
        assert client.stores is client.stores

    def test_resources_reset_on_namespace_change(self, client: MockartyClient) -> None:
        """Changing namespace resets cached API resources."""
        first_mocks = client.mocks
        client.namespace = "other-ns"
        assert client.mocks is not first_mocks


# ── Error handling ───────────────────────────────────────────────────


class TestErrorHandling:
    """Test that HTTP errors are mapped to the correct SDK exceptions."""

    @respx.mock
    def test_401_raises_unauthorized(self, client: MockartyClient) -> None:
        """401 response raises MockartyUnauthorizedError."""
        respx.get("http://localhost:5770/api/v1/mocks/abc").mock(
            return_value=httpx.Response(401, json={"error": "invalid token"})
        )
        with pytest.raises(MockartyUnauthorizedError) as exc_info:
            client.mocks.get("abc")
        assert exc_info.value.status_code == 401
        assert "invalid token" in exc_info.value.message

    @respx.mock
    def test_403_raises_forbidden(self, client: MockartyClient) -> None:
        """403 response raises MockartyForbiddenError."""
        respx.get("http://localhost:5770/api/v1/mocks/abc").mock(
            return_value=httpx.Response(403, json={"error": "forbidden"})
        )
        with pytest.raises(MockartyForbiddenError):
            client.mocks.get("abc")

    @respx.mock
    def test_404_raises_not_found(self, client: MockartyClient) -> None:
        """404 response raises MockartyNotFoundError."""
        respx.get("http://localhost:5770/api/v1/mocks/missing").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        with pytest.raises(MockartyNotFoundError):
            client.mocks.get("missing")

    @respx.mock
    def test_409_raises_conflict(self, client: MockartyClient) -> None:
        """409 response raises MockartyConflictError."""
        respx.post("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(409, json={"error": "conflict"})
        )
        with pytest.raises(MockartyConflictError):
            client.mocks.create({"id": "dup"})

    @respx.mock
    def test_429_raises_rate_limit(self, client: MockartyClient) -> None:
        """429 response raises MockartyRateLimitError."""
        respx.get("http://localhost:5770/api/v1/mocks").mock(
            return_value=httpx.Response(429, json={"error": "rate limited"})
        )
        with pytest.raises(MockartyRateLimitError):
            client.mocks.list()

    @respx.mock
    def test_500_raises_server_error(self, client: MockartyClient) -> None:
        """500 response raises MockartyServerError."""
        respx.get("http://localhost:5770/api/v1/mocks/abc").mock(
            return_value=httpx.Response(500, json={"error": "internal error"})
        )
        with pytest.raises(MockartyServerError):
            client.mocks.get("abc")

    @respx.mock
    def test_generic_4xx_raises_api_error(self, client: MockartyClient) -> None:
        """Unhandled 4xx codes raise MockartyAPIError."""
        respx.get("http://localhost:5770/api/v1/mocks/abc").mock(
            return_value=httpx.Response(422, json={"error": "unprocessable"})
        )
        with pytest.raises(MockartyAPIError) as exc_info:
            client.mocks.get("abc")
        assert exc_info.value.status_code == 422

    @respx.mock
    def test_error_request_id_extracted(self, client: MockartyClient) -> None:
        """X-Request-Id header is captured in the exception."""
        respx.get("http://localhost:5770/api/v1/mocks/abc").mock(
            return_value=httpx.Response(
                500,
                json={"error": "boom"},
                headers={"X-Request-Id": "req-123"},
            )
        )
        with pytest.raises(MockartyServerError) as exc_info:
            client.mocks.get("abc")
        assert exc_info.value.request_id == "req-123"

    @respx.mock
    def test_error_with_plain_text_body(self, client: MockartyClient) -> None:
        """Error response with non-JSON body is handled gracefully."""
        respx.get("http://localhost:5770/api/v1/mocks/abc").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(MockartyServerError) as exc_info:
            client.mocks.get("abc")
        assert "Internal Server Error" in exc_info.value.message
