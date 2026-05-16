# Copyright (c) 2026 Mockarty. All rights reserved.

"""Strict mock-server matchers — Wave 4 batch 2 piece 2.

Exercises every matcher's :meth:`validate` and the mock server's
strict-mode wiring. The full happy-path / Pact V3-V4 serialisation
tests live in :mod:`test_pact_matchers` / :mod:`test_pact_mock_server`;
this suite focuses on strict-validation pass + fail behaviour and
plugin-driven content-type negotiation.
"""

from __future__ import annotations

import concurrent.futures
import json
import struct
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from mockarty.pact import (
    ArrayContains,
    Boolean,
    Consumer,
    Decimal,
    EachKey,
    EachLike,
    EachValue,
    Equality,
    Integer,
    JSONPath,
    Like,
    MaxType,
    MinMaxType,
    MinType,
    MockServer,
    PactMismatchError,
    Regex,
    XMLPath,
)
from mockarty.pact.matchers import Matcher, Mismatch, _validate_value


# ── HTTP helper ──────────────────────────────────────────────────────


def _http(
    method: str,
    url: str,
    body: Any = None,
    headers: Optional[Dict[str, str]] = None,
    raw: Optional[bytes] = None,
) -> Tuple[int, bytes]:
    """Send a request through stdlib; return ``(status, body)``."""

    if raw is not None:
        data = raw
    elif body is None:
        data = None
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body)
    else:
        data = json.dumps(body).encode("utf-8")
        headers = {**(headers or {}), "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ── Matcher validate() — edge cases ──────────────────────────────────


class TestLikeValidate:
    def test_same_int_type(self):
        assert Like(1).validate(42) == []

    def test_int_vs_string_mismatch(self):
        out = Like(1).validate("nope")
        assert len(out) == 1 and out[0].expected.startswith("same type")

    def test_bool_not_int(self):
        # Python quirk: bool is a subclass of int. Pact-style matchers
        # MUST reject bool when expected is int (and vice-versa).
        assert Like(1).validate(True)[0].expected.startswith("same type")
        assert Like(True).validate(1)[0].expected.startswith("same type")

    def test_nested_dict(self):
        m = Like({"a": Like(1), "b": Like("s")})
        assert m.validate({"a": 99, "b": "x"}) == []
        problems = m.validate({"a": "wrong", "b": "ok"})
        assert len(problems) == 1
        assert problems[0].path == "$.a"

    def test_missing_key(self):
        m = Like({"a": 1})
        out = m.validate({})
        assert any("present" in p.expected for p in out)

    def test_unicode_keys(self):
        m = Like({"имя": "x", "🎯": "y"})
        assert m.validate({"имя": "y", "🎯": "z"}) == []

    def test_very_long_string(self):
        big = "x" * 100_000
        assert Like("seed").validate(big) == []

    def test_none_template(self):
        assert Like(None).validate(None) == []
        assert Like(None).validate(0)[0].expected.startswith("same type")


class TestStrictPrimitives:
    def test_integer_rejects_float(self):
        assert Integer(1).validate(1.0)[0].expected == "integer"

    def test_integer_rejects_bool(self):
        assert Integer(1).validate(True)[0].expected == "integer"

    def test_integer_accepts_negative_and_big(self):
        assert Integer(1).validate(-2**62) == []
        assert Integer(1).validate(2**100) == []

    def test_decimal_accepts_int(self):
        assert Decimal(1.0).validate(7) == []

    def test_decimal_rejects_bool(self):
        assert Decimal(1.0).validate(True)[0].expected == "decimal"

    def test_decimal_rejects_string(self):
        assert Decimal(1.0).validate("1.5")[0].expected == "decimal"

    def test_boolean_rejects_int(self):
        assert Boolean(True).validate(1)[0].expected == "boolean"

    def test_boolean_accepts_bool(self):
        assert Boolean(True).validate(False) == []


class TestRegex:
    def test_simple_pattern(self):
        assert Regex(r"\d+", "1").validate("42") == []

    def test_no_match(self):
        out = Regex(r"^\d+$", "1").validate("nope")
        assert out and "matching" in out[0].expected

    def test_non_string(self):
        out = Regex(r"\d+", "1").validate(42)
        assert out and "string" in out[0].expected

    def test_unicode_pattern(self):
        # Cyrillic word characters via \w + re.UNICODE (default in py3).
        out = Regex(r"^[А-Я]+$", "ТЕСТ").validate("ПРИВЕТ")
        assert out == []

    def test_compile_error_at_construction(self):
        with pytest.raises(ValueError):
            Regex(r"(unclosed", "x")

    def test_very_long_input(self):
        big = "a" * 10_000 + "B"
        assert Regex(r"B$", "B").validate(big) == []


class TestEachLikeValidate:
    def test_min_bound(self):
        m = EachLike(Like(1), min=2)
        assert m.validate([1, 2]) == []
        assert "length >= 2" in m.validate([1])[0].expected

    def test_max_bound(self):
        m = EachLike(Like(1), min=0, max=3)
        assert "length <= 3" in m.validate([1, 2, 3, 4])[0].expected

    def test_non_array(self):
        out = EachLike(Like(1), min=1).validate({"oops": 1})
        assert out[0].expected == "array"

    def test_per_item_mismatch_path(self):
        m = EachLike(Like(1), min=0)
        out = m.validate([1, "bad", 3])
        assert any("$[1]" in p.path for p in out)


class TestMinMaxType:
    def test_min_type(self):
        assert MinType(Like(1), min=2).validate([1, 2]) == []
        out = MinType(Like(1), min=2).validate([1])
        assert "length >= 2" in out[0].expected

    def test_max_type(self):
        assert MaxType(Like(1), max=2).validate([1, 2]) == []
        out = MaxType(Like(1), max=1).validate([1, 2])
        assert "length <= 1" in out[0].expected

    def test_min_max_type(self):
        m = MinMaxType(Like(1), min=1, max=2)
        assert m.validate([1]) == []
        assert m.validate([1, 2]) == []
        out = m.validate([])
        assert "[1, 2]" in out[0].expected
        out = m.validate([1, 2, 3])
        assert "[1, 2]" in out[0].expected


class TestEquality:
    def test_strict_equality(self):
        assert Equality(42).validate(42) == []
        assert Equality(42).validate(43)[0].expected.startswith("equal to")

    def test_dict_equality(self):
        assert Equality({"a": 1}).validate({"a": 1}) == []
        assert Equality({"a": 1}).validate({"a": 2})[0].path == "$"

    def test_unicode_equality(self):
        assert Equality("café 🚀").validate("café 🚀") == []


class TestEachKeyEachValue:
    def test_each_key_pass(self):
        m = EachKey(Regex(r"^[a-z]+$", "x"), {"x": 1})
        assert m.validate({"foo": 1, "bar": 2}) == []

    def test_each_key_fail(self):
        m = EachKey(Regex(r"^[a-z]+$", "x"), {"x": 1})
        out = m.validate({"Foo": 1})
        assert out and "matching" in out[0].expected

    def test_each_key_non_dict(self):
        m = EachKey(Regex(r".+", "x"), {})
        assert m.validate([1, 2])[0].expected == "object"

    def test_each_value_pass(self):
        m = EachValue(Integer(0), {"x": 1})
        assert m.validate({"a": 1, "b": 2}) == []

    def test_each_value_fail(self):
        m = EachValue(Integer(0), {"x": 1})
        out = m.validate({"a": "nope"})
        assert any(p.expected == "integer" for p in out)


class TestArrayContains:
    def test_pass(self):
        m = ArrayContains([Like(1), Like("x")])
        assert m.validate([1, "y", 2]) == []

    def test_missing_variant(self):
        m = ArrayContains([Like(1), Like("x")])
        out = m.validate([1])
        assert any("variant[1]" in p.expected for p in out)

    def test_non_array(self):
        m = ArrayContains([Like(1)])
        assert m.validate("nope")[0].expected == "array"


class TestJSONPath:
    def test_simple(self):
        m = JSONPath("$.a.b", Integer(0), example={"a": {"b": 7}})
        assert m.validate({"a": {"b": 42}}) == []
        assert m.validate({"a": {"b": "x"}})[0].expected == "integer"

    def test_array_index(self):
        m = JSONPath("$.list[0]", Like("x"), example={"list": ["x"]})
        assert m.validate({"list": ["y"]}) == []
        out = m.validate({"list": []})
        assert out and "node at" in out[0].expected

    def test_bracket_key(self):
        m = JSONPath('$["weird key"]', Like(1), example={"weird key": 1})
        assert m.validate({"weird key": 9}) == []

    def test_invalid_path_prefix(self):
        with pytest.raises(ValueError):
            JSONPath("no-dollar", Like(1), example={})

    def test_missing_node(self):
        m = JSONPath("$.absent", Like(1), example={})
        out = m.validate({"present": 1})
        assert out and "node at" in out[0].expected


class TestXMLPath:
    def test_simple_text(self):
        m = XMLPath("/root/child", Regex(r"^\d+$", "1"), example="<root><child>1</child></root>")
        assert m.validate("<root><child>42</child></root>") == []

    def test_text_mismatch(self):
        m = XMLPath("/root/child", Regex(r"^\d+$", "1"), example="<root><child>1</child></root>")
        out = m.validate("<root><child>nope</child></root>")
        assert out

    def test_malformed_xml(self):
        m = XMLPath("/root", Like(""), example="<root/>")
        out = m.validate("<not-xml")
        assert out and "valid XML" in out[0].expected

    def test_non_string_actual(self):
        m = XMLPath("/root", Like(""), example="<root/>")
        out = m.validate(123)
        assert out[0].expected == "XML document"

    def test_root_mismatch(self):
        m = XMLPath("/expected", Like(""), example="<expected/>")
        out = m.validate("<other/>")
        assert out and out[0].expected == "root <expected>"

    def test_invalid_path_prefix(self):
        with pytest.raises(ValueError):
            XMLPath("no-slash", Like(""), example="")


# ── Mock-server strict mode (end-to-end) ─────────────────────────────


class TestMockServerStrict:
    def test_strict_pass(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("strict pass").with_request(
            "POST",
            "/p",
            body={"id": Integer(1), "name": Regex(r"^[A-Z][a-z]+$", "Alice")},
        ).will_respond_with(200, body={"ok": True})

        with c.start(strict=True) as server:
            status, _ = _http(
                "POST",
                f"{server.url}/p",
                {"id": 7, "name": "Bob"},
            )
            assert status == 200

    def test_strict_fails_wrong_type(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("strict fail").with_request(
            "POST", "/p", body={"id": Integer(1)}
        ).will_respond_with(200)

        with pytest.raises(PactMismatchError):
            with c.start(strict=True) as server:
                status, body = _http(
                    "POST", f"{server.url}/p", {"id": "not-int"}
                )
                assert status == 400
                payload = json.loads(body)
                assert payload["error"] == "strict pact mismatch"
                assert payload["mismatches"][0]["expected"] == "integer"

    def test_strict_regex_fail(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("strict regex").with_request(
            "POST", "/p", body={"email": Regex(r".+@.+\..+", "a@b.com")}
        ).will_respond_with(200)

        with pytest.raises(PactMismatchError, match="strict"):
            with c.start(strict=True) as server:
                _http("POST", f"{server.url}/p", {"email": "no-at"})

    def test_strict_each_like_min_fail(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("strict each_like").with_request(
            "POST", "/p", body={"items": EachLike(Like(1), min=2)}
        ).will_respond_with(200)

        with pytest.raises(PactMismatchError):
            with c.start(strict=True) as server:
                _http("POST", f"{server.url}/p", {"items": [1]})

    def test_strict_off_by_default(self, tmp_path: Path):
        """Without strict=True the server must NOT reject bad bodies —
        backward compatibility with Wave 2 callers."""

        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("legacy").with_request(
            "POST", "/p", body={"id": Integer(1)}
        ).will_respond_with(200, body={"ok": True})

        with c.start() as server:
            status, _ = _http("POST", f"{server.url}/p", {"id": "garbage"})
            assert status == 200

    def test_strict_mismatch_includes_path(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("nested").with_request(
            "POST",
            "/p",
            body={"user": {"age": Integer(0)}},
        ).will_respond_with(200)

        with pytest.raises(PactMismatchError):
            with c.start(strict=True) as server:
                status, body = _http(
                    "POST", f"{server.url}/p", {"user": {"age": "old"}}
                )
                assert status == 400
                msg = json.loads(body)["mismatches"][0]
                assert msg["path"].endswith(".age")

    def test_strict_unicode_body(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("uni").with_request(
            "POST", "/p", body={"имя": Like("Алиса")}
        ).will_respond_with(200, body={"ok": True})

        with c.start(strict=True) as server:
            status, _ = _http("POST", f"{server.url}/p", {"имя": "Боб"})
            assert status == 200

    def test_strict_unhit_still_raises(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("unhit").with_request("GET", "/x").will_respond_with(200)

        with pytest.raises(PactMismatchError, match="unhit"):
            with c.start(strict=True):
                pass

    def test_mismatches_property(self, tmp_path: Path):
        c = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        c.upon_receiving("x").with_request(
            "POST", "/x", body={"id": Integer(1)}
        ).will_respond_with(200)

        server = MockServer(
            [b.build() for b in c.interactions], strict=True
        ).start()
        try:
            _http("POST", f"{server.url}/x", {"id": "no"})
            assert any(isinstance(m, Mismatch) for m in server.mismatches)
        finally:
            server.stop()


# ── Concurrency under strict mode ────────────────────────────────────


def test_strict_concurrent_requests(tmp_path: Path):
    c = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    c.upon_receiving("strict ping").with_request(
        "POST", "/ping", body={"n": Integer(0)}
    ).will_respond_with(200, body={"ok": True})

    with c.start(strict=True) as server:

        def one(i: int):
            status, _ = _http("POST", f"{server.url}/ping", {"n": i})
            return status

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(one, range(32)))
        assert statuses == [200] * 32


# ── _validate_value direct tests ─────────────────────────────────────


class TestValidateValueWalker:
    def test_scalar_equality(self):
        assert _validate_value(1, 1, "$") == []
        assert _validate_value(1, 2, "$")[0].path == "$"

    def test_list_length_mismatch(self):
        out = _validate_value([1, 2], [1], "$")
        assert "length" in out[0].expected

    def test_list_non_list(self):
        out = _validate_value([1], "nope", "$")
        assert out[0].expected == "array"

    def test_dict_missing_key(self):
        out = _validate_value({"a": 1}, {}, "$")
        assert any("present" in p.expected for p in out)

    def test_dict_non_dict(self):
        out = _validate_value({"a": 1}, "nope", "$")
        assert out[0].expected == "object"

    def test_matcher_delegation(self):
        out = _validate_value(Integer(0), "x", "$")
        assert out and out[0].expected == "integer"


# ── Mismatch class shape ─────────────────────────────────────────────


def test_mismatch_eq_and_hash():
    a = Mismatch("$.x", "int", 1)
    b = Mismatch("$.x", "int", 1)
    c = Mismatch("$.y", "int", 1)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert a != "not-a-mismatch"
