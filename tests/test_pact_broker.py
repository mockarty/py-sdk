# Copyright (c) 2026 Mockarty. All rights reserved.

"""Unit tests for mockarty.pact.broker.BrokerClient.

Uses an in-process stub HTTP server (no network) — same approach as
the Go SDK broker tests so the two cross-validate.
"""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from mockarty.pact.broker import (
    BrokerClient,
    BrokerError,
    CanIDeployResult,
    PactNotFoundError,
)

SAMPLE_PACT = json.dumps(
    {
        "consumer": {"name": "OrderClient"},
        "provider": {"name": "OrderAPI"},
        "interactions": [],
        "metadata": {"pactSpecification": {"version": "4.0"}},
    }
).encode()


class _Capture:
    """Shared mutable record of incoming requests."""

    def __init__(self) -> None:
        self.method = ""
        self.path = ""
        self.headers: dict[str, str] = {}
        self.body = b""
        self.tag_paths: list[str] = []
        self.branch_header = ""
        # Programmable response.
        self.response_status = 200
        self.response_body: bytes = b"{}"


@pytest.fixture()
def broker_stub():
    """Spin up an HTTPServer in a daemon thread, yield (base_url, capture)."""

    cap = _Capture()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:  # silence noisy server log
            pass

        def _record(self) -> None:
            cap.method = self.command
            cap.path = self.path
            cap.headers = {k: v for k, v in self.headers.items()}
            length = int(self.headers.get("Content-Length", "0") or 0)
            cap.body = self.rfile.read(length) if length else b""
            if "/tags/" in self.path:
                cap.tag_paths.append(self.path)
            elif self.headers.get("X-Pact-Consumer-Branch"):
                # Persist branch header from the publish PUT — tag
                # PUTs overwrite headers otherwise.
                cap.branch_header = self.headers["X-Pact-Consumer-Branch"]

        def _reply(self) -> None:
            self.send_response(cap.response_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(cap.response_body)

        def do_GET(self) -> None:  # noqa: N802
            self._record()
            self._reply()

        def do_PUT(self) -> None:  # noqa: N802
            self._record()
            self._reply()

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", cap
    finally:
        srv.shutdown()
        srv.server_close()


def test_no_base_url_raises(monkeypatch):
    monkeypatch.delenv("PACT_BROKER_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="base_url"):
        BrokerClient()


def test_env_var_reads(monkeypatch):
    monkeypatch.setenv("PACT_BROKER_BASE_URL", "https://broker/")
    monkeypatch.setenv("PACT_BROKER_TOKEN", "tok-1")
    c = BrokerClient()
    assert c.base_url == "https://broker"  # trailing slash stripped
    assert c.token == "tok-1"


def test_publish_happy_path(broker_stub):
    url, cap = broker_stub
    cap.response_status = 201
    c = BrokerClient(base_url=url, token="abc")
    c.publish(SAMPLE_PACT, consumer_version="1.0.0")
    assert cap.method == "PUT"
    assert cap.path == "/pacts/provider/OrderAPI/consumer/OrderClient/version/1.0.0"
    assert cap.headers["Authorization"] == "Bearer abc"
    assert cap.body == SAMPLE_PACT


def test_publish_basic_auth_fallback(broker_stub):
    url, cap = broker_stub
    c = BrokerClient(base_url=url, username="ci", password="s3cret")
    c.publish(SAMPLE_PACT, consumer_version="1.0")
    want = "Basic " + base64.b64encode(b"ci:s3cret").decode()
    assert cap.headers["Authorization"] == want


def test_publish_bearer_wins_over_basic(broker_stub):
    url, cap = broker_stub
    c = BrokerClient(base_url=url, token="tok-x", username="u", password="p")
    c.publish(SAMPLE_PACT, consumer_version="1.0")
    assert cap.headers["Authorization"].startswith("Bearer ")


def test_publish_with_branch_and_tags(broker_stub):
    url, cap = broker_stub
    c = BrokerClient(base_url=url)
    c.publish(SAMPLE_PACT, consumer_version="2.0", branch="main",
              tags=["prod", "stable", ""])  # empty filtered
    assert cap.branch_header == "main"
    assert len(cap.tag_paths) == 2
    assert any(p.endswith("/tags/prod") for p in cap.tag_paths)
    assert any(p.endswith("/tags/stable") for p in cap.tag_paths)


def test_publish_4xx_surfaces_body(broker_stub):
    url, cap = broker_stub
    cap.response_status = 400
    cap.response_body = b'{"errors":["bad pact"]}'
    c = BrokerClient(base_url=url)
    with pytest.raises(BrokerError) as ei:
        c.publish(SAMPLE_PACT, consumer_version="1.0")
    assert ei.value.status == 400
    assert "bad pact" in ei.value.body


def test_publish_rejects_malformed_pact():
    c = BrokerClient(base_url="http://x")
    with pytest.raises(ValueError):
        c.publish(b"not-json", consumer_version="1.0")
    with pytest.raises(ValueError):
        c.publish(b"{}", consumer_version="1.0")


def test_publish_requires_consumer_version():
    c = BrokerClient(base_url="http://x")
    with pytest.raises(ValueError, match="consumer_version"):
        c.publish(SAMPLE_PACT, consumer_version="  ")


def test_fetch_404_raises_sentinel(broker_stub):
    url, cap = broker_stub
    cap.response_status = 404
    c = BrokerClient(base_url=url)
    with pytest.raises(PactNotFoundError):
        c.fetch("X", "Y", "1.0")


def test_fetch_latest_uses_latest_segment(broker_stub):
    url, cap = broker_stub
    cap.response_body = SAMPLE_PACT
    c = BrokerClient(base_url=url)
    body = c.fetch_latest("X", "Y")
    assert cap.path.endswith("/version/latest")
    assert body == SAMPLE_PACT


def test_can_i_deploy_deployable(broker_stub):
    url, cap = broker_stub
    cap.response_body = json.dumps(
        {"summary": {"deployable": True, "reason": "all verified"}}
    ).encode()
    c = BrokerClient(base_url=url)
    res = c.can_i_deploy("OrderClient", "1.0", "prod")
    assert isinstance(res, CanIDeployResult)
    assert res.deployable is True
    assert res.reason == "all verified"
    assert "pacticipant=OrderClient" in cap.path
    assert "environment=prod" in cap.path


def test_can_i_deploy_not_deployable(broker_stub):
    url, cap = broker_stub
    cap.response_body = json.dumps(
        {"summary": {"deployable": False, "reason": "OrderAPI unverified"}}
    ).encode()
    c = BrokerClient(base_url=url)
    res = c.can_i_deploy("X", "1.0")
    assert res.deployable is False
    assert "unverified" in res.reason


def test_can_i_deploy_requires_args():
    c = BrokerClient(base_url="http://x")
    with pytest.raises(ValueError):
        c.can_i_deploy("", "1.0")
    with pytest.raises(ValueError):
        c.can_i_deploy("X", "")


def test_can_i_deploy_unparsable_payload(broker_stub):
    url, cap = broker_stub
    cap.response_body = b"<<not json>>"
    c = BrokerClient(base_url=url)
    with pytest.raises(BrokerError, match="unparsable JSON"):
        c.can_i_deploy("X", "1.0")
