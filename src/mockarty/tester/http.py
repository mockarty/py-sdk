# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""HTTP facet — mirrors ``sdk/go-sdk/tester/http.go``."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

from .interpolate import interpolate
from .jsonpath import equal_json_scalar, resolve_jsonpath, JSONPathError
from .tester import StepRecord, Tester


class HTTPFacet:
    """Returned by ``Tester.http()``. Each verb method starts a step."""

    def __init__(self, tester: Tester) -> None:
        self._t = tester

    def get(self, path: str) -> "HTTPStep":
        return self._req("GET", path)

    def post(self, path: str) -> "HTTPStep":
        return self._req("POST", path)

    def put(self, path: str) -> "HTTPStep":
        return self._req("PUT", path)

    def patch(self, path: str) -> "HTTPStep":
        return self._req("PATCH", path)

    def delete(self, path: str) -> "HTTPStep":
        return self._req("DELETE", path)

    def head(self, path: str) -> "HTTPStep":
        return self._req("HEAD", path)

    def _req(self, method: str, path: str) -> "HTTPStep":
        self._t._flush_pending()
        step = HTTPStep(self._t, method, path)
        self._t._set_pending(step)
        return step


class HTTPStep:
    """One HTTP call. Lazy-send on first Expect/Extract."""

    def __init__(self, tester: Tester, method: str, path: str) -> None:
        self._t = tester
        self._method = method
        self._path = path
        self._headers: dict[str, str] = {}
        self._body: Optional[bytes] = None
        self._sent = False
        self._committed = False
        self._abort = False
        self._resp: Optional[httpx.Response] = None
        self._resp_body = b""
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    # ── builders ──────────────────────────────────────────────────────

    def header(self, k: str, v: str) -> "HTTPStep":
        if self._sent:
            return self._fail("header() after send")
        self._headers[k] = interpolate(v, self._t._snapshot_vars())
        return self

    def json(self, v: Any) -> "HTTPStep":
        if self._sent:
            return self._fail("json() after send")
        try:
            raw = json.dumps(v).encode()
        except (TypeError, ValueError) as e:
            self._abort = True
            return self._fail(f"marshal body: {e}")
        self._body = interpolate(raw.decode(), self._t._snapshot_vars()).encode()
        self._headers.setdefault("Content-Type", "application/json")
        return self

    def body(self, b: bytes, content_type: str = "") -> "HTTPStep":
        if self._sent:
            return self._fail("body() after send")
        if _should_interp_body(content_type):
            b = interpolate(b.decode(errors="replace"), self._t._snapshot_vars()).encode()
        self._body = b
        if content_type:
            self._headers["Content-Type"] = content_type
        return self

    # ── verdict + assertions ──────────────────────────────────────────

    def send(self) -> "HTTPStep":
        self._ensure_sent()
        return self

    def expect_status(self, code: int) -> "HTTPStep":
        if not self._ensure_sent():
            return self
        if self._resp.status_code != code:
            self._fail(f"expect_status: want {code}, got {self._resp.status_code}")
        return self

    def expect_header(self, k: str, v: str) -> "HTTPStep":
        if not self._ensure_sent():
            return self
        got = self._resp.headers.get(k, "")
        if got != v:
            self._fail(f"expect_header {k}: want {v!r}, got {got!r}")
        return self

    def expect_body_contains(self, sub: str) -> "HTTPStep":
        if not self._ensure_sent():
            return self
        if sub.encode() not in self._resp_body:
            self._fail(f"expect_body_contains: {sub!r} not found")
        return self

    def expect_json_path(self, path: str, want: Any) -> "HTTPStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_path(path)
        except JSONPathError as e:
            return self._fail(f"expect_json_path {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(f"expect_json_path {path}: want {want!r}, got {got!r}")
        return self

    def expect_json_array_len(self, path: str, n: int) -> "HTTPStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_path(path)
        except JSONPathError as e:
            return self._fail(f"expect_json_array_len {path}: {e}")
        if not isinstance(got, list):
            return self._fail(f"expect_json_array_len {path}: not an array")
        if len(got) != n:
            self._fail(f"expect_json_array_len {path}: want {n}, got {len(got)}")
        return self

    def extract(self, path: str, name: str) -> "HTTPStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_path(path)
        except JSONPathError as e:
            return self._fail(f"extract {path}: {e}")
        self._t.set_var(name, _stringify(got))
        return self

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # ── internals ─────────────────────────────────────────────────────

    def _fail(self, msg: str) -> "HTTPStep":
        self._failures.append(msg)
        return self

    def _eval_path(self, path: str):
        doc = json.loads(self._resp_body or b"null")
        return resolve_jsonpath(doc, path)

    def _build_url(self) -> str:
        p = interpolate(self._path, self._t._snapshot_vars())
        if p.startswith(("http://", "https://")):
            return p
        base = self._t.base_url
        if not base:
            return p
        if not p.startswith("/"):
            p = "/" + p
        return base + p

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            self._fail("skipped: fail-fast triggered by earlier step")
            return False
        url = self._build_url()
        try:
            req_headers = dict(self._t._default_headers)
            req_headers.update(self._headers)
            self._started_at = time.time()
            self._resp = self._t._http.request(
                self._method, url, headers=req_headers, content=self._body,
            )
            self._ended_at = time.time()
            self._resp_body = self._resp.content
        except Exception as e:  # network errors, etc.
            self._ended_at = time.time()
            self._fail(f"http: {e}")
            self._abort = True
            return False
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="http",
            method=self._method,
            url=self._build_url(),
            name=f"{self._method} {self._build_url()}",
            status_or_code=self._resp.status_code if self._resp else 0,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)
        _emit_allure_step(self._t, rec)


def _should_interp_body(ct: str) -> bool:
    ct = ct.lower()
    return ct.startswith("text/") or ct == "application/x-www-form-urlencoded"


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)
    return json.dumps(v, separators=(",", ":"))


def _emit_allure_step(tester: Tester, rec: StepRecord) -> None:
    """Best-effort hand-off into the existing Mockarty Allure plugin.

    The plugin (``mockarty.testing``) hooks pytest and exposes a
    ``with step(name)`` context manager. We can't reach into that from a
    pure SDK with no test context, so the SDK records the step on the
    Tester and leaves Allure integration to the pytest plugin (which
    sees the report via the tester fixture).
    """
    # Intentionally a no-op for now — the Tester report is the
    # authoritative artefact; pytest plugin consumes it.
    _ = tester, rec
