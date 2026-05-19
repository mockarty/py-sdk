"""Unit tests for mockarty.protocols.websocket.

The ``websockets`` package is optional. These tests cover construction
+ parameter validation + the import-error path without needing a live
WebSocket server.
"""

from __future__ import annotations

import pytest

from mockarty.protocols.telemetry import AccumulatingRecorder
from mockarty.protocols.websocket import WebSocketClient, WebSocketImportError


def test_init_empty_url_rejected():
    with pytest.raises(ValueError):
        WebSocketClient("")


def test_init_payload_cap_clamps_negative():
    cli = WebSocketClient("ws://x", payload_cap=-1)
    assert cli._payload_cap == 0


def test_init_default_recorder_is_nop():
    cli = WebSocketClient("ws://x")
    from mockarty.protocols.telemetry import NopRecorder
    assert isinstance(cli._recorder, NopRecorder)


def test_close_idempotent_without_connect():
    cli = WebSocketClient("ws://x")
    cli.close()
    cli.close()  # second call must not raise


def test_send_raises_friendly_error_when_websockets_missing(monkeypatch):
    """Tightest path: simulate `websockets` import failure and check
    the user-facing error class kicks in."""
    rec = AccumulatingRecorder()
    cli = WebSocketClient("ws://nope", recorder=rec)

    # Force the lazy import inside _connect_if_needed to fail. The
    # cleanest way is to remove the module from sys.modules + block
    # re-import via the meta-path finder. Easier: monkeypatch
    # _connect_if_needed to raise WebSocketImportError directly.
    def explode(*_a, **_k):
        raise WebSocketImportError()

    monkeypatch.setattr(cli, "_connect_if_needed", explode)
    with pytest.raises(WebSocketImportError):
        cli.send("payload")
    # Failed send must still record a broken step.
    assert rec.steps()[0]["status"] == "broken"


def test_recv_records_broken_step_on_error(monkeypatch):
    rec = AccumulatingRecorder()
    cli = WebSocketClient("ws://nope", recorder=rec)

    def explode(*_a, **_k):
        raise RuntimeError("recv failed")

    monkeypatch.setattr(cli, "_connect_if_needed", explode)
    with pytest.raises(RuntimeError):
        cli.recv()
    assert rec.steps()[0]["status"] == "broken"
    assert "recv failed" in rec.steps()[0]["message"]
