"""Undefined (unmatched) request management examples.

Demonstrates:
  - Listing unmatched requests that hit Mockarty without a matching mock
  - Inspecting undefined request details
  - Creating mocks from undefined requests (auto-stub)
  - Ignoring irrelevant undefined requests
  - Batch deletion of undefined requests
  - Clearing all undefined requests
  - Workflow: identify gaps in mock coverage
"""

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def list_undefined_requests(client: MockartyClient) -> list[str]:
    """List all unmatched requests.

    Undefined requests are logged when a request arrives at Mockarty
    but no mock matches its route, method, or conditions. These
    indicate gaps in your mock coverage.
    """
    requests = client.undefined.list()
    print(f"Undefined requests ({len(requests)}):")
    for req in requests[:10]:
        print(f"  - {req.id}: {req.method} {req.path}")
        if req.headers:
            print(f"    Content-Type: {req.headers.get('Content-Type', 'N/A')}")
        if req.body:
            body_preview = str(req.body)[:80]
            print(f"    Body: {body_preview}...")
        print(f"    Timestamp: {req.timestamp}")

    return [r.id for r in requests]


def create_mock_from_undefined(client: MockartyClient) -> None:
    """Create a mock from an undefined request.

    This is the fastest way to stub new endpoints:
      1. Send a real request to Mockarty
      2. It gets logged as undefined (no matching mock)
      3. Create a mock from it with one API call

    The generated mock uses the request's route and method,
    with a basic 200 response. You can then customize it.
    """
    requests = client.undefined.list()
    if not requests:
        print("No undefined requests available. Send some requests first.")
        return

    # Create a mock from the first undefined request
    req = requests[0]
    print(f"Creating mock from: {req.method} {req.path}")
    mock = client.undefined.create_mock(req.id)
    print(f"Created mock: {mock.id}")
    if mock.http:
        print(f"  Route:  {mock.http.route}")
        print(f"  Method: {mock.http.http_method}")

    # Clean up the created mock
    client.mocks.delete(mock.id)
    print(f"  (cleaned up mock {mock.id})")


def create_mocks_from_all_undefined(client: MockartyClient) -> None:
    """Bulk-create mocks from all undefined requests.

    Useful during initial mock setup: send real traffic to Mockarty,
    then auto-generate stubs for everything.
    """
    requests = client.undefined.list()
    if not requests:
        print("No undefined requests to process.")
        return

    created_ids = []
    for req in requests:
        try:
            mock = client.undefined.create_mock(req.id)
            created_ids.append(mock.id)
            route = mock.http.route if mock.http else "unknown"
            print(f"  Created: {mock.id} -> {route}")
        except Exception as e:
            print(f"  Skipped {req.id}: {e}")

    print(f"Created {len(created_ids)} mocks from undefined requests")

    # Clean up
    for mid in created_ids:
        try:
            client.mocks.delete(mid)
        except Exception:
            pass


def ignore_undefined_request(client: MockartyClient) -> None:
    """Mark an undefined request as ignored.

    Ignored requests are hidden from the default listing.
    Use this for health checks, favicon requests, or other
    noise you do not want to mock.
    """
    requests = client.undefined.list()
    if not requests:
        print("No undefined requests to ignore.")
        return

    # Find requests that are likely noise (health checks, favicons)
    for req in requests:
        if req.path in ("/favicon.ico", "/health", "/robots.txt"):
            client.undefined.ignore(req.id)
            print(f"Ignored: {req.method} {req.path}")


def delete_specific_undefined(client: MockartyClient) -> None:
    """Delete specific undefined requests by ID."""
    requests = client.undefined.list()
    if len(requests) < 2:
        print("Need at least 2 undefined requests for batch delete demo.")
        return

    ids_to_delete = [requests[0].id, requests[1].id]
    client.undefined.delete(ids_to_delete)
    print(f"Deleted {len(ids_to_delete)} undefined requests")


def clear_all_undefined(client: MockartyClient) -> None:
    """Clear all undefined requests.

    Useful after you have reviewed all gaps and created the
    necessary mocks. Gives you a clean slate to detect new
    undefined routes.
    """
    client.undefined.clear_all()
    print("Cleared all undefined requests")


# ---------------------------------------------------------------------------
# Coverage Gap Analysis Workflow
# ---------------------------------------------------------------------------

def coverage_gap_workflow(client: MockartyClient) -> None:
    """Analyze mock coverage gaps using undefined requests.

    Workflow:
      1. Run your integration tests against Mockarty
      2. List undefined requests to find coverage gaps
      3. Auto-create mocks for missing endpoints
      4. Re-run tests to verify coverage
      5. Clear the undefined request log
    """
    print("--- Coverage Gap Analysis ---")

    # Step 1: List undefined requests
    requests = client.undefined.list()
    if not requests:
        print("No coverage gaps detected. All requests matched a mock.")
        return

    print(f"Step 1: Found {len(requests)} unmatched requests")

    # Step 2: Group by route pattern
    routes: dict[str, int] = {}
    for req in requests:
        key = f"{req.method} {req.path}"
        routes[key] = routes.get(key, 0) + 1

    print("Step 2: Coverage gaps by route:")
    for route, count in sorted(routes.items(), key=lambda x: -x[1]):
        print(f"  {route}: {count} request(s)")

    # Step 3: Create mocks for unique routes
    seen_routes: set[str] = set()
    created = 0
    for req in requests:
        route_key = f"{req.method} {req.path}"
        if route_key not in seen_routes:
            try:
                mock = client.undefined.create_mock(req.id)
                seen_routes.add(route_key)
                created += 1
                print(f"  Auto-stubbed: {mock.id}")
                # Clean up for demo purposes
                client.mocks.delete(mock.id)
            except Exception:
                pass

    print(f"Step 3: Created {created} mock stubs")

    # Step 4: Clear undefined requests
    client.undefined.clear_all()
    print("Step 4: Cleared undefined request log for next run")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== List Undefined Requests ===")
        request_ids = list_undefined_requests(client)
        print()

        print("=== Create Mock from Undefined ===")
        create_mock_from_undefined(client)
        print()

        print("=== Ignore Noise ===")
        ignore_undefined_request(client)
        print()

        print("=== Coverage Gap Analysis ===")
        coverage_gap_workflow(client)
        print()

        print("Undefined requests example complete.")


if __name__ == "__main__":
    main()
