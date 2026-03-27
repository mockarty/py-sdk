# Copyright (c) 2026 Mockarty. All rights reserved.

"""Shared pytest fixtures for SDK tests."""

from __future__ import annotations

import pytest
import respx

from mockarty import MockartyClient


@pytest.fixture
def base_url() -> str:
    """Base URL used across all tests."""
    return "http://localhost:5770"


@pytest.fixture
def api_key() -> str:
    """Fake API key for testing."""
    return "mk_test_key_12345"


@pytest.fixture
def client(base_url: str, api_key: str) -> MockartyClient:
    """Provide a MockartyClient configured for testing."""
    c = MockartyClient(
        base_url=base_url,
        api_key=api_key,
        namespace="test-ns",
        timeout=5.0,
        max_retries=0,
    )
    yield c  # type: ignore[misc]
    c.close()


@pytest.fixture
def mock_api(base_url: str) -> respx.MockRouter:
    """Provide a respx router scoped to the test base URL."""
    with respx.mock(base_url=base_url) as router:
        yield router
