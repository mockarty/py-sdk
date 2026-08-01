# Copyright (c) 2026 Mockarty. All rights reserved.

"""Synchronous (request/response) message-pact tests — Pact V4
Synchronous/Messages. Async messages already covered in test_pact_message.py."""

from __future__ import annotations

import json

from mockarty.pact.matchers import Integer, Like
from mockarty.pact.message import MessagePact


def test_sync_message_shape():
    mp = MessagePact("rpc-consumer", "rpc-provider")
    (
        mp.given("a user exists")
        .expects_to_receive("a get-user request/response")
        .with_content({"op": "getUser", "id": Integer(7)})
        .expects_response({"id": Integer(7), "name": Like("Alice")})
        .with_response_metadata({"status": "ok"})
    )
    doc = json.loads(mp.to_json())
    ix = doc["interactions"][0]
    assert ix["type"] == "Synchronous/Messages"
    assert "contents" in ix  # the request
    resp = ix["response"]
    assert isinstance(resp, list) and len(resp) == 1
    assert "contents" in resp[0]
    assert resp[0]["metadata"] == {"status": "ok"}
    assert "matchingRules" in resp[0]  # from Integer/Like in the reply


def test_async_message_unchanged():
    mp = MessagePact("c", "p")
    mp.given("s").expects_to_receive("evt").with_content({"a": 1})
    doc = json.loads(mp.to_json())
    ix = doc["interactions"][0]
    assert ix["type"] == "Asynchronous/Messages"
    assert "response" not in ix
