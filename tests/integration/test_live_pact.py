# Copyright (c) 2026 Mockarty. All rights reserved.

"""End-to-end Pact V3+V4 consumer flow against a real HTTP client.

The Pact mock server is in-process by design (see
``feedback_sdk_thin_layer.md`` — the SDK doesn't depend on the admin
to verify a contract, the admin is only the *broker* for sharing the
generated ``pact.json`` between consumer and provider). So these tests
don't need the live admin per se, but they belong with the integration
suite because they exercise the runtime end-to-end with a real network
client (``requests``) rather than respx-mocked transports.
"""

from __future__ import annotations

import json
import pathlib

import pytest
import requests

from mockarty.pact import (
    Consumer,
    EachLike,
    Like,
    PactMismatchError,
    Regex,
    plugins as pact_plugins,
)
from mockarty.pact.plugins.spi import Plugin


class TestConsumerHappyPath:
    def test_v4_consumer_flow_emits_valid_pact_json(self, tmp_path: pathlib.Path) -> None:
        pact = (
            Consumer("py-sdk-live")
            .with_provider("PaymentService")
            .with_spec_version("V4")
            .with_output_dir(str(tmp_path / "pacts"))
        )
        (
            pact.given("payment service is up")
                .upon_receiving("a charge request")
                .with_request(
                    "POST", "/charge", body={"amount": Like(100), "currency": Like("USD")}
                )
                .will_respond_with(200, body={"id": Regex(r"[a-z0-9]+", "abc123")})
        )
        (
            pact.given("auth required")
                .upon_receiving("a status check")
                .with_request("GET", "/status")
                .will_respond_with(200, body={"items": EachLike({"id": Like("x")})})
        )

        with pact.start() as server:
            # Match both interactions in order.
            r1 = requests.post(
                f"{server.url}/charge",
                json={"amount": 42, "currency": "USD"},
                timeout=5,
            )
            assert r1.status_code == 200
            r2 = requests.get(f"{server.url}/status", timeout=5)
            assert r2.status_code == 200
            server.verify()

        # Pact written to disk.
        outfiles = list(pathlib.Path(tmp_path / "pacts").glob("*.json"))
        assert len(outfiles) == 1, outfiles
        doc = json.loads(outfiles[0].read_text(encoding="utf-8"))

        # V4 schema invariants.
        assert doc["metadata"]["pactSpecification"]["version"].startswith("4")
        assert doc["consumer"]["name"] == "py-sdk-live"
        assert doc["provider"]["name"] == "PaymentService"
        # V4 puts interactions under a key shared with V3 but each
        # entry should carry ``type`` (V4-only) and the matching rules
        # should be nested under ``request``/``response``.
        interactions = doc.get("interactions", [])
        assert len(interactions) == 2
        for it in interactions:
            assert "request" in it and "response" in it
            # The Like/Regex matchers turn into structured rules; at
            # the very least the bodies must NOT be the raw matcher
            # objects.
            req_body = it["request"].get("body")
            if isinstance(req_body, dict):
                assert all(not str(v).startswith("Like(") for v in req_body.values())

    def test_unmatched_request_raises_pact_mismatch(
        self, tmp_path: pathlib.Path
    ) -> None:
        pact = (
            Consumer("py-sdk-mismatch")
            .with_provider("StrictService")
            .with_spec_version("V4")
            .with_output_dir(str(tmp_path / "pacts"))
        )
        (
            pact.given("strict mode")
                .upon_receiving("a known request")
                .with_request("GET", "/known")
                .will_respond_with(200, body={"ok": True})
        )

        # Do NOT call /known — verify() should complain.
        with pytest.raises(PactMismatchError):
            with pact.start() as server:
                requests.get(f"{server.url}/unknown", timeout=5)
                # context-manager exit calls verify() → raises.


class _EchoPlugin:
    """Minimal plugin that echoes the payload as ``application/x-echo``.

    Satisfies the :class:`Plugin` protocol with the bare minimum
    surface so the registry/mock-server integration can be exercised
    end-to-end without pulling in protobuf or grpc deps.
    """

    name = "echo-test-plugin"
    version = "0.1.0"
    supported_content_types = ["application/x-echo"]

    def match_request(self, expected, actual, headers):  # type: ignore[override]
        # Always succeed — the plugin's role here is just to prove the
        # runtime invokes us. Real plugins return a list of Mismatch.
        return []

    def generate_response(self, template, headers):  # type: ignore[override]
        body = template if isinstance(template, (bytes, bytearray)) else str(template).encode("utf-8")
        return bytes(body), {"Content-Type": "application/x-echo"}


class TestPactPluginRuntime:
    @pytest.fixture(autouse=True)
    def _isolate_plugin_registry(self):
        # Test-only helper: reset the registry around each test so we
        # don't bleed plugin registration into other suites.
        pact_plugins.reset()
        yield
        pact_plugins.reset()

    def test_register_plugin_round_trips_into_pact_metadata(
        self, tmp_path: pathlib.Path
    ) -> None:
        plugin = _EchoPlugin()
        assert isinstance(plugin, Plugin)  # SPI satisfied
        pact_plugins.register(plugin)
        assert "echo-test-plugin" in pact_plugins.names()

        pact = (
            Consumer("py-sdk-plugin")
            .with_provider("PluginService")
            .with_spec_version("V4")
            .with_output_dir(str(tmp_path / "pacts"))
            .with_plugin("echo-test-plugin", "0.1.0")
        )
        (
            pact.given("plugin is registered")
                .upon_receiving("an echo payload")
                .with_request(
                    "POST",
                    "/echo",
                    headers={"Content-Type": "application/x-echo"},
                    body=b"raw-bytes-here",
                )
                .will_respond_with(
                    200,
                    headers={"Content-Type": "application/x-echo"},
                    body=b"raw-bytes-here",
                )
        )
        with pact.start() as server:
            r = requests.post(
                f"{server.url}/echo",
                data=b"raw-bytes-here",
                headers={"Content-Type": "application/x-echo"},
                timeout=5,
            )
            # Plugin contract: just route succeeds.
            assert r.status_code == 200
            server.verify()

        # Plugin metadata round-trips into the pact file.
        out = list(pathlib.Path(tmp_path / "pacts").glob("*.json"))[0]
        doc = json.loads(out.read_text(encoding="utf-8"))
        plugins_meta = doc.get("plugins") or doc.get("metadata", {}).get("plugins")
        assert plugins_meta, f"plugin metadata missing from pact file: {doc!r}"
        names = [p.get("name") for p in plugins_meta] if isinstance(plugins_meta, list) else []
        assert "echo-test-plugin" in names
