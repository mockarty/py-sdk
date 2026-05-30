# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for ChaosAPI profile CRUD against a running
admin.

Drives create_profile -> list_profiles -> delete_profile -> gone entirely
through the SDK, verifying the chaos-profile envelope round-trips. Gated by
MOCKARTY_LIVE_TOKEN (same convention as test_flow_runs_live.py); skips offline.
"""

from __future__ import annotations

import os
import time

import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")


def _profile_id(p: dict) -> str | None:
    return p.get("id") if isinstance(p, dict) else None


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_chaos_profile_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    name = f"py-sdk-chaos-{int(time.time() * 1000)}"
    try:
        created = client.chaos.create_profile({"name": name, "namespace": "sandbox"})
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"chaos feature unavailable (license): {exc}")
        raise

    profile_id = _profile_id(created)
    assert profile_id, f"create_profile returned no id: {created!r}"
    assert created.get("name") == name, f"create returned name={created.get('name')!r}, want {name!r}"

    deleted = False
    try:
        profiles = client.chaos.list_profiles()
        assert any(_profile_id(p) == profile_id for p in profiles), (
            f"list_profiles() did not include {profile_id!r} (count={len(profiles)})"
        )
    finally:
        client.chaos.delete_profile(profile_id)
        deleted = True

    if deleted:
        remaining = client.chaos.list_profiles()
        assert not any(_profile_id(p) == profile_id for p in remaining), (
            f"profile {profile_id!r} still listed after delete_profile"
        )
