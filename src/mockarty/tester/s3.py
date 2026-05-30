# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""S3 facet — mirrors ``sdk/go-sdk/tester/s3.go``.

``S3Client`` is a protocol the user implements (or adapts an existing
client to). ``mockarty.protocols.s3.Client`` satisfies it directly; tests
pass an in-memory fake so no real S3 endpoint is required.
"""

from __future__ import annotations

import time
from typing import Optional, Protocol

from ..protocols import s3 as s3proto
from .interpolate import interpolate
from .tester import StepRecord, Tester


class S3Client(Protocol):
    """Minimal contract the S3 facet needs."""

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str = "",
        metadata: Optional[dict] = None,
    ) -> "s3proto.PutResult": ...

    def get_object(self, bucket: str, key: str) -> "s3proto.GetResult": ...

    def head_object(self, bucket: str, key: str) -> "s3proto.HeadResult": ...

    def list_objects(self, bucket: str, prefix: str = "") -> "s3proto.ListResult": ...

    def delete_object(self, bucket: str, key: str) -> "s3proto.DeleteResult": ...


_OPS = ("put", "get", "head", "list", "delete")


class S3Facet:
    def __init__(self, tester: Tester, client: S3Client) -> None:
        self._t = tester
        self._client = client

    def put(self, bucket: str, key: str) -> "S3Step":
        return self._step("put", bucket, key)

    def get(self, bucket: str, key: str) -> "S3Step":
        return self._step("get", bucket, key)

    def head(self, bucket: str, key: str) -> "S3Step":
        return self._step("head", bucket, key)

    def list(self, bucket: str) -> "S3Step":
        return self._step("list", bucket, "")

    def delete(self, bucket: str, key: str) -> "S3Step":
        return self._step("delete", bucket, key)

    def _step(self, op: str, bucket: str, key: str) -> "S3Step":
        self._t._flush_pending()
        v = self._t._snapshot_vars()
        step = S3Step(
            self._t,
            self._client,
            op,
            interpolate(bucket, v),
            interpolate(key, v),
        )
        self._t._set_pending(step)
        return step


class S3Step:
    def __init__(
        self, tester: Tester, client: S3Client, op: str, bucket: str, key: str
    ) -> None:
        self._t = tester
        self._client = client
        self._op = op
        self._bucket = bucket
        self._key = key
        self._prefix = ""
        self._content_type = ""
        self._body = b""
        self._metadata: dict[str, str] = {}
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._err: Optional[Exception] = None
        self._failures: list[str] = []
        self._put: Optional[s3proto.PutResult] = None
        self._get: Optional[s3proto.GetResult] = None
        self._head: Optional[s3proto.HeadResult] = None
        self._list: Optional[s3proto.ListResult] = None
        self._delete: Optional[s3proto.DeleteResult] = None

    # ── builders ──────────────────────────────────────────────────────

    def body(self, text: str) -> "S3Step":
        if self._guard("body"):
            return self
        self._body = interpolate(text, self._t._snapshot_vars()).encode("utf-8")
        return self

    def bytes(self, b: bytes) -> "S3Step":
        if self._guard("bytes"):
            return self
        self._body = bytes(b)
        return self

    def content_type(self, ct: str) -> "S3Step":
        if self._guard("content_type"):
            return self
        self._content_type = ct
        return self

    def meta(self, k: str, v: str) -> "S3Step":
        if self._guard("meta"):
            return self
        self._metadata[k] = interpolate(v, self._t._snapshot_vars())
        return self

    def prefix(self, p: str) -> "S3Step":
        if self._guard("prefix"):
            return self
        self._prefix = interpolate(p, self._t._snapshot_vars())
        return self

    # ── assertions ────────────────────────────────────────────────────

    def expect_ok(self) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            self._fail(f"expect_ok: {self._err}")
        return self

    def expect_error(self) -> "S3Step":
        self._ensure_sent()
        if self._err is None:
            self._fail("expect_error: operation succeeded")
        return self

    def expect_status(self, code: int) -> "S3Step":
        if not self._ensure_sent():
            return self
        got = self._status_code()
        if got != code:
            self._fail(f"expect_status: want {code}, got {got}")
        return self

    def expect_body_contains(self, sub: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "get":
            return self._fail("expect_body_contains only valid after get()")
        if sub not in self._get.body.decode("utf-8", "replace"):
            self._fail(f"expect_body_contains: {sub!r} not found")
        return self

    def expect_body_equals(self, want: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "get":
            return self._fail("expect_body_equals only valid after get()")
        got = self._get.body.decode("utf-8", "replace")
        if got != want:
            self._fail(f"expect_body_equals: want {want!r}, got {got!r}")
        return self

    def expect_meta(self, k: str, want: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op == "get":
            meta = self._get.metadata
        elif self._op == "head":
            meta = self._head.metadata
        else:
            return self._fail("expect_meta only valid after get() or head()")
        got = meta.get(k, "")
        if got != want:
            self._fail(f"expect_meta[{k}]: want {want!r}, got {got!r}")
        return self

    def expect_content_type(self, want: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op == "get":
            got = self._get.content_type
        elif self._op == "head":
            got = self._head.content_type
        else:
            return self._fail("expect_content_type only valid after get() or head()")
        if got != want:
            self._fail(f"expect_content_type: want {want!r}, got {got!r}")
        return self

    def expect_exists(self) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "head":
            return self._fail("expect_exists only valid after head()")
        if not self._head.exists:
            self._fail("expect_exists: object not found")
        return self

    def expect_absent(self) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "head":
            return self._fail("expect_absent only valid after head()")
        if self._head.exists:
            self._fail("expect_absent: object exists")
        return self

    def expect_object_count(self, n: int) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "list":
            return self._fail("expect_object_count only valid after list()")
        if len(self._list.objects) != n:
            self._fail(f"expect_object_count: want {n}, got {len(self._list.objects)}")
        return self

    def expect_key(self, key: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "list":
            return self._fail("expect_key only valid after list()")
        if not any(o.key == key for o in self._list.objects):
            self._fail(f"expect_key: {key!r} not in listing")
        return self

    # ── extraction / escape hatches ───────────────────────────────────

    def extract_etag(self, name: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op == "put":
            etag = self._put.etag
        elif self._op == "get":
            etag = self._get.etag
        elif self._op == "head":
            etag = self._head.etag
        else:
            return self._fail("extract_etag only valid after put(), get(), or head()")
        self._t.set_var(name, etag)
        return self

    def extract_body(self, name: str) -> "S3Step":
        if not self._ensure_sent():
            return self
        if self._op != "get":
            return self._fail("extract_body only valid after get()")
        self._t.set_var(name, self._get.body.decode("utf-8", "replace"))
        return self

    def get_body(self) -> bytes:
        self._ensure_sent()
        return self._get.body if self._get else b""

    def objects(self) -> list:
        self._ensure_sent()
        return list(self._list.objects) if self._list else []

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # ── internals ─────────────────────────────────────────────────────

    def _fail(self, msg: str) -> "S3Step":
        self._failures.append(msg)
        return self

    def _guard(self, method: str) -> bool:
        if self._sent:
            self._fail(f"{method}() called after send")
            return True
        return False

    def _status_code(self) -> int:
        res = {
            "put": self._put,
            "get": self._get,
            "head": self._head,
            "list": self._list,
            "delete": self._delete,
        }[self._op]
        return res.status_code if res else 0

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            self._fail("skipped: fail-fast triggered by earlier step")
            return False
        self._started_at = time.time()
        try:
            if self._op == "put":
                self._put = self._client.put_object(
                    self._bucket,
                    self._key,
                    self._body,
                    self._content_type,
                    self._metadata,
                )
            elif self._op == "get":
                self._get = self._client.get_object(self._bucket, self._key)
            elif self._op == "head":
                self._head = self._client.head_object(self._bucket, self._key)
            elif self._op == "list":
                self._list = self._client.list_objects(self._bucket, self._prefix)
            elif self._op == "delete":
                self._delete = self._client.delete_object(self._bucket, self._key)
        except Exception as e:
            self._err = e
            # Capture the status code carried by S3Error results when the
            # client raises (so expect_status still works on errors).
            self._capture_error_status(e)
        self._ended_at = time.time()
        return True

    def _capture_error_status(self, e: Exception) -> None:
        # protocols.s3.Client raises S3Error with the status embedded in
        # the message; the result dataclasses are not populated on raise.
        # For 404-style negative tests we synthesise a result so
        # expect_status(404) works. Parse the "(<code>)" token.
        import re

        m = re.search(r"\((\d{3})\)", str(e))
        code = int(m.group(1)) if m else 0
        if self._op == "get" and self._get is None:
            self._get = s3proto.GetResult(status_code=code)
        elif self._op == "put" and self._put is None:
            self._put = s3proto.PutResult(status_code=code)
        elif self._op == "delete" and self._delete is None:
            self._delete = s3proto.DeleteResult(status_code=code)
        elif self._op == "list" and self._list is None:
            self._list = s3proto.ListResult(status_code=code)

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        target = self._bucket
        if self._key:
            target += "/" + self._key
        rec = StepRecord(
            protocol="s3",
            method=self._op,
            name=f"s3 {self._op} {target}",
            url=target,
            status_or_code=self._status_code(),
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)
