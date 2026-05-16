# Copyright (c) 2026 Mockarty. All rights reserved.

"""Hand-rolled property tests for matchers + plugins.

We don't depend on ``hypothesis`` (the parent SDK keeps its dependency
graph thin), so we drive randomness via the stdlib ``random`` module
with a fixed seed for reproducibility. The properties under test are:

* ``Like(x).validate(y) == [] ⇔ same Pact type``
* ``Integer / Decimal / Boolean / Regex`` round-trip arbitrary inputs
  inside their expected type without false negatives
* ``EachLike(min=N).validate(list_of_len_K) == [] ⇔ K ≥ N``
* gRPC frame ``_wrap_frame ∘ _unwrap_frame`` is identity
* ``ProtobufPlugin`` byte fallback: equal bytes never mismatch
"""

from __future__ import annotations

import random
import string

import pytest

from mockarty.pact.matchers import (
    Boolean,
    Decimal,
    EachLike,
    Integer,
    Like,
    Mismatch,
    Regex,
    _same_type,
)
from mockarty.pact.plugins.grpc import _unwrap_frame, _wrap_frame
from mockarty.pact.plugins.protobuf import ProtobufPlugin


SEED = 1729  # Ramanujan's taxicab — fixed seed for reproducibility.


def _rand_str(rng: random.Random, n: int) -> str:
    alphabet = string.ascii_letters + string.digits + "_- ёЁ漢🚀"
    return "".join(rng.choice(alphabet) for _ in range(n))


# ── Like / type semantics ────────────────────────────────────────────


def test_property_like_int_same_type():
    rng = random.Random(SEED)
    for _ in range(200):
        v = rng.randint(-(2**62), 2**62)
        assert Like(0).validate(v) == []


def test_property_like_int_rejects_other_types():
    rng = random.Random(SEED + 1)
    for _ in range(200):
        v = rng.choice([_rand_str(rng, 5), [1, 2], {"a": 1}, None, 1.5])
        out = Like(0).validate(v)
        assert out, f"Like(0) should have rejected {v!r}"


def test_property_like_string_accepts_any_string():
    rng = random.Random(SEED + 2)
    for _ in range(200):
        length = rng.randint(0, 200)
        s = _rand_str(rng, length)
        assert Like("seed").validate(s) == []


def test_property_same_type_symmetric_on_same_kind():
    rng = random.Random(SEED + 3)
    samples = [
        1,
        0.5,
        "x",
        True,
        False,
        None,
        [],
        {},
        [1, 2],
        {"a": 1},
    ]
    for a in samples:
        for b in samples:
            ab = _same_type(a, b)
            ba = _same_type(b, a)
            # Type compatibility should be symmetric except for the
            # int ↔ float promotion (one-way: expected=float accepts int).
            if isinstance(a, float) and isinstance(b, int) and not isinstance(b, bool):
                assert ab is True  # expected float accepts int
            elif isinstance(b, float) and isinstance(a, int) and not isinstance(a, bool):
                assert ba is True
            else:
                assert ab == ba


# ── Integer / Decimal / Boolean / Regex ──────────────────────────────


def test_property_integer_rejects_non_int():
    rng = random.Random(SEED + 4)
    for _ in range(100):
        bad = rng.choice([1.5, "1", [1], None, True])
        out = Integer(0).validate(bad)
        assert out and out[0].expected == "integer"


def test_property_decimal_accepts_int_and_float():
    rng = random.Random(SEED + 5)
    for _ in range(200):
        v = rng.choice([rng.randint(-1000, 1000), rng.random() * 100 - 50])
        assert Decimal(0.0).validate(v) == []


def test_property_boolean_only_bool():
    rng = random.Random(SEED + 6)
    for _ in range(100):
        v = rng.choice([True, False])
        assert Boolean(False).validate(v) == []
        # And anything else fails:
        v = rng.choice([0, 1, "", "true", None, [], {}])
        out = Boolean(False).validate(v)
        assert out and out[0].expected == "boolean"


def test_property_regex_digits():
    rng = random.Random(SEED + 7)
    m = Regex(r"^\d+$", "1")
    for _ in range(100):
        v = "".join(rng.choice(string.digits) for _ in range(rng.randint(1, 20)))
        assert m.validate(v) == []


def test_property_regex_rejects_non_string():
    rng = random.Random(SEED + 8)
    m = Regex(r".+", "x")
    for _ in range(50):
        v = rng.choice([1, 1.5, True, None, [1], {"a": 1}])
        out = m.validate(v)
        assert out and "string" in out[0].expected


# ── EachLike bounds ──────────────────────────────────────────────────


def test_property_eachlike_min_bound():
    rng = random.Random(SEED + 9)
    for _ in range(80):
        n = rng.randint(0, 5)
        m = EachLike(Like(1), min=n)
        for k in range(0, 7):
            data = [rng.randint(0, 100) for _ in range(k)]
            out = m.validate(data)
            if k < n:
                assert out, f"len={k}, min={n} should mismatch"
            else:
                assert out == [], f"len={k}, min={n} should pass"


def test_property_eachlike_max_bound():
    rng = random.Random(SEED + 10)
    for _ in range(80):
        cap = rng.randint(0, 5)
        m = EachLike(Like(1), min=0, max=cap)
        for k in range(0, 7):
            data = [rng.randint(0, 100) for _ in range(k)]
            out = m.validate(data)
            if k > cap:
                assert out
            else:
                assert out == []


# ── gRPC framing identity ────────────────────────────────────────────


def test_property_grpc_frame_roundtrip():
    rng = random.Random(SEED + 11)
    for _ in range(200):
        size = rng.randint(0, 4096)
        payload = bytes(rng.randint(0, 255) for _ in range(size))
        frame = _wrap_frame(payload)
        ok, body, _ = _unwrap_frame(frame)
        assert ok and body == payload


def test_property_grpc_unwrap_rejects_short_prefix():
    rng = random.Random(SEED + 12)
    for n in range(0, 5):  # bytes < 5 must be rejected
        raw = bytes(rng.randint(0, 255) for _ in range(n))
        ok, _, _ = _unwrap_frame(raw)
        assert ok is False


# ── ProtobufPlugin byte fallback ─────────────────────────────────────


def test_property_protobuf_byte_equality():
    rng = random.Random(SEED + 13)
    p = ProtobufPlugin()
    for _ in range(100):
        size = rng.randint(0, 256)
        payload = bytes(rng.randint(0, 255) for _ in range(size))
        assert p.match_request(payload, payload, {}) == []
        # And any 1-byte flip is detected.
        if size:
            idx = rng.randint(0, size - 1)
            mutated = bytearray(payload)
            mutated[idx] ^= 0xFF
            out = p.match_request(payload, bytes(mutated), {})
            assert out


# ── Mismatch equality property ──────────────────────────────────────


def test_property_mismatch_equality_reflexive():
    rng = random.Random(SEED + 14)
    for _ in range(50):
        path = "$." + _rand_str(rng, 5)
        m = Mismatch(path, "x", rng.randint(0, 100))
        assert m == Mismatch(path, m.expected, m.actual)
        assert m != Mismatch(path + ".other", m.expected, m.actual)
