# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for the Python Tester Socket.IO facet.

Runs an in-process minimal Socket.IO v4 server (Engine.IO v4 over the
WebSocket transport) so the facet is exercised end-to-end without the
testbackend binary. Requires the ``websockets`` package (SDK
``protocols`` extra).
"""

from __future__ import annotations

import json
import threading

import pytest

websockets_sync = pytest.importorskip("websockets.sync.server")

from mockarty.tester import Tester  # noqa: E402


def _handle(conn):
    # Engine.IO open handshake.
    conn.send('0{"sid":"abc","upgrades":[],"pingInterval":25000,"pingTimeout":20000}')
    for frame in conn:
        text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
        if not text or text[0] != "4":
            continue
        sio = text[1:]
        if sio.startswith("0"):
            tail = sio[1:]
            ns = ""
            if tail.startswith("/"):
                comma = tail.find(",")
                if comma >= 0:
                    ns = tail[:comma]
            if ns:
                conn.send(f'40{ns},{{"sid":"s1"}}')
            else:
                conn.send('40{"sid":"s1"}')
        elif sio.startswith("2"):
            body = sio[1:]
            ns = ""
            if body.startswith("/"):
                comma = body.find(",")
                if comma >= 0:
                    ns = body[:comma]
                    body = body[comma + 1 :]
            try:
                arr = json.loads(body)
            except json.JSONDecodeError:
                continue
            if not arr:
                continue
            name = arr[0]
            prefix = f"42{ns}," if ns else "42"
            if name == "echo":
                conn.send(prefix + json.dumps(["echo", arr[1] if len(arr) > 1 else None]))
            elif name == "greet":
                who = arr[1] if len(arr) > 1 else ""
                conn.send(prefix + json.dumps(["greeting", {"msg": f"hello {who}"}]))


class _Server:
    def __init__(self):
        self._srv = websockets_sync.serve(_handle, "127.0.0.1", 0)
        self.port = self._srv.socket.getsockname()[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def close(self):
        self._srv.shutdown()


@pytest.fixture
def sio_server():
    srv = _Server()
    yield srv
    srv.close()


def test_socketio_emit_echo(sio_server):
    t = Tester()
    (t.socketio(sio_server.url).connect()
        .emit("echo", {"n": 1})
        .emit("greet", "World")
        .collect(2.0)
        .expect_connected()
        .expect_event("echo")
        .expect_event("greeting")
        .expect_event_arg_contains("echo", '"n": 1')
        .expect_event_json_path("greeting", "$.msg", "hello World")
        .extract("greeting", "$.msg", "greet_msg"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["greet_msg"] == "hello World"


def test_socketio_namespace(sio_server):
    t = Tester()
    (t.socketio(sio_server.url).connect()
        .namespace("/admin")
        .emit("echo", "ns-payload")
        .collect(2.0)
        .expect_connected()
        .expect_event("echo")
        .expect_event_arg_contains("echo", "ns-payload"))
    t.finish()
    assert t.ok(), t.errors()


@pytest.mark.parametrize(
    "scenario,want_ok",
    [
        ("dial_failure", False),
        ("missing_event", False),
        ("wrong_jsonpath", False),
    ],
)
def test_socketio_negative(sio_server, scenario, want_ok):
    t = Tester()
    if scenario == "dial_failure":
        (t.socketio("ws://127.0.0.1:1/socket.io/")
            .connect().connect_timeout(0.5).collect(0.5).expect_connected())
    elif scenario == "missing_event":
        (t.socketio(sio_server.url).connect()
            .emit("echo", "x").collect(1.0).expect_event("never-emitted"))
    elif scenario == "wrong_jsonpath":
        (t.socketio(sio_server.url).connect()
            .emit("greet", "Bob").collect(1.0)
            .expect_event_json_path("greeting", "$.msg", "hello Alice"))
    t.finish()
    assert t.ok() == want_ok, t.errors()
