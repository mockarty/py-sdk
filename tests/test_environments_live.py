# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for EnvironmentAPI CRUD against a running admin.

Drives create -> get -> list -> update -> delete -> gone entirely through the
SDK, verifying the api-tester Environment envelope round-trips. Note the wire
shape: ``variables`` is a flat ``{name: value}`` MAP (not a list of objects),
and the methods return raw dicts. Environments parameterise collection / perf
runs, so the wire shape must not drift. Gated by MOCKARTY_LIVE_TOKEN (same
convention as test_flow_runs_live.py); skips offline.
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
def test_environment_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    name = f"py-sdk-env-{int(time.time() * 1000)}"
    env = {
        "name": name,
        "namespace": "sandbox",
        "variables": {"BASE_URL": "http://example.test"},
    }

    try:
        created = client.environments.create(env)
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"environments feature unavailable (license): {exc}")
        raise

    env_id = created.get("id")
    assert env_id, f"create returned no id: {created!r}"
    assert created.get("name") == name, f"create returned name={created.get('name')!r}, want {name!r}"
    assert created.get("variables", {}).get("BASE_URL") == "http://example.test", (
        f"variables map did not round-trip on create: {created.get('variables')!r}"
    )

    deleted = False
    try:
        # get returns the flat environment dict
        fetched = client.environments.get(env_id)
        assert fetched.get("id") == env_id, f"get returned id={fetched.get('id')!r}, want {env_id!r}"

        # list returns an array including the created environment
        envs = client.environments.list()
        assert any(e.get("id") == env_id for e in envs), (
            f"list() did not include {env_id!r} (count={len(envs)})"
        )

        # update mutates the variables map and round-trips
        updated = client.environments.update(
            env_id,
            {
                "name": name,
                "namespace": "sandbox",
                "variables": {"BASE_URL": "http://changed.test", "TOKEN": "xyz"},
            },
        )
        uvars = updated.get("variables", {})
        assert uvars.get("BASE_URL") == "http://changed.test", (
            f"update did not change BASE_URL: {uvars!r}"
        )
        assert uvars.get("TOKEN") == "xyz", f"update did not add TOKEN: {uvars!r}"
    finally:
        client.environments.delete(env_id)
        deleted = True

    if deleted:
        remaining = client.environments.list()
        assert not any(e.get("id") == env_id for e in remaining), (
            f"environment {env_id!r} still listed after delete"
        )
