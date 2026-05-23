"""WebSocket test client with auto-step capture.

Uses the ``websockets`` package (RFC 6455 reference implementation
for Python) via its sync façade. The dependency is optional — pull
it via the SDK's ``protocols`` extra::

    pip install 'mockarty[protocols]'

The client surfaces a small sync API tuned for CI tests: ``connect``,
``send``, ``recv``, ``close``. Each ``send`` and ``recv`` records a
step so the TCM run shows a per-frame timeline. Long-running
subscriptions are best handled via :class:`SseClient` instead.
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from typing import Any, Optional, Union

from .telemetry import NopRecorder, Step, StepRecorder, cap_preview, new_step_key


class WebSocketImportError(ImportError):
    """Raised when the ``websockets`` package is not installed.

    Provides a friendly hint pointing at the SDK's ``protocols`` extra
    so users don't have to hunt for the upstream package name."""

    def __init__(self) -> None:
        super().__init__(
            "mockarty websocket: the 'websockets' package is required. "
            "Install with: pip install 'mockarty[protocols]'"
        )


class WebSocketClient:
    """Sync WebSocket client.

    Parameters
    ----------
    url:
        ``ws://`` or ``wss://`` endpoint.
    headers:
        Extra HTTP headers sent in the opening handshake.
    recorder:
        Optional step recorder.
    open_timeout:
        Handshake deadline (seconds). Default 10.
    payload_cap:
        Max bytes of frame payload captured into step parameters.
        Default 1024.

    The underlying ``websockets`` client connection is opened lazily
    on the first :meth:`send` / :meth:`recv`. Call :meth:`close` (or
    use as a context manager) to release the socket.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        recorder: Optional[StepRecorder] = None,
        open_timeout: float = 10.0,
        payload_cap: int = 1024,
    ) -> None:
        if not url:
            raise ValueError("mockarty websocket: empty url")
        self._url = url
        self._headers = dict(headers or {})
        self._recorder = recorder if recorder is not None else NopRecorder()
        self._open_timeout = open_timeout
        self._payload_cap = max(0, payload_cap)
        self._conn: Any = None
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def __enter__(self) -> "WebSocketClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def _connect_if_needed(self) -> Any:
        if self._conn is not None:
            return self._conn
        try:
            from websockets.sync.client import connect as _ws_connect
        except ImportError as exc:  # pragma: no cover - depends on env
            raise WebSocketImportError() from exc
        # websockets sync.client accepts `additional_headers` as list-of-tuples
        # OR Headers; pass the dict for compatibility with both modern + legacy.
        self._conn = _ws_connect(
            self._url,
            additional_headers=list(self._headers.items()),
            open_timeout=self._open_timeout,
        )
        return self._conn

    def send(self, payload: Union[str, bytes, dict, list]) -> None:
        """Send one frame. Dicts / lists are JSON-encoded; bytes go
        as a binary frame; strings as text."""
        step_name = "ws:send"
        started = time.time()
        try:
            conn = self._connect_if_needed()
            if isinstance(payload, (dict, list)):
                wire = json.dumps(payload)
            else:
                wire = payload
            conn.send(wire)
        except Exception as exc:
            self._record(step_name, started, "broken", exc, {
                "payload": cap_preview(_as_str(payload), self._payload_cap),
            })
            raise
        self._record(step_name, started, "passed", None, {
            "payload": cap_preview(_as_str(payload), self._payload_cap),
        })

    def recv(self, *, timeout: Optional[float] = None) -> Union[str, bytes]:
        """Wait for one frame. Returns the raw text/bytes payload.

        ``timeout`` overrides the connection-default read timeout.
        Pass ``None`` to wait indefinitely (capped by ``open_timeout``
        on the handshake side).
        """
        step_name = "ws:recv"
        started = time.time()
        try:
            conn = self._connect_if_needed()
            frame = conn.recv(timeout=timeout) if timeout is not None else conn.recv()
        except Exception as exc:
            self._record(step_name, started, "broken", exc, {"timeout": str(timeout)})
            raise
        self._record(step_name, started, "passed", None, {
            "payload": cap_preview(_as_str(frame), self._payload_cap),
            "size": str(len(frame) if isinstance(frame, (str, bytes)) else 0),
        })
        return frame

    def recv_json(self, *, timeout: Optional[float] = None) -> Any:
        """Convenience wrapper: pull a text frame and JSON-decode it."""
        frame = self.recv(timeout=timeout)
        if isinstance(frame, bytes):
            frame = frame.decode("utf-8")
        return json.loads(frame)

    def close(self) -> None:
        """Close the underlying WebSocket. Idempotent."""
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        finally:
            self._conn = None

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


def _as_str(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


