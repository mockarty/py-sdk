# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""gRPC facet for the fluent Tester DSL.

Mirrors ``sdk/go-sdk/tester/grpc.go`` and the Java port so a gRPC suite
translates 1:1 across the three SDKs. The facet is the fluent assertion layer
over a user-supplied *invoker* — any object with::

    invoke_json(full_method: str, req: Any) -> dict   # raises on a gRPC error

The facet performs NO protobuf reflection itself; the invoker (a real gRPC
client, or an in-memory fake in tests) does the transcoding. Requests and
responses are JSON-shaped at the SDK boundary.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from .interpolate import interpolate
from .jsonpath import JSONPathError, resolve_jsonpath
from .jsonpath import equal_json_scalar
from .tester import StepRecord, Tester


class GRPCFacet:
    def __init__(self, tester: Tester, invoker: Any) -> None:
        self._t = tester
        self._invoker = invoker

    def call(self, full_method: str, req: Any = None) -> "GRPCStep":
        self._t._flush_pending()
        step = GRPCStep(
            self._t, self._invoker,
            interpolate(full_method, self._t._snapshot_vars()), req,
        )
        self._t._set_pending(step)
        return step


class GRPCStep:
    def __init__(self, tester: Tester, invoker: Any, full_method: str, req: Any) -> None:
        self._t = tester
        self._invoker = invoker
        self._full_method = full_method
        self._req = req
        self._resp: dict = {}
        self._err: Optional[Exception] = None
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    # ── assertions ────────────────────────────────────────────────────

    def expect_ok(self) -> "GRPCStep":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            self._fail(f"expect_ok: {self._err}")
        return self

    def expect_error(self) -> "GRPCStep":
        self._ensure_sent()
        if self._err is None:
            self._fail("expect_error: call succeeded")
        return self

    def expect_field(self, path: str, want: Any) -> "GRPCStep":
        """Alias for :meth:`expect_json_path` — matches the canonical chain verb."""
        return self.expect_json_path(path, want)

    def expect_json_path(self, path: str, want: Any) -> "GRPCStep":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            return self._fail(f"expect_json_path {path}: call errored: {self._err}")
        try:
            got = resolve_jsonpath(self._resp, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"expect_json_path {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(f"expect_json_path {path}: want {want!r}, got {got!r}")
        return self

    def extract(self, path: str, var_name: str) -> "GRPCStep":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            return self._fail(f"extract {path}: call errored: {self._err}")
        try:
            got = resolve_jsonpath(self._resp, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"extract {path}: {e}")
        self._t.set_var(var_name, _stringify(got))
        return self

    def response(self) -> dict:
        self._ensure_sent()
        return dict(self._resp)

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # ── internals ─────────────────────────────────────────────────────

    def _fail(self, msg: str) -> "GRPCStep":
        self._failures.append(msg)
        return self

    def _ensure_sent(self) -> bool:
        if self._sent:
            return self._err is None and not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            self._fail("skipped: fail-fast triggered by earlier step")
            return False
        # Per-step request interpolation — round-trip through JSON so {{var}}
        # substitution is consistent with HTTP / Kafka.
        if self._req is not None:
            try:
                self._req = json.loads(
                    interpolate(json.dumps(self._req), self._t._snapshot_vars())
                )
            except (TypeError, ValueError):
                pass  # leave req as-is if it isn't JSON-serialisable
        self._started_at = time.time()
        try:
            resp = self._invoker.invoke_json(self._full_method, self._req)
            self._resp = resp if isinstance(resp, dict) else {}
        except Exception as e:  # noqa: BLE001 — any invoker error is a gRPC error
            self._err = e
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="grpc",
            method="unary",
            name=f"grpc {self._full_method}",
            url=self._full_method,
            status_or_code=0 if self._err is None else 1,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)


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
    return json.dumps(v)
