# Copyright (c) 2026 Mockarty. All rights reserved.

"""Protocol catalogue + per-protocol endpoint descriptors.

A target picks exactly one protocol via one of the
``Target.<protocol>_endpoint(...)`` methods. Each helper records a
:class:`Endpoint` descriptor under the target's protocol slot; the
transpiler then maps the descriptor onto the right server-side fields
(e.g. ``targetBaseUrl`` for HTTP, ``options.grpcAddress`` for gRPC,
``options.graphqlEndpoint`` for GraphQL, etc.).

Each protocol corresponds to a server-side fuzzer module — the SDK
stays a thin descriptor layer and never tries to talk the protocol
itself.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class Protocol(str, Enum):
    """Wire-protocol enum. Stored on the Target so the transpiler can
    pick the right options block.
    """

    HTTP = "http"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    SOAP = "soap"
    WEBSOCKET = "websocket"


class Endpoint:
    """Protocol-tagged endpoint descriptor.

    The fields are deliberately permissive — different protocols use
    different subsets. Validation lives in :mod:`mockarty.fuzz.transpile`
    so we can produce a clean error before hitting the network.
    """

    __slots__ = (
        "protocol",
        "method",
        "url",
        "path",
        "service",
        "rpc_method",
        "use_tls",
        "topic",
        "queue",
        "exchange",
        "soap_action",
        "ws_subprotocol",
        "extras",
    )

    def __init__(
        self,
        protocol: Protocol,
        *,
        method: str = "",
        url: str = "",
        path: str = "",
        service: str = "",
        rpc_method: str = "",
        use_tls: bool = False,
        topic: str = "",
        queue: str = "",
        exchange: str = "",
        soap_action: str = "",
        ws_subprotocol: str = "",
        extras: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.protocol = protocol
        self.method = method
        self.url = url
        self.path = path
        self.service = service
        self.rpc_method = rpc_method
        self.use_tls = use_tls
        self.topic = topic
        self.queue = queue
        self.exchange = exchange
        self.soap_action = soap_action
        self.ws_subprotocol = ws_subprotocol
        self.extras = dict(extras or {})

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for the SDK metadata block. Empty fields dropped."""

        d: Dict[str, Any] = {"protocol": self.protocol.value}
        for k in (
            "method",
            "url",
            "path",
            "service",
            "rpc_method",
            "topic",
            "queue",
            "exchange",
            "soap_action",
            "ws_subprotocol",
        ):
            v = getattr(self, k)
            if v:
                d[k] = v
        if self.use_tls:
            d["use_tls"] = True
        if self.extras:
            d["extras"] = dict(self.extras)
        return d

    def __repr__(self) -> str:
        return f"Endpoint({self.to_dict()!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Endpoint):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.to_dict().items(), key=lambda kv: kv[0])))
