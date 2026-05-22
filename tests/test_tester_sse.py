# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for the Python port of the SSE Tester facet."""

from __future__ import annotations

import respx
import httpx

from mockarty.tester import Tester


def _sse_response(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, headers={"Content-Type": "text/event-stream"}, content=body)


@respx.mock
def test_sse_parse_basic():
    body = (
        "event: updated\ndata: {\"id\":42}\nid: e1\n\n"
        "event: created\ndata: {\"id\":43}\n\n"
    )
    respx.get("http://api.test/stream").mock(return_value=_sse_response(body))

    t = Tester(base_url="http://api.test")
    (t.sse("/stream").subscribe()
        .listen(2.0)
        .expect_exact_events(2)
        .expect_event("updated")
        .expect_event("created")
        .expect_json_path("updated", "$.id", 42)
        .extract("created", "$.id", "created_id"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["created_id"] == "43"


@respx.mock
def test_sse_multiline_data():
    respx.get("http://api.test/").mock(
        return_value=_sse_response("event: log\ndata: line1\ndata: line2\n\n"),
    )
    t = Tester(base_url="http://api.test")
    (t.sse("/").subscribe()
        .listen(1.0)
        .expect_event("log")
        .expect_event_data("log", "line1\nline2"))
    t.finish()
    assert t.ok(), t.errors()


@respx.mock
def test_sse_default_event_name():
    respx.get("http://api.test/").mock(
        return_value=_sse_response("data: {\"x\":1}\n\n"),
    )
    t = Tester(base_url="http://api.test")
    (t.sse("/").subscribe()
        .listen(1.0)
        .expect_event("message")
        .expect_json_path("message", "$.x", 1))
    t.finish()
    assert t.ok(), t.errors()


@respx.mock
def test_sse_comments_ignored():
    respx.get("http://api.test/").mock(
        return_value=_sse_response(": heartbeat\n\nevent: tick\ndata: 1\n\n"),
    )
    t = Tester(base_url="http://api.test")
    (t.sse("/").subscribe()
        .listen(1.0)
        .expect_exact_events(1)
        .expect_event("tick"))
    t.finish()
    assert t.ok(), t.errors()


@respx.mock
def test_sse_server_error():
    respx.get("http://api.test/").mock(
        return_value=httpx.Response(500, content=""),
    )
    t = Tester(base_url="http://api.test")
    t.sse("/").subscribe().listen(0.5)
    t.finish()
    assert not t.ok()
