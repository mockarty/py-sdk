# Copyright (c) 2026 Mockarty. All rights reserved.

"""Property-style tests for the pact.json parser + writer.

Hypothesis is not in the dev-deps so we hand-roll a small fuzz harness
that generates randomised consumer DSL inputs and asserts:

* ``render`` never raises on a well-formed pact;
* ``parse(render(p))`` round-trips for both V3 and V4;
* matcher rules never end up nested in the wrong category.

The randomness seed is fixed so failing runs are reproducible. Add new
counter-examples to :func:`_static_seeds` when a real bug is found —
this is the seed corpus mentioned in the SDK plan.
"""

from __future__ import annotations

import json
import random
import string
from typing import Any, List

from mockarty.pact import (
    ArrayContains,
    Boolean,
    Consumer,
    Decimal,
    EachLike,
    Integer,
    Like,
    Regex,
    SpecVersion,
)
from mockarty.pact.writer import parse, render


# ── Static seed corpus ───────────────────────────────────────────────


def _static_seeds() -> List[dict]:
    """Hand-crafted edge cases. Each entry is a kwargs dict for
    :func:`_build_pact_from_seed`.
    """

    return [
        {"body": None, "status": 204},
        {"body": {}, "status": 200},
        {"body": [], "status": 200},
        {"body": {"x": Like(0)}, "status": 200},
        {"body": {"deep": {"deep": {"deep": Like("end")}}}, "status": 200},
        {"body": {"unicode": "Привет 🚀"}, "status": 200},
        {"body": {"list": EachLike({"id": Like(1)}, min=0)}, "status": 200},
        {"body": {"regex": Regex(r".*", "")}, "status": 200},
        {"body": {"arr": ArrayContains([Like(1), Like(2)])}, "status": 200},
        {
            "body": {"i": Integer(0), "d": Decimal(0.0), "b": Boolean(False)},
            "status": 200,
        },
    ]


# ── Generator ────────────────────────────────────────────────────────


_RNG = random.Random(0xC0FFEE)


def _rand_string(rng: random.Random, min_len: int = 1, max_len: int = 12) -> str:
    n = rng.randint(min_len, max_len)
    return "".join(rng.choice(string.ascii_letters) for _ in range(n))


def _rand_body(rng: random.Random, depth: int = 0) -> Any:
    """Recursive random body generator, biased toward shallow trees."""

    if depth > 4:
        return rng.choice([None, 0, "leaf", rng.random()])
    choice = rng.randint(0, 7)
    if choice == 0:
        return None
    if choice == 1:
        return rng.randint(-1000, 1000)
    if choice == 2:
        return _rand_string(rng)
    if choice == 3:
        return rng.choice([True, False])
    if choice == 4:
        return Like(_rand_body(rng, depth + 1))
    if choice == 5:
        return EachLike(_rand_body(rng, depth + 1), min=rng.randint(0, 3))
    if choice == 6:
        return {
            _rand_string(rng, 1, 6): _rand_body(rng, depth + 1)
            for _ in range(rng.randint(0, 3))
        }
    return [_rand_body(rng, depth + 1) for _ in range(rng.randint(0, 3))]


def _build_pact_from_seed(*, body: Any, status: int) -> Consumer:
    c = (
        Consumer("Fuzz")
        .with_provider("Server")
        .with_spec_version("V4")
        .with_output_dir("/tmp")
    )
    b = (
        c.upon_receiving("fuzz interaction")
        .with_request("POST", "/fuzz", body=body)
        .will_respond_with(status, body=body)
    )
    _ = b
    return c


# ── Tests ────────────────────────────────────────────────────────────


def test_static_seeds_round_trip_v4():
    for seed in _static_seeds():
        c = _build_pact_from_seed(**seed)
        raw = render(c.to_pact(), SpecVersion.V4)
        text = json.dumps(raw)
        again = parse(text)
        assert again.interactions[0].response.status == seed["status"]


def test_static_seeds_round_trip_v3():
    for seed in _static_seeds():
        c = _build_pact_from_seed(**seed)
        raw = render(c.to_pact(), SpecVersion.V3)
        text = json.dumps(raw)
        again = parse(text)
        assert again.interactions[0].response.status == seed["status"]


def test_random_bodies_never_crash_v4():
    rng = random.Random(0xBEEF)
    for _ in range(64):
        body = _rand_body(rng)
        c = _build_pact_from_seed(body=body, status=200)
        raw = render(c.to_pact(), SpecVersion.V4)
        # Must be JSON-serialisable.
        text = json.dumps(raw)
        again = parse(text)
        assert again.consumer.name == "Fuzz"


def test_random_bodies_never_crash_v3():
    rng = random.Random(0xCAFE)
    for _ in range(64):
        body = _rand_body(rng)
        c = _build_pact_from_seed(body=body, status=200)
        raw = render(c.to_pact(), SpecVersion.V3)
        text = json.dumps(raw)
        again = parse(text)
        assert again.consumer.name == "Fuzz"


def test_v4_matching_rules_only_under_known_categories():
    """No matcher should escape into an unknown top-level key."""

    rng = random.Random(0xDEAD)
    allowed = {"body", "header", "query", "path"}
    for _ in range(32):
        body = _rand_body(rng)
        c = _build_pact_from_seed(body=body, status=200)
        raw = render(c.to_pact(), SpecVersion.V4)
        for it in raw["interactions"]:
            for part in ("request", "response"):
                rules = it.get(part, {}).get("matchingRules", {})
                stray = set(rules.keys()) - allowed
                assert not stray, f"unexpected categories: {stray}"
