# Copyright (c) 2026 Mockarty. All rights reserved.

"""Built-in gRPC plugin for the V4 Pact runtime.

The plugin handles ``application/grpc`` and ``application/grpc+proto``
payloads. We do NOT spin up an actual gRPC server (that's the admin
node's job) — Pact contracts here describe the **wire frame** the
consumer expects, so we validate / generate the gRPC length-prefixed
framing on top of the inner protobuf body.

Frame format (HTTP/2 fallback: same on plain HTTP for our mock):

    [1 byte  : compressed-flag (0 == not compressed)]
    [4 bytes : big-endian message length]
    [N bytes : message payload]

Real gRPC requires HTTP/2 + trailers; the stdlib HTTP server can't do
that, so we serve the framing over HTTP/1.1 with ``Content-Type:
application/grpc``. Tests can either round-trip a known frame or use
:class:`mockarty.pact.matchers.Like` against the decoded payload.
"""

from __future__ import annotations

import struct
from typing import Any, Dict, List, Mapping, Tuple

from mockarty.pact.matchers import Mismatch, _validate_value
from mockarty.pact.plugins.spi import Plugin, coerce_to_bytes


_FRAME_HEADER = struct.Struct(">BI")  # 1-byte flag, 4-byte BE length


def _wrap_frame(payload: bytes) -> bytes:
    return _FRAME_HEADER.pack(0, len(payload)) + payload


def _unwrap_frame(raw: bytes) -> Tuple[bool, bytes, str]:
    """Return ``(ok, payload, reason)``. ``ok=False`` means malformed."""

    if len(raw) < _FRAME_HEADER.size:
        return False, b"", f"frame shorter than 5 bytes (got {len(raw)})"
    flag, length = _FRAME_HEADER.unpack_from(raw, 0)
    if flag not in (0, 1):
        return False, b"", f"unknown compression flag {flag}"
    body = raw[_FRAME_HEADER.size : _FRAME_HEADER.size + length]
    if len(body) != length:
        return False, b"", f"declared length {length} but got {len(body)} bytes"
    return True, body, ""


class GRPCPlugin:
    """Built-in gRPC plugin — framing-only, no native runtime."""

    name = "grpc"
    version = "1.0.0"
    supported_content_types = [
        "application/grpc",
        "application/grpc+proto",
        "application/grpc+json",
    ]

    def match_request(
        self,
        expected: Any,
        actual: bytes,
        headers: Mapping[str, str],
    ) -> List[Mismatch]:
        ok, payload, reason = _unwrap_frame(bytes(actual))
        if not ok:
            return [Mismatch("$.body", "well-formed gRPC frame", reason)]
        # If the expected body is bytes, treat as opaque payload equality.
        if isinstance(expected, (bytes, bytearray)):
            if payload == bytes(expected):
                return []
            return [
                Mismatch(
                    "$.body",
                    f"gRPC payload equal to {len(expected)}-byte template",
                    f"payload of {len(payload)} bytes (differs)",
                ),
            ]
        # If expected is a Matcher / dict / list, decode as JSON and
        # walk it through the matcher engine — common pattern for
        # ``application/grpc+json`` and consumer-driven proto-less stubs.
        if "+json" in _content_type(headers) or isinstance(expected, (dict, list)):
            import json as _json

            try:
                decoded = _json.loads(payload.decode("utf-8"))
            except Exception as exc:
                return [
                    Mismatch(
                        "$.body",
                        "JSON payload inside gRPC frame",
                        f"decode error: {exc}",
                    ),
                ]
            return _validate_value(expected, decoded, "$.body")
        # Anything else — fall back to bytes equality on the inner payload.
        if payload == coerce_to_bytes(expected):
            return []
        return [
            Mismatch(
                "$.body",
                f"gRPC payload equal to {len(coerce_to_bytes(expected))}-byte template",
                f"payload of {len(payload)} bytes (differs)",
            ),
        ]

    def generate_response(
        self,
        template: Any,
        headers: Mapping[str, str],
    ) -> Tuple[bytes, Dict[str, str]]:
        out_headers = {k: str(v) for k, v in headers.items()}
        out_headers.setdefault("Content-Type", "application/grpc")
        # gRPC clients typically expect a trailer with ``grpc-status: 0``.
        # We can't send real HTTP/2 trailers, but we set the header so
        # naive clients see a successful call.
        out_headers.setdefault("grpc-status", "0")
        payload_bytes = coerce_to_bytes(template)
        return _wrap_frame(payload_bytes), out_headers


def _content_type(headers: Mapping[str, str]) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return str(v).split(";", 1)[0].strip().lower()
    return ""


__all__ = ["GRPCPlugin"]
