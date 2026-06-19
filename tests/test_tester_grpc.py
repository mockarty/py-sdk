# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Unit tests for the gRPC facet against an in-memory fake invoker (no real
gRPC server / protobuf reflection needed). Mirrors the Go/Java port."""

from __future__ import annotations

from mockarty.tester.tester import Tester


class _FakeInvoker:
    def invoke_json(self, full_method: str, req):
        if full_method.endswith("/Get"):
            return {"name": "Alice", "id": 42, "auth": {"token": "abc"}}
        raise RuntimeError("NOT_FOUND: no such user")


def test_grpc_ok_expect_extract():
    t = Tester()
    (t.grpc(_FakeInvoker()).call("user.UserService/Get", {"id": 42})
        .expect_ok()
        .expect_field("$.name", "Alice")
        .expect_json_path("$.id", 42)
        .extract("$.auth.token", "tok")
        .done())
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["tok"] == "abc"


def test_grpc_expect_error():
    t = Tester()
    (t.grpc(_FakeInvoker()).call("user.UserService/Missing", None)
        .expect_error()
        .done())
    t.finish()
    assert t.ok(), t.errors()  # the error was expected


def test_grpc_expect_ok_on_error_fails():
    t = Tester()
    (t.grpc(_FakeInvoker()).call("user.UserService/Missing", None)
        .expect_ok()
        .done())
    t.finish()
    assert not t.ok()


def test_grpc_request_var_interpolation():
    t = Tester()
    t.set_var("uid", "7")
    captured = {}

    class _Capture:
        def invoke_json(self, full_method, req):
            captured["req"] = req
            return {"ok": True}

    (t.grpc(_Capture()).call("svc/M", {"id": "{{uid}}"}).expect_ok().done())
    t.finish()
    assert t.ok(), t.errors()
    assert captured["req"] == {"id": "7"}
