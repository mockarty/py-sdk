# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for ``mockarty.pact.matchers`` — every matcher class.

These exercise the V3 / V4 rule shape difference + the constructor
guards. The writer integration tests in ``test_pact_writer.py`` cover
how the rules land in the final pact.json.
"""

from __future__ import annotations

import pytest

from mockarty.pact.matchers import (
    ArrayContains,
    Boolean,
    Decimal,
    EachKey,
    EachKeyLike,
    EachLike,
    EachValue,
    Equality,
    Integer,
    Like,
    MatchType,
    MaxType,
    MinMaxType,
    MinType,
    Regex,
    Term,
)
from mockarty.pact.types import SpecVersion


class TestSimpleMatchers:
    def test_like(self):
        m = Like(42)
        assert m.example == 42
        assert m.v3_rule() == {"match": "type"}
        assert m.v4_rule() == {"matchers": [{"match": "type"}], "combine": "AND"}
        assert m.rule_for(SpecVersion.V3) == m.v3_rule()
        assert m.rule_for(SpecVersion.V4) == m.v4_rule()

    def test_integer_coerces_example(self):
        m = Integer(3.9)
        assert m.example == 3
        assert m.v3_rule() == {"match": "integer"}
        assert m.v4_rule()["matchers"][0]["match"] == "integer"

    def test_decimal_coerces_example(self):
        m = Decimal(1)
        assert m.example == 1.0
        assert isinstance(m.example, float)
        assert m.v3_rule() == {"match": "decimal"}

    def test_boolean(self):
        m = Boolean(1)
        assert m.example is True
        assert m.v3_rule() == {"match": "boolean"}

    def test_regex_carries_pattern(self):
        m = Regex(r"\d+", "42")
        assert m.example == "42"
        assert m.regex == r"\d+"
        assert m.v3_rule() == {"match": "regex", "regex": r"\d+"}
        v4 = m.v4_rule()
        assert v4["matchers"][0]["match"] == "regex"
        assert v4["matchers"][0]["regex"] == r"\d+"

    def test_term_alias_of_regex(self):
        assert Term is Regex

    def test_equality_v3_empty_v4_typed(self):
        m = Equality("hello")
        assert m.v3_rule() == {}  # V3 default is equality, no rule needed
        assert m.v4_rule()["matchers"][0]["match"] == "equality"


class TestEachLike:
    def test_min_max_bounds(self):
        with pytest.raises(ValueError):
            EachLike("x", min=-1)
        with pytest.raises(ValueError):
            EachLike("x", min=3, max=2)

    def test_example_repeats_min_times(self):
        m = EachLike({"id": 1}, min=3)
        assert m.example == [{"id": 1}, {"id": 1}, {"id": 1}]

    def test_v3_v4_rules(self):
        m = EachLike("x", min=2, max=5)
        v3 = m.v3_rule()
        assert v3 == {"match": "type", "min": 2, "max": 5}
        v4 = m.v4_rule()
        assert v4["matchers"][0]["min"] == 2
        assert v4["matchers"][0]["max"] == 5

    def test_min_zero_renders_at_least_one_example(self):
        m = EachLike("x", min=0)
        # Need at least one example for the verifier to know the type;
        # the rule still says min=0.
        assert m.example == ["x"]
        assert m.v3_rule()["min"] == 0


class TestMinMaxBoundsMatchers:
    def test_min_type(self):
        m = MinType("x", min=3)
        assert m.example == ["x"] * 3
        assert m.v3_rule() == {"match": "type", "min": 3}

    def test_min_type_invalid(self):
        with pytest.raises(ValueError):
            MinType("x", min=-1)

    def test_max_type(self):
        m = MaxType("x", max=4)
        assert m.example == ["x"]
        assert m.v3_rule() == {"match": "type", "max": 4}

    def test_max_type_invalid(self):
        with pytest.raises(ValueError):
            MaxType("x", max=-1)

    def test_min_max_type(self):
        m = MinMaxType("x", min=1, max=3)
        assert m.v3_rule() == {"match": "type", "min": 1, "max": 3}
        v4 = m.v4_rule()
        assert v4["matchers"][0]["max"] == 3

    def test_min_max_type_invalid(self):
        with pytest.raises(ValueError):
            MinMaxType("x", min=2, max=1)


class TestArrayContains:
    def test_at_least_one_variant_required(self):
        with pytest.raises(ValueError):
            ArrayContains([])

    def test_resolves_inner_matchers_in_example(self):
        m = ArrayContains([Like("a"), Like("b")])
        assert m.example == ["a", "b"]

    def test_v3_falls_back_to_type(self):
        m = ArrayContains([1, 2])
        assert m.v3_rule() == {"match": "type"}

    def test_v4_arrayContains_shape(self):
        m = ArrayContains([1, 2])
        v4 = m.v4_rule()
        assert v4["matchers"][0]["match"] == "arrayContains"
        assert v4["matchers"][0]["variants"] == [{"index": 0}, {"index": 1}]


class TestEachKeyEachValue:
    def test_each_key_inner_must_be_matcher(self):
        with pytest.raises(TypeError):
            EachKey("not-a-matcher", {})  # type: ignore[arg-type]

    def test_each_key_v3_fallback(self):
        m = EachKey(Regex(r"[a-z]+", "foo"), {"foo": 1, "bar": 2})
        assert m.v3_rule() == {"match": "type"}
        assert m.example == {"foo": 1, "bar": 2}

    def test_each_key_v4(self):
        m = EachKey(Regex(r"[a-z]+", "foo"), {"foo": 1})
        v4 = m.v4_rule()
        assert v4["matchers"][0]["match"] == "eachKey"
        assert v4["matchers"][0]["rules"][0]["matchers"][0]["regex"] == r"[a-z]+"

    def test_each_value_inner_must_be_matcher(self):
        with pytest.raises(TypeError):
            EachValue(123, {"foo": 1})  # type: ignore[arg-type]

    def test_each_value_v4(self):
        m = EachValue(Integer(0), {"foo": 1})
        v4 = m.v4_rule()
        assert v4["matchers"][0]["match"] == "eachValue"

    def test_each_key_like_alias(self):
        assert EachKeyLike is EachKey


def test_match_type_constants():
    # MatchType is a str subclass used as a symbolic enum.
    assert MatchType.TYPE == "type"
    assert MatchType.REGEX == "regex"
    assert MatchType.ARRAY_CONTAINS == "arrayContains"


def test_matcher_repr_includes_class_name():
    m = Like("hi")
    assert "Like" in repr(m)
    assert "hi" in repr(m)
