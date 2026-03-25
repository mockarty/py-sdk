"""Quick-start example for the Mockarty Python SDK.

Demonstrates the minimal workflow:
  1. Create a client
  2. Check server health
  3. Create an HTTP mock
  4. Verify it was saved
  5. Clean up
"""

from mockarty import MockartyClient, MockBuilder

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def main() -> None:
    # -- 1. Create a client (context-manager auto-closes on exit) -----------
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        # -- 2. Health check ------------------------------------------------
        health = client.health.check()
        print(f"Server status: {health.status}, version: {health.release_id}")

        # -- 3. Create a simple GET mock ------------------------------------
        mock = (
            MockBuilder.http("/api/hello", "GET")
            .id("hello-world")
            .respond(200, body={"message": "Hello from Mockarty!"})
            .build()
        )

        result = client.mocks.create(mock)
        print(f"Created mock: {result.mock.id} (overwritten={result.overwritten})")

        # -- 4. Retrieve it back and verify ---------------------------------
        fetched = client.mocks.get("hello-world")
        print(f"Fetched mock route: {fetched.http.route}")

        # -- 5. Clean up ----------------------------------------------------
        client.mocks.delete("hello-world")
        print("Mock deleted.")


if __name__ == "__main__":
    main()
