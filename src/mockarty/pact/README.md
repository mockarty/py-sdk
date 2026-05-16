# `mockarty.pact` — Pact V3 + V4 consumer DSL

Pure-Python contract-testing DSL for Mockarty SDK. Generates pact.json
artefacts that any Pact-compatible verifier consumes (Mockarty admin
server, pact-go, the `pact-broker` CLI, etc.). **No Rust FFI**, no
`libpact_ffi`, no compiled dependencies — only stdlib + pydantic v2.

This module is the Python side of Wave 2 of the SDK pivot
(`docs/research/SDK_FRAMEWORK_PLAN.md` rev 3, §3 Pact compat, Owner
Q12). The Go SDK has a sibling package (`sdk/go-sdk/pact`).

## Quick start

```python
import requests
from mockarty.pact import Consumer, Like

pact = (
    Consumer("OrderService")
    .with_provider("PaymentService")
    .with_spec_version("V4")          # or "V3"
    .with_output_dir("./pacts")
)

pact.given("payment service is up") \
    .upon_receiving("a charge request") \
    .with_request("POST", "/charge", body={"amount": Like(100)}) \
    .will_respond_with(200, body={"id": Like("abc")})

def test_charge():
    with pact.start() as server:
        resp = requests.post(f"{server.url}/charge", json={"amount": 42})
        assert resp.status_code == 200
        # On clean exit:
        #   1. server.verify() asserts every registered interaction was
        #      called and no unexpected request arrived.
        #   2. The pact.json is written to ./pacts/.
```

If you only want the contract file (no in-process mock server because
you drive expectations against an external WireMock-style server like
`mockarty-cli`), skip `.start()` and call `.write()` directly:

```python
path = pact.write()
print("wrote", path)
```

## V3 vs V4 selection

The DSL is identical; only the output JSON shape changes. Pick the
version with `.with_spec_version("V3" | "V4")`. Default is **V4**.

| Aspect                  | V3                                  | V4                                          |
|-------------------------|-------------------------------------|---------------------------------------------|
| `metadata.pactSpecification.version` | `3.0.0`                  | `4.0`                                       |
| Provider states         | Singular `providerState` (string)   | Plural `providerStates` (list of objects)   |
| Interaction type        | (no field)                          | `Synchronous/HTTP` (Phase 1)                |
| `matchingRules` shape   | Flat `{ "$.body.x": rule }`         | Nested `body / header / query / path`       |
| Per-rule shape          | `{"match": "type"}`                 | `{"matchers": [{"match": "type"}], "combine": "AND"}` |
| Plugins                 | (not supported)                     | `metadata.plugins[]` recorded, runtime is Phase 2 |
| Interaction `key`       | (not present)                       | Auto-derived stable identifier              |
| `pending` flag          | (not present)                       | `false` unless `.pending(True)`             |

Both versions are first-class for consumer-side DSL. V4-only matchers
(`EachKey`, `EachValue`, `ArrayContains`, `Equality`) degrade to a
type-match on V3 instead of failing, so the same test code can switch
spec versions without rewriting.

## Matcher table

| Matcher                              | V3 rule                             | V4 rule                                                | Notes                                |
|--------------------------------------|-------------------------------------|--------------------------------------------------------|--------------------------------------|
| `Like(example)`                      | `{"match": "type"}`                 | `{"matchers": [{"match": "type"}]}`                    | Most common                          |
| `Integer(example=0)`                 | `{"match": "integer"}`              | `{"matchers": [{"match": "integer"}]}`                 |                                      |
| `Decimal(example=0.0)`               | `{"match": "decimal"}`              | `{"matchers": [{"match": "decimal"}]}`                 |                                      |
| `Boolean(example=False)`             | `{"match": "boolean"}`              | `{"matchers": [{"match": "boolean"}]}`                 |                                      |
| `Regex(regex, example)`              | `{"match": "regex", "regex": ...}`  | `{"matchers": [{"match": "regex", ...}]}`              | Alias: `Term`                        |
| `Equality(example)`                  | (no rule — V3 default behaviour)    | `{"matchers": [{"match": "equality"}]}`                |                                      |
| `EachLike(template, min=1, max=None)`| `{"match": "type", "min": ...}`     | nested `min`/`max`                                     | Array template                       |
| `MinType(template, min)`             | `{"match": "type", "min": ...}`     | nested                                                 | Array ≥ min                          |
| `MaxType(template, max)`             | `{"match": "type", "max": ...}`     | nested                                                 | Array ≤ max                          |
| `MinMaxType(template, min, max)`     | `{"match": "type", "min", "max"}`   | nested                                                 |                                      |
| `ArrayContains(variants)`            | falls back to `{"match": "type"}`   | `{"matchers": [{"match": "arrayContains", ...}]}`      | V4-only semantics                    |
| `EachKey(inner, example)`            | falls back to `{"match": "type"}`   | `{"matchers": [{"match": "eachKey", ...}]}`            | V4-only; alias `EachKeyLike`         |
| `EachValue(inner, example)`          | falls back to `{"match": "type"}`   | `{"matchers": [{"match": "eachValue", ...}]}`          | V4-only                              |

Nest matchers freely:

```python
from mockarty.pact import Like, EachLike, Regex

body = {
    "user": Like({
        "id": Like(42),
        "email": Regex(r".+@.+", "alice@example.com"),
        "roles": EachLike("admin", min=1),
    }),
}
```

## Fixtures (pytest)

Two opt-in fixtures live in `mockarty.pact.pytest_plugin`. Import them
into your `conftest.py` if you want them:

```python
# conftest.py
from mockarty.pact.pytest_plugin import pact_output_dir, pact_consumer_factory  # noqa: F401
```

`pact_consumer_factory(consumer, provider, spec_version="V4")` returns
a fresh `Consumer` pointed at a `tmp_path`-backed directory.

## What this module does NOT do

* **Verification**: provider-side verification is the verifier's job.
  Use Mockarty admin server (`/api/v1/contracts/verify`), `pact-broker`
  CLI, or any other Pact verifier on the generated pact.json.
* **Plugins (runtime)**: `.with_plugin(...)` records the plugin entry
  for V4 round-trip fidelity but emits a `UserWarning` — actual plugin
  execution lives in Mockarty admin server (Phase 2, per Owner Q12).
* **Async / messaging interactions**: only `Synchronous/HTTP` is
  emitted today. `Asynchronous/Messages` and `Synchronous/Messages`
  ship in Phase 2.
* **Broker publish**: use the platform `Contracts()` REST API on the
  Mockarty client to publish/verify; this DSL only produces the file.

## Phase 2 roadmap

1. V4 plugin runtime (mirror of the Go SDK plugin-client work).
2. `Asynchronous/Messages` + `Synchronous/Messages` interaction types.
3. `Verifier` thin wrapper (`pact.Verifier().with_source(...).verify(...)`).
4. Hypothesis-based property tests for the matcher-rule transformer
   (the seeds live in `tests/test_pact_matchers.py` today).
