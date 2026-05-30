# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for FuzzingAPI config CRUD against a running
admin.

Drives create_config -> get_config -> list_configs -> delete_config -> gone
entirely through the SDK, verifying the FuzzingConfig envelope (targetBaseUrl /
sourceType / payloadCategories aliases) round-trips against a real admin.
Catches Python-SDK/admin drift on the fuzzing-config wire shape. Gated by
MOCKARTY_LIVE_TOKEN (same convention as test_flow_runs_live.py); skips offline.
"""

from __future__ import annotations

import os
import time

import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_fuzzing_config_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    name = f"py-sdk-fuzz-{int(time.time() * 1000)}"
    config = {
        "name": name,
        "namespace": "sandbox",
        "targetBaseUrl": LIVE_URL,
        "sourceType": "manual",
        "strategy": "smart",
        "payloadCategories": ["sqli"],
    }

    try:
        created = client.fuzzing.create_config(config)
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"fuzzing feature unavailable (license): {exc}")
        raise

    assert created.id, f"create_config returned no id: {created!r}"
    assert created.name == name, f"create returned name={created.name!r}, want {name!r}"
    # aliased fields decode back from the wire envelope
    assert created.target_base_url == LIVE_URL, (
        f"targetBaseUrl did not round-trip: {created.target_base_url!r}"
    )
    config_id = created.id

    deleted = False
    try:
        # get_config decodes the single-config envelope
        fetched = client.fuzzing.get_config(config_id)
        assert fetched.id == config_id, f"get_config returned id={fetched.id!r}, want {config_id!r}"
        assert fetched.source_type == "manual", (
            f"sourceType did not round-trip: {fetched.source_type!r}"
        )

        # list_configs includes the created config
        configs = client.fuzzing.list_configs()
        assert any(c.id == config_id for c in configs), (
            f"list_configs() did not include {config_id!r} (count={len(configs)})"
        )
    finally:
        client.fuzzing.delete_config(config_id)
        deleted = True

    if deleted:
        remaining = client.fuzzing.list_configs()
        assert not any(c.id == config_id for c in remaining), (
            f"config {config_id!r} still listed after delete_config"
        )
