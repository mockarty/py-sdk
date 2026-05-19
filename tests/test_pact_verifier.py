# Copyright (c) 2026 Mockarty. All rights reserved.

"""Unit tests for mockarty.pact.verifier.Verifier."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from mockarty.pact.broker import BrokerClient
from mockarty.pact.verifier import VerificationResult, Verifier


SIMPLE_PACT = json.dumps(
    {
        "consumer": {"name": "OrderClient"},
        "provider": {"name": "OrderAPI"},
        "interactions": [
            {
                "description": "fetch order 42",
                "providerStates": [{"name": "order 42 exists"}],
                "request": {"method": "GET", "path": "/orders/42"},
                "response": {
                    "status": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"id": 42},
                },
            }
        ],
        "metadata": {"pactSpecification": {"version": "4.0"}},
    }
).encode()

V3_PACT = json.dumps(
    {
        "consumer": {"name": "OrderClient"},
        "provider": {"name": "OrderAPI"},
        "interactions": [
            {
                "description": "fetch one",
                "providerState": "data exists",
                "request": {"method": "GET", "path": "/x"},
                "response": {"status": 204},
            }
        ],
    }
).encode()


class _Provider:
    """Programmable HTTP stub used as the verifier's target."""

    def __init__(self) -> None:
        self.status = 200
        self.body = b'{"id": 42}'
        self.content_type = "application/json"
        self.last_path = ""
        self.last_method = ""
        self.last_headers: dict[str, str] = {}


@pytest.fixture()
def provider():
    prov = _Provider()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None: pass

        def _record(self) -> None:
            prov.last_method = self.command
            prov.last_path = self.path
            prov.last_headers = {k: v for k, v in self.headers.items()}

        def do_GET(self) -> None:  # noqa: N802
            self._record()
            self.send_response(prov.status)
            self.send_header("Content-Type", prov.content_type)
            self.end_headers()
            self.wfile.write(prov.body)

        do_POST = do_GET  # same handler

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", prov
    finally:
        srv.shutdown()
        srv.server_close()


def test_provider_url_required():
    with pytest.raises(ValueError, match="provider_url"):
        Verifier(provider_url="   ")


def test_happy_path(provider):
    url, _prov = provider
    v = Verifier(provider_url=url)
    res = v.verify_pact_bytes(SIMPLE_PACT)
    assert isinstance(res, VerificationResult)
    assert res.ok, [ir.mismatches for ir in res.interactions if not ir.passed]
    assert res.interactions[0].state == "order 42 exists"


def test_status_mismatch(provider):
    url, prov = provider
    prov.status = 500
    res = Verifier(provider_url=url).verify_pact_bytes(SIMPLE_PACT)
    assert not res.ok
    assert any(m.path == "$.status" for m in res.interactions[0].mismatches)


def test_body_mismatch(provider):
    url, prov = provider
    prov.body = b'{"id": 99}'
    res = Verifier(provider_url=url).verify_pact_bytes(SIMPLE_PACT)
    assert not res.ok
    assert any("id" in m.path for m in res.interactions[0].mismatches)


def test_state_handler_invoked(provider):
    url, _prov = provider
    seen: list[str] = []
    v = Verifier(provider_url=url).with_state_handler(
        "order 42 exists", lambda state, params: seen.append(state)
    )
    res = v.verify_pact_bytes(SIMPLE_PACT)
    assert res.ok
    assert seen == ["order 42 exists"]


def test_state_handler_error(provider):
    url, _prov = provider
    v = Verifier(provider_url=url).with_state_handler(
        "order 42 exists",
        lambda *_: (_ for _ in ()).throw(RuntimeError("DB down")),
    )
    res = v.verify_pact_bytes(SIMPLE_PACT)
    assert not res.ok
    assert "state setup" in res.interactions[0].error
    assert "DB down" in res.interactions[0].error


def test_state_setup_url(provider):
    url, _prov = provider
    setup_hits: list[bytes] = []

    class SetupHandler(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None: pass

        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("Content-Length", "0") or 0)
            setup_hits.append(self.rfile.read(n))
            self.send_response(200)
            self.end_headers()

    setup_srv = HTTPServer(("127.0.0.1", 0), SetupHandler)
    threading.Thread(target=setup_srv.serve_forever, daemon=True).start()
    try:
        setup_url = f"http://127.0.0.1:{setup_srv.server_address[1]}/setup"
        v = Verifier(provider_url=url).with_state_setup_url(setup_url)
        res = v.verify_pact_bytes(SIMPLE_PACT)
        assert res.ok
        assert len(setup_hits) == 1
        assert b"order 42 exists" in setup_hits[0]
    finally:
        setup_srv.shutdown(); setup_srv.server_close()


def test_request_filter(provider):
    url, prov = provider
    v = Verifier(provider_url=url).with_request_filter(
        lambda req: req["headers"].__setitem__("Authorization", "Bearer test")
    )
    res = v.verify_pact_bytes(SIMPLE_PACT)
    assert res.ok
    assert prov.last_headers.get("Authorization") == "Bearer test"


