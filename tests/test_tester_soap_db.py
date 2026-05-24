# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for Python Tester SOAP + DB facets."""

from __future__ import annotations

import respx
import httpx

from mockarty.tester import DBExecResult, Tester


USER_RESPONSE = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetUserResponse xmlns="urn:test">
      <user>
        <id>42</id>
        <name>Alice</name>
      </user>
    </GetUserResponse>
  </soap:Body>
</soap:Envelope>"""

FAULT_RESPONSE = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <soap:Fault>
      <faultcode>soap:Client</faultcode>
      <faultstring>Invalid user id</faultstring>
    </soap:Fault>
  </soap:Body>
</soap:Envelope>"""


# ── SOAP ───────────────────────────────────────────────────────────────


@respx.mock
def test_soap_happy_path():
    respx.post("http://api.test/svc").mock(return_value=httpx.Response(
        200, content=USER_RESPONSE.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
    ))
    t = Tester(base_url="http://api.test")
    (t.soap("/svc").call("urn:test#GetUser", '<GetUser xmlns="urn:test"><id>42</id></GetUser>')
        .expect_status(200)
        .expect_no_fault()
        .expect_xpath("//*[local-name()='name']/text()", "Alice")
        .expect_xpath_contains("//*[local-name()='name']/text()", "Ali")
        .extract("//*[local-name()='name']/text()", "user"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["user"] == "Alice"


@respx.mock
def test_soap_fault_detected():
    respx.post("http://api.test/svc").mock(return_value=httpx.Response(
        500, content=FAULT_RESPONSE.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
    ))
    t = Tester(base_url="http://api.test")
    (t.soap("/svc").call("op", "<X/>")
        .expect_fault("Client")
        .expect_xpath("//*[local-name()='faultstring']/text()", "Invalid user id"))
    t.finish()
    assert t.ok(), t.errors()


@respx.mock
def test_soap_expect_no_fault_fails_on_fault():
    respx.post("http://api.test/svc").mock(return_value=httpx.Response(
        500, content=FAULT_RESPONSE.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
    ))
    t = Tester(base_url="http://api.test")
    t.soap("/svc").call("op", "<X/>").expect_no_fault()
    t.finish()
    assert not t.ok()


@respx.mock
def test_soap_body_interpolation():
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode()
        return httpx.Response(200, content=USER_RESPONSE.encode("utf-8"))

    respx.post("http://api.test/svc").mock(side_effect=handler)
    t = Tester(base_url="http://api.test")
    t.set_var("id", "42")
    (t.soap("/svc")
        .call("op", "<GetUser><id>{{id}}</id></GetUser>")
        .expect_status(200))
    t.finish()
    assert "<id>42</id>" in captured["body"]


@respx.mock
def test_soap_xpath_missing_fails():
    respx.post("http://api.test/svc").mock(return_value=httpx.Response(
        200, content=USER_RESPONSE.encode("utf-8"),
    ))
    t = Tester(base_url="http://api.test")
    (t.soap("/svc").call("op", "<X/>")
        .expect_xpath("//*[local-name()='missing']/text()", "x"))
    t.finish()
    assert not t.ok()


# ── DB ─────────────────────────────────────────────────────────────────


class FakeDB:
    def __init__(self):
        self.queries: dict[str, list[dict]] = {}
        self.execs: dict[str, DBExecResult] = {}
        self.errs: dict[str, Exception] = {}
        self.calls: list[tuple] = []

    def query(self, sql, *args):
        self.calls.append(("query", sql, args))
        if sql in self.errs:
            raise self.errs[sql]
        return self.queries.get(sql, [])

    def exec(self, sql, *args):
        self.calls.append(("exec", sql, args))
        if sql in self.errs:
            raise self.errs[sql]
        return self.execs.get(sql, DBExecResult())


def test_db_query_happy_path():
    db = FakeDB()
    db.queries["SELECT id, name FROM users WHERE id = ?"] = [
        {"id": 42, "name": "Alice"},
    ]
    t = Tester()
    (t.db(db)
        .query("SELECT id, name FROM users WHERE id = ?", 42)
        .expect_ok()
        .expect_row_count(1)
        .expect_column("name", "Alice")
        .expect_field(0, "id", 42)
        .extract(0, "name", "user"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["user"] == "Alice"


def test_db_exec_happy_path():
    db = FakeDB()
    db.execs["UPDATE users SET name = ? WHERE id = ?"] = DBExecResult(rows_affected=1)
    t = Tester()
    (t.db(db)
        .exec("UPDATE users SET name = ? WHERE id = ?", "Bob", 42)
        .expect_ok()
        .expect_affected(1))
    t.finish()
    assert t.ok(), t.errors()


def test_db_expect_error():
    db = FakeDB()
    db.errs["BAD"] = RuntimeError("syntax error")
    t = Tester()
    t.db(db).query("BAD").expect_error()
    t.finish()
    assert t.ok(), t.errors()


def test_db_expect_field_row_out_of_range():
    db = FakeDB()
    t = Tester()
    (t.db(db).query("SELECT * FROM nothing")
        .expect_field(0, "id", 1)
        .extract(0, "id", "x"))
    t.finish()
    assert not t.ok()


def test_db_arg_interpolation():
    db = FakeDB()
    db.queries["SELECT ?"] = [{"x": "alice"}]
    t = Tester()
    t.set_var("user", "alice")
    t.db(db).query("SELECT ?", "{{user}}").expect_row_count(1)
    t.finish()
    assert t.ok(), t.errors()
    assert db.calls[0] == ("query", "SELECT ?", ("alice",))


def test_db_extract_type_shapes():
    db = FakeDB()
    db.queries["X"] = [{
        "s": "alice", "i": 42, "f": 3.14, "b": True,
        "y": b"bytes", "n": None,
    }]
    t = Tester()
    (t.db(db).query("X")
        .extract(0, "s", "vs")
        .extract(0, "i", "vi")
        .extract(0, "f", "vf")
        .extract(0, "b", "vb")
        .extract(0, "y", "vy")
        .extract(0, "n", "vn"))
    t.finish()
    v = t.vars()
    assert v["vs"] == "alice"
    assert v["vi"] == "42"
    assert v["vf"] == "3.14"
    assert v["vb"] == "true"
    assert v["vy"] == "bytes"
    assert v["vn"] == ""


def test_db_misuse_expect_affected_after_query():
    db = FakeDB()
    db.queries["X"] = []
    t = Tester()
    t.db(db).query("X").expect_affected(1)
    t.finish()
    assert not t.ok()
