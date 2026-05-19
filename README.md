<p align="center">
  <img src="https://raw.githubusercontent.com/mockarty/py-sdk/main/logo.svg" alt="Mockarty" width="400">
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

## Protocol Clients

Beyond *configuring* mocks, the SDK ships test clients to *drive* the
system under test for SOAP / GraphQL / SSE / WebSocket — each captures
every call as a TCM step so the external run shows a per-call timeline:

- `mockarty.protocols.soap`      — SOAP 1.1 / 1.2 with stdlib XML parsing
- `mockarty.protocols.graphql`   — GraphQL with auto operation-name extraction
- `mockarty.protocols.sse`       — Server-Sent Events (WHATWG parser, `collect` + `stream`)
- `mockarty.protocols.websocket` — WebSocket via the optional `protocols` extra
- `mockarty.protocols.telemetry` — shared `Step` / `AccumulatingRecorder`

```python
from mockarty import Client
from mockarty.protocols import AccumulatingRecorder
from mockarty.protocols.graphql import GraphQLClient

client = Client("http://localhost:5770", api_token="...")
rec = AccumulatingRecorder()

gql = GraphQLClient("http://app/graphql", recorder=rec)
gql.execute("query GetUser { user { id } }")

# At test finish, push the captured timeline:
client.external_runs().report(case_name="my case", status="passed", steps=rec.steps())
```

For WebSocket support:

```bash
pip install "mockarty[protocols]"
```

Full cross-language reference (Python / Go / Java side-by-side, every
protocol, options, classification rules, troubleshooting):
**[SDK Protocol Clients](https://mockarty.ru/docs/sdk-protocol-clients)**.

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

## Allure Compatibility (default-ON)

Mockarty ships **seamless Allure interop** — existing Allure-based test
suites run through Mockarty with **zero refactor**. Three usage styles
work in the same project, in the same test file, mixed freely:

```bash
pip install mockarty[allure]   # pulls in allure-pytest 2.13+
```

1.  **Pure Allure** — your existing code:

    ```python
    import allure

    @allure.feature("auth")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login():
        with allure.step("submit login form"):
            ...
    ```

    Steps, attachments and labels flow into Mockarty's test-case
    accumulator automatically. The native `allure-results/` output
    continues to work too — both sinks receive every event.

2.  **Mockarty native**:

    ```python
    from mockarty.testing import test_case, step, attach

    @test_case("CASE-LOGIN-1")
    def test_login():
        with step("submit login form"):
            attach("payload.json", b"{...}", content_type="application/json")
    ```

3.  **Drop-in alias** — for migrating codebases that prefer a clean
    `import` swap:

    ```python
    import mockarty.allure as allure   # surface mirrors `allure` 1:1

    @allure.feature("auth")
    def test_login():
        with allure.step("submit"):
            ...
    ```

### Configuration

| Env var | Default | Effect |
|---|---|---|
| `MOCKARTY_ALLURE_MIRROR` | `on` | Set to `off` to disable the Allure → Mockarty mirror entirely. The pytest plugin's listener is not registered when off. |
| `MOCKARTY_ALLURE_SHIM` | `off` | Set to `on` (advisory) to register `mockarty.allure` as `sys.modules["allure"]` *when allure-pytest is not installed*. Lets pure-Allure code run as no-op in environments without the real package. |

### How it works

The pytest plugin's `pytest_configure` hook registers a listener with
`allure_commons.plugin_manager` that observes Allure's native lifecycle
hooks (`start_step`, `stop_step`, `attach_data`, `add_label`, etc.).
Each observed event is mirrored onto the active Mockarty `CaseFrame`
— if the user's test has no explicit `@mockarty.testing.test_case`
binding, the plugin opens an implicit frame keyed on the test node id
so Allure decorators still produce a Mockarty case run.

The reverse direction (`mockarty.testing.step` → `allure.step`) has
existed since `0.3.0` and continues to work. When both decorator
families participate in a single step, the suppression context-var
prevents double-counting.

## License

MIT
