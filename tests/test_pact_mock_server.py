# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mock server tests — full consumer flow + concurrency + edge cases.

We exercise the in-process threaded HTTP server with stdlib
``urllib.request`` so the test doesn't pull a heavier client. (The
SDK ships ``httpx`` as a hard dep, but using stdlib here keeps the
test independent of the SDK's HTTP client.)
"""

from __future__ import annotations

import concurrent.futures
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from mockarty.pact import (
    Consumer,
    Like,
    MockServer,
    PactMismatchError,
    Regex,
)
from mockarty.pact.interaction import InteractionBuilder


def _http(
    method: str,
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
):
    """Tiny stdlib HTTP helper. Returns ``(status, body_bytes)``."""

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers or {},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — local
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ── Happy path ───────────────────────────────────────────────────────


class TestHappyPath:
    def test_consumer_full_flow_v4(self, tmp_path: Path):
        consumer = (
            Consumer("OrderService")
            .with_provider("PaymentService")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.given("payment service is up").upon_receiving(
            "a charge request"
        ).with_request("POST", "/charge", body={"amount": Like(100)}).will_respond_with(
            200, body={"id": Like("abc")}
        )

        with consumer.start() as server:
            status, body = _http("POST", f"{server.url}/charge", {"amount": 42})
            assert status == 200
            payload = json.loads(body)
            assert payload == {"id": "abc"}

        pact_file = tmp_path / "OrderService-PaymentService.json"
        assert pact_file.exists()
        contents = json.loads(pact_file.read_text("utf-8"))
        assert contents["metadata"]["pactSpecification"]["version"] == "4.0"

    def test_consumer_full_flow_v3(self, tmp_path: Path):
        consumer = (
            Consumer("OrderService")
            .with_provider("PaymentService")
            .with_spec_version("V3")
            .with_output_dir(tmp_path)
        )
        consumer.given("ready").upon_receiving("ping").with_request(
            "GET", "/ping"
        ).will_respond_with(200, headers={"X-Pong": "yes"}, body={"ok": True})

        with consumer.start() as server:
            status, body = _http("GET", f"{server.url}/ping")
            assert status == 200
            assert json.loads(body) == {"ok": True}

        pact_file = tmp_path / "OrderService-PaymentService.json"
        assert pact_file.exists()
        contents = json.loads(pact_file.read_text("utf-8"))
        assert contents["metadata"]["pactSpecification"]["version"] == "3.0.0"


# ── Failure modes ────────────────────────────────────────────────────


class TestVerificationFailures:
    def test_unhit_interaction_raises_on_ctx_exit(self, tmp_path: Path):
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("ping").with_request("GET", "/ping").will_respond_with(
            200
        )

        with pytest.raises(PactMismatchError, match="unhit"):
            with consumer.start():
                # Never call the server.
                pass

    def test_unmatched_request_recorded(self, tmp_path: Path):
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("ping").with_request("GET", "/ping").will_respond_with(
            200
        )

        with pytest.raises(PactMismatchError, match="unmatched"):
            with consumer.start() as server:
                # Send an unexpected POST + don't hit the expected GET.
                status, _ = _http("POST", f"{server.url}/totally-unknown", {})
                assert status == 500
                # Also hit the expected one so that part of verify passes.
                _http("GET", f"{server.url}/ping")

    def test_test_failure_skips_verify_but_writes_pact(self, tmp_path: Path):
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("ping").with_request("GET", "/ping").will_respond_with(
            200
        )

        with pytest.raises(RuntimeError, match="user code"):
            with consumer.start():
                raise RuntimeError("user code blew up")
        # Pact still written for inspection.
        assert (tmp_path / "A-B.json").exists()


# ── Matchers materialised at runtime ─────────────────────────────────


class TestMatchersInResponse:
    def test_regex_response_body_returns_example(self, tmp_path: Path):
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("regex sample").with_request(
            "GET", "/r"
        ).will_respond_with(200, body={"code": Regex(r"[A-Z]{3}", "USD")})

        with consumer.start() as server:
            _, body = _http("GET", f"{server.url}/r")
            assert json.loads(body) == {"code": "USD"}


# ── Query params ─────────────────────────────────────────────────────


def test_query_params_must_match(tmp_path: Path):
    consumer = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    consumer.upon_receiving("with query").with_request(
        "GET", "/q", query={"page": "1"}
    ).will_respond_with(200, body={"ok": True})

    with consumer.start() as server:
        status, _ = _http("GET", f"{server.url}/q?page=1")
        assert status == 200


def test_query_param_mismatch_returns_500(tmp_path: Path):
    consumer = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    consumer.upon_receiving("with query").with_request(
        "GET", "/q", query={"page": "1"}
    ).will_respond_with(200)

    server = MockServer([b.build() for b in consumer.interactions]).start()
    try:
        status, _ = _http("GET", f"{server.url}/q?page=99")
        assert status == 500
    finally:
        server.stop()


# ── Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_unicode_body(self, tmp_path: Path):
        # Russian + emoji + Chinese, ensure no encoding regressions in
        # the writer or the mock server.
        text = "Привет, мир! 你好 🚀"
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("unicode echo").with_request(
            "POST", "/u"
        ).will_respond_with(200, body={"msg": text})

        with consumer.start() as server:
            _, body = _http("POST", f"{server.url}/u", {"x": 1})
            payload = json.loads(body)
            assert payload["msg"] == text

        contents = json.loads((tmp_path / "A-B.json").read_text("utf-8"))
        assert contents["interactions"][0]["response"]["body"]["msg"] == text

    def test_very_long_body(self, tmp_path: Path):
        long_str = "x" * 100_000
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("huge").with_request("POST", "/huge").will_respond_with(
            200, body={"data": long_str}
        )

        with consumer.start() as server:
            _, body = _http("POST", f"{server.url}/huge", {"x": 1})
            assert json.loads(body)["data"] == long_str

    def test_binary_response_body(self, tmp_path: Path):
        # V4 explicitly supports binary attachments; our mock server
        # just streams bytes for non-JSON bodies.
        blob = bytes(range(256))
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("blob").with_request("GET", "/blob").will_respond_with(
            200,
            headers={"Content-Type": "application/octet-stream"},
            body=blob,
        )

        with consumer.start() as server:
            _, body = _http("GET", f"{server.url}/blob")
            assert body == blob

    def test_nested_matchers(self, tmp_path: Path):
        consumer = (
            Consumer("A")
            .with_provider("B")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving("nested").with_request("GET", "/n").will_respond_with(
            200,
            body={
                "user": Like(
                    {
                        "id": Like(1),
                        "email": Regex(r".+@.+", "a@b.com"),
                    }
                ),
            },
        )

        with consumer.start() as server:
            _, body = _http("GET", f"{server.url}/n")
            data = json.loads(body)
            assert data == {"user": {"id": 1, "email": "a@b.com"}}


# ── Concurrency ──────────────────────────────────────────────────────


def test_parallel_mock_servers_dont_collide(tmp_path: Path):
    """Run several consumers in parallel threads — each gets its own
    free port and writes its own pact.json. Catches socket leaks +
    state sharing between handler instances.
    """

    def run_one(name: str):
        consumer = (
            Consumer(name)
            .with_provider("Server")
            .with_spec_version("V4")
            .with_output_dir(tmp_path)
        )
        consumer.upon_receiving(f"{name} ping").with_request(
            "GET", "/ping"
        ).will_respond_with(200, body={"who": Like(name)})
        with consumer.start() as server:
            status, body = _http("GET", f"{server.url}/ping")
            assert status == 200
            assert json.loads(body) == {"who": name}
        return (tmp_path / f"{name}-Server.json").exists()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run_one, [f"C{i:02d}" for i in range(8)]))
    assert all(results)


def test_concurrent_requests_to_one_server(tmp_path: Path):
    consumer = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    # Allow many calls to /ping by registering one interaction that
    # matches each request.
    consumer.upon_receiving("ping").with_request("GET", "/ping").will_respond_with(
        200, body={"ok": True}
    )

    with consumer.start() as server:

        def do_one(_i: int):
            status, _ = _http("GET", f"{server.url}/ping")
            return status

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            statuses = list(pool.map(do_one, range(64)))
        assert statuses == [200] * 64


# ── Server lifecycle ─────────────────────────────────────────────────


def test_start_twice_raises():
    consumer = (
        Consumer("A").with_provider("B").with_spec_version("V4").with_output_dir("/tmp")
    )
    consumer.upon_receiving("x").with_request("GET", "/x").will_respond_with(200)

    server = MockServer([b.build() for b in consumer.interactions]).start()
    try:
        with pytest.raises(RuntimeError, match="already started"):
            server.start()
    finally:
        server.stop()


def test_stop_idempotent():
    consumer = (
        Consumer("A").with_provider("B").with_spec_version("V4").with_output_dir("/tmp")
    )
    consumer.upon_receiving("x").with_request("GET", "/x").will_respond_with(200)
    server = MockServer([b.build() for b in consumer.interactions])
    server.stop()  # not started — should be a no-op
    server.start()
    server.stop()
    server.stop()  # double-stop must not raise


def test_url_before_start_raises():
    server = MockServer([])
    with pytest.raises(RuntimeError):
        _ = server.port


def test_reset_clears_hits(tmp_path: Path):
    consumer = (
        Consumer("A")
        .with_provider("B")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )
    consumer.upon_receiving("x").with_request("GET", "/x").will_respond_with(200)
    server = MockServer([b.build() for b in consumer.interactions]).start()
    try:
        _http("GET", f"{server.url}/x")
        server.reset()
        # After reset, /x has not been hit, so verify should fail.
        with pytest.raises(PactMismatchError):
            server.verify()
    finally:
        server.stop()


def test_builder_validation_on_build():
    # Missing description.
    with pytest.raises(ValueError, match="upon_receiving"):
        InteractionBuilder().with_request("GET", "/x").will_respond_with(200).build()
