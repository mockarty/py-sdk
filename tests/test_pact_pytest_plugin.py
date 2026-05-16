# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the optional pytest fixtures in ``mockarty.pact.pytest_plugin``."""

from __future__ import annotations

import json
from pathlib import Path

from mockarty.pact import Like
from mockarty.pact.pytest_plugin import (  # noqa: F401 — fixture registration
    pact_consumer_factory,
    pact_output_dir,
)


def test_factory_yields_configured_consumer(pact_consumer_factory, pact_output_dir):  # noqa: F811 — pytest fixture injection
    c = pact_consumer_factory("X", "Y", spec_version="V3")
    assert c.consumer_name == "X"
    assert c.provider_name == "Y"
    assert c.output_dir == pact_output_dir
    # Make sure the spec coercion took.
    assert c.spec_version.value == "3.0.0"


def test_factory_can_run_a_full_test(pact_consumer_factory, pact_output_dir: Path):  # noqa: F811
    c = pact_consumer_factory("X", "Y")
    c.upon_receiving("ping").with_request("GET", "/p").will_respond_with(
        200, body={"ok": Like(True)}
    )
    import urllib.request

    with c.start() as server:
        with urllib.request.urlopen(f"{server.url}/p", timeout=5) as r:  # noqa: S310
            body = r.read()
        assert json.loads(body) == {"ok": True}
    assert (pact_output_dir / "X-Y.json").exists()
