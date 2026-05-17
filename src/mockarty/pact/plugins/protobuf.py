# Copyright (c) 2026 Mockarty. All rights reserved.

"""Built-in Protobuf plugin for the V4 Pact runtime.

The plugin handles ``application/x-protobuf`` and
``application/protobuf`` payloads. Two execution paths:

* **Fast path** — when ``google.protobuf`` is importable AND the user
  supplied a Protobuf message instance as the template, we parse the
  incoming bytes into a copy of the message and compare field-by-field.
* **Fallback** — degrade to byte-level comparison so tests that don't
  carry a real proto schema still produce a sensible diff. Mismatches
  include a hex dump of the differing prefix so the user can see what
  the wire format looks like.

The plugin never compiles `.proto` files at runtime and never spawns
``protoc``. Users wanting full schema fidelity register a Python
``google.protobuf.message.Message`` subclass as the template (the
common pattern in proto3 codebases).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from mockarty.pact.matchers import Mismatch
from mockarty.pact.plugins.spi import coerce_to_bytes


# ``google.protobuf`` is optional. We probe it once at import time and
# cache the message base class so ``isinstance`` checks stay cheap.
try:  # pragma: no cover — depends on the executor's environment
    from google.protobuf.message import Message as _PbMessage  # type: ignore
except Exception:  # pragma: no cover
    _PbMessage = None  # type: ignore[assignment]


def _hex_diff(expected: bytes, actual: bytes, max_bytes: int = 16) -> str:
    """Return a short hex preview of the first differing window."""

    n = min(len(expected), len(actual), max_bytes)
    diff_at = next(
        (i for i in range(n) if expected[i] != actual[i]),
        n,
    )
    end = min(diff_at + max_bytes, max(len(expected), len(actual)))
    exp_window = expected[diff_at:end].hex()
    act_window = actual[diff_at:end].hex()
    return f"@offset {diff_at}: expected {exp_window or '<EOF>'}, got {act_window or '<EOF>'}"


class ProtobufPlugin:
    """Built-in protobuf plugin (no FFI)."""

    name = "protobuf"
    version = "1.0.0"
    supported_content_types = [
        "application/x-protobuf",
        "application/protobuf",
        "application/vnd.google.protobuf",
    ]

    def match_request(
        self,
        expected: Any,
        actual: bytes,
        headers: Mapping[str, str],
    ) -> List[Mismatch]:
        # ── Real protobuf path ──────────────────────────────────────
        if _PbMessage is not None and isinstance(expected, _PbMessage):
            try:
                parsed = type(expected)()
                parsed.ParseFromString(bytes(actual))
            except Exception as exc:  # protobuf raises DecodeError + others
                return [
                    Mismatch(
                        "$.body",
                        f"valid {type(expected).__name__} bytes",
                        f"parse error: {exc}",
                    ),
                ]
            if parsed.SerializeToString() != expected.SerializeToString():
                return [
                    Mismatch(
                        "$.body",
                        f"protobuf payload equal to {type(expected).__name__}",
                        "different field values",
                    ),
                ]
            return []
        # ── Byte-equality fallback ───────────────────────────────────
        expected_bytes = coerce_to_bytes(expected)
        if bytes(actual) == expected_bytes:
            return []
        return [
            Mismatch(
                "$.body",
                f"protobuf bytes equal to {len(expected_bytes)}-byte template",
                _hex_diff(expected_bytes, bytes(actual)),
            ),
        ]

    def generate_response(
        self,
        template: Any,
        headers: Mapping[str, str],
    ) -> Tuple[bytes, Dict[str, str]]:
        out_headers = {k: str(v) for k, v in headers.items()}
        out_headers.setdefault("Content-Type", "application/x-protobuf")
        if _PbMessage is not None and isinstance(template, _PbMessage):
            return template.SerializeToString(), out_headers
        return coerce_to_bytes(template), out_headers


__all__ = ["ProtobufPlugin"]