def test_v3_singular_state(provider):
    url, prov = provider
    prov.status = 204
    prov.body = b""
    seen: list[str] = []
    v = Verifier(provider_url=url).with_state_handler(
        "data exists", lambda state, params: seen.append(state)
    )
    res = v.verify_pact_bytes(V3_PACT)
    assert res.ok
    assert seen == ["data exists"]


def test_verify_from_file(tmp_path, provider):
    url, _prov = provider
    p = tmp_path / "pact.json"
    p.write_bytes(SIMPLE_PACT)
    res = Verifier(provider_url=url).verify_pact_file(p)
    assert res.ok


def test_verify_from_broker_requires_broker(provider):
    url, _prov = provider
    v = Verifier(provider_url=url)
    with pytest.raises(RuntimeError, match="with_broker"):
        v.verify_from_broker("c", "p", "v")


def test_verify_from_broker_roundtrip(provider):
    url, _prov = provider

    class BrokerHandler(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None: pass

        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(SIMPLE_PACT)

    bsrv = HTTPServer(("127.0.0.1", 0), BrokerHandler)
    threading.Thread(target=bsrv.serve_forever, daemon=True).start()
    try:
        broker = BrokerClient(base_url=f"http://127.0.0.1:{bsrv.server_address[1]}")
        v = Verifier(provider_url=url).with_broker(broker)
        res = v.verify_from_broker("OrderClient", "OrderAPI", "1.0")
        assert res.ok
    finally:
        bsrv.shutdown(); bsrv.server_close()


def test_publish_results():
    captured: list[dict[str, Any]] = []

    class BrokerHandler(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None: pass

        def do_POST(self) -> None:  # noqa: N802
            n = int(self.headers.get("Content-Length", "0") or 0)
            captured.append(json.loads(self.rfile.read(n)))
            self.send_response(201)
            self.end_headers()

    bsrv = HTTPServer(("127.0.0.1", 0), BrokerHandler)
    threading.Thread(target=bsrv.serve_forever, daemon=True).start()
    try:
        broker = BrokerClient(base_url=f"http://127.0.0.1:{bsrv.server_address[1]}",
                              token="tok")
        v = Verifier(
            provider_url="http://x",
            provider_name="OrderAPI",
            provider_version="1.2.3",
        ).with_broker(broker)
        from mockarty.pact.verifier import InteractionResult

        result = VerificationResult(interactions=[
            InteractionResult(description="fetch order 42", passed=True),
        ])
        v.publish_results("OrderClient", "OrderAPI", "1.0", result)
        assert len(captured) == 1
        assert captured[0]["success"] is True
        assert captured[0]["providerApplicationVersion"] == "1.2.3"
    finally:
        bsrv.shutdown(); bsrv.server_close()


def test_publish_results_requires_version():
    broker = BrokerClient(base_url="http://x")
    v = Verifier(provider_url="http://y").with_broker(broker)
    with pytest.raises(RuntimeError, match="provider_version"):
        v.publish_results("c", "p", "v", VerificationResult())


def test_garbage_pact_json():
    v = Verifier(provider_url="http://x")
    with pytest.raises(ValueError):
        v.verify_pact_bytes(b"<<not json>>")


def test_strict_states_raises_on_unhandled_state(provider):
    url, _prov = provider
    v = Verifier(provider_url=url).with_strict_states()
    res = v.verify_pact_bytes(SIMPLE_PACT)
    assert not res.ok
    assert "strict mode" in res.interactions[0].error


def test_verify_pact_bytes_skips_message_interactions(provider):
    url, _prov = provider
    mixed = json.dumps({
        "consumer": {"name": "c"},
        "provider": {"name": "p"},
        "interactions": [
            {
                "description": "fetch order 42",
                "providerStates": [{"name": "order 42 exists"}],
                "request": {"method": "GET", "path": "/orders/42"},
                "response": {"status": 200,
                             "headers": {"Content-Type": "application/json"},
                             "body": {"id": 42}},
            },
            {
                "type": "Asynchronous/Messages",
                "description": "an order-created event",
                "contents": {"contentType": "application/json", "content": {"x": 1}},
            },
        ],
    }).encode()
    res = Verifier(provider_url=url).verify_pact_bytes(mixed)
    assert len(res.interactions) == 1
    assert res.interactions[0].description == "fetch order 42"


def test_pact_doc_with_non_dict_interaction():
    """Coercion path: non-dict entries become empty failed interactions."""
    raw = json.dumps({"interactions": ["not-a-dict", 42, None, {}]}).encode()
    v = Verifier(provider_url="http://127.0.0.1:1")
    # The four entries should all be coerced into empty interaction dicts;
    # all will then fail at the HTTP call because the URL points nowhere.
    res = v.verify_pact_bytes(raw)
    assert len(res.interactions) == 4
    assert all(not ir.passed for ir in res.interactions)
