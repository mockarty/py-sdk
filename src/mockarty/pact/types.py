# Copyright (c) 2026 Mockarty. All rights reserved.

"""Pydantic v2 models that mirror the Pact V3 and V4 JSON schemas.

These models are the single source of truth for what the writer
serialises. The fluent DSL in :mod:`mockarty.pact.consumer` builds
instances of these models, the writer dumps them, and the parser
(used by tests + fuzz harness) reads them back.

Reference specs:

* V3 — https://github.com/pact-foundation/pact-specification/tree/version-3
* V4 — https://github.com/pact-foundation/pact-specification/tree/version-4

Phase 1 only models the **HTTP / synchronous** interaction type. The
V4 ``Synchronous/HTTP`` shape is emitted; ``Synchronous/Messages`` and
``Asynchronous/Messages`` are deferred to Phase 2 per
``SDK_FRAMEWORK_PLAN.md`` §3.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field


class SpecVersion(str, Enum):
    """Pact specification version.

    The two values are the only legal payload for the
    ``pact_specification.version`` field in pact.json. We accept them
    as plain strings in the DSL (``"V3"`` / ``"V4"``) and map both
    upper- and lower-case forms via :func:`coerce_spec_version`.
    """

    V3 = "3.0.0"
    V4 = "4.0"


def coerce_spec_version(value: str | SpecVersion) -> SpecVersion:
    """Normalise the user's spec-version input.

    Accepts ``"V3"``, ``"v3"``, ``"3"``, ``"3.0.0"``, ``SpecVersion.V3``
    and the V4 equivalents. Anything else raises ``ValueError`` — we'd
    rather fail early than silently write the wrong schema.
    """

    if isinstance(value, SpecVersion):
        return value
    s = str(value).strip().lower().lstrip("v")
    if s in {"3", "3.0", "3.0.0"}:
        return SpecVersion.V3
    if s in {"4", "4.0", "4.0.0"}:
        return SpecVersion.V4
    raise ValueError(
        f"unsupported Pact spec version: {value!r} (allowed: V3, V4)",
    )


# ── Metadata ────────────────────────────────────────────────────────────


class Pacticipant(BaseModel):
    """Consumer or provider identity (same shape in V3 and V4)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str


class PactSpecification(BaseModel):
    """The ``pact_specification`` block inside ``metadata``."""

    model_config = ConfigDict(populate_by_name=True)

    version: str


class PluginEntry(BaseModel):
    """V4 ``plugins[]`` entry — recorded for round-trip fidelity only.

    Phase 1 does not execute plugin runtimes; the entry is stored in
    metadata so a future verifier can match what the consumer declared.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    version: str = ""
    configuration: Dict[str, Any] = Field(default_factory=dict)


class Metadata(BaseModel):
    """``metadata`` block — same key set in V3 and V4, but
    ``plugins`` is V4-only."""

    model_config = ConfigDict(populate_by_name=True)

    pact_specification: PactSpecification = Field(alias="pactSpecification")
    client: Dict[str, str] = Field(
        default_factory=lambda: {
            "name": "mockarty-py-sdk",
            "version": "0.3.0",
        },
    )
    # V4-only — pydantic will drop the field on V3 dumps via writer.
    plugins: Optional[List[PluginEntry]] = None


# ── Interaction parts ──────────────────────────────────────────────────


class RequestPart(BaseModel):
    """HTTP request inside an interaction.

    The ``matching_rules`` block is what tells the verifier how to
    compare the actual request against the expected one. In V3 it is a
    flat dict keyed by JSONPath expressions; in V4 it is a nested dict
    keyed by category (``body`` / ``header`` / ``query`` / ``path``).

    Headers / query are typed ``Any`` (not ``str``) on the in-memory
    model so that users can pass matcher sentinels — the writer unwraps
    them into concrete strings during serialisation.
    """

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    method: str = "GET"
    path: str = "/"
    query: Dict[str, List[Any]] = Field(default_factory=dict)
    headers: Dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    matching_rules: Dict[str, Any] = Field(
        default_factory=dict,
        alias="matchingRules",
    )
    generators: Dict[str, Any] = Field(default_factory=dict)


class ResponsePart(BaseModel):
    """HTTP response inside an interaction."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    status: int = 200
    headers: Dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    matching_rules: Dict[str, Any] = Field(
        default_factory=dict,
        alias="matchingRules",
    )
    generators: Dict[str, Any] = Field(default_factory=dict)


class ProviderState(BaseModel):
    """One element of V4 ``providerStates`` (or, when collapsed, the
    sole V3 ``providerState``)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class Interaction(BaseModel):
    """A single request/response pair inside the contract.

    Identical in V3 and V4 except that V4 has:

    * ``type`` discriminator (``Synchronous/HTTP`` in Phase 1);
    * ``providerStates`` (plural, list) instead of ``providerState``;
    * ``key`` — a stable per-interaction identifier;
    * ``pending`` flag, defaulting to ``False``.
    """

    model_config = ConfigDict(populate_by_name=True)

    description: str = ""
    provider_states: List[ProviderState] = Field(
        default_factory=list,
        alias="providerStates",
    )
    request: RequestPart = Field(default_factory=RequestPart)
    response: ResponsePart = Field(default_factory=ResponsePart)
    # V4-only:
    type: Optional[str] = None
    key: Optional[str] = None
    pending: Optional[bool] = None


# ── Top-level contract ─────────────────────────────────────────────────


class Pact(BaseModel):
    """The whole pact.json document."""

    model_config = ConfigDict(populate_by_name=True)

    consumer: Pacticipant
    provider: Pacticipant
    interactions: List[Interaction] = Field(default_factory=list)
    metadata: Metadata


# ── Helpers ────────────────────────────────────────────────────────────


def freeze_headers(headers: Optional[Mapping[str, str]]) -> Dict[str, str]:
    """Normalise a mapping of headers so the writer output is deterministic.

    Pact's JSON shape allows arbitrary case in keys, but for diffing it
    helps to canonicalise. We preserve the user's original casing but
    iterate in insertion order; this keeps the output stable across
    Python versions (≥3.7 dict ordering).
    """

    if not headers:
        return {}
    return {str(k): str(v) for k, v in headers.items()}
