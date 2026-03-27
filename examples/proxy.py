"""Proxy mode examples.

Demonstrates:
  - HTTP proxy via MockBuilder (mock-based proxy)
  - HTTP proxy via Proxy API (direct forwarding)
  - SOAP proxy via Proxy API
  - gRPC proxy via Proxy API
  - Proxy with delay, header replacement, and tags
  - Mixing proxied and mocked endpoints
"""

from mockarty import MockBuilder, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


# ---------------------------------------------------------------------------
# Mock-based Proxy (MockBuilder)
# ---------------------------------------------------------------------------

def basic_proxy(client: MockartyClient) -> None:
    """Forward all requests to a real backend service via a proxy mock."""
    mock = (
        MockBuilder.http("/api/upstream/:path", "GET")
        .id("proxy-basic")
        .proxy_to("https://api.example.com")
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/upstream/:path -> https://api.example.com (proxy)")


def proxy_with_delay(client: MockartyClient) -> None:
    """Proxy with artificial delay to test timeout handling.

    The delay is applied AFTER the real response is received,
    simulating network latency or slow processing.
    """
    mock = (
        MockBuilder.http("/api/slow-upstream/:path", "GET")
        .id("proxy-slow")
        .proxy_to("https://api.example.com")
        .respond(200, delay=5000)
        .build()
    )
    client.mocks.create(mock)
    print("Created: GET /api/slow-upstream/:path -> proxy with 5s delay")


def proxy_all_methods(client: MockartyClient) -> None:
    """Set up proxy for multiple HTTP methods on the same route."""
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    for method in methods:
        mock = (
            MockBuilder.http("/proxy/v2/:path", method)
            .id(f"proxy-v2-{method.lower()}")
            .proxy_to("https://staging-api.example.com")
            .build()
        )
        client.mocks.create(mock)
    print(f"Created: proxy for {', '.join(methods)} /proxy/v2/:path")


def proxy_with_tags(client: MockartyClient) -> None:
    """Tag proxy mocks for easy identification and cleanup."""
    mock = (
        MockBuilder.http("/api/external/:path", "GET")
        .id("proxy-external-tagged")
        .proxy_to("https://external-service.example.com")
        .tags("proxy", "external", "staging")
        .build()
    )
    client.mocks.create(mock)
    print("Created: tagged proxy mock for external service")


def proxy_specific_endpoint(client: MockartyClient) -> None:
    """Proxy a specific endpoint while mocking others.

    This pattern is useful for integration testing where you want
    real behavior for some endpoints and mocked for others.
    """
    # Real payment processing (proxied)
    proxy_mock = (
        MockBuilder.http("/api/payments/charge", "POST")
        .id("proxy-real-payment")
        .proxy_to("https://payment-provider.example.com")
        .tags("proxy", "payments")
        .build()
    )
    client.mocks.create(proxy_mock)
    print("Created: POST /api/payments/charge -> real provider (proxied)")

    # Mocked payment status (not proxied)
    status_mock = (
        MockBuilder.http("/api/payments/:id/status", "GET")
        .id("mock-payment-status")
        .respond(200, body={
            "paymentId": "$.pathParam.id",
            "status": "completed",
            "amount": 99.99,
        })
        .tags("mock", "payments")
        .build()
    )
    client.mocks.create(status_mock)
    print("Created: GET /api/payments/:id/status -> mocked response")


# ---------------------------------------------------------------------------
# Direct Proxy API (HTTP, SOAP, gRPC)
# ---------------------------------------------------------------------------

def proxy_http_request(client: MockartyClient) -> None:
    """Proxy an HTTP request through Mockarty via the Proxy API.

    The Proxy API lets you forward arbitrary requests without
    creating mocks first. Useful for one-off testing or debugging.
    """
    result = client.proxy.http({
        "method": "GET",
        "url": "https://jsonplaceholder.typicode.com/posts/1",
        "headers": {
            "Accept": "application/json",
            "X-Request-Id": "sdk-proxy-test-001",
        },
    })
    print("HTTP proxy result:")
    print(f"  Status:       {result.get('statusCode')}")
    print(f"  Content-Type: {result.get('headers', {}).get('Content-Type')}")
    print(f"  Body preview: {str(result.get('body', ''))[:100]}")


def proxy_http_post(client: MockartyClient) -> None:
    """Proxy an HTTP POST request through Mockarty."""
    result = client.proxy.http({
        "method": "POST",
        "url": "https://jsonplaceholder.typicode.com/posts",
        "headers": {
            "Content-Type": "application/json",
        },
        "body": {
            "title": "Test Post from Mockarty SDK",
            "body": "This request was proxied through Mockarty.",
            "userId": 1,
        },
    })
    print("HTTP POST proxy result:")
    print(f"  Status: {result.get('statusCode')}")
    print(f"  Body:   {result.get('body')}")


def proxy_soap_request(client: MockartyClient) -> None:
    """Proxy a SOAP request through Mockarty.

    SOAP proxying handles the XML envelope, WS-Addressing headers,
    and SOAPAction automatically.
    """
    result = client.proxy.soap({
        "url": "https://www.dataaccess.com/webservicesserver/NumberConversion.wso",
        "soapAction": "http://www.dataaccess.com/webservicesserver/NumberToWords",
        "body": """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <NumberToWords xmlns="http://www.dataaccess.com/webservicesserver/">
      <ubiNum>42</ubiNum>
    </NumberToWords>
  </soap:Body>
</soap:Envelope>""",
        "headers": {
            "Content-Type": "text/xml; charset=utf-8",
        },
    })
    print("SOAP proxy result:")
    print(f"  Status: {result.get('statusCode')}")
    print(f"  Body:   {str(result.get('body', ''))[:200]}")


def proxy_grpc_request(client: MockartyClient) -> None:
    """Proxy a gRPC request through Mockarty.

    gRPC proxying works with JSON-encoded protobuf messages.
    The target must be a gRPC server endpoint.
    """
    result = client.proxy.grpc({
        "target": "grpc://localhost:9090",
        "service": "user.UserService",
        "method": "GetUser",
        "metadata": {
            "authorization": "Bearer test-token-123",
        },
        "body": {
            "userId": "usr-42",
        },
    })
    print("gRPC proxy result:")
    print(f"  Status:   {result.get('status')}")
    print(f"  Response: {result.get('body')}")
    if result.get("metadata"):
        print(f"  Metadata: {result.get('metadata')}")


# ---------------------------------------------------------------------------
# Advanced Proxy Patterns
# ---------------------------------------------------------------------------

def proxy_with_response_inspection(client: MockartyClient) -> None:
    """Proxy a request and inspect the full response details.

    Useful for debugging or understanding what a remote service returns
    before creating corresponding mocks.
    """
    result = client.proxy.http({
        "method": "GET",
        "url": "https://httpbin.org/headers",
        "headers": {
            "X-Custom-Header": "test-value",
            "Accept": "application/json",
        },
    })
    print("Proxy with response inspection:")
    print(f"  Status:  {result.get('statusCode')}")
    print(f"  Headers: {result.get('headers')}")
    print(f"  Body:    {result.get('body')}")
    print(f"  Latency: {result.get('latencyMs')}ms")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Mock-based Proxy ===")
        basic_proxy(client)
        proxy_with_delay(client)
        proxy_all_methods(client)
        proxy_with_tags(client)
        proxy_specific_endpoint(client)
        print()

        print("=== Proxy API: HTTP ===")
        proxy_http_request(client)
        print()
        proxy_http_post(client)
        print()

        print("=== Proxy API: SOAP ===")
        proxy_soap_request(client)
        print()

        print("=== Proxy API: gRPC ===")
        proxy_grpc_request(client)
        print()

        print("=== Response Inspection ===")
        proxy_with_response_inspection(client)
        print()

        # Clean up mock-based proxies
        mock_ids = [
            "proxy-basic", "proxy-slow",
            "proxy-v2-get", "proxy-v2-post", "proxy-v2-put",
            "proxy-v2-delete", "proxy-v2-patch",
            "proxy-external-tagged",
            "proxy-real-payment", "mock-payment-status",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("All proxy example mocks cleaned up.")


if __name__ == "__main__":
    main()
