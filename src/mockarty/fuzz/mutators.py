# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mutator catalogue for the fuzz DSL.

A mutator drives how the engine perturbs a seed before sending it. The
canonical names map 1:1 onto the server's payload categories — picking
``Mutator.JSON`` enables JSON-aware structural mutations (key drops,
type swaps, etc.), ``Mutator.BYTES`` enables byte-level bit flips, and
so on.

The :class:`Mutator` enum is intentionally string-typed so the
transpiled JSON config uses plain strings (the server's
``payloadCategories`` field is ``[]string``).

Users who need a non-standard mutator can attach a custom descriptor
via :func:`Mutator.custom`. The custom payload is round-tripped
verbatim under a ``customMutators`` key in the SDK metadata; the
server validates known names server-side.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class Mutator(str, Enum):
    """Built-in mutator catalogue.

    Names match the server's ``payloadCategories`` strings so the
    transpiler can emit them without translation.
    """

    JSON = "json"
    XML = "xml"
    BYTES = "bytes"
    STRING = "string"
    URL = "url"
    HEADER = "header"
    GRPC = "grpc"
    GRAPHQL = "graphql"

    # Security-focused categories — same shape on the wire.
    SQLI = "sqli"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    SSRF = "ssrf"
    XXE = "xxe"
    SSTI = "ssti"
    AUTH_BYPASS = "auth_bypass"
    NOSQLI = "nosql_injection"
    LDAPI = "ldap_injection"
    XPATHI = "xpath_injection"
    ORMI = "orm_injection"

    # Surface-level fuzzers.
    BOUNDARY_VALUES = "boundary_values"
    UNICODE = "unicode"
    FORMAT_STRINGS = "format_strings"
    NAUGHTY_STRINGS = "naughty_strings"

    @staticmethod
    def custom(name: str, config: Dict[str, Any] | None = None) -> "CustomMutator":
        """Wrap a user-defined mutator descriptor.

        The ``name`` is appended to the server's payload categories
        list verbatim; the ``config`` dict is carried under
        ``_sdkMeta.customMutators[name]`` so a future server release
        can pick it up without breaking the schema.
        """

        if not name:
            raise ValueError("custom mutator name must be non-empty")
        return CustomMutator(name=name, config=dict(config or {}))


class CustomMutator:
    """Wrapper around a user-defined mutator descriptor."""

    __slots__ = ("name", "config")

    def __init__(self, *, name: str, config: Dict[str, Any]) -> None:
        self.name = name
        self.config = config

    def __repr__(self) -> str:
        return f"CustomMutator(name={self.name!r}, config={self.config!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CustomMutator):
            return NotImplemented
        return self.name == other.name and self.config == other.config

    def __hash__(self) -> int:
        return hash((self.name, tuple(sorted(self.config.items()))))
