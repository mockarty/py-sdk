# `mockarty.fuzz` — Language-Side Fuzz DSL

> Status: **Phase 1** — fluent DSL, transpile-to-JSON, submit/wait/stream,
> local-spawn via `mockarty-cli`. No embedded fuzz runtime, no FFI, no
> compiled deps.

The `mockarty.fuzz` package lets you describe a fuzz target in idiomatic
Python and hand the description to a running Mockarty admin server
(`/api/v1/fuzzing/run`) or to `mockarty-cli fuzz run` for air-gapped
CI. The server / CLI does the actual mutation, transport, dedup and
detection work — the SDK stays a **thin descriptor layer** per
`feedback_sdk_thin_layer.md`.

## Quick start

```python
from datetime import timedelta
from mockarty.client import MockartyClient
from mockarty.fuzz import (
    Target,
    Seed,
    Mutator,
    AssertStatus,
    AssertNoCrash,
    Runner,
)

# 1. Describe the target.
target = (
    Target("login-flow")
    .description("Stress-test login endpoint")
    .http_endpoint("POST", "/api/v1/login",
                   base_url="https://api.example.com")
    .seeds([
        Seed("valid",      '{"username":"admin","password":"secret"}'),
        Seed("missing-pw", '{"username":"admin"}'),
        Seed.from_file("./corpus/login.json"),
    ])
    .mutator(Mutator.JSON)
    .mutator(Mutator.SQLI)
    .duration(timedelta(minutes=5))
    .stop_on_finding(True)
    .reporter("allure")
    .assertion(AssertStatus(range(200, 300)))
    .assertion(AssertNoCrash())
)

# 2. Submit to a running admin server.
client = MockartyClient(base_url="https://mockarty.local", token="…")
runner = Runner(client)
job_id = runner.submit(target)
result = runner.wait(job_id, timeout=600)

assert result.passed, f"{result.total_findings} findings, see {result.id}"
```

## Surface table

| Class / function          | Purpose                                                        |
| ------------------------- | -------------------------------------------------------------- |
| `Target`                  | Fluent target builder; `to_json()` produces the wire config    |
| `Seed`                    | One seed corpus entry; `from_file`, `bytes` helpers            |
| `Mutator`                 | Built-in mutator catalogue (`JSON`, `XML`, `BYTES`, `SQLI`, …) |
| `Mutator.custom(name, …)` | Wrap a user-defined mutator descriptor                         |
| `Protocol`                | HTTP / gRPC / GraphQL / Kafka / RabbitMQ / SOAP / WebSocket    |
| `AssertStatus`            | Pass when response status is in range / set                    |
| `AssertNoCrash`           | Pass unless detector signals a crash                           |
| `AssertResponseTimeUnder` | Pass when response time < limit                                |
| `AssertNoErrorInBody`     | Pass when body does NOT match a regex                          |
| `assertion(kind, **)`     | Forward-compat free-form assertion                             |
| `Runner.submit / wait`    | HTTP path — POST config, poll for result                       |
| `Runner.stream`           | Iterate snapshots until the run terminates                     |
| `Runner.local_spawn`      | Subprocess path — `mockarty-cli fuzz run --config <tmp>`       |
| `Runner.stop`             | Best-effort cancel                                             |
| `write_to(target, path)`  | Dump the transpiled config to a file                           |
| `transpile(target)`       | Lower-level rendering helper (`Target.to_json()` calls it)     |
| `parse(payload)`          | Round-trip helper used by tests                                |
| `Result`, `Finding`       | Run-level + per-finding dataclasses                            |

## Hybrid pattern — `Runner` + `mockarty-cli`

For CI runners that can't reach the admin server's HTTP port, the
runner falls back to subprocess mode:

```python
runner = Runner()  # no HTTP client
out = runner.local_spawn(target, extra_args=["--report", "allure"])
assert out.succeeded, out.stderr
```

The runner writes the canonical config to a temp file, invokes
`mockarty-cli fuzz run --config <path>` and surfaces stdout / stderr /
exit code in a :class:`LocalSpawnResult`. Same target, same JSON,
zero code changes between modes.

## Protocols

```python
Target("…").http_endpoint("GET", "/users/:id")
Target("…").grpc_endpoint("UserService", "GetUser",
                          address="localhost:9000", use_tls=True)
Target("…").graphql_endpoint("https://api/graphql")
Target("…").kafka_endpoint("localhost:9092", topic="users")
Target("…").rabbitmq_endpoint("amqp://…", queue="orders")
Target("…").soap_endpoint("https://…/svc", soap_action="GetUser")
Target("…").websocket_endpoint("wss://…/ws", subprotocol="json")
```

The transpiler routes each protocol's fields onto the right server
slots (`options.grpcAddress` for gRPC, `options.graphqlEndpoint` for
GraphQL, `targetBaseUrl` for HTTP/SOAP/WS, etc.).

## Schema parity

The wire JSON matches `internal/fuzzing/config.go` (`FuzzConfig` +
`FuzzOptions` + `FuzzSeedRequest`). Anything Mockarty-specific the SDK
introduces (assertions, reporters, custom-mutator configs) lives under
the `_sdkMeta` sentinel so the server can pick it up without breaking
the canonical fields.

## Phase 2 backlog

* Real-time SSE stream instead of polling (`/api/v1/fuzzing/run/{id}/events`).
* Finding-triage helpers — `runner.triage(finding_id, status="confirmed")`.
* Built-in reporters (Allure / SARIF / JUnit) that consume `Result`
  and emit artifacts to the project's `--alluredir` etc. on its
  behalf.
* `Target.from_openapi(path)` — derive seeds from an OpenAPI spec on
  the client side (mirrors `internal/fuzzing/source/openapi.go`).
* Async runner (`AsyncRunner`) for fully non-blocking pytest-asyncio
  workflows.
* Per-finding deep-link helpers — `finding.admin_url(base)`.
