"""HTTP protocol mock examples.

Covers the most common HTTP mocking patterns:
  - GET with path parameters
  - POST with body conditions
  - Header conditions
  - Faker template functions
  - Response delay
  - OneOf (sequential and random)
  - TTL and usage limiter
"""

from mockarty import AssertAction, MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def get_with_path_params(client: MockartyClient) -> None:
    """GET /api/users/:id -- path parameter interpolation."""
    mock = (
        MockBuilder.http("/api/users/:id", "GET")
        .id("user-get-by-id")
        .respond(200, body={
            "id": "$.pathParam.id",
            "name": "$.fake.FirstName",
            "email": "$.fake.Email",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/users/:id")


def post_with_body_conditions(client: MockartyClient) -> None:
    """POST /api/orders -- match only if body contains specific fields."""
    mock = (
        MockBuilder.http("/api/orders", "POST")
        .id("order-create-premium")
        .condition("type", AssertAction.EQUALS, "premium")
        .condition("amount", AssertAction.NOT_EMPTY)
        .respond(201, body={
            "orderId": "$.fake.UUID",
            "type": "$.req.type",
            "amount": "$.req.amount",
            "status": "confirmed",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: POST /api/orders (premium condition)")


def header_conditions(client: MockartyClient) -> None:
    """GET /api/protected -- match only with a specific header."""
    mock = (
        MockBuilder.http("/api/protected", "GET")
        .id("protected-resource")
        .header_condition("X-Client-Version", AssertAction.MATCHES, "^2\\.")
        .respond(200, body={"data": "v2-only content"})
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/protected (header condition)")


def query_param_conditions(client: MockartyClient) -> None:
    """GET /api/search -- match on query parameters."""
    mock = (
        MockBuilder.http("/api/search", "GET")
        .id("search-active")
        .query_condition("status", AssertAction.EQUALS, "active")
        .respond(200, body={
            "results": [
                {"id": "$.fake.UUID", "status": "active"},
                {"id": "$.fake.UUID", "status": "active"},
            ],
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/search?status=active")


def faker_templates(client: MockartyClient) -> None:
    """Demonstrate various Faker template functions in responses."""
    mock = (
        MockBuilder.http("/api/fake-user", "GET")
        .id("fake-user-profile")
        .respond(200, body={
            "id": "$.fake.UUID",
            "firstName": "$.fake.FirstName",
            "lastName": "$.fake.LastName",
            "email": "$.fake.Email",
            "phone": "$.fake.PhoneNumber",
            "company": "$.fake.Company",
            "address": {
                "street": "$.fake.StreetAddress",
                "city": "$.fake.City",
                "state": "$.fake.State",
                "zip": "$.fake.Zip",
                "country": "$.fake.Country",
            },
            "avatar": "$.fake.URL",
            "registeredAt": "$.fake.DateISO",
            "bio": "$.fake.Sentence",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/fake-user (Faker templates)")


def response_with_delay(client: MockartyClient) -> None:
    """Simulate a slow endpoint (2000 ms delay)."""
    mock = (
        MockBuilder.http("/api/slow", "GET")
        .id("slow-endpoint")
        .respond(200, body={"status": "ok"}, delay=2000)
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/slow (2s delay)")


def one_of_sequential(client: MockartyClient) -> None:
    """Return responses in order (first call -> first response, etc.)."""
    mock = (
        MockBuilder.http("/api/flaky", "GET")
        .id("flaky-sequential")
        .respond_with_one_of(order="order")
        .add_response(200, body={"attempt": 1, "status": "ok"})
        .add_response(500, body={"error": "Internal Server Error"})
        .add_response(200, body={"attempt": 3, "status": "recovered"})
        .done()
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/flaky (OneOf sequential)")


def one_of_random(client: MockartyClient) -> None:
    """Return a random response from the list on each call."""
    mock = (
        MockBuilder.http("/api/random-status", "GET")
        .id("random-status")
        .respond_with_one_of(order="random")
        .add_response(200, body={"status": "healthy"})
        .add_response(503, body={"status": "degraded"})
        .add_response(200, body={"status": "healthy"})
        .add_response(429, body={"error": "rate limited"})
        .done()
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/random-status (OneOf random)")


def ttl_and_limiter(client: MockartyClient) -> None:
    """Mock that auto-expires after 1 hour and allows at most 10 uses."""
    mock = (
        MockBuilder.http("/api/promo", "GET")
        .id("promo-limited")
        .ttl(3600)
        .use_limiter(10)
        .respond(200, body={
            "code": "$.fake.UUID",
            "discount": 25,
            "message": "Limited offer!",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/promo (TTL=3600s, max 10 uses)")


def response_with_custom_headers(client: MockartyClient) -> None:
    """Return custom response headers."""
    mock = (
        MockBuilder.http("/api/download", "GET")
        .id("download-file")
        .respond(
            200,
            body={"url": "https://cdn.example.com/file.zip"},
            headers={
                "X-RateLimit-Remaining": ["99"],
                "Cache-Control": ["no-cache"],
            },
        )
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/download (custom response headers)")


def prioritized_mocks(client: MockartyClient) -> None:
    """Higher-priority mock matched first when routes overlap."""
    # Low-priority catch-all
    default_mock = (
        MockBuilder.http("/api/items/:id", "GET")
        .id("items-default")
        .priority(1)
        .respond(200, body={"id": "$.pathParam.id", "tier": "standard"})
        .build()
    )
    # High-priority override for VIP header
    vip_mock = (
        MockBuilder.http("/api/items/:id", "GET")
        .id("items-vip")
        .priority(100)
        .header_condition("X-VIP", AssertAction.EQUALS, "true")
        .respond(200, body={"id": "$.pathParam.id", "tier": "vip", "discount": 30})
        .build()
    )
    client.mocks.create(default_mock)
    client.mocks.create(vip_mock)
    print("Created: GET /api/items/:id (priority-based matching)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        get_with_path_params(client)
        post_with_body_conditions(client)
        header_conditions(client)
        query_param_conditions(client)
        faker_templates(client)
        response_with_delay(client)
        one_of_sequential(client)
        one_of_random(client)
        ttl_and_limiter(client)
        response_with_custom_headers(client)
        prioritized_mocks(client)

        # Clean up all created mocks
        mock_ids = [
            "user-get-by-id", "order-create-premium", "protected-resource",
            "search-active", "fake-user-profile", "slow-endpoint",
            "flaky-sequential", "random-status", "promo-limited",
            "download-file", "items-default", "items-vip",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll HTTP example mocks cleaned up.")


if __name__ == "__main__":
    main()
