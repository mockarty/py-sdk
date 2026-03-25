"""pytest fixtures and integration testing patterns.

This file demonstrates how to use the built-in Mockarty pytest fixtures
for integration tests.

Setup:
  1. Add to your conftest.py:
       pytest_plugins = ["mockarty.testing.fixtures"]

  2. Set environment variables:
       export MOCKARTY_BASE_URL="http://localhost:5770"
       export MOCKARTY_API_KEY="your-api-key"

  3. Run tests:
       pytest examples/testing_fixtures.py -v

Available fixtures:
  - ``mockarty_client`` -- auto-closing MockartyClient instance
  - ``mock_cleanup``    -- creates mocks that auto-delete after each test
"""

import os

import pytest

from mockarty import AssertAction, MockBuilder, MockartyClient


# ---------------------------------------------------------------------------
# If not using pytest_plugins, you can import fixtures directly in conftest.py:
#
#   from mockarty.testing.fixtures import mockarty_client, mock_cleanup
# ---------------------------------------------------------------------------

# Register the fixtures plugin
pytest_plugins = ["mockarty.testing.fixtures"]


class TestBasicMocking:
    """Basic mock lifecycle tests."""

    def test_create_and_fetch_mock(self, mockarty_client: MockartyClient) -> None:
        """Create a mock and verify it can be fetched."""
        mock = (
            MockBuilder.http("/test/fixture-demo", "GET")
            .id("fixture-test-1")
            .respond(200, body={"test": True})
            .build()
        )

        result = mockarty_client.mocks.create(mock)
        assert result.mock.id == "fixture-test-1"

        fetched = mockarty_client.mocks.get("fixture-test-1")
        assert fetched.http.route == "/test/fixture-demo"

        # Manual cleanup (or use mock_cleanup fixture for auto-cleanup)
        mockarty_client.mocks.delete("fixture-test-1")

    def test_with_auto_cleanup(self, mock_cleanup) -> None:
        """Use mock_cleanup fixture for automatic deletion after test."""
        mock = (
            MockBuilder.http("/test/auto-cleanup", "GET")
            .id("fixture-auto-cleanup")
            .respond(200, body={"cleanup": "automatic"})
            .build()
        )

        # mock_cleanup creates the mock AND registers it for deletion
        created = mock_cleanup(mock)
        assert created.id == "fixture-auto-cleanup"
        # No need to manually delete -- fixture handles it after the test


class TestConditionMatching:
    """Test condition-based mock matching."""

    def test_body_condition(self, mock_cleanup) -> None:
        """Mock with body field condition."""
        mock = (
            MockBuilder.http("/test/orders", "POST")
            .id("fixture-order-condition")
            .condition("type", AssertAction.EQUALS, "express")
            .respond(200, body={"status": "express_confirmed"})
            .build()
        )
        created = mock_cleanup(mock)
        assert created.id is not None

    def test_header_condition(self, mock_cleanup) -> None:
        """Mock with header-based matching."""
        mock = (
            MockBuilder.http("/test/auth", "GET")
            .id("fixture-auth-header")
            .header_condition("Authorization", AssertAction.CONTAINS, "Bearer ")
            .respond(200, body={"authenticated": True})
            .build()
        )
        created = mock_cleanup(mock)
        assert created.id is not None


class TestStoreIntegration:
    """Test store operations in integration tests."""

    def test_global_store_roundtrip(
        self, mockarty_client: MockartyClient
    ) -> None:
        """Write to Global Store and verify the value."""
        key = "test.fixture.key"
        mockarty_client.stores.global_set(key, "fixture-value")

        store = mockarty_client.stores.global_get()
        assert store.get(key) == "fixture-value"

        # Cleanup
        mockarty_client.stores.global_delete(key)

    def test_chain_store_roundtrip(
        self, mockarty_client: MockartyClient
    ) -> None:
        """Write to Chain Store and verify the value."""
        chain_id = "test-fixture-chain"
        mockarty_client.stores.chain_set(chain_id, "step", "started")

        state = mockarty_client.stores.chain_get(chain_id)
        assert state.get("step") == "started"

        # Cleanup
        mockarty_client.stores.chain_delete(chain_id, "step")


class TestMockLifecycle:
    """Test the full mock lifecycle: create, list, update, delete, restore."""

    def test_full_lifecycle(self, mockarty_client: MockartyClient) -> None:
        """Walk through the complete mock lifecycle."""
        mock_id = "fixture-lifecycle-test"

        # Create
        mock = (
            MockBuilder.http("/test/lifecycle", "GET")
            .id(mock_id)
            .respond(200, body={"version": 1})
            .tags("test", "lifecycle")
            .build()
        )
        result = mockarty_client.mocks.create(mock)
        assert result.mock.id == mock_id

        # List (verify it appears)
        page = mockarty_client.mocks.list(search="lifecycle")
        found = any(m.id == mock_id for m in page.items)
        assert found, f"Mock {mock_id} not found in list"

        # Update
        updated_mock = (
            MockBuilder.http("/test/lifecycle", "GET")
            .id(mock_id)
            .respond(200, body={"version": 2})
            .tags("test", "lifecycle", "updated")
            .build()
        )
        mockarty_client.mocks.update(mock_id, updated_mock)

        # Soft delete
        mockarty_client.mocks.delete(mock_id)

        # Restore
        mockarty_client.mocks.restore(mock_id)

        # Permanent delete
        mockarty_client.mocks.purge(mock_id)


# ---------------------------------------------------------------------------
# Custom fixture example: scoped client with a dedicated namespace
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def isolated_client() -> MockartyClient:
    """Client scoped to a test-specific namespace for isolation."""
    client = MockartyClient(
        base_url=os.environ.get("MOCKARTY_BASE_URL", "http://localhost:5770"),
        api_key=os.environ.get("MOCKARTY_API_KEY"),
        namespace="test-isolation",
    )
    yield client
    client.close()


class TestIsolatedNamespace:
    """Tests using an isolated namespace."""

    def test_namespace_is_set(self, isolated_client: MockartyClient) -> None:
        """Verify the client uses the correct namespace."""
        assert isolated_client.namespace == "test-isolation"
