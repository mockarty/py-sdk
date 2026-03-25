"""Advanced usage examples.

Demonstrates:
  - Chain mocks (multi-step workflows)
  - Complex condition combinations
  - Extract to stores (from request data)
  - Batch operations
  - Namespace isolation
  - Mock versioning: list versions, get specific version, restore
  - Batch tag updates and folder organization
  - Request log inspection
"""

from mockarty import AssertAction, MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


# ---------------------------------------------------------------------------
# Chain Mocks (Workflows)
# ---------------------------------------------------------------------------

def order_workflow_chain(client: MockartyClient) -> None:
    """Create a chain of mocks simulating an e-commerce order workflow.

    Chain mocks share a chain_id and can read/write to the Chain Store (cS).
    Each step reads state from previous steps and writes its own state.
    """
    chain_id = "order-workflow"

    # Step 1: Create order
    create_order = (
        MockBuilder.http("/api/orders", "POST")
        .id("chain-create-order")
        .chain_id(chain_id)
        .extract(
            c_store={
                "orderId": "$.fake.UUID",
                "customerName": "$.req.customerName",
                "total": "$.req.total",
            }
        )
        .respond(201, body={
            "orderId": "$.cS.orderId",
            "status": "created",
            "customerName": "$.req.customerName",
        })
        .build()
    )

    # Step 2: Process payment
    process_payment = (
        MockBuilder.http("/api/orders/:orderId/pay", "POST")
        .id("chain-process-payment")
        .chain_id(chain_id)
        .extract(
            c_store={
                "paymentId": "$.fake.UUID",
                "paidAt": "$.fake.DateISO",
            }
        )
        .respond(200, body={
            "orderId": "$.cS.orderId",
            "paymentId": "$.cS.paymentId",
            "status": "paid",
            "total": "$.cS.total",
        })
        .build()
    )

    # Step 3: Ship order
    ship_order = (
        MockBuilder.http("/api/orders/:orderId/ship", "POST")
        .id("chain-ship-order")
        .chain_id(chain_id)
        .extract(
            c_store={
                "trackingNumber": "$.fake.UUID",
                "shippedAt": "$.fake.DateISO",
            }
        )
        .respond(200, body={
            "orderId": "$.cS.orderId",
            "trackingNumber": "$.cS.trackingNumber",
            "status": "shipped",
            "customerName": "$.cS.customerName",
        })
        .build()
    )

    # Step 4: Get order status (reads all chain state)
    get_status = (
        MockBuilder.http("/api/orders/:orderId/status", "GET")
        .id("chain-order-status")
        .chain_id(chain_id)
        .respond(200, body={
            "orderId": "$.cS.orderId",
            "customerName": "$.cS.customerName",
            "total": "$.cS.total",
            "paymentId": "$.cS.paymentId",
            "trackingNumber": "$.cS.trackingNumber",
            "paidAt": "$.cS.paidAt",
            "shippedAt": "$.cS.shippedAt",
        })
        .build()
    )

    for mock in [create_order, process_payment, ship_order, get_status]:
        client.mocks.create(mock)

    print("Created order workflow chain (4 mocks)")
    print("  POST /api/orders -> create order")
    print("  POST /api/orders/:orderId/pay -> process payment")
    print("  POST /api/orders/:orderId/ship -> ship order")
    print("  GET  /api/orders/:orderId/status -> get full status")


# ---------------------------------------------------------------------------
# Complex Conditions
# ---------------------------------------------------------------------------

