# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for ContractAPI config CRUD against a running
admin.

Exercises save_config -> list_configs -> delete_config entirely through the
SDK, verifying the ContractConfig wire shape decodes (specContent / targetUrl
aliases) and that a saved config is listed then removed. Catches a
Python-SDK/admin drift on the contract-config envelope. Gated by
MOCKARTY_LIVE_TOKEN (same convention as test_flow_runs_live.py); skips offline.
"""

from __future__ import annotations

import os
import time

import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")

# Minimal valid OpenAPI document — the admin requires specContent (or specUrl)
# on save, and parses it, so it must be well-formed.
_MIN_SPEC = "openapi: 3.0.0\ninfo:\n  title: parity\n  version: '1'\npaths: {}\n"


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_contract_config_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    name = f"py-sdk-contract-{int(time.time() * 1000)}"
    # NOTE: the admin's POST /contract/configs requires specContent (not the
    # SDK model's bare `spec` field) — send the aliased key explicitly.
    config = {
        "name": name,
        "namespace": "sandbox",
        "targetUrl": f"{LIVE_URL}/health",
        "specContent": _MIN_SPEC,
    }

    try:
        saved = client.contracts.save_config(config)
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"contract feature unavailable (license): {exc}")
        raise
    assert saved.id, f"save_config returned no id: {saved!r}"
    assert saved.name == name, f"save_config returned name={saved.name!r}, want {name!r}"
    config_id = saved.id

    deleted = False
    try:
        # list_configs() includes the saved config (decodes the wire shape)
        configs = client.contracts.list_configs()
        assert any(c.id == config_id for c in configs), (
            f"list_configs() did not include {config_id!r} (count={len(configs)})"
        )
    finally:
        client.contracts.delete_config(config_id)
        deleted = True

    # after delete it's gone from the list
    if deleted:
        remaining = client.contracts.list_configs()
        assert not any(c.id == config_id for c in remaining), (
            f"config {config_id!r} still listed after delete_config"
        )
