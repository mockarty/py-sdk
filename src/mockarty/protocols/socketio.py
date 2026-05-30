# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Minimal Socket.IO v4 (Engine.IO v4) test client — mirrors
``sdk/go-sdk/protocols/socketio``.

Connects to a Socket.IO server (a Mockarty mock or a real server) over
the WebSocket transport, connects a namespace, emits events, and
collects inbound events for assertion — distinct from a raw WebSocket
because it speaks the Engine.IO/Socket.IO framing (handshake, ping/pong,
packet types).

Transport: WebSocket only (the client connects with
``EIO=4&transport=websocket``). HTTP long-polling is intentionally not
implemented. Built on the ``websockets`` package (the SDK's ``protocols``
extra) via its sync façade.

Out of scope: binary attachments (Socket.IO packet type 5/6), ack
callbacks, and the polling transport.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


class SocketIOImportError(ImportError):
    """Raised when the ``websockets`` package is not installed."""

    def __init__(self) -> None:
        super().__init__(
            "mockarty socketio: the 'websockets' package is required. "
            "Install with: pip install 'mockarty[protocols]'"
        )


class SocketIOError(Exception):
    """Raised on dial / namespace-connect failures."""


# Engine.IO packet type prefixes (single ASCII char).
_EIO_OPEN = "0"
_EIO_CLOSE = "1"
_EIO_PING = "2"
_EIO_PONG = "3"
_EIO_MESSAGE = "4"

# Socket.IO packet type prefixes (inside an Engine.IO message).
_SIO_CONNECT = "0"
_SIO_EVENT = "2"
_SIO_CONNECT_ERROR = "4"


@dataclass
class Event:
    name: str = ""
    namespace: str = "/"
    args: list = field(default_factory=list)  # parsed JSON values
    received_at: float = 0.0


