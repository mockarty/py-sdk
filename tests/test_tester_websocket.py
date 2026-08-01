# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Unit tests for the raw WebSocket facet.

These verify the facet LOGIC (send / collect window / assertions / extract /
url-rewrite) against an injected fake WebSocket client, so they run without the
optional ``websockets`` package. A live end-to-end test against a real WS
server is covered by the protocol-level suite (which importorskips websockets).
"""

from __future__ import annotations

import pytest

from mockarty.tester.tester import Tester


class _FakeWS:
    """Stand-in for protocols.websocket.WebSocketClient: records sends and
    replays a fixed inbox, then raises on the next recv (window over)."""

    last_instance: "_FakeWS | None" = None

    def __init__(self, url, headers=None, open_timeout=10.0, **_kw):
        self.url = url
        self.headers = dict(headers or {})
        self.open_timeout = open_timeout
        self.sent: list = []
        self._inbox = ['{"echo":1}', '{"echo":2}']
        self.closed = False
        _FakeWS.last_instance = self

    def send(self, payload):
        self.sent.append(payload)

    def recv(self, *, timeout=None):
        if self._inbox:
            return self._inbox.pop(0)
        raise TimeoutError("no more frames within window")

    def close(self):
        self.closed = True


@pytest.fixture
def fake_ws(monkeypatch):
    monkeypatch.setattr("mockarty.tester.websocket.WebSocketClient", _FakeWS)
    return _FakeWS


def test_ws_connect_send_receive_extract(fake_ws):
    t = Tester(base_url="http://127.0.0.1:9999")
    (t.websocket("/ws").connect()
        .listen(1.0)
        .send("hello")
        .send_json({"k": "v"})
        .expect_connected()
        .expect_received_count(2)
        .expect_received_at_least(2)
        .expect_message_contains(0, "echo")
        .expect_json_path(0, "$.echo", 1)
        .expect_json_path(1, "$.echo", 2)
        .extract(1, "$.echo", "second")
        .done())
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["second"] == "2"
    # http base auto-rewrites to ws://, relative path joined.
    assert _FakeWS.last_instance.url == "ws://127.0.0.1:9999/ws"
    # both outbound frames forwarded (text + json-serialised dict).
    assert _FakeWS.last_instance.sent[0] == "hello"
    assert _FakeWS.last_instance.closed is True


def test_ws_wrong_count_fails(fake_ws):
    t = Tester(base_url="http://x")
    (t.websocket("/ws").connect().listen(1.0).expect_received_count(5).done())
    t.finish()
    assert not t.ok()


def test_ws_absolute_url_passthrough(fake_ws):
    t = Tester()
    (t.websocket("wss://example.test/stream").connect().listen(1.0)
        .expect_received_at_least(1).done())
    t.finish()
    assert t.ok(), t.errors()
    assert _FakeWS.last_instance.url == "wss://example.test/stream"
