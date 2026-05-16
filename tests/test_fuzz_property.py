# Copyright (c) 2026 Mockarty. All rights reserved.

"""Hand-rolled property-style tests with a fixed seed.

``hypothesis`` is NOT in py-sdk's dev-deps (verified via pyproject.toml
and the Wave 2 piece's note in feedback memory) so we use ``random``
with a fixed seed for deterministic CI runs.
"""

from __future__ import annotations

import json
import random
import string
from datetime import timedelta

from mockarty.fuzz import (
    AssertNoCrash,
    AssertStatus,
    Mutator,
    Seed,
    Target,
    parse,
    transpile,
)


def _rand_name(rng: random.Random) -> str:
    alphabet = string.ascii_letters + "_"
    return "".join(rng.choices(alphabet, k=rng.randint(1, 20)))


def _rand_body(rng: random.Random) -> str:
    # Mix of ASCII, control bytes, and unicode.
    chars = string.printable + "Привет 🎉" + "\x00\x01\x02"
    return "".join(rng.choices(chars, k=rng.randint(0, 200)))


def _rand_method(rng: random.Random) -> str:
    return rng.choice(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"])


def _rand_path(rng: random.Random) -> str:
    parts = [
        "".join(
            rng.choices(string.ascii_lowercase + "0123456789-", k=rng.randint(1, 8))
        )
        for _ in range(rng.randint(1, 5))
    ]
    return "/" + "/".join(parts)


def test_property_round_trip_n_random_targets():
    """Build 50 random targets, transpile, re-parse, ensure stable."""

    rng = random.Random(0xC0FFEE)
    for _ in range(50):
        n_seeds = rng.randint(0, 10)
        seeds = [Seed(_rand_name(rng), _rand_body(rng)) for _ in range(n_seeds)]
        # Ensure unique seed names so the corpus stays comparable.
        seen = set()
        unique_seeds = []
        for s in seeds:
            if s.name not in seen:
                unique_seeds.append(s)
                seen.add(s.name)

        t = (
            Target(_rand_name(rng))
            .description(_rand_name(rng))
            .http_endpoint(_rand_method(rng), _rand_path(rng))
            .seeds(unique_seeds)
            .mutator(rng.choice(list(Mutator)))
            .duration(timedelta(seconds=rng.randint(1, 600)))
        )
        if rng.random() < 0.5:
            t.assertion(AssertStatus(range(200, rng.randint(300, 500))))
        if rng.random() < 0.5:
            t.assertion(AssertNoCrash(strict=rng.random() < 0.5))

        first = transpile(t)
        payload = json.dumps(first, sort_keys=True, ensure_ascii=False)
        reparsed = parse(json.loads(payload))
        again = reparsed.model_dump(
            by_alias=True, exclude_defaults=True, exclude_none=True
        )
        assert json.dumps(again, sort_keys=True, ensure_ascii=False) == payload, (
            "round-trip diverged for seed-set " + repr(first)
        )


def test_property_empty_seeds_is_valid():
    rng = random.Random(0xDEADBEEF)
    t = Target(_rand_name(rng)).http_endpoint("GET", "/").mutator(Mutator.JSON)
    out = transpile(t)
    # Empty seeds → key absent (excluded as default).
    assert "seedRequests" not in out or out["seedRequests"] == []


def test_property_long_payloads_dont_truncate():
    rng = random.Random(42)
    body = "".join(rng.choices(string.printable, k=10_000))
    t = Target("long").http_endpoint("POST", "/").seeds([Seed("s", body)])
    out = transpile(t)
    assert out["seedRequests"][0]["body"] == body


def test_property_many_mutators_all_serialise_into_payload_categories():
    """Every built-in mutator round-trips into payloadCategories."""

    every = list(Mutator)
    t = Target("all").http_endpoint("GET", "/")
    for m in every:
        t.mutator(m)
    out = transpile(t)
    assert out["payloadCategories"] == [m.value for m in every]


def test_property_random_assertion_combinations_round_trip():
    rng = random.Random(123)
    for _ in range(20):
        assertions = []
        if rng.random() < 0.7:
            lo = 200 + rng.randint(0, 50)
            hi = lo + 1 + rng.randint(0, 100)
            assertions.append(AssertStatus(range(lo, hi)))
        if rng.random() < 0.7:
            assertions.append(AssertNoCrash(strict=rng.random() < 0.5))
        t = Target("a").http_endpoint("GET", "/")
        for a in assertions:
            t.assertion(a)
        out = transpile(t)
        if assertions:
            assert len(out["_sdkMeta"]["assertions"]) == len(assertions)
