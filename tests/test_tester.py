# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for the Python port of the fluent Tester DSL.

Uses ``respx`` to mock httpx calls — same as the rest of the py-sdk
suite.
"""

from __future__ import annotations

import pytest
import respx

from mockarty.tester import Tester
from mockarty.tester.interpolate import interpolate
from mockarty.tester.jsonpath import resolve_jsonpath, JSONPathError


# ── interpolate + jsonpath unit tests ─────────────────────────────────


def test_interpolate_basic():
    assert interpolate("hi {{n}}", {"n": "ann"}) == "hi ann"
    assert interpolate("plain", {}) == "plain"
    assert interpolate("x {{missing}} y", {}) == "x {{missing}} y"
    assert interpolate("{{ n }}", {"n": "x"}) == "x"  # trim


def test_jsonpath_basic():
    doc = {"a": {"b": ["x", "y", 3]}, "name": "alice"}
    assert resolve_jsonpath(doc, "$") == doc
    assert resolve_jsonpath(doc, "$.name") == "alice"
    assert resolve_jsonpath(doc, "$.a.b[0]") == "x"
    assert resolve_jsonpath(doc, "$.a.b[-1]") == 3
    assert resolve_jsonpath(doc, "$.a.b[*]") == ["x", "y", 3]
    with pytest.raises(JSONPathError):
        resolve_jsonpath(doc, "$.a.z")
    with pytest.raises(JSONPathError):
        resolve_jsonpath(doc, "$.a.b[99]")


# ── HTTP facet tests ──────────────────────────────────────────────────


@respx.mock
def test_http_get_expect_status_json():
    respx.get("http://api.test/users/42").respond(
        200, json={"id": 42, "name": "Alice", "roles": ["admin", "ops"]},
    )
    t = Tester(base_url="http://api.test")
    (t.http().get("/users/42")
        .expect_status(200)
        .expect_json_path("$.id", 42)
        .expect_json_path("$.name", "Alice")
        .expect_json_array_len("$.roles", 2)
        .expect_json_path("$.roles[0]", "admin"))
    t.finish()
    assert t.ok(), t.errors()
    assert len(t.report()) == 1


@respx.mock
def test_http_chain_extract_and_interpolate():
    respx.get("http://api.test/login").respond(200, json={"token": "tok-123"})
    route = respx.post("http://api.test/orders").respond(
        201, json={"id": 99, "status": "created"},
    )

    t = Tester(base_url="http://api.test")
    (t.http().get("/login")
        .expect_status(200)
        .extract("$.token", "token"))
    (t.http().post("/orders")
        .header("X-Auth", "Bearer {{token}}")
        .json({"userId": 42})
        .expect_status(201)
        .expect_json_path("$.id", 99))
    t.finish()

    assert t.ok(), t.errors()
    assert route.called
    auth = route.calls.last.request.headers["X-Auth"]
    assert auth == "Bearer tok-123"


@respx.mock
def test_http_failures_accumulate():
    respx.get("http://api.test/x").respond(200, json={"id": 1})
    t = Tester(base_url="http://api.test")
    (t.http().get("/x")
        .expect_status(204)        # fail
        .expect_json_path("$.id", 99))  # fail
    t.finish()
    assert not t.ok()
    assert len(t.errors()) == 2


@respx.mock
def test_http_fail_fast_short_circuits():
    respx.get("http://api.test/a").respond(500)
    second = respx.get("http://api.test/b").respond(200)
    t = Tester(base_url="http://api.test", fail_fast=True)
    t.http().get("/a").expect_status(200)
    t.http().get("/b").expect_status(200)
    t.finish()
    assert not second.called  # fail-fast skipped the second call


@respx.mock
def test_http_json_body_interpolation():
    route = respx.post("http://api.test/").respond(200, json={"ok": True})
    t = Tester(base_url="http://api.test")
    t.set_var("user", "alice")
    (t.http().post("/")
        .json({"name": "{{user}}"})
        .expect_status(200))
    t.finish()
    body = route.calls.last.request.content.decode()
    assert '"name": "alice"' in body or '"name":"alice"' in body


@respx.mock
def test_http_extract_scalar_shapes():
    respx.get("http://api.test/").respond(
        200, json={"id": 42, "active": True, "name": "alice", "tags": ["a", "b"], "missing": None},
    )
    t = Tester(base_url="http://api.test")
    (t.http().get("/")
        .extract("$.id", "id")
        .extract("$.active", "active")
        .extract("$.name", "name")
        .extract("$.tags", "tags")
        .extract("$.missing", "missing"))
    t.finish()
    v = t.vars()
    assert v["id"] == "42"
    assert v["active"] == "true"
    assert v["name"] == "alice"
    assert v["tags"] == '["a","b"]'
    assert v["missing"] == ""


@respx.mock
def test_auto_flush_on_ok():
    respx.get("http://api.test/").respond(204)
    t = Tester(base_url="http://api.test")
    t.http().get("/").expect_status(200)  # mismatch — but no finish()
    assert not t.ok()  # auto-flushed
    assert len(t.errors()) == 1


@respx.mock
def test_http_methods():
    for verb in ("PUT", "PATCH", "DELETE", "HEAD"):
        respx.route(method=verb, host="api.test").respond(200, headers={"X-Method": verb})
    t = Tester(base_url="http://api.test")
    t.http().put("/x").expect_header("X-Method", "PUT")
    t.http().patch("/x").expect_header("X-Method", "PATCH")
    t.http().delete("/x").expect_header("X-Method", "DELETE")
    t.http().head("/x").expect_header("X-Method", "HEAD")
    t.finish()
    assert t.ok(), t.errors()


# ── GraphQL facet tests ───────────────────────────────────────────────


@respx.mock
def test_graphql_happy_path():
    respx.post("http://api.test/graphql").respond(
        200, json={"data": {"user": {"id": 42, "name": "Alice"}}},
    )
    t = Tester(base_url="http://api.test")
    (t.graphql("/graphql")
        .query("{ user(id: 42) { id name } }", {"id": 42})
        .expect_status(200)
        .expect_no_errors()
        .expect_field("$.data.user.name", "Alice")
        .extract("$.data.user.name", "user"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["user"] == "Alice"


@respx.mock
def test_graphql_errors_array():
    respx.post("http://api.test/graphql").respond(
        200, json={"data": None, "errors": [{"message": "boom"}, {"message": "again"}]},
    )
    t = Tester(base_url="http://api.test")
    (t.graphql("/graphql")
        .query("errIt", None)
        .expect_errors(2)
        .expect_field("$.errors[0].message", "boom"))
    t.finish()
    assert t.ok(), t.errors()


@respx.mock
def test_graphql_expect_no_errors_fails_on_errors():
    respx.post("http://api.test/graphql").respond(
        200, json={"data": None, "errors": [{"message": "boom"}]},
    )
    t = Tester(base_url="http://api.test")
    t.graphql("/graphql").query("X", None).expect_no_errors()
    t.finish()
    assert not t.ok()


# ── Context manager ───────────────────────────────────────────────────


@respx.mock
def test_tester_context_manager():
    respx.get("http://api.test/").respond(200)
    with Tester(base_url="http://api.test") as t:
        t.http().get("/").expect_status(200)
    # __exit__ called finish + close — exit clean.
