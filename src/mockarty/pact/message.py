# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Message-pact DSL — async/messaging contracts.

Consumer-side declaration of Kafka events, AMQP messages, SNS
notifications, NATS subjects, etc. Mirrors the V4
``Asynchronous/Messages`` interaction type from the pact-foundation
spec so produced files verify against any compatible verifier
(pact-jvm, pact-python, our own ``Verifier``).

Consumer flow::

    mp = (
        MessagePact("OrderConsumer", "OrderEvents")
        .given("user 42 exists")
        .expects_to_receive("an order-created event")
        .with_metadata({"topic": "orders"})
        .with_content({
            "orderId": Like(42),
            "status":  Regex(r"^(open|closed)$", "open"),
        })
    )

    # Verify the consumer's real handler can decode the example bytes.
    mp.verify(handle_order_event)
    mp.write_file("./pacts")

Provider flow uses ``Verifier.with_message_producer`` to register a
per-description callback that returns the actual bytes the provider
would publish, then ``verifier.verify_message_pact_bytes(raw)`` matches
them against the recorded shape.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from mockarty.pact.matchers import Matcher


MESSAGE_INTERACTION_TYPE = "Asynchronous/Messages"
SYNC_MESSAGE_INTERACTION_TYPE = "Synchronous/Messages"

MessageHandler = Callable[[bytes, Mapping[str, str]], None]
"""Consumer handler: raises if it cannot decode/process the bytes."""

MessageProducer = Callable[[str, list[dict[str, Any]]], tuple[bytes, Mapping[str, str]]]
"""Provider producer: ``(description, states) -> (bytes, metadata)``."""


@dataclasses.dataclass
class MessageReply:
    """One expected reply in a synchronous (request/response) message.

    Matchers inside ``content`` are extracted to ``matchingRules`` exactly like
    a request body.
    """

    content: Any = None
    metadata: dict[str, str] = dataclasses.field(default_factory=dict)
    content_type: str = ""


@dataclasses.dataclass
class Message:
    description: str = ""
    states: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    metadata: dict[str, str] = dataclasses.field(default_factory=dict)
    content: Any = None
    content_type: str = ""
    # Non-empty => SYNCHRONOUS message: ``content`` is the request and each
    # entry here is an expected reply.
    responses: list["MessageReply"] = dataclasses.field(default_factory=list)


