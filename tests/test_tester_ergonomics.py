# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for the Python port of Wrap / Eventually / Parallel."""

from __future__ import annotations

import threading

import respx

from mockarty.tester import Tester, eventually, parallel, wrap


@respx.mock
def test_wrap_groups_steps():
    respx.get("http://api.test/").respond(200)
    t = Tester(base_url="http://api.test")

    def chain():
        t.http().get("/").expect_status(200)
        t.http().get("/").expect_status(200)

    wrap(t, "two calls", chain)
    t.finish()
    assert t.ok(), t.errors()
    # 2 HTTP steps + 1 wrap-group step = 3 records.
    assert len(t.report()) == 3
    # The group step is recorded last (after flush of nested chains).
    assert t.report()[-1].name == "two calls"
    assert t.report()[-1].protocol == "group"


@respx.mock
def test_eventually_succeeds_after_retries():
    counter = {"n": 0}

    def handler(request):
        counter["n"] += 1
        if counter["n"] < 3:
            import httpx
            return httpx.Response(500)
        import httpx
        return httpx.Response(200)

    respx.get("http://api.test/").mock(side_effect=handler)
    t = Tester(base_url="http://api.test")

    def attempt():
        t.http().get("/").expect_status(200)
        if not t.ok():
            return RuntimeError("not ready")
        return None

    ok = eventually(t, within=2.0, interval=0.02, fn=attempt)
    assert ok, t.errors()
    assert counter["n"] >= 3


@respx.mock
def test_eventually_times_out():
    respx.get("http://api.test/").respond(500)
    t = Tester(base_url="http://api.test")

    def attempt():
        t.http().get("/").expect_status(200)
        if not t.ok():
            return RuntimeError("nope")
        return None

    ok = eventually(t, within=0.15, interval=0.03, fn=attempt)
    assert not ok
    assert not t.ok()


@respx.mock
def test_parallel_fanout():
    respx.get("http://api.test/x").respond(200)
    t = Tester(base_url="http://api.test")
    parallel(
        t,
        lambda b: b.http().get("/x").expect_status(200),
        lambda b: b.http().get("/x").expect_status(200),
        lambda b: b.http().get("/x").expect_status(200),
    )
    t.finish()
    assert t.ok(), t.errors()
    assert len(t.report()) == 3


@respx.mock
def test_parallel_merges_failures():
    respx.get("http://api.test/x").respond(204)
    t = Tester(base_url="http://api.test")
    parallel(
        t,
        lambda b: b.http().get("/x").expect_status(204),  # pass
        lambda b: b.http().get("/x").expect_status(200),  # fail
    )
    t.finish()
    assert not t.ok()
    assert len(t.report()) == 2


def test_parallel_empty_noop():
    t = Tester()
    parallel(t)
    t.finish()
    assert t.ok()
    assert len(t.report()) == 0
