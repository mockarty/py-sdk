# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for the Python Tester S3 + SMTP facets.

Both use protocol-based interfaces so we plug in an in-memory fake —
no live S3 / SMTP server required.
"""

from __future__ import annotations

import pytest

from mockarty.protocols import s3 as s3proto
from mockarty.protocols import smtp as smtpproto
from mockarty.tester import Tester


# ── S3 fake ────────────────────────────────────────────────────────────


class FakeS3:
    def __init__(self):
        self.objects = {}  # "bucket/key" -> (body, content_type, meta, etag)
        self.force_err = None

    def put_object(self, bucket, key, body, content_type="", metadata=None):
        if self.force_err is not None:
            raise self.force_err
        self.objects[f"{bucket}/{key}"] = (body, content_type, dict(metadata or {}), f"etag-{key}")
        return s3proto.PutResult(status_code=200, etag=f"etag-{key}")

    def get_object(self, bucket, key):
        o = self.objects.get(f"{bucket}/{key}")
        if o is None:
            raise s3proto.S3Error("mockarty s3: get_object: NoSuchKey (404): missing")
        body, ct, meta, etag = o
        return s3proto.GetResult(
            status_code=200, body=body, content_type=ct, etag=etag, metadata=meta
        )

    def head_object(self, bucket, key):
        o = self.objects.get(f"{bucket}/{key}")
        if o is None:
            return s3proto.HeadResult(status_code=404, exists=False)
        body, ct, meta, etag = o
        return s3proto.HeadResult(
            status_code=200, exists=True, content_type=ct, etag=etag,
            metadata=meta, content_length=len(body),
        )

    def list_objects(self, bucket, prefix=""):
        res = s3proto.ListResult(status_code=200)
        for k, (body, _ct, _meta, etag) in self.objects.items():
            if not k.startswith(bucket + "/"):
                continue
            key = k[len(bucket) + 1 :]
            if prefix and not key.startswith(prefix):
                continue
            res.objects.append(s3proto.ObjectInfo(key=key, size=len(body), etag=etag))
        return res

    def delete_object(self, bucket, key):
        self.objects.pop(f"{bucket}/{key}", None)
        return s3proto.DeleteResult(status_code=204)


def test_s3_put_get_lifecycle():
    cli = FakeS3()
    t = Tester()
    (t.s3(cli).put("reports", "q1.csv")
        .body("a,b,c").content_type("text/csv").meta("owner", "finance")
        .expect_ok().expect_status(200).extract_etag("etag"))
    (t.s3(cli).get("reports", "q1.csv")
        .expect_ok()
        .expect_body_equals("a,b,c")
        .expect_body_contains("b,c")
        .expect_content_type("text/csv")
        .expect_meta("owner", "finance"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["etag"] == "etag-q1.csv"


def test_s3_head_and_list():
    cli = FakeS3()
    t = Tester()
    t.s3(cli).put("b", "k1").body("x").expect_ok()
    t.s3(cli).put("b", "k2").body("yy").expect_ok()
    t.s3(cli).head("b", "k1").expect_exists().expect_status(200)
    t.s3(cli).head("b", "missing").expect_absent().expect_status(404)
    t.s3(cli).list("b").expect_object_count(2).expect_key("k1").expect_key("k2")
    t.finish()
    assert t.ok(), t.errors()


def test_s3_delete_then_missing():
    cli = FakeS3()
    t = Tester()
    t.s3(cli).put("b", "k").body("v").expect_ok()
    t.s3(cli).delete("b", "k").expect_ok().expect_status(204)
    t.s3(cli).get("b", "k").expect_error().expect_status(404)
    t.finish()
    assert t.ok(), t.errors()


def test_s3_interpolation():
    cli = FakeS3()
    t = Tester()
    t.set_var("bkt", "dyn")
    t.set_var("name", "report.txt")
    t.s3(cli).put("{{bkt}}", "{{name}}").body("payload").expect_ok()
    t.s3(cli).get("{{bkt}}", "{{name}}").expect_body_equals("payload")
    t.finish()
    assert t.ok(), t.errors()
    assert "dyn/report.txt" in cli.objects


@pytest.mark.parametrize(
    "scenario,want_ok",
    [
        ("expect_ok_on_missing", False),
        ("wrong_body", False),
        ("wrong_meta", False),
        ("list_count_mismatch", False),
        ("put_error", False),
        ("negative_get_passes", True),
    ],
)
def test_s3_negative(scenario, want_ok):
    cli = FakeS3()
    t = Tester()
    if scenario == "expect_ok_on_missing":
        t.s3(cli).get("b", "nope").expect_ok()
    elif scenario == "wrong_body":
        t.s3(cli).put("b", "k").body("real").expect_ok()
        t.s3(cli).get("b", "k").expect_body_equals("wrong")
    elif scenario == "wrong_meta":
        t.s3(cli).put("b", "k").body("v").meta("a", "1").expect_ok()
        t.s3(cli).get("b", "k").expect_meta("a", "2")
    elif scenario == "list_count_mismatch":
        t.s3(cli).put("b", "k").body("v").expect_ok()
        t.s3(cli).list("b").expect_object_count(5)
    elif scenario == "put_error":
        cli.force_err = RuntimeError("boom")
        t.s3(cli).put("b", "k").body("v").expect_ok()
    elif scenario == "negative_get_passes":
        t.s3(cli).get("b", "ghost").expect_error().expect_status(404)
    t.finish()
    assert t.ok() == want_ok, t.errors()


# ── SMTP fake ──────────────────────────────────────────────────────────


class FakeSMTP:
    def __init__(self):
        self.sent = []
        self.reject_err = None

    def send(self, msg):
        if self.reject_err is not None:
            raise self.reject_err
        self.sent.append(msg)
        return smtpproto.SendResult(raw=f"From: {msg.from_addr}\nSubject: {msg.subject}\n\n{msg.body}")


def test_smtp_send_accepted():
    srv = FakeSMTP()
    t = Tester()
    (t.smtp(srv).send("alice@corp", "bob@corp", "carol@corp")
        .subject("Invoice 42").body("Please pay.").header("X-Priority", "1")
        .expect_accepted())
    t.finish()
    assert t.ok(), t.errors()
    assert len(srv.sent) == 1
    m = srv.sent[0]
    assert m.from_addr == "alice@corp" and len(m.to) == 2
    assert m.subject == "Invoice 42" and m.headers["X-Priority"] == "1"


def test_smtp_interpolation():
    srv = FakeSMTP()
    t = Tester()
    t.set_var("id", "INV-7")
    t.set_var("rcpt", "dyn@corp")
    (t.smtp(srv).send("sys@corp", "{{rcpt}}")
        .subject("Order {{id}}").body("Ref {{id}}").expect_accepted())
    t.finish()
    assert t.ok(), t.errors()
    m = srv.sent[0]
    assert m.to[0] == "dyn@corp" and m.subject == "Order INV-7" and "INV-7" in m.body


@pytest.mark.parametrize(
    "scenario,want_ok",
    [
        ("rejected_expect_accepted", False),
        ("rejected_expect_rejected", True),
        ("accepted_expect_rejected", False),
    ],
)
def test_smtp_negative(scenario, want_ok):
    srv = FakeSMTP()
    t = Tester()
    if scenario == "rejected_expect_accepted":
        srv.reject_err = smtpproto.SMTPSendError("550 mailbox unavailable")
        t.smtp(srv).send("a@x", "b@y").expect_accepted()
    elif scenario == "rejected_expect_rejected":
        srv.reject_err = smtpproto.SMTPSendError("550 mailbox unavailable")
        t.smtp(srv).send("a@x", "b@y").expect_rejected().expect_error_contains("550")
    elif scenario == "accepted_expect_rejected":
        t.smtp(srv).send("a@x", "b@y").expect_rejected()
    t.finish()
    assert t.ok() == want_ok, t.errors()
