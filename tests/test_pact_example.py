# Copyright (c) 2026 Mockarty. All rights reserved.

"""Worked example mirroring the README — runnable pytest case.

This is the test users are expected to copy-paste as a starting point.
Keep the comments verbose; this file is the *documentation* of the
intended consumer flow.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from mockarty.pact import (
    Consumer,
    EachLike,
    Integer,
    Like,
    Regex,
)


def test_order_service_charges_payment_service(tmp_path: Path):
    """A complete consumer-side Pact test exercising the V4 flow.

    Steps:
    1. Declare the contract via the fluent DSL.
    2. Start the ephemeral mock server.
    3. Drive the real client code against ``server.url``.
    4. Let the context manager verify + write pact.json on exit.
    """

    # ── 1. Declare the contract ─────────────────────────────────────
    pact = (
        Consumer("OrderService")
        .with_provider("PaymentService")
        .with_spec_version("V4")
        .with_output_dir(tmp_path)
    )

    pact.given("payment service is up", region="eu").upon_receiving(
        "a charge request"
    ).with_request(
        "POST",
        "/charge",
        headers={"Authorization": Like("Bearer ts-1")},
        body={
            "amount": Integer(100),
            "currency": Regex(r"[A-Z]{3}", "USD"),
            "items": EachLike({"sku": Like("X-1")}, min=1),
        },
    ).will_respond_with(
        200,
        headers={"Content-Type": "application/json"},
        body={
            "id": Like("ch_abc"),
            "status": Regex(r"(?:succeeded|pending)", "succeeded"),
        },
    )

    # ── 2 + 3 + 4 ───────────────────────────────────────────────────
    with pact.start() as server:
        # Simulate the order-service's real HTTP code:
        req = urllib.request.Request(
            f"{server.url}/charge",
            data=json.dumps(
                {
                    "amount": 42,
                    "currency": "EUR",
                    "items": [{"sku": "P1"}],
                }
            ).encode("utf-8"),
            headers={"Authorization": "Bearer my-token"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            assert resp.status == 200
            body = json.loads(resp.read())

        # The mock server returns the examples from the matchers — so
        # the client can assert on shape without coupling to specific
        # values.
        assert "id" in body
        assert body["status"] == "succeeded"

    # The pact.json was written to tmp_path/OrderService-PaymentService.json
    pact_file = tmp_path / "OrderService-PaymentService.json"
    assert pact_file.exists()
    contents = json.loads(pact_file.read_text("utf-8"))
    assert contents["consumer"]["name"] == "OrderService"
    assert contents["provider"]["name"] == "PaymentService"
    assert contents["metadata"]["pactSpecification"]["version"] == "4.0"
    assert len(contents["interactions"]) == 1
    it = contents["interactions"][0]
    assert it["type"] == "Synchronous/HTTP"
    # Verify the V4 nested matchingRules shape.
    rules = it["request"]["matchingRules"]["body"]
    assert "$.amount" in rules
    assert rules["$.amount"]["matchers"][0]["match"] == "integer"
