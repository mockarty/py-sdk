"""Collections and test run examples.

Demonstrates:
  - Listing collections
  - Executing a collection's tests
  - Running multiple collections together
  - Viewing test run history
  - Exporting collections
"""

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def list_collections(client: MockartyClient) -> None:
    """List all API Tester collections."""
    collections = client.collections.list()
    print(f"Found {len(collections)} collections:")
    for coll in collections:
        print(f"  - {coll.id}: {coll.name} (protocol={coll.protocol})")


def get_collection_details(client: MockartyClient, collection_id: str) -> None:
    """Get detailed information about a specific collection."""
    coll = client.collections.get(collection_id)
    print(f"Collection: {coll.name}")
    print(f"  ID:          {coll.id}")
    print(f"  Protocol:    {coll.protocol}")
    print(f"  Type:        {coll.collection_type}")
    print(f"  Description: {coll.description}")
    print(f"  Created:     {coll.created_at}")


def execute_collection(client: MockartyClient, collection_id: str) -> None:
    """Run all tests in a collection and report results."""
    print(f"Executing collection: {collection_id}")
    result = client.collections.execute(collection_id)
    print(f"  Status:  {result.status}")
    print(f"  Total:   {result.total_tests}")
    print(f"  Passed:  {result.passed}")
    print(f"  Failed:  {result.failed}")
    print(f"  Skipped: {result.skipped}")
    print(f"  Duration: {result.duration_ms}ms")


def execute_multiple_collections(
    client: MockartyClient, collection_ids: list[str]
) -> None:
    """Run tests from multiple collections in one request."""
    print(f"Executing {len(collection_ids)} collections together")
    result = client.collections.execute_multiple(collection_ids)
    print(f"  Status: {result.status}")
    print(f"  Total:  {result.total_tests}")
    print(f"  Passed: {result.passed}")
    print(f"  Failed: {result.failed}")


def view_test_runs(client: MockartyClient) -> None:
    """List all historical test runs."""
    runs = client.test_runs.list()
    print(f"Found {len(runs)} test runs:")
    for run in runs[:5]:  # Show only the latest 5
        print(f"  - {run.id}: status={run.status}")


def view_collection_test_runs(
    client: MockartyClient, collection_id: str
) -> None:
    """List test runs for a specific collection."""
    runs = client.test_runs.list_by_collection(collection_id)
    print(f"Test runs for collection {collection_id}: {len(runs)}")
    for run in runs[:5]:
        print(f"  - {run.id}: status={run.status}")


def export_collection(client: MockartyClient, collection_id: str) -> None:
    """Export a collection as a downloadable archive."""
    data = client.collections.export(collection_id)
    filename = f"collection-{collection_id}.zip"
    with open(filename, "wb") as f:
        f.write(data)
    print(f"Exported collection to {filename} ({len(data)} bytes)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        # List all collections
        list_collections(client)
        print()

        # View test run history
        view_test_runs(client)
        print()

        # The following operations require existing collection IDs.
        # Replace these with real IDs from your Mockarty instance.
        #
        # get_collection_details(client, "my-collection-id")
        # execute_collection(client, "my-collection-id")
        # execute_multiple_collections(client, ["col-1", "col-2"])
        # view_collection_test_runs(client, "my-collection-id")
        # export_collection(client, "my-collection-id")

        print("Collections example complete.")


if __name__ == "__main__":
    main()
