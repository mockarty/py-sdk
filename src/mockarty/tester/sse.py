# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""SSE facet — mirrors ``sdk/go-sdk/tester/sse.go``.

Uses httpx streaming so no extra dependency. Parses the WHATWG
Server-Sent Events line format.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .interpolate import interpolate
from .jsonpath import equal_json_scalar, resolve_jsonpath, JSONPathError
from .tester import StepRecord, Tester


@dataclass
class SSEEvent:
    event: str = ""  # "" → default "message"
    data: str = ""
    id: str = ""
    retry: int = 0


class SSEFacet:
    def __init__(self, tester: Tester, endpoint: str) -> None:
        self._t = tester
        self._endpoint = endpoint

    def subscribe(self) -> "SSEStep":
        self._t._flush_pending()
        step = SSEStep(self._t, self._endpoint)
        self._t._set_pending(step)
        return step


class SSEStep:
    def __init__(self, tester: Tester, endpoint: str) -> None:
        self._t = tester
        self._endpoint = interpolate(endpoint, tester._snapshot_vars())
        self._listen = 5.0
        self._headers: dict[str, str] = {}
        self._last_event_id = ""
        self._sent = False
        self._committed = False
        self._abort = False
        self._events: list[SSEEvent] = []
        self._status_code = 0
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    # builders
    def listen(self, seconds: float) -> "SSEStep":
        if self._sent:
            return self._fail("listen() after subscribe")
        if seconds > 0:
            self._listen = seconds
        return self

    def header(self, k: str, v: str) -> "SSEStep":
        if self._sent:
            return self._fail("header() after subscribe")
        self._headers[k] = interpolate(v, self._t._snapshot_vars())
        return self

    def last_event_id(self, id_: str) -> "SSEStep":
        if self._sent:
            return self._fail("last_event_id() after subscribe")
        self._last_event_id = id_
        return self

    # assertions
    def expect_min_events(self, n: int) -> "SSEStep":
        if not self._ensure_sent():
            return self
        if len(self._events) < n:
            self._fail(f"expect_min_events: want >={n}, got {len(self._events)}")
        return self

    def expect_exact_events(self, n: int) -> "SSEStep":
        if not self._ensure_sent():
            return self
        if len(self._events) != n:
            self._fail(f"expect_exact_events: want {n}, got {len(self._events)}")
        return self

    def expect_event(self, name: str) -> "SSEStep":
        if not self._ensure_sent():
            return self
        if self._find_event(name) is None:
            self._fail(f"expect_event {name!r}: not received ({len(self._events)} events)")
        return self

    def expect_event_data(self, name: str, data: str) -> "SSEStep":
        if not self._ensure_sent():
            return self
        ev = self._find_event(name)
        if ev is None:
            return self._fail(f"expect_event_data {name!r}: event not received")
        if ev.data != data:
            self._fail(f"expect_event_data {name!r}: want {data!r}, got {ev.data!r}")
        return self

    def expect_json_path(self, event_name: str, path: str, want: Any) -> "SSEStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval(event_name, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"expect_json_path[{event_name}] {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(f"expect_json_path[{event_name}] {path}: want {want!r}, got {got!r}")
        return self

    def extract(self, event_name: str, path: str, var_name: str) -> "SSEStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval(event_name, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"extract[{event_name}] {path}: {e}")
        from .http import _stringify
        self._t.set_var(var_name, _stringify(got))
        return self

    def events(self) -> list[SSEEvent]:
        self._ensure_sent()
        return list(self._events)

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # internals
    def _fail(self, msg: str) -> "SSEStep":
        self._failures.append(msg)
        return self

    def _find_event(self, name: str) -> Optional[SSEEvent]:
        target = name or "message"
        for ev in self._events:
            ev_name = ev.event or "message"
            if ev_name == target:
                return ev
        return None

    def _eval(self, event_name: str, path: str):
        ev = self._find_event(event_name)
        if ev is None:
            raise ValueError(f"event {event_name!r} not received")
        doc = json.loads(ev.data)
        return resolve_jsonpath(doc, path)

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            return self._fail("skipped: fail-fast triggered by earlier step")._abort  # type: ignore

        url = self._endpoint
        if not url.startswith(("http://", "https://")):
            if self._t.base_url:
                if not url.startswith("/"):
                    url = "/" + url
                url = self._t.base_url + url
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            **self._t._default_headers,
            **self._headers,
        }
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id
        self._started_at = time.time()
        try:
            with self._t._http.stream("GET", url, headers=headers, timeout=self._listen) as resp:
                self._status_code = resp.status_code
                if resp.status_code // 100 != 2:
                    self._fail(f"sse: HTTP {resp.status_code}")
                    self._abort = True
                    self._ended_at = time.time()
                    return False
                self._events = _parse_sse(resp.iter_lines(), self._listen, self._started_at)
        except httpx.ReadTimeout:
            # End-of-listen-window — legitimate "nothing came" outcome.
            pass
        except Exception as e:
            self._fail(f"sse: {e}")
            self._abort = True
            self._ended_at = time.time()
            return False
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="sse",
            method="GET",
            url=self._endpoint,
            name=f"sse {self._endpoint}",
            status_or_code=self._status_code,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)


def _parse_sse(lines, listen_sec: float, started_at: float) -> list[SSEEvent]:
    out: list[SSEEvent] = []
    cur = SSEEvent()
    data_parts: list[str] = []
    seen = False
    deadline = started_at + listen_sec

    def dispatch():
        nonlocal cur, data_parts, seen
        if not seen:
            return
        cur.data = "\n".join(data_parts)
        out.append(cur)
        cur = SSEEvent()
        data_parts = []
        seen = False

    for line in lines:
        if time.time() > deadline:
            break
        if line == "":
            dispatch()
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field_, _, value = line.partition(":")
        else:
            field_, value = line, ""
        if value.startswith(" "):
            value = value[1:]
        if field_ == "event":
            cur.event = value
            seen = True
        elif field_ == "data":
            data_parts.append(value)
            seen = True
        elif field_ == "id":
            cur.id = value
            seen = True
        elif field_ == "retry":
            try:
                cur.retry = int(value)
                seen = True
            except ValueError:
                pass
    dispatch()
    return out
