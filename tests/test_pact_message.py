# Copyright (c) 2026 Mockarty. All rights reserved.

"""Unit tests for mockarty.pact.message — message-pact DSL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mockarty.pact.matchers import Like, Regex
from mockarty.pact.message import (
    MESSAGE_INTERACTION_TYPE,
    MessagePact,
    parse_message_pact_doc,
)
from mockarty.pact.verifier import Verifier


def test_message_pact_to_json_v4_shape():
    mp = (
        MessagePact("OrderConsumer", "OrderEvents")
        .given("user 42 exists")
        .expects_to_receive("an order-created event")
        .with_metadata({"topic": "orders"})
        .with_content({"orderId": 42, "status": "open"})
    )
    raw = mp.to_json()
    doc = json.loads(raw)
    assert doc["consumer"]["name"] == "OrderConsumer"
    assert len(doc["interactions"]) == 1
    ix = doc["interactions"][0]
    assert ix["type"] == MESSAGE_INTERACTION_TYPE
    assert ix["description"] == "an order-created event"
    assert ix["contents"]["contentType"] == "application/json"
    assert ix["metadata"] == {"topic": "orders"}


def test_message_pact_requires_consumer_provider():
    with pytest.raises(ValueError):
        MessagePact("", "p")
    with pytest.raises(ValueError):
        MessagePact("c", "")


def test_message_pact_v3_shape():
    mp = (
        MessagePact("c", "p", spec="3.0.0")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"k": "v"})
    )
    doc = json.loads(mp.to_json())
    assert "messages" in doc
    assert "interactions" not in doc


def test_message_pact_requires_given_cursor():
    mp = MessagePact("c", "p")
    with pytest.raises(RuntimeError, match="given"):
        mp.expects_to_receive("oops")
    with pytest.raises(RuntimeError, match="given"):
        mp.with_content({})


def test_verify_happy_path():
    mp = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 7})
    )
    seen: list[bytes] = []

    def handler(content: bytes, meta):
        seen.append(content)

    mp.verify(handler)
    assert seen
    assert b'"id"' in seen[0]


def test_verify_consumer_rejects():
    mp = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 7})
    )

    def handler(content: bytes, meta):
        raise ValueError("cannot parse")

    with pytest.raises(RuntimeError, match="cannot parse"):
        mp.verify(handler)


def test_verify_nil_handler():
    mp = MessagePact("c", "p")
    with pytest.raises(ValueError):
        mp.verify(None)  # type: ignore[arg-type]


def test_write_file(tmp_path: Path):
    mp = (
        MessagePact("OrderConsumer", "OrderEvents")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 1})
    )
    path = mp.write_file(tmp_path)
    assert Path(path).parent == tmp_path
    body = Path(path).read_bytes()
    assert MESSAGE_INTERACTION_TYPE.encode() in body


def test_matchers_resolved_in_consumer_verify():
    mp = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"orderId": Like(42), "status": Regex(r"^(open|closed)$", "open")})
    )
    captured: list[bytes] = []
    mp.verify(lambda content, _meta: captured.append(content))
    body = json.loads(captured[0])
    # Matchers must be replaced by their example values in the bytes
    # the consumer's handler sees.
    assert body == {"orderId": 42, "status": "open"}


def test_parse_v4_doc():
    mp = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_metadata({"k": "v"})
        .with_content({"id": 1})
    )
    msgs = parse_message_pact_doc(mp.to_json())
    assert len(msgs) == 1
    assert msgs[0].description == "msg"
    assert msgs[0].metadata == {"k": "v"}
    assert msgs[0].states[0]["name"] == "st"


def test_parse_v3_doc():
    mp = (
        MessagePact("c", "p", spec="3.0.0")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 1})
    )
    msgs = parse_message_pact_doc(mp.to_json())
    assert len(msgs) == 1
    assert msgs[0].description == "msg"


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_message_pact_doc(b"<<not json>>")


def test_verifier_message_happy_path():
    raw = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 7})
        .to_json()
    )
    v = Verifier(provider_url="http://x").with_message_producer(
        "msg", lambda desc, states: (b'{"id": 7}', {})
    )
    res = v.verify_message_pact_bytes(raw)
    assert res.ok


def test_verifier_message_content_mismatch():
    raw = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 7})
        .to_json()
    )
    v = Verifier(provider_url="http://x").with_message_producer(
        "msg", lambda desc, states: (b'{"id": 999}', {})
    )
    res = v.verify_message_pact_bytes(raw)
    assert not res.ok
    assert res.interactions[0].mismatches


def test_verifier_message_no_producer():
    raw = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 7})
        .to_json()
    )
    res = Verifier(provider_url="http://x").verify_message_pact_bytes(raw)
    assert not res.ok
    assert "no MessageProducer" in res.interactions[0].error


def test_verifier_message_producer_errors():
    raw = (
        MessagePact("c", "p")
        .given("st")
        .expects_to_receive("msg")
        .with_content({"id": 7})
        .to_json()
    )

    def bad(desc, states):
        raise RuntimeError("kafka down")

    v = Verifier(provider_url="http://x").with_message_producer("msg", bad)
    res = v.verify_message_pact_bytes(raw)
    assert "kafka down" in res.interactions[0].error
