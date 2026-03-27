"""gRPC mock examples.

Demonstrates:
  - Unary method mock
  - Request field conditions
  - Metadata conditions
  - Error responses (gRPC status codes)
"""

from mockarty import AssertAction, MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def unary_method_mock(client: MockartyClient) -> None:
    """Basic gRPC unary mock: UserService.GetUser."""
    mock = (
        MockBuilder.grpc("user.UserService", "GetUser")
        .id("grpc-get-user")
        .respond(200, body={
            "user": {
                "id": "$.req.id",
                "name": "$.fake.FirstName",
                "email": "$.fake.Email",
                "role": "admin",
            }
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: gRPC user.UserService/GetUser")


def request_field_conditions(client: MockartyClient) -> None:
    """Match gRPC request only when certain fields have specific values."""
    mock = (
        MockBuilder.grpc("order.OrderService", "CreateOrder")
        .id("grpc-create-order-premium")
        .condition("tier", AssertAction.EQUALS, "premium")
        .condition("items", AssertAction.NOT_EMPTY)
        .respond(200, body={
            "orderId": "$.fake.UUID",
            "tier": "$.req.tier",
            "status": "CONFIRMED",
            "estimatedDelivery": "$.fake.DateISO",
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: gRPC order.OrderService/CreateOrder (premium condition)")


def metadata_conditions(client: MockartyClient) -> None:
    """Match based on gRPC metadata (equivalent to HTTP headers)."""
    mock = (
        MockBuilder.grpc("auth.AuthService", "ValidateToken")
        .id("grpc-validate-token")
        .meta_condition("authorization", AssertAction.CONTAINS, "Bearer ")
        .meta_condition("x-request-id", AssertAction.NOT_EMPTY)
        .respond(200, body={
            "valid": True,
            "userId": "$.fake.UUID",
            "expiresIn": 3600,
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: gRPC auth.AuthService/ValidateToken (metadata conditions)")


def error_response(client: MockartyClient) -> None:
    """Return a gRPC error with status code and message.

    gRPC error codes are returned via the ``error`` field as a string.
    The status code maps to gRPC codes (e.g., NOT_FOUND, PERMISSION_DENIED).
    """
    # Not found error
    not_found_mock = (
        MockBuilder.grpc("product.ProductService", "GetProduct")
        .id("grpc-product-not-found")
        .condition("id", AssertAction.EQUALS, "nonexistent")
        .respond(404, error="product not found")
        .priority(10)
        .build()
    )
    client.mocks.create(not_found_mock)
    print("Created: gRPC product.ProductService/GetProduct (NOT_FOUND)")

    # Permission denied error
    permission_denied = (
        MockBuilder.grpc("admin.AdminService", "DeleteUser")
        .id("grpc-admin-denied")
        .respond(403, error="insufficient permissions")
        .build()
    )
    client.mocks.create(permission_denied)
    print("Created: gRPC admin.AdminService/DeleteUser (PERMISSION_DENIED)")


def grpc_with_delay(client: MockartyClient) -> None:
    """Simulate a slow gRPC call with a 3-second delay."""
    mock = (
        MockBuilder.grpc("analytics.AnalyticsService", "GenerateReport")
        .id("grpc-slow-report")
        .respond(200, body={
            "reportId": "$.fake.UUID",
            "status": "completed",
            "rows": 42,
        }, delay=3000)
        .build()
    )
    client.mocks.create(mock)
    print("Created: gRPC analytics.AnalyticsService/GenerateReport (3s delay)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        unary_method_mock(client)
        request_field_conditions(client)
        metadata_conditions(client)
        error_response(client)
        grpc_with_delay(client)

        # Clean up
        mock_ids = [
            "grpc-get-user", "grpc-create-order-premium",
            "grpc-validate-token", "grpc-product-not-found",
            "grpc-admin-denied", "grpc-slow-report",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll gRPC example mocks cleaned up.")


if __name__ == "__main__":
    main()
