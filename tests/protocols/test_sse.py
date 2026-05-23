"""Unit tests for mockarty.protocols.sse."""

from __future__ import annotations

import pytest

from mockarty.protocols.sse import _parse_sse_stream


def _iter(text: str):
    # httpx iter_lines yields lines without trailing newlines.
    return iter(text.split("\n"))


def test_parse_single_event_passes_data():
    events = list(_parse_sse_stream(_iter("data: hello\n\n")))
    assert len(events) == 1
    assert events[0].data == "hello"


def test_parse_multiple_events_dispatch_on_blank_line():
    text = "data: one\n\ndata: two\n\ndata: three\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert [e.data for e in events] == ["one", "two", "three"]


def test_parse_named_event_with_id():
    text = "event: orderCreated\nid: 42\ndata: payload\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].event == "orderCreated"
    assert events[0].id == "42"
    assert events[0].data == "payload"


def test_parse_multiline_data_concatenates_with_newline():
    text = "data: line1\ndata: line2\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].data == "line1\nline2"


def test_parse_comment_lines_skipped():
    text = ": keep-alive\ndata: hi\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].data == "hi"


def test_parse_retry_field_int():
    text = "retry: 5000\ndata: x\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].retry == 5000


def test_parse_retry_invalid_ignored():
    text = "retry: ten\ndata: x\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].retry is None


def test_parse_unknown_field_ignored():
    # Per spec, unknown field names are silently dropped.
    text = "weird: ignored\ndata: kept\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].data == "kept"


def test_parse_event_without_data_is_not_dispatched():
    # Per spec, blank-line dispatch fires only when data is non-empty.
    text = "event: heartbeat\n\ndata: real\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert [e.data for e in events] == ["real"]


def test_parse_field_value_space_stripped_once():
    # "data: hello" → "hello" (single space after colon is stripped).
    text = "data: hello\n\n"
    events = list(_parse_sse_stream(_iter(text)))
    assert events[0].data == "hello"
    # "data:no-space" → "no-space" (no space to strip).
    text2 = "data:no-space\n\n"
    events2 = list(_parse_sse_stream(_iter(text2)))
    assert events2[0].data == "no-space"


def test_sse_client_empty_url_rejected():
    from mockarty.protocols.sse import SseClient
    with pytest.raises(ValueError):
        SseClient("")


def test_sse_client_collect_zero_max_rejected():
    from mockarty.protocols.sse import SseClient
    cli = SseClient("http://x")
    with pytest.raises(ValueError):
        cli.collect(max_events=0)
    cli.close()
