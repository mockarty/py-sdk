# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""GraphQL facet — mirrors ``sdk/go-sdk/tester/graphql.go``.

Direct httpx call (not via HTTP facet) so chain pending machinery
does not race with the underlying transport step.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

from .interpolate import interpolate
from .jsonpath import equal_json_scalar, resolve_jsonpath, JSONPathError
from .tester import StepRecord, Tester


class GraphQLFacet:
    def __init__(self, tester: Tester, endpoint: str) -> None:
        self._t = tester
        self._endpoint = endpoint

    def query(self, operation: str, variables: Optional[dict] = None) -> "GraphQLStep":
        self._t._flush_pending()
        step = GraphQLStep(self._t, self._endpoint, operation, variables)
        self._t._set_pending(step)
        return step


class GraphQLStep:
    def __init__(
        self,
        tester: Tester,
        endpoint: str,
        operation: str,
        variables: Optional[dict],
    ) -> None:
        self._t = tester
        vars_ = tester._snapshot_vars()
        self._endpoint = interpolate(endpoint, vars_)
        self._operation = interpolate(operation, vars_)
        self._variables = variables
        self._headers: dict[str, str] = {}
        self._sent = False
        self._committed = False
        self._abort = False
        self._resp: Optional[httpx.Response] = None
        self._parsed: dict[str, Any] = {}
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    def header(self, k: str, v: str) -> "GraphQLStep":
        if self._sent:
            return self._fail("header() after send")
        self._headers[k] = interpolate(v, self._t._snapshot_vars())
        return self

    def expect_status(self, code: int) -> "GraphQLStep":
        if not self._ensure_sent():
            return self
        if self._resp is not None and self._resp.status_code != code:
            self._fail(f"expect_status: want {code}, got {self._resp.status_code}")
        return self

    def expect_no_errors(self) -> "GraphQLStep":
        if not self._ensure_sent():
            return self
        errs = self._parsed.get("errors") or []
        if errs:
            msgs = [e.get("message", "") for e in errs]
            self._fail(f"expect_no_errors: {len(errs)} error(s): {msgs}")
        return self

    def expect_errors(self, n: int) -> "GraphQLStep":
        if not self._ensure_sent():
            return self
        errs = self._parsed.get("errors") or []
        if len(errs) < n:
            self._fail(f"expect_errors: want >={n}, got {len(errs)}")
        return self

    def expect_field(self, path: str, want: Any) -> "GraphQLStep":
        if not self._ensure_sent():
            return self
        try:
            got = resolve_jsonpath(self._envelope(), path)
        except JSONPathError as e:
            return self._fail(f"expect_field {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(f"expect_field {path}: want {want!r}, got {got!r}")
        return self

    def extract(self, path: str, name: str) -> "GraphQLStep":
        if not self._ensure_sent():
            return self
        try:
            got = resolve_jsonpath(self._envelope(), path)
        except JSONPathError as e:
            return self._fail(f"extract {path}: {e}")
        from .http import _stringify  # share canonical stringify

        self._t.set_var(name, _stringify(got))
        return self

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # ── internals ─────────────────────────────────────────────────────

    def _fail(self, msg: str) -> "GraphQLStep":
        self._failures.append(msg)
        return self

    def _envelope(self) -> dict:
        env: dict[str, Any] = {"data": self._parsed.get("data")}
        if self._parsed.get("errors"):
            env["errors"] = self._parsed["errors"]
        if self._parsed.get("extensions"):
            env["extensions"] = self._parsed["extensions"]
        return env

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            self._fail("skipped: fail-fast triggered by earlier step")
            return False
        body = {"query": self._operation}
        if self._variables is not None:
            body["variables"] = self._variables
        raw = json.dumps(body)
        raw = interpolate(raw, self._t._snapshot_vars())

        url = self._endpoint
        if not url.startswith(("http://", "https://")):
            if self._t.base_url:
                if not url.startswith("/"):
                    url = "/" + url
                url = self._t.base_url + url

        headers = {
            "Content-Type": "application/json",
            **self._t._default_headers,
            **self._headers,
        }
        try:
            self._started_at = time.time()
            self._resp = self._t._http.request(
                "POST", url, headers=headers, content=raw.encode()
            )
            self._ended_at = time.time()
        except Exception as e:
            self._ended_at = time.time()
            self._fail(f"graphql: {e}")
            self._abort = True
            return False
        try:
            self._parsed = self._resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            self._fail(f"graphql: parse response: {e}")
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
            protocol="graphql",
            method="POST",
            url=self._endpoint,
            name=f"graphql {self._endpoint}",
            status_or_code=self._resp.status_code if self._resp else 0,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)
