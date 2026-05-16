# Copyright (c) 2026 Mockarty. All rights reserved.

"""Plugin SPI (Service Provider Interface) for the V4 Pact runtime.

A *plugin* is a content-type adapter the mock server invokes when an
incoming or outgoing request carries a non-JSON payload. Plugins are
pure-Python objects implementing :class:`Plugin` — no FFI, no native
libraries, no subprocess.

The contract is deliberately small so the SDK can stay air-gapped and
zero-dependency: a plugin tells the runtime what content-types it
handles, validates an incoming request body against the declared
contract, and renders the outgoing response body.

This module only defines the Protocol — concrete plugins live next to
it (:mod:`protobuf`, :mod:`grpc`) and the user-facing registry is in
:mod:`registry`. The mock server never imports plugin implementations
directly; it walks the registry, which makes adding a new plugin a
two-file change (the plugin module + a registry call).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Protocol, Tuple, runtime_checkable

from mockarty.pact.matchers import Mismatch


@runtime_checkable
class Plugin(Protocol):
    """Adapter for one content-type family.

    All four members are required. The simplest viable plugin is a
    pass-through that copies the example body unchanged — see
    :class:`mockarty.pact.plugins.protobuf.ProtobufPlugin` for a real
    implementation that round-trips through ``google.protobuf`` if it
    happens to be importable, and degrades to byte-equality otherwise.
    """

    #: Stable lowercase identifier, used by ``Consumer.with_plugin``.
    name: str

    #: Plugin semver (free-form string). Phase 1 simply records this in
    #: the pact metadata for round-trip fidelity; future verifiers may
    #: refuse to load a plugin whose version is missing.
    version: str

    #: Lower-cased Content-Types the plugin handles. The mock server
    #: matches them via case-insensitive equality on the bare type
    #: (parameters like ``; charset=utf-8`` are stripped before lookup).
    supported_content_types: List[str]

    def match_request(
        self,
        expected: Any,
        actual: bytes,
        headers: Mapping[str, str],
    ) -> List[Mismatch]:
        """Validate ``actual`` (raw bytes) against the declared template.

        Return an empty list on success. Each :class:`Mismatch` entry is
        returned verbatim to the client (HTTP 400 envelope) and folded
        into :meth:`MockServer.verify`.
        """
        ...

    def generate_response(
        self,
        template: Any,
        headers: Mapping[str, str],
    ) -> Tuple[bytes, Dict[str, str]]:
        """Render the response body + headers to send back to the client.

        ``template`` is whatever the user passed as ``body=`` on the
        interaction (matchers or raw bytes). Return ``(payload_bytes,
        outbound_headers)``; the runtime preserves the headers as-is
        (no merging), so plugins must include their own Content-Type.
        """
        ...


# ── Helpers shared by the built-in plugins ──────────────────────────


def coerce_to_bytes(value: Any) -> bytes:
    """Lossless ``Any → bytes`` coercion used by ad-hoc plugins.

    * ``bytes`` / ``bytearray`` → unchanged
    * ``str`` → UTF-8
    * ``dict`` / ``list`` → JSON (UTF-8)
    * anything else → ``str(...)`` UTF-8

    Plugins are free to call this so they don't all reinvent the wheel,
    but the SPI doesn't depend on it.
    """

    import json

    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False).encode("utf-8")
    return str(value).encode("utf-8")


__all__ = ["Plugin", "coerce_to_bytes"]