class Client:
    """Sync Socket.IO client. One client per test thread."""

    def __init__(self, conn, handshake: dict) -> None:
        self._conn = conn
        self._handshake = handshake
        self._inbound: list[Event] = []
        self._closed = False

    @property
    def handshake(self) -> dict:
        return self._handshake

    # ── construction ──────────────────────────────────────────────────

    @classmethod
    def dial(
        cls,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> "Client":
        try:
            from websockets.sync.client import connect as _ws_connect
        except ImportError as exc:  # pragma: no cover - depends on env
            raise SocketIOImportError() from exc

        ws_url = _normalize_url(url)
        try:
            conn = _ws_connect(
                ws_url,
                additional_headers=list((headers or {}).items()),
                open_timeout=timeout,
            )
        except Exception as exc:
            raise SocketIOError(f"mockarty socketio: dial {ws_url}: {exc}") from exc

        # Read the Engine.IO open handshake.
        try:
            frame = conn.recv(timeout=timeout)
        except Exception as exc:
            conn.close()
            raise SocketIOError(
                f"mockarty socketio: handshake read: {exc}"
            ) from exc
        text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
        if not text or text[0] != _EIO_OPEN:
            conn.close()
            raise SocketIOError(
                f"mockarty socketio: expected open handshake, got {text!r}"
            )
        handshake = {}
        try:
            handshake = json.loads(text[1:])
        except json.JSONDecodeError:
            pass
        return cls(conn, handshake)

    # ── operations ────────────────────────────────────────────────────

    def connect(self, namespace: str = "/", wait: float = 3.0) -> None:
        """Perform the Socket.IO namespace CONNECT and wait for the ack."""
        namespace = namespace or "/"
        pkt = _EIO_MESSAGE + _SIO_CONNECT
        if namespace != "/":
            pkt += namespace + ","
        self._send(pkt)
        deadline = time.time() + wait
        while time.time() < deadline:
            typ, ns, body = self._read_socketio(max(deadline - time.time(), 0.01))
            if typ is None:
                continue
            if typ == _SIO_CONNECT and _ns_match(ns, namespace):
                return
            if typ == _SIO_CONNECT_ERROR:
                raise SocketIOError(f"mockarty socketio: connect error: {body}")
        raise SocketIOError(f"mockarty socketio: connect to {namespace!r} timed out")

    def emit(self, namespace: str, event: str, *args: Any) -> None:
        namespace = namespace or "/"
        payload = json.dumps([event, *args])
        pkt = _EIO_MESSAGE + _SIO_EVENT
        if namespace != "/":
            pkt += namespace + ","
        pkt += payload
        self._send(pkt)

    def collect(self, window: float) -> list[Event]:
        """Read inbound frames for ``window`` seconds, accumulating EVENT
        packets (and answering Engine.IO pings)."""
        deadline = time.time() + window
        start = len(self._inbound)
        while time.time() < deadline:
            typ, ns, body = self._read_socketio(max(deadline - time.time(), 0.01))
            if typ is None:
                # Timeout / non-event frame — keep looping until the window
                # closes (matching the Go/WS listen-window semantics).
                if body == "__timeout__":
                    break
                continue
            if typ == _SIO_EVENT:
                ev = _parse_event(ns, body)
                if ev is not None:
                    self._inbound.append(ev)
        return list(self._inbound[start:])

    def events(self) -> list[Event]:
        return list(self._inbound)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ── internals ─────────────────────────────────────────────────────

    def _send(self, text: str) -> None:
        try:
            self._conn.send(text)
        except Exception as exc:
            raise SocketIOError(f"mockarty socketio: send: {exc}") from exc

    def _read_socketio(self, timeout: float):
        """Read one Engine.IO frame, answering pings transparently, and
        return ``(sio_type, namespace, body)`` for the next message frame.

        Returns ``(None, "", "__timeout__")`` on read timeout, and
        ``(None, "", "")`` for skipped (ping/pong/open) frames.
        """
        try:
            frame = self._conn.recv(timeout=timeout)
        except TimeoutError:
            return None, "", "__timeout__"
        except Exception:
            return None, "", "__timeout__"
        text = frame if isinstance(frame, str) else frame.decode("utf-8", "replace")
        if not text:
            return None, "", ""
        head = text[0]
        if head == _EIO_PING:
            try:
                self._conn.send(_EIO_PONG + text[1:])
            except Exception:
                pass
            return None, "", ""
        if head in (_EIO_PONG, _EIO_OPEN):
            return None, "", ""
        if head == _EIO_CLOSE:
            return None, "", "__timeout__"
        if head != _EIO_MESSAGE:
            return None, "", ""
        sio = text[1:]
        if not sio:
            return None, "", ""
        typ = sio[0]
        rest = sio[1:]
        ns = "/"
        if rest.startswith("/"):
            comma = rest.find(",")
            if comma >= 0:
                ns = rest[:comma]
                rest = rest[comma + 1 :]
        # Strip a leading ack id (digits) if present.
        rest = rest.lstrip("0123456789")
        return typ, ns, rest


# ── helpers ───────────────────────────────────────────────────────────


def _parse_event(ns: str, body: str) -> Optional[Event]:
    try:
        arr = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(arr, list) or not arr:
        return None
    name = arr[0]
    if not isinstance(name, str):
        return None
    return Event(name=name, namespace=ns, args=arr[1:], received_at=time.time())


def _ns_match(got: str, want: str) -> bool:
    got = got or "/"
    want = want or "/"
    return got == want


def _normalize_url(url: str) -> str:
    u = url
    if u.startswith("http://"):
        u = "ws://" + u[len("http://") :]
    elif u.startswith("https://"):
        u = "wss://" + u[len("https://") :]
    base, _, query = u.partition("?")
    if "/socket.io" not in base:
        base = base.rstrip("/") + "/socket.io/"
    if "EIO=" not in query:
        query = (query + "&" if query else "") + "EIO=4&transport=websocket"
    return base + "?" + query