class MessagePact:
    """Consumer-side builder for message contracts."""

    def __init__(self, consumer: str, provider: str, *, spec: str = "4.0") -> None:
        if not consumer.strip() or not provider.strip():
            raise ValueError("consumer and provider names are required")
        self.consumer = consumer
        self.provider = provider
        self.spec = spec
        self.messages: list[Message] = []
        # last-message cursor for fluent chain
        self._cursor: Message | None = None

    # ------------------------------------------------------------------
    # fluent DSL
    # ------------------------------------------------------------------

    def given(self, state: str, params: Mapping[str, Any] | None = None) -> MessagePact:
        msg = Message(states=[{"name": state, "params": dict(params or {})}])
        self.messages.append(msg)
        self._cursor = msg
        return self

    def expects_to_receive(self, description: str) -> MessagePact:
        self._require_cursor().description = description
        return self

    def with_metadata(self, meta: Mapping[str, str]) -> MessagePact:
        self._require_cursor().metadata.update(
            {str(k): str(v) for k, v in meta.items()}
        )
        return self

    def with_content(self, body: Any) -> MessagePact:
        c = self._require_cursor()
        c.content = body
        if not c.content_type:
            c.content_type = "application/json"
        return self

    def with_content_type(self, ct: str) -> MessagePact:
        self._require_cursor().content_type = ct
        return self

    def expects_response(self, body: Any) -> MessagePact:
        """Declare an expected reply, turning this into a SYNCHRONOUS message:
        ``with_content`` becomes the request the consumer sends and each
        ``expects_response`` adds one acceptable reply. Call more than once to
        allow several acceptable replies."""
        self._require_cursor().responses.append(
            MessageReply(content=body, content_type="application/json")
        )
        return self

    def with_response_metadata(self, meta: Mapping[str, str]) -> MessagePact:
        """Attach metadata to the most recently declared response."""
        c = self._require_cursor()
        if c.responses:
            c.responses[-1].metadata.update(dict(meta))
        return self

    def _require_cursor(self) -> Message:
        if self._cursor is None:
            raise RuntimeError(
                "call .given(...) first to start a message before "
                ".expects_to_receive() / .with_content() / etc."
            )
        return self._cursor

    # ------------------------------------------------------------------
    # output
    # ------------------------------------------------------------------

    def to_json(self) -> bytes:
        doc: dict[str, Any] = {
            "consumer": {"name": self.consumer},
            "provider": {"name": self.provider},
            "metadata": {
                "pactSpecification": {"version": self.spec},
                "mockarty": {"role": "messageConsumer"},
            },
        }
        if self.spec.startswith("4"):
            doc["interactions"] = [_serialise_v4(m) for m in self.messages]
        else:
            doc["messages"] = [_serialise_v3(m) for m in self.messages]
        return json.dumps(doc, indent=2).encode("utf-8")

    def write_file(self, directory: str | os.PathLike[str]) -> str:
        Path(directory).mkdir(parents=True, exist_ok=True)
        name = (
            _safe(self.consumer.lower()) + "-" + _safe(self.provider.lower()) + ".json"
        )
        path = Path(directory) / name
        path.write_bytes(self.to_json())
        return str(path)

    # ------------------------------------------------------------------
    # consumer verification
    # ------------------------------------------------------------------

    def verify(self, handler: MessageHandler) -> None:
        """Invoke ``handler`` once per queued message with the
        example bytes.

        Short-circuit semantics: the FIRST handler exception aborts
        the loop and is re-raised as ``RuntimeError`` (consistent with
        the Go + Java SDKs). To exercise every message regardless of
        prior failures, wrap each call yourself or build a custom
        handler that collects + swallows its own exceptions.
        """
        if handler is None:
            raise ValueError("handler is required")
        for m in self.messages:
            resolved = _resolve(m.content)
            raw = _encode_body(resolved, m.content_type)
            try:
                handler(raw, m.metadata)
            except Exception as e:  # noqa: BLE001 — surface to caller
                raise RuntimeError(f"consumer rejected {m.description!r}: {e}") from e


# ----------------------------------------------------------------------
# provider-side verification — extends the Verifier
# ----------------------------------------------------------------------


