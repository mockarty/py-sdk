"""Server-Sent Events test client with auto-step capture.

Subscribes to an SSE endpoint, parses the framed ``data:``/``event:``/
``id:`` lines per the WHATWG `Server-Sent Events`_ spec, and yields
:class:`SseEvent` instances. One step is recorded per call to
:meth:`SseClient.collect` covering the total event count + duration.

.. _Server-Sent Events: https://html.spec.whatwg.org/multipage/server-sent-events.html
"""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

import httpx

from .telemetry import NopRecorder, Step, StepRecorder, cap_preview, new_step_key


@dataclass
class SseEvent:
    """One parsed Server-Sent Event."""

    data: str
    id: Optional[str] = None
    event: Optional[str] = None
    retry: Optional[int] = None
    raw_lines: list[str] = field(default_factory=list)


class SseClient:
    """Sync SSE subscriber.

    The client supports two read modes:

    * :meth:`collect` — pull up to ``max_events`` events with a
      total deadline; returns when the deadline or the cap fires.
      Suited to assertion-style tests that expect "should produce
      exactly N events".
    * :meth:`stream` — generator that yields events lazily; the
      caller breaks when satisfied. Suited to long-lived tests.

    Both record one step per CALL (not per event) so the TCM timeline
    is readable even for high-volume streams.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        recorder: Optional[StepRecorder] = None,
        timeout: float = 30.0,
        payload_cap: int = 1024,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not url:
            raise ValueError("mockarty sse: empty url")
        self._url = url
        self._headers = {"Accept": "text/event-stream", **(headers or {})}
        self._recorder = recorder if recorder is not None else NopRecorder()
        self._payload_cap = max(0, payload_cap)
        self._owned_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout, read=None))
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._owned_client and self._client is not None:
            self._client.close()

    def __enter__(self) -> "SseClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def collect(self, max_events: int = 1, max_duration: float = 30.0) -> list[SseEvent]:
        """Pull up to ``max_events`` events or until ``max_duration``
        seconds elapse. Returns the events received so far when either
        limit fires; never raises on timeout.

        Step classification (review fix — the previous version always
        recorded "passed" even when the deadline fired with zero
        events, which masked unreachable / silent streams as if the
        run had succeeded):

          - HTTP non-2xx                  → "failed"
          - transport error               → "broken"
          - deadline AND zero events      → "broken" (env didn't send)
          - cap hit OR deadline + N events → "passed"
        """
        if max_events <= 0:
            raise ValueError("mockarty sse: max_events must be >= 1")
        events: list[SseEvent] = []
        started = time.time()
        deadline = started + max_duration
        deadline_fired = False
        try:
            with self._client.stream("GET", self._url, headers=self._headers) as resp:
                if resp.status_code >= 400:
                    self._record("sse:collect", started, "failed",
                                 RuntimeError(f"HTTP {resp.status_code}"),
                                 {"http_status": str(resp.status_code), "count": "0"})
                    return events
                for event in _parse_sse_stream(resp.iter_lines()):
                    events.append(event)
                    if len(events) >= max_events:
                        break
                    if time.time() >= deadline:
                        deadline_fired = True
                        break
        except httpx.HTTPError as exc:
            self._record("sse:collect", started, "broken", exc, {"count": str(len(events))})
            raise
        if deadline_fired and not events:
            self._record("sse:collect", started, "broken",
                         RuntimeError("deadline expired before first event"), {
                "count": "0",
                "url": cap_preview(self._url, self._payload_cap),
                "reason": "deadline",
            })
            return events
        self._record("sse:collect", started, "passed", None, {
            "count": str(len(events)),
            "url": cap_preview(self._url, self._payload_cap),
            "reason": "deadline" if deadline_fired else "cap",
        })
        return events

    def stream(self) -> Iterator[SseEvent]:
        """Yield events lazily. The caller is responsible for breaking
        when satisfied. The step is recorded when the generator
        terminates (either by exhaustion or by the caller breaking)."""
        started = time.time()
        count = 0
        try:
            with self._client.stream("GET", self._url, headers=self._headers) as resp:
                if resp.status_code >= 400:
                    self._record("sse:stream", started, "failed",
                                 RuntimeError(f"HTTP {resp.status_code}"),
                                 {"http_status": str(resp.status_code), "count": "0"})
                    return
                for event in _parse_sse_stream(resp.iter_lines()):
                    count += 1
                    yield event
        except httpx.HTTPError as exc:
            self._record("sse:stream", started, "broken", exc, {"count": str(count)})
            raise
        finally:
            self._record("sse:stream", started, "passed", None, {
                "count": str(count),
                "url": cap_preview(self._url, self._payload_cap),
            })

    def _record(
        self,
        name: str,
        started: float,
        status: str,
        err: Optional[BaseException],
        params: dict[str, str],
    ) -> None:
        finished = time.time()
        with self._lock:
            seq = next(self._counter)
        step = Step(
            key=new_step_key(name, seq),
            name=name,
            status=status,
            started_at=started,
            finished_at=finished,
            duration_ms=max(0, int((finished - started) * 1000)),
            parameters=params,
            message=str(err) if err else "",
        )
        self._recorder.record(step)


def _parse_sse_stream(lines: Iterator[str]) -> Iterator[SseEvent]:
    """Parse a stream of UTF-8 lines into :class:`SseEvent` instances.

    Follows the WHATWG spec dispatch rules:
    - blank line → dispatch the accumulated event.
    - line starting with ``:`` → comment (skip).
    - ``field`` or ``field:value`` → set field.
    - unknown field name → ignore (per spec).

    The httpx ``iter_lines`` strips the trailing ``\\n`` already.
    """
    data_buf: list[str] = []
    event_name: Optional[str] = None
    event_id: Optional[str] = None
    retry: Optional[int] = None
    raw_lines: list[str] = []
    for line in lines:
        raw_lines.append(line)
        if line == "":
            if data_buf:
                yield SseEvent(
                    data="\n".join(data_buf),
                    id=event_id,
                    event=event_name,
                    retry=retry,
                    raw_lines=list(raw_lines),
                )
            # Reset for the next event.
            data_buf = []
            event_name = None
            retry = None
            raw_lines = []
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
        else:
            field, value = line, ""
        if field == "data":
            data_buf.append(value)
        elif field == "event":
            event_name = value
        elif field == "id":
            event_id = value
        elif field == "retry":
            try:
                retry = int(value)
            except ValueError:
                pass
        # Unknown fields ignored per spec.
