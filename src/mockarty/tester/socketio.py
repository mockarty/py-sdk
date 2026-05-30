# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Socket.IO facet — mirrors ``sdk/go-sdk/tester/socketio.go``.

Distinct from the WebSocket facet — it speaks the Engine.IO/Socket.IO
framing (handshake, namespace connect, named events) via
``mockarty.protocols.socketio.Client``.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from ..protocols import socketio as sioproto
from .interpolate import interpolate
from .jsonpath import JSONPathError, equal_json_scalar, resolve_jsonpath
from .tester import StepRecord, Tester


class SocketIOFacet:
    def __init__(self, tester: Tester, url: str) -> None:
        self._t = tester
        self._url = url

    def connect(self) -> "SocketIOStep":
        self._t._flush_pending()
        step = SocketIOStep(self._t, interpolate(self._url, self._t._snapshot_vars()))
        self._t._set_pending(step)
        return step


class SocketIOStep:
    def __init__(self, tester: Tester, url: str) -> None:
        self._t = tester
        self._url = url
        self._namespace = "/"
        self._window = 3.0
        self._conn_wait = 3.0
        self._headers: list[tuple[str, str]] = []
        self._outbound: list[tuple[str, tuple]] = []
        self._received: list[sioproto.Event] = []
        self._connect_err: Optional[Exception] = None
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    # ── builders ──────────────────────────────────────────────────────

    def namespace(self, ns: str) -> "SocketIOStep":
        if self._guard("namespace"):
            return self
        self._namespace = interpolate(ns, self._t._snapshot_vars())
        return self

    def header(self, k: str, v: str) -> "SocketIOStep":
        if self._guard("header"):
            return self
        self._headers.append((k, interpolate(v, self._t._snapshot_vars())))
        return self

    def connect_timeout(self, seconds: float) -> "SocketIOStep":
        if self._guard("connect_timeout"):
            return self
        if seconds > 0:
            self._conn_wait = seconds
        return self

    def emit(self, event: str, *args: Any) -> "SocketIOStep":
        if self._guard("emit"):
            return self
        v = self._t._snapshot_vars()
        interpolated = tuple(
            interpolate(a, v) if isinstance(a, str) else a for a in args
        )
        self._outbound.append((interpolate(event, v), interpolated))
        return self

    def collect(self, seconds: float) -> "SocketIOStep":
        if not self._sent and seconds > 0:
            self._window = seconds
        self._ensure_sent()
        return self

    # ── assertions ────────────────────────────────────────────────────

    def expect_connected(self) -> "SocketIOStep":
        self._ensure_sent()
        if self._connect_err is not None:
            self._fail(f"expect_connected: {self._connect_err}")
        return self

    def expect_event(self, name: str) -> "SocketIOStep":
        if not self._ensure_sent():
            return self
        if self._find(name) < 0:
            self._fail(f"expect_event: {name!r} not received")
        return self

    def expect_event_count(self, name: str, n: int) -> "SocketIOStep":
        if not self._ensure_sent():
            return self
        count = sum(1 for e in self._received if e.name == name)
        if count != n:
            self._fail(f"expect_event_count[{name}]: want {n}, got {count}")
        return self

    def expect_received_count(self, n: int) -> "SocketIOStep":
        if not self._ensure_sent():
            return self
        if len(self._received) != n:
            self._fail(f"expect_received_count: want {n}, got {len(self._received)}")
        return self

    def expect_event_arg_contains(self, name: str, sub: str) -> "SocketIOStep":
        if not self._ensure_sent():
            return self
        idx = self._find(name)
        if idx < 0:
            return self._fail(f"expect_event_arg_contains: {name!r} not received")
        if not self._received[idx].args:
            return self._fail(f"expect_event_arg_contains[{name}]: event has no args")
        if sub not in json.dumps(self._received[idx].args[0]):
            self._fail(f"expect_event_arg_contains[{name}]: {sub!r} not found")
        return self

    def expect_event_json_path(self, name: str, path: str, want: Any) -> "SocketIOStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_arg(name, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"expect_event_json_path[{name}] {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(
                f"expect_event_json_path[{name}] {path}: want {want!r}, got {got!r}"
            )
        return self

    def extract(self, name: str, path: str, var_name: str) -> "SocketIOStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_arg(name, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"extract[{name}] {path}: {e}")
        self._t.set_var(var_name, _stringify(got))
        return self

    def received(self) -> list:
        self._ensure_sent()
        return list(self._received)

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # ── internals ─────────────────────────────────────────────────────

    def _fail(self, msg: str) -> "SocketIOStep":
        self._failures.append(msg)
        return self

    def _guard(self, method: str) -> bool:
        if self._sent:
            self._fail(f"{method}() called after connect")
            return True
        return False

    def _find(self, name: str) -> int:
        for i, e in enumerate(self._received):
            if e.name == name:
                return i
        return -1

    def _eval_arg(self, name: str, path: str) -> Any:
        idx = self._find(name)
        if idx < 0:
            raise ValueError(f"event {name!r} not received")
        if not self._received[idx].args:
            raise ValueError(f"event {name!r} has no args")
        return resolve_jsonpath(self._received[idx].args[0], path)

    def _ensure_sent(self) -> bool:
        if self._sent:
            return self._connect_err is None and not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            self._fail("skipped: fail-fast triggered by earlier step")
            return False
        self._started_at = time.time()
        client = None
        try:
            client = sioproto.Client.dial(
                self._url, headers=dict(self._headers), timeout=self._conn_wait
            )
            client.connect(self._namespace, wait=self._conn_wait)
            for event, args in self._outbound:
                client.emit(self._namespace, event, *args)
            self._received = client.collect(self._window)
        except Exception as e:
            self._connect_err = e
            self._fail(f"socket.io: {e}")
            self._abort = True
            self._ended_at = time.time()
            return False
        finally:
            if client is not None:
                client.close()
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="socketio",
            method="event",
            name=f"socket.io {self._url}",
            url=self._url,
            status_or_code=len(self._received),
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