def parse_message_pact_doc(raw: bytes) -> list[Message]:
    """Parse a message pact (V3 or V4) into Message objects."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"message pact is not valid JSON: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError("pact root must be a JSON object")
    out: list[Message] = []
    for ix in doc.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        if ix.get("type") != MESSAGE_INTERACTION_TYPE:
            continue
        out.append(_decode_v4(ix))
    for mr in doc.get("messages") or []:
        if isinstance(mr, dict):
            out.append(_decode_v3(mr))
    return out


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe(s: str) -> str:
    return _SAFE_NAME_RE.sub("_", s) or "pact"


def _resolve(v: Any) -> Any:
    if isinstance(v, Matcher):
        return _resolve(v.example)
    if isinstance(v, dict):
        return {k: _resolve(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_resolve(x) for x in v]
    return v


def _encode_body(body: Any, content_type: str) -> bytes:
    if body is None:
        return b""
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    if "json" in content_type.lower() or not content_type:
        return json.dumps(body).encode("utf-8")
    # Last-resort JSON encode for non-JSON content types — keeps the
    # consumer-side verify path useful even with unusual content types.
    return json.dumps(body).encode("utf-8")


def _serialise_v4(m: Message) -> dict[str, Any]:
    sync = bool(m.responses)
    ix: dict[str, Any] = {
        "type": SYNC_MESSAGE_INTERACTION_TYPE if sync else MESSAGE_INTERACTION_TYPE,
        "description": m.description,
    }
    if m.states:
        ix["providerStates"] = [
            {k: v for k, v in s.items() if v not in (None, {}, "")} for s in m.states
        ]
    rules: dict[str, dict[str, Any]] = {}
    # Root the body at "$" (not "$.body"): the server re-roots message body
    # rules under the "body" category, so "$.id" becomes "$.body.id". Using
    # "$.body" here would double it to "$.body.body.id".
    content_value = _walk_and_extract(m.content, "$", rules)
    ix["contents"] = {
        "contentType": m.content_type or "application/json",
        "content": content_value,
    }
    if rules:
        ix["matchingRules"] = {"body": rules}
    if m.metadata:
        ix["metadata"] = m.metadata
    if sync:
        # Synchronous/Messages: contents above is the request; response[] holds
        # the expected replies, each with its own contents + matchingRules.
        responses: list[dict[str, Any]] = []
        for r in m.responses:
            r_rules: dict[str, dict[str, Any]] = {}
            entry: dict[str, Any] = {
                "contents": {
                    "contentType": r.content_type or "application/json",
                    "content": _walk_and_extract(r.content, "$", r_rules),
                }
            }
            if r_rules:
                entry["matchingRules"] = {"body": r_rules}
            if r.metadata:
                entry["metadata"] = r.metadata
            responses.append(entry)
        ix["response"] = responses
    return ix


def _serialise_v3(m: Message) -> dict[str, Any]:
    mr: dict[str, Any] = {"description": m.description}
    if len(m.states) == 1:
        mr["providerState"] = m.states[0].get("name", "")
    elif len(m.states) > 1:
        mr["providerStates"] = [{"name": s.get("name", "")} for s in m.states]
    rules: dict[str, dict[str, Any]] = {}
    mr["contents"] = _walk_and_extract(m.content, "$.body", rules)
    if rules:
        mr["matchingRules"] = rules
    if m.metadata:
        mr["metaData"] = m.metadata
    return mr


def _walk_and_extract(body: Any, path: str, rules: dict[str, dict[str, Any]]) -> Any:
    """Strip matchers out of the body into a `path -> rule` map,
    returning the body with matchers replaced by their examples."""
    if isinstance(body, Matcher):
        # Messages are written V4, so use the matcher's V4 rule entry
        # ({"matchers": [...], "combine": "AND"}). The previous code looked for
        # a non-existent `.spec` attribute, so message-content matchers NEVER
        # emitted matchingRules — they were silently dropped to plain examples.
        rules[path] = body.v4_rule()
        return _walk_and_extract(body.example, path, rules)
    if isinstance(body, dict):
        return {k: _walk_and_extract(v, f"{path}.{k}", rules) for k, v in body.items()}
    if isinstance(body, list):
        return [_walk_and_extract(v, f"{path}[*]", rules) for v in body]
    return body


def _decode_v4(ix: dict[str, Any]) -> Message:
    m = Message()
    m.description = str(ix.get("description", ""))
    m.states = _decode_states(ix)
    contents = ix.get("contents") or {}
    if isinstance(contents, dict):
        m.content_type = str(contents.get("contentType", ""))
        m.content = contents.get("content")
    meta = ix.get("metadata") or {}
    if isinstance(meta, dict):
        m.metadata = {str(k): str(v) for k, v in meta.items() if isinstance(v, str)}
    return m


def _decode_v3(mr: dict[str, Any]) -> Message:
    m = Message()
    m.description = str(mr.get("description", ""))
    m.states = _decode_states(mr)
    m.content = mr.get("contents")
    meta = mr.get("metaData") or mr.get("metadata") or {}
    if isinstance(meta, dict):
        m.metadata = {str(k): str(v) for k, v in meta.items() if isinstance(v, str)}
    return m


def _decode_states(ix: dict[str, Any]) -> list[dict[str, Any]]:
    arr = ix.get("providerStates")
    if isinstance(arr, list):
        return [s for s in arr if isinstance(s, dict)]
    s = ix.get("providerState")
    if isinstance(s, str) and s:
        return [{"name": s, "params": {}}]
    return []


__all__ = [
    "MESSAGE_INTERACTION_TYPE",
    "SYNC_MESSAGE_INTERACTION_TYPE",
    "Message",
    "MessageHandler",
    "MessagePact",
    "MessageProducer",
    "MessageReply",
    "parse_message_pact_doc",
]
