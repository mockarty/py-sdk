# Copyright (c) 2026 Mockarty. All rights reserved.

"""pytest fixtures for testing with Mockarty.

Register these fixtures by adding to ``conftest.py``::

    pytest_plugins = ["mockarty.testing.fixtures"]

Or import them directly::

    from mockarty.testing.fixtures import mockarty_client, mock_cleanup
"""

from __future__ import annotations

import os
from typing import Any, Callable, Generator

import pytest

from mockarty.client import MockartyClient
from mockarty.models.mock import Mock


@pytest.fixture
def mockarty_client() -> Generator[MockartyClient, None, None]:
    """Provide a :class:`MockartyClient` that auto-closes after the test.

    Configuration is read from environment variables:

    - ``MOCKARTY_BASE_URL`` (default: ``http://localhost:5770``)
    - ``MOCKARTY_API_KEY`` (default: ``None``)
    """
    client = MockartyClient(
        base_url=os.environ.get("MOCKARTY_BASE_URL", "http://localhost:5770"),
        api_key=os.environ.get("MOCKARTY_API_KEY"),
    )
    yield client
    client.close()


@pytest.fixture
def mock_cleanup(
    mockarty_client: MockartyClient,
) -> Generator[Callable[[Mock | dict[str, Any]], Mock], None, None]:
    """Create mocks that are automatically deleted after the test.

    Usage::

        def test_something(mock_cleanup):
            from mockarty import MockBuilder
            mock = MockBuilder.http("/test", "GET").respond(200).build()
            created = mock_cleanup(mock)
            assert created.id is not None

    Returns:
        A callable that creates a mock and tracks it for cleanup.
    """
    created_ids: list[str] = []

    def _create(mock: Mock | dict[str, Any]) -> Mock:
        result = mockarty_client.mocks.create(mock)
        if result.mock.id:
            created_ids.append(result.mock.id)
        return result.mock

    yield _create

    for mock_id in created_ids:
        try:
            mockarty_client.mocks.delete(mock_id)
        except Exception:
            pass
