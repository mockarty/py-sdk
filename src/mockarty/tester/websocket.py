# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Raw WebSocket facet for the fluent Tester DSL.

Mirrors ``sdk/go-sdk/tester/websocket.go`` and the Java port so a WS suite
translates 1:1 across the three SDKs. Distinct from the Socket.IO facet — this
speaks plain WebSocket frames (text + binary) with no Engine.IO framing, over
the ``websockets`` package (the same optional dependency the Socket.IO facet
uses). Connect, flush the queued outbound frames, collect inbound frames for a
bounded ``listen`` window (the window elapsing or a clean close is NOT a
failure), then assert on the received messages.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from ..protocols.websocket import WebSocketClient
from .interpolate import interpolate
from .jsonpath import JSONPathError, equal_json_scalar, resolve_jsonpath
from .tester import StepRecord, Tester


class WebSocketFacet:
    def __init__(self, tester: Tester, url: str) -> None:
        self._t = tester
        self._url = url

    def connect(self) -> "WebSocketStep":
        self._t._flush_pending()
        step = WebSocketStep(self._t, interpolate(self._url, self._t._snapshot_vars()))
        self._t._set_pending(step)
        return step


class WebSocketStep:
    def __init__(self, tester: Tester, url: str) -> None:
        self._t = tester
        self._url = url
        self._listen = 5.0
        self._headers: list[tuple[str, str]] = []
        self._outbound: list[Any] = []  # str | bytes | (dict|list)
        self._received: list[Any] = []  # str | bytes
        self._connect_err: Optional[Exception] = None
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    # ── builders ──────────────────────────────────────────────────────

    def header(self, k: str, v: str) -> "WebSocketStep":
        if self._guard("header"):
            return self
        self._headers.append((k, interpolate(v, self._t._snapshot_vars())))
        return self

    def listen(self, seconds: float) -> "WebSocketStep":
        if self._guard("listen"):
            return self
        if seconds and seconds > 0:
            self._listen = seconds
        return self

    def send(self, text: str) -> "WebSocketStep":
        if self._guard("send"):
            return self
        self._outbound.append(interpolate(text, self._t._snapshot_vars()))
        return self

    def send_json(self, value: Any) -> "WebSocketStep":
        if self._guard("send_json"):
            return self
        self._outbound.append(value)
        return self

    def send_binary(self, payload: bytes) -> "WebSocketStep":
        if self._guard("send_binary"):
            return self
        self._outbound.append(payload if payload is not None else b"")
        return self

    # ── assertions ────────────────────────────────────────────────────

    def expect_connected(self) -> "WebSocketStep":
        self._ensure_sent()
        if self._connect_err is not None:
            self._fail(f"expect_connected: {self._connect_err}")
        return self

    def expect_received_count(self, n: int) -> "WebSocketStep":
        if not self._ensure_sent():
            return self
        if len(self._received) != n:
            self._fail(f"expect_received_count: want {n}, got {len(self._received)}")
        return self

    def expect_received_at_least(self, n: int) -> "WebSocketStep":
        if not self._ensure_sent():
            return self
        if len(self._received) < n:
            self._fail(f"expect_received_at_least: want >={n}, got {len(self._received)}")
        return self

    def expect_message_contains(self, idx: int, sub: str) -> "WebSocketStep":
        if not self._ensure_sent():
            return self
        msg = self._at(idx)
        if msg is None:
            return self._fail(f"expect_message_contains[{idx}]: no such message ({len(self._received)} received)")
        if sub not in _as_text(msg):
            self._fail(f"expect_message_contains[{idx}]: {sub!r} not in {_as_text(msg)!r}")
        return self

    def expect_json_path(self, idx: int, path: str, want: Any) -> "WebSocketStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_at(idx, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"expect_json_path[{idx}] {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(f"expect_json_path[{idx}] {path}: want {want!r}, got {got!r}")
        return self

    def extract(self, idx: int, path: str, var_name: str) -> "WebSocketStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_at(idx, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"extract[{idx}] {path}: {e}")
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

    def _fail(self, msg: str) -> "WebSocketStep":
        self._failures.append(msg)
        return self

    def _guard(self, method: str) -> bool:
        if self._sent:
            self._fail(f"{method}() called after connect")
            return True
        return False

    def _at(self, idx: int) -> Any:
        if idx < 0 or idx >= len(self._received):
            return None
        return self._received[idx]

    def _eval_at(self, idx: int, path: str) -> Any:
        msg = self._at(idx)
        if msg is None:
            raise ValueError(f"no message at index {idx}")
        return resolve_jsonpath(json.loads(_as_text(msg)), path)

    def _ws_url(self) -> str:
        u = self._url
        if u.startswith(("ws://", "wss://")):
            return u
        if u.startswith("http://"):
            return "ws://" + u[len("http://"):]
        if u.startswith("https://"):
            return "wss://" + u[len("https://"):]
        base = self._t.base_url
        if base.startswith("http://"):
            base = "ws://" + base[len("http://"):]
        elif base.startswith("https://"):
            base = "wss://" + base[len("https://"):]
        if not u.startswith("/"):
            u = "/" + u
        return base + u

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
            client = WebSocketClient(
                self._ws_url(), headers=dict(self._headers), open_timeout=self._listen
            )
            for payload in self._outbound:
                client.send(payload)
            deadline = time.time() + self._listen
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    self._received.append(client.recv(timeout=remaining))
                except Exception:
                    # Timeout / clean close ends the window — not a failure
                    # (an empty stream is visible via expect_received_*).
                    break
        except Exception as e:
            self._connect_err = e
            self._fail(f"ws: {e}")
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
            protocol="websocket",
            method="message",
            name=f"ws {self._url}",
            url=self._url,
            status_or_code=len(self._received),
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)


def _as_text(msg: Any) -> str:
    if isinstance(msg, (bytes, bytearray)):
        return bytes(msg).decode("utf-8", "replace")
    return str(msg)


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
