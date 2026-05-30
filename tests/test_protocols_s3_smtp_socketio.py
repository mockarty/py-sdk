# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Protocol-client tests for s3 / smtp / socketio.

The S3 client is exercised against an in-process http.server stub; the
SMTP message builder and the socketio URL/event helpers are tested
directly (no server needed).
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from mockarty.protocols import s3 as s3proto
from mockarty.protocols import smtp as smtpproto
from mockarty.protocols import socketio as sioproto


# ── S3 client against a stub server ────────────────────────────────────


class _S3Handler(BaseHTTPRequestHandler):
    store: dict = {}
    meta: dict = {}

    def log_message(self, *args):  # silence
        pass

    def _key(self):
        return self.path.split("?", 1)[0].lstrip("/")

    def do_PUT(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        key = self._key()
        type(self).store[key] = body
        if self.headers.get("x-amz-meta-owner"):
            type(self).meta[key] = self.headers["x-amz-meta-owner"]
        self.send_response(200)
        self.send_header("ETag", '"deadbeef"')
        self.end_headers()

    def do_GET(self):
        if self.path.endswith("/") or "list-type" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(
                b'<?xml version="1.0"?><ListBucketResult>'
                b"<IsTruncated>false</IsTruncated>"
                b'<Contents><Key>k1</Key><Size>3</Size><ETag>"e1"</ETag>'
                b"<LastModified>2026-01-01T00:00:00Z</LastModified></Contents>"
                b"</ListBucketResult>"
            )
            return
        key = self._key()
        if key not in type(self).store:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"<Error><Code>NoSuchKey</Code><Message>nf</Message></Error>")
            return
        body = type(self).store[key]
        self.send_response(200)
        self.send_header("ETag", '"deadbeef"')
        self.send_header("Content-Type", "text/plain")
        if type(self).meta.get(key):
            self.send_header("x-amz-meta-owner", type(self).meta[key])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        key = self._key()
        if key not in type(self).store:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("ETag", '"deadbeef"')
        self.end_headers()

    def do_DELETE(self):
        type(self).store.pop(self._key(), None)
        self.send_response(204)
        self.end_headers()


@pytest.fixture
def s3_server():
    _S3Handler.store = {}
    _S3Handler.meta = {}
    srv = HTTPServer(("127.0.0.1", 0), _S3Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_s3_client_lifecycle(s3_server):
    cli = s3proto.Client(s3_server)
    put = cli.put_object("bucket", "k1", b"abc", "text/plain", {"owner": "fin"})
    assert put.status_code == 200 and put.etag == "deadbeef"

    get = cli.get_object("bucket", "k1")
    assert get.body == b"abc" and get.content_type == "text/plain"
    assert get.metadata["owner"] == "fin"

    head = cli.head_object("bucket", "k1")
    assert head.exists
    assert not cli.head_object("bucket", "nope").exists

    lst = cli.list_objects("bucket")
    assert len(lst.objects) == 1 and lst.objects[0].key == "k1"

    delr = cli.delete_object("bucket", "k1")
    assert delr.status_code == 204

    with pytest.raises(s3proto.S3Error):
        cli.get_object("bucket", "k1")
    cli.close()


def test_s3_client_signer(s3_server):
    called = {"n": 0}

    def signer(req: httpx.Request):
        called["n"] += 1
        req.headers["Authorization"] = "AWS4-HMAC-SHA256 ..."

    cli = s3proto.Client(s3_server, signer=signer)
    cli.put_object("b", "k", b"x")
    assert called["n"] == 1
    cli.close()


def test_s3_client_empty_bucket():
    cli = s3proto.Client("http://example.invalid")
    with pytest.raises(ValueError):
        cli.get_object("", "k")
    cli.close()


# ── SMTP message builder ───────────────────────────────────────────────


def test_smtp_validation():
    cli = smtpproto.Client("127.0.0.1", 0)
    with pytest.raises(smtpproto.SMTPSendError):
        cli.send(smtpproto.Message(to=["b@y"]))
    with pytest.raises(smtpproto.SMTPSendError):
        cli.send(smtpproto.Message(from_addr="a@x"))


# ── Socket.IO helpers ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,want",
    [
        ("http://h:8080", "ws://h:8080/socket.io/?EIO=4&transport=websocket"),
        ("https://h", "wss://h/socket.io/?EIO=4&transport=websocket"),
        ("ws://h/socket.io/", "ws://h/socket.io/?EIO=4&transport=websocket"),
        (
            "ws://h/socket.io/?EIO=4&transport=websocket",
            "ws://h/socket.io/?EIO=4&transport=websocket",
        ),
        (
            "http://h/socket.io/?token=x",
            "ws://h/socket.io/?token=x&EIO=4&transport=websocket",
        ),
    ],
)
def test_socketio_normalize_url(raw, want):
    assert sioproto._normalize_url(raw) == want


def test_socketio_parse_event():
    ev = sioproto._parse_event("/admin", '["greeting",{"msg":"hi"}]')
    assert ev is not None and ev.name == "greeting" and ev.namespace == "/admin"
    assert ev.args == [{"msg": "hi"}]
    assert sioproto._parse_event("/", "not json") is None
    assert sioproto._parse_event("/", "[]") is None


def test_socketio_ns_match():
    assert sioproto._ns_match("", "/")
    assert sioproto._ns_match("/", "")
    assert sioproto._ns_match("/admin", "/admin")
    assert not sioproto._ns_match("/admin", "/user")
