# Copyright (c) 2026 Mockarty. All rights reserved.

"""Writer tests — V3 vs V4 schema shape + round-trip via parse()."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mockarty.pact import (
    Consumer,
    EachKey,
    EachLike,
    Equality,
    Integer,
    Like,
    Regex,
    SpecVersion,
)
from mockarty.pact.writer import parse, render


# ── Helpers ────────────────────────────────────────────────────────────


def _build_complex_pact(spec: str) -> Consumer:
    """Same DSL invocation reused by V3+V4 schema tests."""

    consumer = (
        Consumer("OrderService").with_provider("PaymentService").with_spec_version(spec)
    )
    consumer.given("payment service is up", region="eu").upon_receiving(
        "a charge request"
    ).with_request(
        "POST",
        "/charge",
        query={"trace": Regex(r"[a-z0-9-]+", "abc-123")},
        headers={"X-Trace": Like("trace-1")},
        body={
            "amount": Integer(100),
            "currency": Regex(r"[A-Z]{3}", "USD"),
            "tags": EachLike("vip", min=2),
            "meta": EachKey(Like("k"), {"foo": 1, "bar": 2}),
            "status": Equality("pending"),
        },
    ).will_respond_with(
        200,
        headers={"Content-Type": "application/json"},
        body={
            "id": Like("abc"),
            "items": EachLike({"sku": Like("X-1")}, min=1),
        },
    )
    return consumer


# ── V4 schema ─────────────────────────────────────────────────────────


class TestV4Schema:
    def test_renders_synchronous_http_type(self):
        c = _build_complex_pact("V4")
        out = render(c.to_pact(), SpecVersion.V4)
        assert out["interactions"][0]["type"] == "Synchronous/HTTP"
        assert out["interactions"][0]["pending"] is False
        assert "key" in out["interactions"][0]

    def test_metadata_version_is_v4(self):
        c = _build_complex_pact("V4")
        out = render(c.to_pact(), SpecVersion.V4)
        assert out["metadata"]["pactSpecification"]["version"] == "4.0"

    def test_provider_states_is_list(self):
        c = _build_complex_pact("V4")
        out = render(c.to_pact(), SpecVersion.V4)
        states = out["interactions"][0]["providerStates"]
        assert isinstance(states, list)
        assert states[0]["name"] == "payment service is up"
        assert states[0]["params"] == {"region": "eu"}

    def test_matching_rules_nested_by_category(self):
        c = _build_complex_pact("V4")
        out = render(c.to_pact(), SpecVersion.V4)
        rules = out["interactions"][0]["request"]["matchingRules"]
        assert "body" in rules
        assert "$.amount" in rules["body"]
        assert rules["body"]["$.amount"]["matchers"][0]["match"] == "integer"

    def test_response_matchers_nested(self):
        c = _build_complex_pact("V4")
        out = render(c.to_pact(), SpecVersion.V4)
        rules = out["interactions"][0]["response"]["matchingRules"]
        assert rules["body"]["$.id"]["matchers"][0]["match"] == "type"

    def test_body_examples_materialised(self):
        c = _build_complex_pact("V4")
        out = render(c.to_pact(), SpecVersion.V4)
        body = out["interactions"][0]["request"]["body"]
        assert body["amount"] == 100
        assert body["currency"] == "USD"
        assert body["tags"] == ["vip", "vip"]
        assert body["status"] == "pending"

    def test_plugins_recorded(self):
        c = Consumer("A").with_provider("B").with_spec_version("V4")
        with pytest.warns(UserWarning, match="protobuf"):
            c.with_plugin("protobuf", "0.1.0", path="/tmp/x")
        c.given("s").upon_receiving("d").with_request("GET", "/x").will_respond_with(
            200
        )
        out = render(c.to_pact(), SpecVersion.V4)
        plugins = out["metadata"].get("plugins")
        assert plugins
        assert plugins[0]["name"] == "protobuf"
        assert plugins[0]["configuration"] == {"path": "/tmp/x"}


# ── V3 schema ─────────────────────────────────────────────────────────


class TestV3Schema:
    def test_renders_no_type_field(self):
        c = _build_complex_pact("V3")
        out = render(c.to_pact(), SpecVersion.V3)
        assert "type" not in out["interactions"][0]
        assert "key" not in out["interactions"][0]
        assert "pending" not in out["interactions"][0]

    def test_metadata_version_is_v3(self):
        c = _build_complex_pact("V3")
        out = render(c.to_pact(), SpecVersion.V3)
        assert out["metadata"]["pactSpecification"]["version"] == "3.0.0"
        # Plugins must NOT appear on V3.
        assert "plugins" not in out["metadata"]

    def test_provider_state_singular_string(self):
        c = _build_complex_pact("V3")
        out = render(c.to_pact(), SpecVersion.V3)
        it = out["interactions"][0]
        assert it["providerState"] == "payment service is up"
        assert "providerStates" not in it

    def test_matching_rules_flat(self):
        c = _build_complex_pact("V3")
        out = render(c.to_pact(), SpecVersion.V3)
        rules = out["interactions"][0]["request"]["matchingRules"]
        # Flat keys, no nesting under "body".
        assert "body" not in rules
        assert "$.body.amount" in rules
        assert rules["$.body.amount"] == {"match": "integer"}

    def test_v4_only_matcher_degrades_gracefully_on_v3(self):
        c = _build_complex_pact("V3")
        out = render(c.to_pact(), SpecVersion.V3)
        rules = out["interactions"][0]["request"]["matchingRules"]
        # ArrayContains / EachKey fall back to type-match on V3 — still
        # produce a sensible rule, no missing-key error.
        assert rules["$.body.meta"] == {"match": "type"}


# ── Round-trip via parse() ────────────────────────────────────────────


@pytest.mark.parametrize(
    "spec_str,spec_enum",
    [
        ("V3", SpecVersion.V3),
        ("V4", SpecVersion.V4),
    ],
)
def test_roundtrip_parse(spec_str, spec_enum):
    c = _build_complex_pact(spec_str)
    out = render(c.to_pact(), spec_enum)
    serialised = json.dumps(out)
    again = parse(serialised)
    # Consumer + provider + interaction count survive.
    assert again.consumer.name == "OrderService"
    assert again.provider.name == "PaymentService"
    assert len(again.interactions) == 1
    assert again.metadata.pact_specification.version == spec_enum.value


def test_roundtrip_parse_accepts_dict():
    c = _build_complex_pact("V4")
    out = render(c.to_pact(), SpecVersion.V4)
    again = parse(out)
    assert again.interactions[0].description == "a charge request"


# ── write() file-system side effect ───────────────────────────────────


def test_write_creates_dir_and_file(tmp_path: Path):
    c = (
        Consumer("Alpha")
        .with_provider("Beta")
        .with_spec_version("V4")
        .with_output_dir(tmp_path / "deep" / "nested")
    )
    c.given("ready").upon_receiving("ping").with_request("GET", "/p").will_respond_with(
        204
    )
    path = c.write()
    assert path.exists()
    assert path.name == "Alpha-Beta.json"
    data = json.loads(path.read_text("utf-8"))
    assert data["consumer"]["name"] == "Alpha"


def test_write_custom_filename(tmp_path: Path):
    c = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V3")
        .with_output_dir(tmp_path)
        .with_filename("my-contract.json")
    )
    c.given("s").upon_receiving("d").with_request("GET", "/x").will_respond_with(200)
    path = c.write()
    assert path.name == "my-contract.json"


def test_filename_sanitised_for_weird_names(tmp_path: Path):
    c = (
        Consumer("Order/Service:1.0")
        .with_provider("Payment Service<*>")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    c.given("s").upon_receiving("d").with_request("GET", "/x").will_respond_with(200)
    path = c.write()
    # No slashes or angle brackets in the filename.
    assert "/" not in path.name
    assert "<" not in path.name
    assert path.exists()


# ── Determinism ───────────────────────────────────────────────────────


def test_two_renders_match_byte_for_byte():
    """Running the same DSL twice must produce identical JSON.

    pact.json files are diff-friendly; non-determinism would mean
    every CI run shows the file as modified.
    """

    out1 = render(_build_complex_pact("V4").to_pact(), SpecVersion.V4)
    out2 = render(_build_complex_pact("V4").to_pact(), SpecVersion.V4)
    assert json.dumps(out1) == json.dumps(out2)
