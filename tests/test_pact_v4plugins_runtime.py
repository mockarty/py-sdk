# Copyright (c) 2026 Mockarty. All rights reserved.

"""V4 plugin SPI + built-in plugins (protobuf, gRPC) — Wave 4.

Exercises the plugin registry, Consumer.with_plugin wiring, the
ProtobufPlugin (with and without ``google.protobuf`` installed) and
the GRPCPlugin's wire-frame matching + response generation.
"""

from __future__ import annotations

import json
import struct
import urllib.error
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pytest

from mockarty.pact import (
    Consumer,
    GRPCPlugin,
    Like,
    Mismatch,
    PactMismatchError,
    Plugin,
    PluginAlreadyRegistered,
    ProtobufPlugin,
)
from mockarty.pact.plugins import registry as plugin_registry
from mockarty.pact.plugins import reset_to_builtins
from mockarty.pact.plugins.grpc import _unwrap_frame, _wrap_frame
from mockarty.pact.plugins.spi import coerce_to_bytes


# ── HTTP helper ──────────────────────────────────────────────────────


def _http(
    method: str,
    url: str,
    raw: bytes,
    content_type: str,
) -> Tuple[int, bytes, Dict[str, str]]:
    req = urllib.request.Request(
        url,
        data=raw,
        method=method,
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


# ── Registry ──────────────────────────────────────────────────────────


class TestRegistry:
    def setup_method(self):
        reset_to_builtins()

    def test_builtins_registered(self):
        assert plugin_registry.get("protobuf") is not None
        assert plugin_registry.get("grpc") is not None
        assert "protobuf" in plugin_registry.names()
        assert "grpc" in plugin_registry.names()

    def test_register_duplicate_raises(self):
        with pytest.raises(PluginAlreadyRegistered):
            plugin_registry.register(ProtobufPlugin())

    def test_register_replace_ok(self):
        # No exception when explicitly replacing.
        plugin_registry.register(ProtobufPlugin(), replace=True)

    def test_unregister(self):
        assert plugin_registry.unregister("protobuf") is True
        assert plugin_registry.get("protobuf") is None
        # Removing again returns False.
        assert plugin_registry.unregister("protobuf") is False
        reset_to_builtins()

    def test_each_iterates(self):
        names = sorted(p.name for p in plugin_registry.each())
        assert "protobuf" in names and "grpc" in names

    def test_register_non_plugin_rejected(self):
        with pytest.raises(TypeError):
            plugin_registry.register(object())  # type: ignore[arg-type]

    def test_register_blank_name(self):
        class Broken:
            name = ""
            version = "1.0"
            supported_content_types: List[str] = ["x/y"]

            def match_request(self, expected, actual, headers):  # type: ignore[no-untyped-def]
                return []

            def generate_response(self, template, headers):  # type: ignore[no-untyped-def]
                return b"", {}

        with pytest.raises(ValueError):
            plugin_registry.register(Broken())  # type: ignore[arg-type]


# ── ProtobufPlugin ────────────────────────────────────────────────────


class TestProtobufPlugin:
    def test_metadata(self):
        p = ProtobufPlugin()
        assert p.name == "protobuf"
        assert "application/x-protobuf" in p.supported_content_types

    def test_byte_equality_pass(self):
        p = ProtobufPlugin()
        assert p.match_request(b"\x08\x01", b"\x08\x01", {}) == []

    def test_byte_equality_fail(self):
        p = ProtobufPlugin()
        out = p.match_request(b"\x08\x01", b"\x08\x02", {})
        assert out and "@offset" in out[0].actual

    def test_string_template_byte_compare(self):
        p = ProtobufPlugin()
        assert p.match_request("hello", b"hello", {}) == []
        out = p.match_request("hello", b"world", {})
        assert out

    def test_generate_response_bytes(self):
        p = ProtobufPlugin()
        payload, hdrs = p.generate_response(b"\x00\x01\x02", {})
        assert payload == b"\x00\x01\x02"
        assert hdrs["Content-Type"] == "application/x-protobuf"

    def test_generate_response_preserves_custom_header(self):
        p = ProtobufPlugin()
        _, hdrs = p.generate_response(b"x", {"Content-Type": "application/protobuf"})
        assert hdrs["Content-Type"] == "application/protobuf"

    def test_empty_body(self):
        p = ProtobufPlugin()
        # empty == empty is OK
        assert p.match_request(b"", b"", {}) == []

    def test_real_protobuf_roundtrip(self):
        """When google.protobuf is importable, full schema parity."""

        try:
            from google.protobuf import descriptor_pb2  # type: ignore
        except ImportError:
            pytest.skip("google.protobuf not installed")

        p = ProtobufPlugin()
        expected = descriptor_pb2.FileDescriptorProto(name="foo.proto", package="x")
        actual_bytes = descriptor_pb2.FileDescriptorProto(
            name="foo.proto", package="x"
        ).SerializeToString()
        assert p.match_request(expected, actual_bytes, {}) == []

    def test_real_protobuf_field_difference(self):
        try:
            from google.protobuf import descriptor_pb2  # type: ignore
        except ImportError:
            pytest.skip("google.protobuf not installed")

        p = ProtobufPlugin()
        expected = descriptor_pb2.FileDescriptorProto(name="foo.proto")
        actual_bytes = descriptor_pb2.FileDescriptorProto(
            name="other.proto"
        ).SerializeToString()
        out = p.match_request(expected, actual_bytes, {})
        assert out and "different field values" in out[0].actual

    def test_real_protobuf_parse_error(self):
        try:
            from google.protobuf import descriptor_pb2  # type: ignore
        except ImportError:
            pytest.skip("google.protobuf not installed")

        p = ProtobufPlugin()
        expected = descriptor_pb2.FileDescriptorProto()
        # garbage bytes will fail ParseFromString
        out = p.match_request(expected, b"\xff\xff\xff\xff\xff\xff\xff\xff", {})
        assert out and "parse error" in out[0].actual


# ── GRPCPlugin ────────────────────────────────────────────────────────


class TestGRPCPlugin:
    def test_metadata(self):
        p = GRPCPlugin()
        assert p.name == "grpc"
        assert "application/grpc" in p.supported_content_types

    def test_wrap_unwrap_roundtrip(self):
        for payload in (b"", b"x", b"\x00" * 1024, b"abc\xff\x00\xff"):
            frame = _wrap_frame(payload)
            ok, body, _ = _unwrap_frame(frame)
            assert ok and body == payload

    def test_unwrap_too_short(self):
        ok, _, reason = _unwrap_frame(b"\x00\x00")
        assert not ok and "shorter" in reason

    def test_unwrap_bad_flag(self):
        # flag byte must be 0 or 1
        bad = b"\x02" + struct.pack(">I", 1) + b"x"
        ok, _, reason = _unwrap_frame(bad)
        assert not ok and "compression flag" in reason

    def test_unwrap_truncated_payload(self):
        bad = b"\x00" + struct.pack(">I", 5) + b"abc"  # declared 5, sent 3
        ok, _, reason = _unwrap_frame(bad)
        assert not ok and "declared length" in reason

    def test_match_request_bytes_pass(self):
        p = GRPCPlugin()
        actual = _wrap_frame(b"payload")
        assert p.match_request(b"payload", actual, {}) == []

    def test_match_request_bytes_fail(self):
        p = GRPCPlugin()
        actual = _wrap_frame(b"different")
        out = p.match_request(b"payload", actual, {})
        assert out

    def test_match_request_json_payload(self):
        p = GRPCPlugin()
        inner = json.dumps({"id": 7}).encode("utf-8")
        actual = _wrap_frame(inner)
        # When expected is a dict, plugin walks the matcher engine.
        assert p.match_request({"id": Like(0)}, actual, {}) == []
        out = p.match_request({"id": Like("string")}, actual, {})
        assert out

    def test_match_request_malformed_frame(self):
        p = GRPCPlugin()
        out = p.match_request(b"x", b"\x00\x00", {})
        assert out and "frame" in out[0].expected

    def test_generate_response_wraps_frame(self):
        p = GRPCPlugin()
        payload, hdrs = p.generate_response(b"abc", {})
        ok, body, _ = _unwrap_frame(payload)
        assert ok and body == b"abc"
        assert hdrs["Content-Type"] == "application/grpc"
        assert hdrs["grpc-status"] == "0"

    def test_generate_response_json_template(self):
        p = GRPCPlugin()
        payload, _ = p.generate_response({"id": 7}, {})
        ok, body, _ = _unwrap_frame(payload)
        assert ok and json.loads(body) == {"id": 7}


# ── Consumer.with_plugin wiring ──────────────────────────────────────


class TestConsumerWithPlugin:
    def setup_method(self):
        reset_to_builtins()

    def test_with_known_plugin_no_warning(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warn → exception
            c.with_plugin("protobuf")

    def test_with_unknown_plugin_warns(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        with pytest.warns(UserWarning, match="not in registry"):
            c.with_plugin("nonexistent-plugin")

    def test_with_plugin_blank_name(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        with pytest.raises(ValueError):
            c.with_plugin("")

    def test_with_plugin_rejected_on_v3(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V3")
            .with_output_dir(tmp_path)
        )
        with pytest.raises(ValueError, match="V4-only"):
            c.with_plugin("protobuf")

    def test_metadata_persisted(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.with_plugin("protobuf", version="1.0.0", schema="foo.proto")
        c.upon_receiving("x").with_request("GET", "/x").will_respond_with(200)
        path = c.write()
        contents = json.loads(path.read_text("utf-8"))
        plugins = contents["metadata"]["plugins"]
        assert any(p["name"] == "protobuf" for p in plugins)
        assert any(p["configuration"].get("schema") == "foo.proto" for p in plugins)

    def test_version_mismatch_warns(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        # Built-in is 1.0.0; request a different version.
        with pytest.warns(UserWarning, match="version mismatch"):
            c.with_plugin("protobuf", version="9.9.9")


# ── End-to-end mock-server + plugin ─────────────────────────────────


class TestPluginEndToEnd:
    def setup_method(self):
        reset_to_builtins()

    def test_grpc_plugin_serves_response(self, tmp_path: Path):
        c = (
            Consumer("Client")
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
            .with_plugin("grpc")
        )
        c.upon_receiving("grpc echo").with_request(
            "POST", "/svc/Echo", body=b"hello"
        ).will_respond_with(
            200,
            headers={"Content-Type": "application/grpc"},
            body=b"world",
        )

        with c.start(strict=True) as server:
            frame = _wrap_frame(b"hello")
            status, body, hdrs = _http(
                "POST", f"{server.url}/svc/Echo", frame, "application/grpc"
            )
            assert status == 200
            assert hdrs.get("Content-Type") == "application/grpc"
            ok, payload, _ = _unwrap_frame(body)
            assert ok and payload == b"world"

    def test_grpc_plugin_strict_fail(self, tmp_path: Path):
        c = (
            Consumer("Client")
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
            .with_plugin("grpc")
        )
        c.upon_receiving("grpc fail").with_request(
            "POST", "/svc/Echo", body=b"expected"
        ).will_respond_with(
            200, headers={"Content-Type": "application/grpc"}, body=b"resp"
        )

        with pytest.raises(PactMismatchError):
            with c.start(strict=True) as server:
                bad_frame = _wrap_frame(b"actually-different")
                status, body, _ = _http(
                    "POST",
                    f"{server.url}/svc/Echo",
                    bad_frame,
                    "application/grpc",
                )
                assert status == 400

    def test_grpc_plugin_json_payload_round_trip(self, tmp_path: Path):
        c = (
            Consumer("Client")
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
            .with_plugin("grpc")
        )
        c.upon_receiving("grpc+json").with_request(
            "POST", "/svc/J", body={"id": Like(0)}
        ).will_respond_with(
            200,
            headers={"Content-Type": "application/grpc+json"},
            body={"ok": True},
        )

        with c.start(strict=True) as server:
            frame = _wrap_frame(json.dumps({"id": 42}).encode("utf-8"))
            status, body, _ = _http(
                "POST", f"{server.url}/svc/J", frame, "application/grpc+json"
            )
            assert status == 200
            ok, payload, _ = _unwrap_frame(body)
            assert ok and json.loads(payload) == {"ok": True}

    def test_protobuf_plugin_byte_equality(self, tmp_path: Path):
        c = (
            Consumer("Client")
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
            .with_plugin("protobuf")
        )
        c.upon_receiving("proto").with_request(
            "POST", "/proto", body=b"\x08\x01"
        ).will_respond_with(
            200,
            headers={"Content-Type": "application/x-protobuf"},
            body=b"\x08\x02",
        )

        with c.start(strict=True) as server:
            status, body, hdrs = _http(
                "POST", f"{server.url}/proto", b"\x08\x01", "application/x-protobuf"
            )
            assert status == 200
            assert body == b"\x08\x02"
            assert hdrs.get("Content-Type") == "application/x-protobuf"

    def test_protobuf_plugin_strict_fail(self, tmp_path: Path):
        c = (
            Consumer("Client")
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
            .with_plugin("protobuf")
        )
        c.upon_receiving("proto fail").with_request(
            "POST", "/proto", body=b"\x08\x01"
        ).will_respond_with(
            200, headers={"Content-Type": "application/x-protobuf"}, body=b"\x08\x02"
        )

        with pytest.raises(PactMismatchError):
            with c.start(strict=True) as server:
                status, _, _ = _http(
                    "POST", f"{server.url}/proto", b"\x99\x99", "application/x-protobuf"
                )
                assert status == 400


# ── SPI protocol checks ──────────────────────────────────────────────


class TestSPIShape:
    def test_protobuf_satisfies_protocol(self):
        # runtime_checkable Protocol check works because the methods exist.
        assert isinstance(ProtobufPlugin(), Plugin)

    def test_grpc_satisfies_protocol(self):
        assert isinstance(GRPCPlugin(), Plugin)

    def test_coerce_to_bytes(self):
        assert coerce_to_bytes(None) == b""
        assert coerce_to_bytes(b"abc") == b"abc"
        assert coerce_to_bytes(bytearray(b"abc")) == b"abc"
        assert coerce_to_bytes("utf-eee 🎯") == "utf-eee 🎯".encode("utf-8")
        assert coerce_to_bytes({"a": 1}) == b'{"a": 1}'
        assert coerce_to_bytes([1, 2]) == b"[1, 2]"
        assert coerce_to_bytes(42) == b"42"


# ── Custom user plugin (registry round-trip) ─────────────────────────


class _EchoPlugin:
    """Tiny user-style plugin used as a registry parity test fixture."""

    name = "echo"
    version = "0.1.0"
    supported_content_types: List[str] = ["application/x-echo"]

    def __init__(self) -> None:
        self.calls: List[bytes] = []

    def match_request(self, expected, actual, headers):  # type: ignore[no-untyped-def]
        self.calls.append(bytes(actual))
        if expected == bytes(actual):
            return []
        return [Mismatch("$.body", f"{expected!r}", actual)]

    def generate_response(self, template, headers):  # type: ignore[no-untyped-def]
        return coerce_to_bytes(template), {"Content-Type": "application/x-echo"}


def test_user_plugin_round_trip(tmp_path: Path):
    reset_to_builtins()
    echo = _EchoPlugin()
    plugin_registry.register(echo)
    try:
        c = (
            Consumer("Client")
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
            .with_plugin("echo")
        )
        c.upon_receiving("echo").with_request(
            "POST", "/e", body=b"ping"
        ).will_respond_with(
            200, headers={"Content-Type": "application/x-echo"}, body=b"pong"
        )

        with c.start(strict=True) as server:
            status, body, _ = _http(
                "POST", f"{server.url}/e", b"ping", "application/x-echo"
            )
            assert status == 200
            assert body == b"pong"
        assert echo.calls == [b"ping"]
    finally:
        plugin_registry.unregister("echo")


# ── Schema parity vs V4 reference fixture ────────────────────────────


def test_pact_json_v4_plugin_block(tmp_path: Path):
    """The metadata.plugins block must match the official V4 schema:
    a list of objects with ``name``, ``version`` (optional), and
    ``configuration`` (optional dict).
    """

    reset_to_builtins()
    c = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
        .with_plugin("protobuf", schema="foo.proto", optional=True)
        .with_plugin("grpc")
    )
    c.upon_receiving("x").with_request("GET", "/x").will_respond_with(200)
    path = c.write()
    raw = json.loads(path.read_text("utf-8"))
    plugins = raw["metadata"]["plugins"]
    assert len(plugins) == 2
    assert plugins[0]["name"] == "protobuf"
    assert plugins[0]["configuration"]["schema"] == "foo.proto"
    assert plugins[1]["name"] == "grpc"
    # version is always present (taken from runtime metadata)
    assert plugins[0]["version"] == "1.0.0"
