# Copyright (c) 2026 Mockarty. All rights reserved.

"""Assertion catalogue tests."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from mockarty.fuzz import (
    AssertNoCrash,
    AssertNoErrorInBody,
    AssertResponseTimeUnder,
    AssertStatus,
    assertion,
)


def test_assert_status_range():
    a = AssertStatus(range(200, 300))
    d = a.to_dict()
    assert d == {"kind": "status", "low": 200, "high": 299}


def test_assert_status_single_int():
    a = AssertStatus(204)
    assert a.to_dict() == {"kind": "status", "codes": [204]}


def test_assert_status_explicit_codes_dedup_and_sort():
    a = AssertStatus([200, 204, 200, 201])
    assert a.to_dict() == {"kind": "status", "codes": [200, 201, 204]}


def test_assert_status_rejects_empty_range():
    with pytest.raises(ValueError):
        AssertStatus(range(0, 0))


def test_assert_status_rejects_strided_range():
    with pytest.raises(ValueError):
        AssertStatus(range(200, 300, 2))


def test_assert_status_rejects_empty_codes():
    with pytest.raises(ValueError):
        AssertStatus([])


def test_assert_no_crash_strict_flag():
    a = AssertNoCrash()
    assert a.to_dict() == {"kind": "no_crash", "strict": False}
    a2 = AssertNoCrash(strict=True)
    assert a2.to_dict()["strict"] is True


def test_assert_response_time_under_accepts_timedelta_or_seconds():
    a = AssertResponseTimeUnder(timedelta(milliseconds=250))
    assert a.to_dict() == {"kind": "response_time_under", "ms": 250}

    a2 = AssertResponseTimeUnder(0.5)
    assert a2.to_dict()["ms"] == 500


def test_assert_response_time_rejects_non_positive():
    with pytest.raises(ValueError):
        AssertResponseTimeUnder(0)
    with pytest.raises(ValueError):
        AssertResponseTimeUnder(timedelta(seconds=-1))


def test_assert_no_error_in_body_compiles_pattern():
    a = AssertNoErrorInBody(r"panic|exception", flags=re.IGNORECASE)
    d = a.to_dict()
    assert d["kind"] == "no_error_in_body"
    assert d["pattern"] == r"panic|exception"
    assert d["flags"] == re.IGNORECASE


def test_assert_no_error_in_body_accepts_compiled_pattern():
    p = re.compile(r"stack", re.MULTILINE)
    a = AssertNoErrorInBody(p)
    assert a.to_dict()["pattern"] == "stack"
    # Compiled patterns carry the user's flags ORed with re.UNICODE on
    # Python 3 — assert MULTILINE is set, not full equality.
    assert a.to_dict()["flags"] & re.MULTILINE


def test_assert_no_error_in_body_validates_at_build_time():
    with pytest.raises(re.error):
        AssertNoErrorInBody(r"(unclosed")


def test_assert_no_error_in_body_includes_description_when_set():
    a = AssertNoErrorInBody(r"e", description="error pattern")
    assert a.to_dict()["description"] == "error pattern"


def test_assertion_factory_emits_free_form_descriptor():
    a = assertion("custom_kind", foo="bar", count=3)
    d = a.to_dict()
    assert d == {"kind": "custom_kind", "foo": "bar", "count": 3}


def test_assertion_factory_requires_kind():
    with pytest.raises(ValueError):
        assertion("")


def test_assertion_equality():
    a1 = AssertStatus(range(200, 300))
    a2 = AssertStatus(range(200, 300))
    assert a1 == a2
    assert hash(a1) == hash(a2)
    assert a1 != AssertNoCrash()


def test_assertion_repr_round_trips_through_dict():
    a = AssertNoCrash(strict=True)
    assert "no_crash" in repr(a)
    assert "True" in repr(a)
