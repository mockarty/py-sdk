# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for PerfAPI config CRUD against a running admin.

Drives create_config -> get_config -> list_configs -> update_config ->
delete_config -> gone entirely through the SDK against /api/v1/perf-configs,
verifying the PerfConfig envelope round-trips. This also guards a model fix:
the server returns the saved config's `id` (and namespace / timestamps), which
PerfConfig now captures — without it create_config() dropped the id and the
caller could never address the config for get/update/delete. Perf configs are
a core CI/CD surface (load tests run from pipelines), so the shape must not
drift. Gated by MOCKARTY_LIVE_TOKEN (same convention as test_flow_runs_live.py);
skips offline.

NOTE: this exercises only the config CRUD surface — it does NOT launch an
actual load run (perf.run), which needs a runner and wall-clock time.
"""

from __future__ import annotations

import os
import time

import pytest

from mockarty import MockartyClient
from mockarty.models.common import PerfConfig

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")

_SCRIPT = (
    'import http from "k6/http";\n'
    "export default function () { http.get(__ENV.TARGET || \"http://127.0.0.1:5770/health\"); }\n"
)


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_perf_config_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    name = f"py-sdk-perf-{int(time.time() * 1000)}"
    config = PerfConfig(
        name=name,
        namespace="sandbox",
        script=_SCRIPT,
        vus=1,
        duration="5s",
    )

    try:
        created = client.perf.create_config(config)
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"perf feature unavailable (license): {exc}")
        raise

    # The server-assigned id must round-trip — without it the config is
    # unaddressable for get/update/delete.
    assert created.id, f"create_config did not surface the server id: {created!r}"
    assert created.name == name, f"create returned name={created.name!r}, want {name!r}"
    config_id = created.id

    deleted = False
    try:
        # get_config decodes the single-config envelope. NOTE: the perf-config
        # STORE persists only name + script (+ org fields); the load profile
        # (vus / duration / stages) lives inside the k6 script's
        # `export const options` per the k6 model, NOT as separate stored
        # columns — the server silently ignores top-level vus/duration on the
        # config-store path (they are honoured only by the inline perf.run()
        # path). So we round-trip name + script here, not vus.
        fetched = client.perf.get_config(config_id)
        assert fetched.id == config_id, f"get_config returned id={fetched.id!r}, want {config_id!r}"
        assert fetched.name == name, f"name did not round-trip: {fetched.name!r}"
        assert fetched.script == _SCRIPT, f"script did not round-trip: {fetched.script!r}"

        # list_configs includes the created config
        configs = client.perf.list_configs()
        assert any(c.id == config_id for c in configs), (
            f"list_configs() did not include {config_id!r} (count={len(configs)})"
        )

        # update_config mutates the script and round-trips
        new_script = _SCRIPT + "// updated\n"
        updated = client.perf.update_config(
            config_id,
            PerfConfig(name=name, namespace="sandbox", script=new_script),
        )
        assert updated.script == new_script, (
            f"update did not persist the changed script: {updated.script!r}"
        )
    finally:
        client.perf.delete_config(config_id)
        deleted = True

    if deleted:
        remaining = client.perf.list_configs()
        assert not any(c.id == config_id for c in remaining), (
            f"perf config {config_id!r} still listed after delete"
        )
