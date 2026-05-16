# Copyright (c) 2026 Mockarty. All rights reserved.

"""Consumer-DSL guard tests + plugin handling + introspection."""

from __future__ import annotations

from pathlib import Path

import pytest

from mockarty.pact import Consumer, SpecVersion


# ── Constructor / configuration guards ───────────────────────────────


class TestConfigurationGuards:
    def test_empty_consumer_name_raises(self):
        with pytest.raises(ValueError):
            Consumer("")

    def test_empty_provider_name_raises(self):
        c = Consumer("A")
        with pytest.raises(ValueError):
            c.with_provider("")

    def test_missing_provider_blocks_to_pact(self):
        c = Consumer("A")
        with pytest.raises(ValueError, match="provider"):
            c.to_pact()

    def test_invalid_spec_version_raises(self):
        c = Consumer("A").with_provider("B")
        with pytest.raises(ValueError):
            c.with_spec_version("V5")

    def test_empty_filename_raises(self):
        c = Consumer("A").with_provider("B")
        with pytest.raises(ValueError):
            c.with_filename("")

    def test_plugin_requires_v4(self):
        c = Consumer("A").with_provider("B").with_spec_version("V3")
        with pytest.raises(ValueError, match="V4-only"):
            c.with_plugin("protobuf")


# ── Builder validation ───────────────────────────────────────────────


class TestBuilderValidation:
    def test_with_request_requires_method(self):
        c = Consumer("A").with_provider("B")
        b = c.upon_receiving("x")
        with pytest.raises(ValueError):
            b.with_request("", "/x")

    def test_with_request_requires_leading_slash(self):
        c = Consumer("A").with_provider("B")
        b = c.upon_receiving("x")
        with pytest.raises(ValueError, match="path"):
            b.with_request("GET", "x")

    def test_status_out_of_range_rejected(self):
        c = Consumer("A").with_provider("B")
        b = c.upon_receiving("x").with_request("GET", "/x")
        with pytest.raises(ValueError):
            b.will_respond_with(99)
        with pytest.raises(ValueError):
            b.will_respond_with(700)

    def test_given_requires_state_name(self):
        c = Consumer("A").with_provider("B")
        with pytest.raises(ValueError):
            c.given("")


# ── Introspection ────────────────────────────────────────────────────


class TestIntrospection:
    def test_spec_version_default_is_v4(self):
        c = Consumer("A").with_provider("B")
        assert c.spec_version is SpecVersion.V4

    def test_output_dir_default(self):
        c = Consumer("A").with_provider("B")
        assert c.output_dir == Path("./pacts")

    def test_interactions_grow(self):
        c = Consumer("A").with_provider("B")
        c.upon_receiving("a").with_request("GET", "/a").will_respond_with(200)
        c.upon_receiving("b").with_request("GET", "/b").will_respond_with(200)
        assert len(c.interactions) == 2

    def test_consumer_provider_names(self):
        c = Consumer("Alpha").with_provider("Beta")
        assert c.consumer_name == "Alpha"
        assert c.provider_name == "Beta"


# ── Multiple given() / chained states ────────────────────────────────


def test_multiple_given_creates_multiple_states():
    c = Consumer("A").with_provider("B").with_spec_version("V4")
    builder = c.given("s1", key=1).given("s2", key=2)
    builder.upon_receiving("x").with_request("GET", "/x").will_respond_with(200)
    pact = c.to_pact()
    assert len(pact.interactions[0].provider_states) == 2
    assert pact.interactions[0].provider_states[0].name == "s1"
    assert pact.interactions[0].provider_states[1].params == {"key": 2}


# ── Add interaction without given / upon_receiving ───────────────────


def test_add_interaction_lower_level():
    c = Consumer("A").with_provider("B")
    b = c.add_interaction()
    b.upon_receiving("manual").with_request("GET", "/m").will_respond_with(200)
    assert len(c.interactions) == 1


# ── with_response_* + with_header convenience ────────────────────────


def test_with_header_chaining(tmp_path):
    c = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    c.upon_receiving("x").with_request("GET", "/x").with_header(
        "Authorization", "Bearer t"
    ).will_respond_with(200).with_response_header("X-Custom", "v").with_response_body(
        {"ok": True}
    )
    pact = c.to_pact()
    req = pact.interactions[0].request
    assert req.headers == {"Authorization": "Bearer t"}
    resp = pact.interactions[0].response
    assert resp.headers == {"X-Custom": "v"}
    assert resp.body == {"ok": True}


def test_pending_flag():
    c = Consumer("A").with_provider("B").with_spec_version("V4")
    b = (
        c.upon_receiving("p")
        .with_request("GET", "/p")
        .will_respond_with(200)
        .pending(True)
    )
    it = b.build()
    assert it.pending is True


def test_explicit_key():
    c = Consumer("A").with_provider("B").with_spec_version("V4")
    b = (
        c.upon_receiving("p")
        .with_request("GET", "/p")
        .will_respond_with(200)
        .key("abc-123")
    )
    it = b.build()
    assert it.key == "abc-123"


def test_started_consumer_forwarders(tmp_path):
    """Touch the property forwarders + ``written_to`` + manual verify."""

    c = (
        Consumer("Alpha")
        .with_provider("Beta")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    c.upon_receiving("ping").with_request("GET", "/p").will_respond_with(200)

    started = c.start()
    try:
        assert started.host == "127.0.0.1"
        assert started.port > 0
        assert started.url.startswith("http://127.0.0.1:")
        assert started.written_to is None
        # Reset is forwarded — clears the (non-existent) hits.
        started.reset()
        import urllib.request

        with urllib.request.urlopen(  # noqa: S310
            f"{started.url}/p",
            timeout=5,
        ) as _r:
            pass
        started.verify()
        path = started.write_pact()
        assert path == started.written_to
    finally:
        started.__exit__(None, None, None)
