# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Pact V3 + V4 consumer DSL for Mockarty SDK.

This package is a pure-Python implementation — **no Rust FFI**, no
``libpact_ffi``, no compiled dependencies. It generates pact.json
artefacts that any Pact-compatible verifier (Mockarty's own
``internal/contract/pact_matcher.go``, the pact-go verifier, the
official ``pact-broker`` CLI, etc.) can consume.

See :doc:`./README` for the design rationale and Phase 2 roadmap.

Quick start::

    from mockarty.pact import Consumer, Like

    pact = (
        Consumer("OrderService")
        .with_provider("PaymentService")
        .with_spec_version("V4")
        .with_output_dir("./pacts")
    )
    pact.given("payment service is up") \\
        .upon_receiving("a charge request") \\
        .with_request("POST", "/charge", body={"amount": Like(100)}) \\
        .will_respond_with(200, body={"id": Like("abc")})

    with pact.start() as server:
        # call server.url from your real HTTP client
        ...
"""

from __future__ import annotations

from mockarty.pact.broker import (
    BrokerClient,
    BrokerError,
    CanIDeployResult,
    PactNotFoundError,
)
from mockarty.pact.consumer import Consumer
from mockarty.pact.message import (
    MESSAGE_INTERACTION_TYPE,
    Message,
    MessagePact,
)
from mockarty.pact.verifier import (
    InteractionResult,
    VerificationResult,
    Verifier,
)
from mockarty.pact.verifier import (
    Mismatch as VerifierMismatch,
)  # avoid shadow of matchers.Mismatch
from mockarty.pact.interaction import InteractionBuilder
from mockarty.pact.matchers import (
    ArrayContains,
    AtLeastOne,
    Boolean,
    ContentType,
    Date,
    DateTime,
    Decimal,
    EachKey,
    EachKeyLike,
    EachLike,
    EachValue,
    Equality,
    Include,
    Integer,
    IPv4,
    JSONPath,
    Like,
    MatchType,
    Matcher,
    MaxType,
    MinMaxType,
    MinType,
    Mismatch,
    NotNull,
    Null,
    Regex,
    Semver,
    Term,
    Time,
    Timestamp,
    UUID,
    XMLPath,
)
from mockarty.pact.mock_server import MockServer, PactMismatchError
from mockarty.pact.plugins import (
    GRPCPlugin,
    Plugin,
    PluginAlreadyRegistered,
    ProtobufPlugin,
)
from mockarty.pact.types import (
    Interaction,
    Metadata,
    Pact,
    Pacticipant,
    PactSpecification,
    PluginEntry,
    ProviderState,
    RequestPart,
    ResponsePart,
    SpecVersion,
)
from mockarty.pact.writer import parse, render, write

__all__ = [
    # Broker
    "BrokerClient",
    "BrokerError",
    "CanIDeployResult",
    "PactNotFoundError",
    # Verifier
    "InteractionResult",
    "VerifierMismatch",
    "VerificationResult",
    "Verifier",
    # Message pact
    "MESSAGE_INTERACTION_TYPE",
    "Message",
    "MessagePact",
    # Top-level DSL
    "Consumer",
    "InteractionBuilder",
    "MockServer",
    "PactMismatchError",
    # Matchers
    "ArrayContains",
    "AtLeastOne",
    "Boolean",
    "ContentType",
    "Date",
    "DateTime",
    "Decimal",
    "EachKey",
    "EachKeyLike",
    "EachLike",
    "EachValue",
    "Equality",
    "IPv4",
    "Include",
    "Integer",
    "JSONPath",
    "Like",
    "MatchType",
    "Matcher",
    "MaxType",
    "MinMaxType",
    "MinType",
    "Mismatch",
    "NotNull",
    "Null",
    "Regex",
    "Semver",
    "Term",
    "Time",
    "Timestamp",
    "UUID",
    "XMLPath",
    # Plugins
    "GRPCPlugin",
    "Plugin",
    "PluginAlreadyRegistered",
    "ProtobufPlugin",
    # Models
    "Interaction",
    "Metadata",
    "Pact",
    "Pacticipant",
    "PactSpecification",
    "PluginEntry",
    "ProviderState",
    "RequestPart",
    "ResponsePart",
    "SpecVersion",
    # Writer / parser
    "parse",
    "render",
    "write",
]
