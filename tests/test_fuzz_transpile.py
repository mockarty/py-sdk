# Copyright (c) 2026 Mockarty. All rights reserved.

"""Transpiler tests — verify the wire JSON matches what the server
expects and that round-tripping is stable.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from mockarty.fuzz import (
    AssertNoCrash,
    AssertResponseTimeUnder,
    AssertStatus,
    Mutator,
    Seed,
    Target,
    parse,
    transpile,
)


def _full_http_target() -> Target:
    return (
        Target("login-flow")
        .description("Stress-test login")
        .namespace("default")
        .source_type("manual")
        .strategy("all")
        .http_endpoint(
            "POST",
            "/api/v1/login",
            base_url="https://api.example.com",
        )
        .seeds(
            [
                Seed("valid", '{"u":"a","p":"b"}'),
                Seed("missing-pw", '{"u":"a"}'),
            ]
        )
        .mutator(Mutator.JSON)
        .mutator(Mutator.SQLI)
        .duration(timedelta(minutes=5))
        .timeout_per_request(timedelta(seconds=10))
        .max_requests(1000)
        .max_rps(50)
        .concurrency(8)
        .mutation_depth(3)
        .follow_redirects(True)
        .stop_on_finding(True)
        .verify_findings(True)
        .auth_header("Bearer t")
        .custom_headers({"X-Tenant": "acme"})
        .include_routes(["/api/v1/*"])
        .exclude_routes(["/api/v1/health"])
        .status_code_alerts([500, 502, 503])
        .response_time_alert(timedelta(seconds=2))
        .detect_patterns(["panic", "exception"])
        .reporter("allure")
        .reporter("junit")
        .assertion(AssertStatus(range(200, 300)))
        .assertion(AssertNoCrash(strict=True))
        .assertion(AssertResponseTimeUnder(timedelta(milliseconds=500)))
    )


def test_transpile_emits_canonical_top_level_keys():
    out = transpile(_full_http_target())
    assert out["name"] == "login-flow"
    assert out["namespace"] == "default"
    # sourceType/strategy default to "manual"/"all" so they are
    # dropped by ``exclude_defaults=True``; explicitly set them to
    # non-defaults below to confirm the alias works.
    assert "sourceType" not in out  # default == "manual" → omitted
    assert "strategy" not in out  # default == "all" → omitted
    assert out["targetBaseUrl"] == "https://api.example.com"
    assert out["payloadCategories"] == ["json", "sqli"]


def test_transpile_non_default_source_type_and_strategy_surface():
    t = (
        Target("t")
        .http_endpoint("GET", "/")
        .source_type("recorder")
        .strategy("security")
    )
    out = transpile(t)
    assert out["sourceType"] == "recorder"
    assert out["strategy"] == "security"


def test_transpile_seed_requests_have_camel_case_aliases():
    out = transpile(_full_http_target())
    sr = out["seedRequests"]
    assert len(sr) == 2
    first = sr[0]
    assert first["method"] == "POST"
    assert first["url"] == "https://api.example.com"
    assert first["path"] == "/api/v1/login"
    assert first["body"] == '{"u":"a","p":"b"}'
    assert first["id"] == "valid"


def test_transpile_options_use_camel_case():
    out = transpile(_full_http_target())
    opts = out["options"]
    assert opts["maxDuration"] == "5m"
    assert opts["timeoutPerReq"] == "10s"
    assert opts["maxRequests"] == 1000
    assert opts["maxRps"] == 50
    assert opts["concurrency"] == 8
    assert opts["mutationDepth"] == 3
    assert opts["followRedirects"] is True
    assert opts["stopOnCritical"] is True
    assert opts["verifyFindings"] is True
    assert opts["authHeader"] == "Bearer t"
    assert opts["customHeaders"] == {"X-Tenant": "acme"}
    assert opts["includeRoutes"] == ["/api/v1/*"]
    assert opts["excludeRoutes"] == ["/api/v1/health"]
    assert opts["statusCodeAlerts"] == [500, 502, 503]
    assert opts["responseTimeAlert"] == 2000
    assert opts["detectPatterns"] == ["panic", "exception"]


def test_transpile_drops_default_zero_options():
    out = transpile(Target("min").http_endpoint("GET", "/").mutator(Mutator.JSON))
    # No options at all → block omitted because every default is empty.
    assert "options" not in out or out["options"] == {}


def test_transpile_sdk_meta_carries_assertions_reporters_endpoint():
    out = transpile(_full_http_target())
    meta = out["_sdkMeta"]
    assert meta["protocol"] == "http"
    assert meta["sdk"] == "mockarty-py"
    assert meta["description"] == "Stress-test login"
    assert meta["reporters"] == ["allure", "junit"]
    kinds = [a["kind"] for a in meta["assertions"]]
    assert kinds == ["status", "no_crash", "response_time_under"]
    assert meta["endpoint"]["protocol"] == "http"
    assert meta["endpoint"]["method"] == "POST"


def test_transpile_grpc_routes_address_and_method():
    t = (
        Target("g")
        .grpc_endpoint("Svc", "Method", address="localhost:9000", use_tls=True)
        .seeds([Seed("a", "{}")])
        .mutator(Mutator.GRPC)
    )
    out = transpile(t)
    opts = out["options"]
    assert opts["grpcAddress"] == "localhost:9000"
    assert opts["grpcServices"] == ["Svc"]
    assert opts["grpcMethods"] == ["Method"]
    assert opts["grpcUseTls"] is True
    # gRPC target → no HTTP base URL
    assert out.get("targetBaseUrl", "") == ""


def test_transpile_graphql_routes_endpoint():
    t = (
        Target("gql")
        .graphql_endpoint("https://api/gql", path="/gql")
        .mutator(Mutator.GRAPHQL)
    )
    out = transpile(t)
    assert out["options"]["graphqlEndpoint"] == "https://api/gql"
    assert out["options"]["graphqlPath"] == "/gql"


def test_transpile_kafka_rabbit_soap_ws_route_url_and_meta():
    for builder, key in (
        (lambda: Target("k").kafka_endpoint("kafka:9092", "topic"), "kafka"),
        (
            lambda: Target("r").rabbitmq_endpoint("amqp://q", exchange="ex"),
            "rabbitmq",
        ),
        (lambda: Target("s").soap_endpoint("https://soap"), "soap"),
        (lambda: Target("w").websocket_endpoint("wss://ws"), "websocket"),
    ):
        t = builder()
        out = transpile(t)
        assert out["_sdkMeta"]["protocol"] == key
        assert out.get("targetBaseUrl")  # populated for all four


def test_transpile_requires_endpoint():
    with pytest.raises(ValueError):
        transpile(Target("no-ep"))


def test_transpile_custom_mutator_emits_config_block():
    t = (
        Target("c")
        .http_endpoint("GET", "/")
        .mutator(Mutator.custom("my-mut", {"depth": 5}))
    )
    out = transpile(t)
    assert "my-mut" in out["payloadCategories"]
    assert out["_sdkMeta"]["customMutators"] == {"my-mut": {"depth": 5}}


def test_transpile_round_trip_is_stable():
    """Build → JSON → parse → re-build → compare. Must be byte-identical."""
    t = _full_http_target()
    first = transpile(t)
    payload = json.dumps(first, sort_keys=True)
    reparsed = parse(json.loads(payload))
    # The re-dump must match the first dump exactly.
    re_dumped = reparsed.model_dump(
        by_alias=True, exclude_defaults=True, exclude_none=True
    )
    assert json.dumps(re_dumped, sort_keys=True) == payload


def test_duration_formatting_picks_compact_unit():
    from mockarty.fuzz.transpile import _format_duration

    assert _format_duration(timedelta(seconds=30)) == "30s"
    assert _format_duration(timedelta(minutes=5)) == "5m"
    assert _format_duration(timedelta(hours=2)) == "2h"
    assert _format_duration(timedelta(milliseconds=250)) == "250ms"
    assert _format_duration(timedelta(seconds=0)) == "0s"
    assert _format_duration(timedelta(milliseconds=1500)) == "1500ms"


def test_extra_passes_through_sdk_meta():
    t = Target("x").http_endpoint("GET", "/").extra("ci", "github")
    out = transpile(t)
    assert out["_sdkMeta"]["extra"] == {"ci": "github"}


def test_openapi_spec_serialised_when_set():
    t = Target("o").http_endpoint("GET", "/").openapi_spec("openapi: 3.0\n")
    out = transpile(t)
    assert out["openapiSpec"] == "openapi: 3.0\n"


def test_to_json_method_delegates_to_transpile():
    t = _full_http_target()
    assert t.to_json() == transpile(t)


def test_transpile_unicode_seed_body_survives_round_trip():
    t = (
        Target("u")
        .http_endpoint("POST", "/")
        .seeds([Seed("u", "Привет 🎉")])
        .mutator(Mutator.JSON)
    )
    out = transpile(t)
    assert out["seedRequests"][0]["body"] == "Привет 🎉"
    # And serialise to JSON without escaping turning it into garbage.
    s = json.dumps(out, ensure_ascii=False)
    assert "Привет" in s


def test_transpile_long_seed_body_preserved():
    long_body = "x" * 50_000
    t = Target("long").http_endpoint("POST", "/").seeds([Seed("long", long_body)])
    out = transpile(t)
    assert len(out["seedRequests"][0]["body"]) == 50_000
