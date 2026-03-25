<p align="center">
  <img src="logo.svg" alt="Mockarty" width="400">
</p>

<h1 align="center">Python SDK</h1>

<p align="center">
  Official Python client library for <a href="https://mockarty.ru">Mockarty</a> — a multi-protocol mock server for HTTP, gRPC, MCP, GraphQL, SOAP, SSE, WebSocket, Kafka, RabbitMQ, and SMTP.
</p>

<p align="center">
  <a href="https://pypi.org/project/mockarty/"><img src="https://img.shields.io/pypi/v/mockarty" alt="PyPI"></a>
  <a href="https://pypi.org/project/mockarty/"><img src="https://img.shields.io/pypi/pyversions/mockarty" alt="Python"></a>
  <a href="https://github.com/mockarty/py-sdk/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mockarty/py-sdk" alt="License"></a>
</p>

## Installation

```bash
pip install mockarty
```

For async HTTP/2 support:

```bash
pip install mockarty[async]
```

## Quick Start

### Synchronous Client

```python
from mockarty import MockartyClient, MockBuilder, AssertAction

# Create a client
client = MockartyClient(
    base_url="http://localhost:5770",
    api_key="your-api-key",
    namespace="sandbox",
)

# Create a mock using the builder
mock = (
    MockBuilder.http("/api/users/:id", "GET")
    .id("user-get")
    .respond(200, body={"id": "$.pathParam.id", "name": "$.fake.FirstName"})
    .ttl(3600)
    .build()
)

result = client.mocks.create(mock)
print(f"Created mock: {result.mock.id}")

# List mocks
page = client.mocks.list(namespace="sandbox", limit=10)
for m in page.items:
    print(f"  {m.id}")

# Health check
health = client.health.check()
print(f"Status: {health.status}")

client.close()
```

### Async Client

```python
import asyncio
from mockarty import AsyncMockartyClient, MockBuilder

async def main():
    async with AsyncMockartyClient(base_url="http://localhost:5770") as client:
        mock = MockBuilder.http("/api/hello", "GET").respond(200, body={"msg": "hello"}).build()
        result = await client.mocks.create(mock)
        print(f"Created: {result.mock.id}")

asyncio.run(main())
```

### Context Manager

```python
with MockartyClient() as client:
    client.mocks.create(mock)
    # client.close() is called automatically
```

### Mock Builder

```python
from mockarty import MockBuilder, AssertAction

# HTTP mock with conditions
mock = (
    MockBuilder.http("/api/orders", "POST")
    .id("create-order")
    .namespace("production")
    .tags("orders", "v2")
    .priority(10)
    .condition("$.body.amount", AssertAction.NOT_EMPTY)
    .header_condition("Authorization", AssertAction.NOT_EMPTY)
    .respond(201, body={
        "orderId": "$.fake.UUID",
        "amount": "$.req.amount",
        "status": "created",
    })
    .callback("https://webhook.site/test", method="POST", body={"event": "order.created"})
    .ttl(7200)
    .build()
)

# gRPC mock
grpc_mock = (
    MockBuilder.grpc("user.UserService", "GetUser")
    .id("grpc-get-user")
    .condition("$.id", AssertAction.NOT_EMPTY)
    .respond(200, body={"id": "$.req.id", "name": "$.fake.FirstName"})
    .build()
)

# MCP mock
mcp_mock = (
    MockBuilder.mcp("get_weather")
    .id("mcp-weather")
    .respond(200, body={"temperature": 22, "city": "$.req.city"})
    .build()
)
```

### Working with Stores

```python
with MockartyClient() as client:
    # Global store
    client.stores.global_set("counter", 0)
    data = client.stores.global_get()
    print(data)  # {"counter": 0}

    # Chain store
    client.stores.chain_set("order-flow", "orderId", "abc-123")
    chain_data = client.stores.chain_get("order-flow")
    print(chain_data)  # {"orderId": "abc-123"}
```

### Error Handling

```python
from mockarty import MockartyClient
from mockarty.errors import MockartyNotFoundError, MockartyAPIError

client = MockartyClient()
try:
    mock = client.mocks.get("non-existent")
except MockartyNotFoundError:
    print("Mock not found")
except MockartyAPIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

## Configuration

The client reads these environment variables as defaults:

| Variable | Description | Default |
|---|---|---|
| `MOCKARTY_BASE_URL` | Mockarty server URL | `http://localhost:5770` |
| `MOCKARTY_API_KEY` | API authentication key | `None` |

## pytest Integration

Install the test extras:

```bash
pip install mockarty[test]
```

Use the provided fixtures in your tests:

```python
# conftest.py
pytest_plugins = ["mockarty.testing.fixtures"]

# test_example.py
def test_create_mock(mock_cleanup):
    from mockarty import MockBuilder
    mock = MockBuilder.http("/test", "GET").respond(200, body="ok").build()
    created = mock_cleanup(mock)
    assert created.id is not None
```

## License

MIT
