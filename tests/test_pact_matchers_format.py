# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the format/scalar matcher catalogue added for server parity:
Null, NotNull, Include, ContentType, AtLeastOne, Date, Time, DateTime
(+Timestamp alias), UUID, Semver, IPv4.

Each test asserts both the emitted V3/V4 rule shape AND the live
``validate`` behaviour (accept valid, reject malformed) so the consumer
mock server enforces the same format the server-side engine does.
"""

from __future__ import annotations

import pytest

from mockarty.pact.matchers import (
    AtLeastOne,
    ContentType,
    Date,
    DateTime,
    IPv4,
    Include,
    NotNull,
    Null,
    Semver,
    Time,
    Timestamp,
    UUID,
)


@pytest.mark.parametrize(
    "matcher, good, bad",
    [
        (Date("2026-06-12"), "2026-06-12", "12/06/2026"),
        (Time("10:30:00"), "10:30:00", "10:30"),
        (DateTime("2026-06-12T10:30:00Z"), "2026-06-12T10:30:00Z", "yesterday"),
        (UUID("550e8400-e29b-41d4-a716-446655440000"), "550e8400-e29b-41d4-a716-446655440000", "not-a-uuid"),
        (Semver("1.2.3"), "1.2.3", "1.2"),
        (IPv4("192.168.0.1"), "192.168.0.1", "::1"),
        (Include("@"), "user@host", "userhost"),
        (ContentType("application/json"), "application/json; charset=utf-8", "text/plain"),
    ],
)
def test_format_matcher_validate(matcher, good, bad):
    assert matcher.validate(good) == []
    assert matcher.validate(bad) != []


def test_null_and_notnull():
    assert Null().validate(None) == []
    assert Null().validate(0) != []
    assert NotNull().validate("x") == []
    assert NotNull().validate(None) != []


def test_at_least_one():
    m = AtLeastOne({"id": 1})
    assert m.validate([{"id": 1}]) == []
    assert m.validate([]) != []
    assert m.validate("nope") != []


def test_date_regex_override():
    m = Date("31/12/2026", regex=r"^\d{2}/\d{2}/\d{4}$")
    assert m.validate("31/12/2026") == []
    assert m.validate("2026-12-31") != []
    assert m.v3_rule() == {"match": "date", "regex": r"^\d{2}/\d{2}/\d{4}$"}


def test_rule_shapes():
    assert UUID().v3_rule() == {"match": "uuid"}
    assert UUID().v4_rule() == {"matchers": [{"match": "uuid"}], "combine": "AND"}
    assert AtLeastOne().v4_rule() == {"matchers": [{"match": "atLeastOne"}], "combine": "AND"}
    assert ContentType("application/json").v3_rule() == {"match": "contentType", "value": "application/json"}
    assert Timestamp("2026-01-01T00:00:00Z")._match == "timestamp"  # type: ignore[attr-defined]
