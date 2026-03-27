"""Store operations examples: Global Store and Chain Store.

Mockarty provides three types of stores:
  - Global Store (gS) -- namespace-scoped shared state
  - Chain Store (cS) -- state shared across related mocks (via chain_id)
  - Mock Store (mS) -- per-mock ephemeral state (set at mock definition time)

This example demonstrates CRUD operations on Global and Chain stores,
plus how to reference store values in mock responses.
"""

from mockarty import MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def global_store_crud(client: MockartyClient) -> None:
    """Global Store: set, get, and delete key-value pairs."""
    # Set a single value
    client.stores.global_set("app.version", "2.1.0")
    print("Global store: set app.version = 2.1.0")

    # Set multiple values at once
    client.stores.global_set_many({
        "feature.darkMode": True,
        "feature.maxUsers": 1000,
        "system.maintenance": False,
    })
    print("Global store: set 3 feature flags")

    # Read the entire global store
    store = client.stores.global_get()
    print(f"Global store contents: {store}")

    # Delete a single key
    client.stores.global_delete("system.maintenance")
    print("Global store: deleted system.maintenance")

    # Delete multiple keys
    client.stores.global_delete_many(["feature.darkMode", "feature.maxUsers"])
    print("Global store: deleted feature flags")


def chain_store_crud(client: MockartyClient) -> None:
    """Chain Store: manage state for a chain of related mocks."""
    chain_id = "order-workflow-123"

    # Set initial chain state
    client.stores.chain_set_many(chain_id, {
        "orderId": "ORD-001",
        "status": "created",
        "items": 3,
        "total": 149.99,
    })
    print(f"Chain store [{chain_id}]: initialized")

    # Read chain state
    state = client.stores.chain_get(chain_id)
    print(f"Chain store [{chain_id}]: {state}")

    # Update a value
    client.stores.chain_set(chain_id, "status", "paid")
    print(f"Chain store [{chain_id}]: updated status -> paid")

    # Delete a key
    client.stores.chain_delete(chain_id, "items")
    print(f"Chain store [{chain_id}]: deleted 'items' key")

    # Delete multiple keys (cleanup)
    client.stores.chain_delete_many(chain_id, ["orderId", "status", "total"])
    print(f"Chain store [{chain_id}]: cleaned up")


def using_stores_in_templates(client: MockartyClient) -> None:
    """Demonstrate referencing store values in mock response templates.

    Template syntax:
      - $.gS.keyName    -- read from Global Store
      - $.cS.keyName    -- read from Chain Store
      - $.mS.keyName    -- read from Mock Store (ephemeral, per-call)
    """
    # Pre-populate the global store with config values
    client.stores.global_set_many({
        "app.name": "MyApp",
        "app.version": "2.1.0",
        "app.environment": "staging",
    })
    print("Global store: populated config values")

    # Pre-populate a chain store
    client.stores.chain_set_many("user-session", {
        "userId": "usr-42",
        "username": "alice",
        "role": "admin",
    })
    print("Chain store [user-session]: populated session data")

    # Mock that reads from Global Store
    config_mock = (
        MockBuilder.http("/api/config", "GET")
        .id("store-config")
        .respond(200, body={
            "appName": "$.gS.app.name",
            "version": "$.gS.app.version",
            "environment": "$.gS.app.environment",
        })
        .build()
    )
    client.mocks.create(config_mock)
    print("Created: GET /api/config (reads from Global Store)")

    # Mock that reads from Chain Store
    session_mock = (
        MockBuilder.http("/api/session", "GET")
        .id("store-session")
        .chain_id("user-session")
        .respond(200, body={
            "userId": "$.cS.userId",
            "username": "$.cS.username",
            "role": "$.cS.role",
            "loggedIn": True,
        })
        .build()
    )
    client.mocks.create(session_mock)
    print("Created: GET /api/session (reads from Chain Store)")

    # Mock using Mock Store (ephemeral per-mock data)
    counter_mock = (
        MockBuilder.http("/api/counter", "POST")
        .id("store-counter")
        .mock_store({"count": 0})
        .respond(200, body={
            "previousCount": "$.mS.count",
            "message": "Counter incremented",
        })
        .build()
    )
    client.mocks.create(counter_mock)
    print("Created: POST /api/counter (uses Mock Store)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        global_store_crud(client)
        print()

        chain_store_crud(client)
        print()

        using_stores_in_templates(client)

        # Clean up mocks
        for mid in ["store-config", "store-session", "store-counter"]:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass

        # Clean up global store
        client.stores.global_delete_many([
            "app.name", "app.version", "app.environment",
        ])
        print("\nAll store examples cleaned up.")


if __name__ == "__main__":
    main()