def complex_conditions(client: MockartyClient) -> None:
    """Combine body, header, and query parameter conditions.

    All conditions must be satisfied (AND logic) for the mock to match.
    """
    mock = (
        MockBuilder.http("/api/advanced/search", "POST")
        .id("advanced-complex-conditions")
        # Body conditions
        .condition("query", AssertAction.NOT_EMPTY)
        .condition("filters.status", AssertAction.EQUALS, "active")
        .condition("filters.region", AssertAction.CONTAINS, "us-")
        # Header conditions
        .header_condition("X-API-Version", AssertAction.EQUALS, "2")
        .header_condition("Accept-Language", AssertAction.MATCHES, "^en")
        # Query parameter conditions
        .query_condition("page", AssertAction.NOT_EMPTY)
        .query_condition("limit", AssertAction.NOT_EMPTY)
        .respond(200, body={
            "results": [
                {"id": "$.fake.UUID", "status": "active"},
                {"id": "$.fake.UUID", "status": "active"},
            ],
            "pagination": {
                "page": "$.queryParam.page",
                "limit": "$.queryParam.limit",
                "total": 42,
            },
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/advanced/search (complex conditions)")


def regex_conditions(client: MockartyClient) -> None:
    """Use regex patterns in conditions."""
    mock = (
        MockBuilder.http("/api/advanced/validate", "POST")
        .id("advanced-regex-conditions")
        # Email format validation
        .condition("email", AssertAction.MATCHES, r"^[\w.+-]+@[\w-]+\.[\w.]+$")
        # Phone number format
        .condition("phone", AssertAction.MATCHES, r"^\+\d{1,3}\d{10}$")
        # UUID format
        .condition("referenceId", AssertAction.MATCHES,
                   r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        .respond(200, body={"valid": True, "message": "All fields validated"})
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/advanced/validate (regex conditions)")


# ---------------------------------------------------------------------------
# Extract to Stores
# ---------------------------------------------------------------------------

def extract_to_stores(client: MockartyClient) -> None:
    """Extract values from incoming requests into stores.

    Extracted values can be referenced by subsequent mocks in the
    same chain or from the global store.
    """
    # Extract user registration data to Global Store
    register_mock = (
        MockBuilder.http("/api/users/register", "POST")
        .id("advanced-extract-register")
        .extract(
            # Extract to Mock Store (available only during this request)
            m_store={
                "generatedId": "$.fake.UUID",
            },
            # Extract to Global Store (available to all mocks in namespace)
            g_store={
                "lastRegisteredEmail": "$.req.email",
                "totalRegistrations": "$.increment($.gS.totalRegistrations)",
            },
        )
        .respond(201, body={
            "userId": "$.mS.generatedId",
            "email": "$.req.email",
            "registrationNumber": "$.gS.totalRegistrations",
        })
        .build()
    )
    client.mocks.create(register_mock)
    print("Created: POST /api/users/register (extract to stores)")

    # A mock that reads the extracted global state
    stats_mock = (
        MockBuilder.http("/api/stats/registrations", "GET")
        .id("advanced-extract-stats")
        .respond(200, body={
            "lastEmail": "$.gS.lastRegisteredEmail",
            "totalRegistrations": "$.gS.totalRegistrations",
        })
        .build()
    )
    client.mocks.create(stats_mock)
    print("Created: GET /api/stats/registrations (reads from Global Store)")


# ---------------------------------------------------------------------------
# Batch Operations
# ---------------------------------------------------------------------------

def batch_operations(client: MockartyClient) -> None:
    """Create and delete multiple mocks in batch."""
    # Build multiple mocks
    mocks = [
        MockBuilder.http(f"/api/batch/resource-{i}", "GET")
        .id(f"batch-resource-{i}")
        .tags("batch", "example")
        .respond(200, body={"resourceId": i, "name": f"Resource {i}"})
        .build()
        for i in range(5)
    ]

    # Batch create
    results = client.mocks.batch_create(mocks)
    print(f"Batch created {len(results)} mocks:")
    for r in results:
        print(f"  - {r.mock.id}: overwritten={r.overwritten}")

    # List with tag filter
    page = client.mocks.list(tags=["batch"])
    print(f"Found {page.total} mocks with 'batch' tag")

    # Batch delete
    ids = [f"batch-resource-{i}" for i in range(5)]
    client.mocks.batch_delete(ids)
    print(f"Batch deleted {len(ids)} mocks")


# ---------------------------------------------------------------------------
# Namespace Isolation
# ---------------------------------------------------------------------------

def namespace_isolation(client: MockartyClient) -> None:
    """Demonstrate namespace isolation and mock copying."""
    # Create a namespace
    client.namespaces.create("staging")
    print("Created namespace: staging")

    # List namespaces
    namespaces = client.namespaces.list()
    print(f"Available namespaces: {namespaces}")

    # Create a mock in sandbox
    mock = (
        MockBuilder.http("/api/ns-demo", "GET")
        .id("ns-demo-mock")
        .respond(200, body={"env": "sandbox"})
        .build()
    )
    client.mocks.create(mock)
    print("Created mock in 'sandbox' namespace")

    # Copy mocks to staging
    client.namespaces.copy_mocks(
        source_namespace="sandbox",
        target_namespace="staging",
        mock_ids=["ns-demo-mock"],
    )
    print("Copied mock to 'staging' namespace")

    # Switch namespace and verify
    original_ns = client.namespace
    client.namespace = "staging"

    try:
        fetched = client.mocks.get("ns-demo-mock")
        print(f"Mock exists in staging: {fetched.id}")
        client.mocks.delete("ns-demo-mock")
    except Exception:
        print("Mock not yet in staging (copy may be async)")

    # Restore original namespace
    client.namespace = original_ns
    client.mocks.delete("ns-demo-mock")
    print("Namespace isolation demo complete")


# ---------------------------------------------------------------------------
# Mock Versioning
# ---------------------------------------------------------------------------

def mock_versioning(client: MockartyClient) -> None:
    """Demonstrate mock version history and rollback.

    Every time a mock is updated (re-created with the same ID),
    Mockarty keeps the previous version. You can:
      - List all versions of a mock
      - Get a specific version
      - Restore a previous version
    """
    mock_id = "advanced-versioned-mock"

    # Version 1: basic response
    v1 = (
        MockBuilder.http("/api/versioned/users/:id", "GET")
        .id(mock_id)
        .tags("versioning-demo")
        .respond(200, body={
            "id": "$.pathParam.id",
            "name": "$.fake.FirstName",
            "version": "v1",
        })
        .build()
    )
    client.mocks.create(v1)
    print(f"Created {mock_id} v1: basic user response")

    # Version 2: add email and phone
    v2 = (
        MockBuilder.http("/api/versioned/users/:id", "GET")
        .id(mock_id)
        .tags("versioning-demo")
        .respond(200, body={
            "id": "$.pathParam.id",
            "name": "$.fake.FirstName",
            "email": "$.fake.Email",
            "phone": "$.fake.Phone",
            "version": "v2",
        })
        .build()
    )
    client.mocks.create(v2)
    print(f"Updated {mock_id} to v2: added email and phone")

    # Version 3: add address and metadata
    v3 = (
        MockBuilder.http("/api/versioned/users/:id", "GET")
        .id(mock_id)
        .tags("versioning-demo")
        .respond(200, body={
            "id": "$.pathParam.id",
            "name": "$.fake.FirstName",
            "email": "$.fake.Email",
            "phone": "$.fake.Phone",
            "address": {
                "street": "$.fake.StreetAddress",
                "city": "$.fake.City",
                "country": "$.fake.Country",
            },
            "createdAt": "$.fake.DateISO",
            "version": "v3",
        })
        .build()
    )
    client.mocks.create(v3)
    print(f"Updated {mock_id} to v3: added address and metadata")

    # List all versions
    versions = client.mocks.list_versions(mock_id)
    print(f"\nVersion history ({len(versions)} versions):")
    for i, ver in enumerate(versions):
        payload = ver.response.payload if ver.response else {}
        v_label = payload.get("version", "?") if isinstance(payload, dict) else "?"
        print(f"  Version {i + 1}: {v_label}")

    # Get a specific version (version 1)
    if len(versions) >= 2:
        old_version = client.mocks.get_version(mock_id, 1)
        old_payload = old_version.response.payload if old_version.response else {}
        print(f"\nVersion 1 payload: {old_payload}")

    # Restore to version 1
    if len(versions) >= 2:
        client.mocks.restore_version(mock_id, 1)
        restored = client.mocks.get(mock_id)
        restored_payload = restored.response.payload if restored.response else {}
        r_label = restored_payload.get("version", "?") if isinstance(restored_payload, dict) else "?"
        print(f"Restored to version 1: current payload version = {r_label}")

    # Clean up
    client.mocks.delete(mock_id)
    print(f"Deleted {mock_id}")


# ---------------------------------------------------------------------------
# Batch Tag Updates
# ---------------------------------------------------------------------------

def batch_tag_operations(client: MockartyClient) -> None:
    """Batch-update tags on multiple mocks.

    Useful for:
      - Tagging a set of mocks for a release
      - Promoting mocks between environments
      - Adding metadata tags for filtering
    """
    # Create some mocks to tag
    mock_ids = []
    for i in range(4):
        mock = (
            MockBuilder.http(f"/api/tagging/endpoint-{i}", "GET")
            .id(f"tag-demo-{i}")
            .tags("initial-tag")
            .respond(200, body={"endpoint": i})
            .build()
        )
        client.mocks.create(mock)
        mock_ids.append(f"tag-demo-{i}")
    print(f"Created {len(mock_ids)} mocks with 'initial-tag'")

    # Batch update: add release and team tags
    client.mocks.batch_update_tags(mock_ids, ["release-3.0", "team-backend", "stable"])
    print(f"Batch updated tags for {len(mock_ids)} mocks: [release-3.0, team-backend, stable]")

    # Verify tags
    page = client.mocks.list(tags=["release-3.0"])
    print(f"Mocks with 'release-3.0' tag: {page.total}")

    # Move some mocks to a folder
    client.mocks.move_to_folder(mock_ids[:2], None)  # Move to root
    print(f"Moved {len(mock_ids[:2])} mocks to root folder")

    # Copy mocks to another namespace
    try:
        client.mocks.copy_to_namespace(mock_ids[:2], "staging")
        print("Copied 2 mocks to 'staging' namespace")
    except Exception as e:
        print(f"Copy to namespace: {e}")

    # Clean up
    for mid in mock_ids:
        try:
            client.mocks.delete(mid)
        except Exception:
            pass
    print("Tag demo mocks cleaned up")


# ---------------------------------------------------------------------------
# Request Logs
# ---------------------------------------------------------------------------

def inspect_request_logs(client: MockartyClient) -> None:
    """Inspect request logs for a specific mock.

    After creating a mock and sending traffic to it, you can view
    the logged requests and responses.
    """
    # Create a mock
    mock = (
        MockBuilder.http("/api/logged-endpoint", "GET")
        .id("advanced-logged")
        .respond(200, body={"logged": True})
        .build()
    )
    client.mocks.create(mock)

    # In a real scenario, send some requests to /api/logged-endpoint first.

    # View logs
    logs = client.mocks.logs("advanced-logged", offset=0, limit=10)
    print(f"Request logs for 'advanced-logged': {logs.total} entries")
    for log in logs.logs:
        print(f"  - {log.id}: called_at={log.called_at}")

    # Delete logs for this mock
    client.mocks.delete_logs("advanced-logged")
    print("Cleared request logs for 'advanced-logged'")

    # Clean up
    client.mocks.delete("advanced-logged")


# ---------------------------------------------------------------------------
# Mock Store (Ephemeral Per-Mock State)
# ---------------------------------------------------------------------------

def mock_store_usage(client: MockartyClient) -> None:
    """Use Mock Store for ephemeral per-mock data.

    Mock Store data is set at creation time and available during
    template rendering, but is not persisted between requests.
    """
    mock = (
        MockBuilder.http("/api/greeting/:lang", "GET")
        .id("advanced-mock-store")
        .mock_store({
            "greetings": {
                "en": "Hello",
                "es": "Hola",
                "fr": "Bonjour",
                "de": "Hallo",
            },
            "defaultLang": "en",
        })
        .respond(200, body={
            "greeting": "$.mS.greetings.$.pathParam.lang",
            "language": "$.pathParam.lang",
            "defaultLanguage": "$.mS.defaultLang",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/greeting/:lang (with mock store)")
    client.mocks.delete("advanced-mock-store")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Chain Mocks (Workflows) ===")
        order_workflow_chain(client)
        print()

        print("=== Complex Conditions ===")
        complex_conditions(client)
        regex_conditions(client)
        print()

        print("=== Extract to Stores ===")
        extract_to_stores(client)
        print()

        print("=== Batch Operations ===")
        batch_operations(client)
        print()

        print("=== Mock Versioning ===")
        mock_versioning(client)
        print()

        print("=== Batch Tag Updates ===")
        batch_tag_operations(client)
        print()

        print("=== Request Logs ===")
        inspect_request_logs(client)
        print()

        print("=== Mock Store ===")
        mock_store_usage(client)
        print()

        # Clean up chain mocks
        chain_mock_ids = [
            "chain-create-order", "chain-process-payment",
            "chain-ship-order", "chain-order-status",
        ]
        condition_mock_ids = [
            "advanced-complex-conditions", "advanced-regex-conditions",
        ]
        extract_mock_ids = [
            "advanced-extract-register", "advanced-extract-stats",
        ]
        for mid in chain_mock_ids + condition_mock_ids + extract_mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass

        # Uncomment for namespace demo (requires namespace creation permissions):
        # namespace_isolation(client)

        print("All advanced examples cleaned up.")


if __name__ == "__main__":
    main()
