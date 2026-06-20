# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Dogfood of the Python Tester DSL (the framework we sell) against a LIVE
Mockarty admin. Seeds real mocks via the admin REST, then points the fluent
Tester facets at them — proving the Python client works end-to-end against the
real product, mirroring the Go sdk_dogfood_tester_dsl tests.

Skipped unless MOCKARTY_DOGFOOD_SERVER is set (e.g. http://127.0.0.1:5970).
Run: MOCKARTY_DOGFOOD_SERVER=http://127.0.0.1:5970 pytest tests/test_dogfood_tester_live.py
"""

from __future__ import annotations

import os
import time
import uuid


def _rt(suffix: str) -> str:
    return f"/pydf/{uuid.uuid4().hex[:10]}{suffix}"

import pytest

httpx = pytest.importorskip("httpx")
from mockarty.tester.tester import Tester  # noqa: E402

SERVER = os.environ.get("MOCKARTY_DOGFOOD_SERVER", "").rstrip("/")
pytestmark = pytest.mark.skipif(not SERVER, reason="set MOCKARTY_DOGFOOD_SERVER to dogfood against a live admin")


@pytest.fixture(scope="module")
def live():
    c = httpx.Client(base_url=SERVER, timeout=30.0)
    # admin/admin → session → API token
    c.post("/api/v1/auth/login", json={"login": "admin", "password": "admin"})
    r = c.post("/api/v1/auth/tokens", json={"name": f"pydf-{uuid.uuid4().hex[:8]}"})
    token = r.json().get("token", "")
    assert token, f"no token: {r.status_code} {r.text[:200]}"
    c.headers["Authorization"] = f"Bearer {token}"
    # Use the always-present "sandbox" namespace (creating a fresh one hits the
    # SQLite trial's max_namespaces limit); unique route prefixes keep tests
    # isolated + parallel-safe.
    yield c, "sandbox"


def _seed_mock(c, mock):
    r = c.post("/api/v1/mocks", json=mock)
    assert r.status_code < 400, f"seed mock failed: {r.status_code} {r.text[:300]}"


def test_pyclient_http_chain_live(live):
    c, ns = live
    base = _rt("")
    _seed_mock(c, {
        "namespace": ns,
        "http": {"route": base + "/login", "httpMethod": "GET"},
        "response": {"statusCode": 200, "headers": {"Content-Type": ["application/json"]},
                     "payload": {"token": "tok-xyz", "user": "alice"}},
    })
    _seed_mock(c, {
        "namespace": ns,
        "http": {"route": base + "/me", "httpMethod": "GET",
                 "headers": [{"path": "Authorization", "assertAction": "equals", "value": "Bearer tok-xyz"}]},
        "response": {"statusCode": 200, "headers": {"Content-Type": ["application/json"]},
                     "payload": {"name": "Alice", "id": 42}},
    })

    t = Tester()
    (t.http().get(f"{SERVER}/stubs/{ns}{base}/login")
        .expect_status(200).expect_json_path("$.user", "alice").extract("$.token", "token"))
    (t.http().get(f"{SERVER}/stubs/{ns}{base}/me")
        .header("Authorization", "Bearer {{token}}")
        .expect_status(200).expect_json_path("$.name", "Alice").extract("$.id", "uid"))
    t.finish()
    assert t.ok(), f"python tester DSL failed against live mocks: {t.errors()}"
    assert t.vars()["uid"] == "42"


def test_pyclient_negative_assertion_fails_live(live):
    c, ns = live
    wroute = _rt("/widget")
    _seed_mock(c, {
        "namespace": ns,
        "http": {"route": wroute, "httpMethod": "GET"},
        "response": {"statusCode": 200, "headers": {"Content-Type": ["application/json"]},
                     "payload": {"name": "Alice"}},
    })
    t = Tester()
    (t.http().get(f"{SERVER}/stubs/{ns}{wroute}")
        .expect_status(200).expect_json_path("$.name", "Bob"))  # live returns Alice → must fail
    t.finish()
    assert not t.ok(), "a wrong JSONPath against the live mock must FAIL the run"


def test_pyclient_sse_live(live):
    c, ns = live
    spath = _rt("/events")
    _seed_mock(c, {
        "namespace": ns,
        "sse": {"eventPath": spath, "eventName": "updates"},
        "response": {"statusCode": 200, "sseEventChain": {"events": [
            {"eventName": "updates", "data": {"status": "connected", "seq": 1}},
            {"eventName": "updates", "data": {"status": "running", "seq": 2}},
        ]}},
    })
    t = Tester()
    (t.sse(f"{SERVER}/stubs/{ns}{spath}").subscribe()
        .listen(4.0)
        .expect_min_events(2)
        .expect_event("updates")
        .expect_json_path("updates", "$.status", "connected")
        .extract("updates", "$.status", "first")
        .done())
    t.finish()
    assert t.ok(), f"python tester SSE DSL failed against live SSE mock: {t.errors()}"
    assert t.vars()["first"] == "connected"


def test_pyclient_graphql_live(live):
    c, ns = live
    route = _rt("/graphql")
    _seed_mock(c, {
        "namespace": ns,
        "pathPrefix": route,
        "graphql": {"operation": "query", "field": "user"},
        "response": {"statusCode": 200, "headers": {"Content-Type": ["application/json"]},
                     "payload": {"data": {"user": {"id": "u-graphql-1", "name": "Mockarty"}}}},
    })
    t = Tester()
    (t.graphql(f"{SERVER}/stubs/{ns}{route}")
        .query("query { user { id name } }")
        .expect_status(200)
        .expect_no_errors()
        .expect_field("$.data.user.id", "u-graphql-1")
        .extract("$.data.user.name", "uname")
        .done())
    t.finish()
    assert t.ok(), f"python GraphQL DSL failed against live mock: {t.errors()}"
    assert t.vars()["uname"] == "Mockarty"


def test_pyclient_soap_live(live):
    c, ns = live
    route = _rt("/soap/calc")
    resp_xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><AddResponse xmlns="urn:Calc"><result>5</result></AddResponse></soap:Body>'
        '</soap:Envelope>'
    )
    _seed_mock(c, {
        "namespace": ns,
        "pathPrefix": route,
        "soap": {"path": route, "service": "Calc", "method": "Add", "action": "urn:Calc/Add"},
        "response": {"statusCode": 200, "headers": {"Content-Type": ["text/xml; charset=utf-8"]},
                     "payload": resp_xml},
    })
    t = Tester()
    (t.soap(f"{SERVER}/stubs/{ns}{route}")
        .call("urn:Calc/Add", '<Add xmlns="urn:Calc"><a>2</a><b>3</b></Add>')
        .expect_status(200)
        .expect_no_fault()
        .expect_xpath_contains("//*[local-name()='result']", "5")
        .done())
    t.finish()
    assert t.ok(), f"python SOAP DSL failed against live mock: {t.errors()}"


def test_pyclient_http_rich_live(live):
    """POST with a JSON body + header/query conditions, multi-assert + extract chain."""
    c, ns = live
    route = _rt("/orders")
    _seed_mock(c, {
        "namespace": ns,
        "http": {"route": route, "httpMethod": "POST",
                 "headers": [{"path": "X-Tenant", "assertAction": "equals", "value": "acme"}]},
        "response": {"statusCode": 201, "headers": {"Content-Type": ["application/json"]},
                     "payload": {"orderId": "ord-777", "status": "created", "items": 3}},
    })
    t = Tester()
    (t.http().post(f"{SERVER}/stubs/{ns}{route}")
        .header("X-Tenant", "acme")
        .json({"sku": "ABC", "qty": 3})
        .expect_status(201)
        .expect_json_path("$.status", "created")
        .expect_json_path("$.items", 3)
        .extract("$.orderId", "oid"))
    t.finish()
    assert t.ok(), f"python rich-HTTP DSL failed against live mock: {t.errors()}"
    assert t.vars()["oid"] == "ord-777"
