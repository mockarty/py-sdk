# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for CollectionAPI against a running admin.

The CollectionAPI is read-only (list / get / execute / export) — there's no
SDK create — so this test seeds a collection via the admin REST API directly,
then verifies the SDK's list() and get() decode the real wire shape and find
it. That catches a Python-SDK/admin drift on the collection envelope (field
names like collectionType / isShared use aliases). Gated by MOCKARTY_LIVE_TOKEN
(same convention as test_flow_runs_live.py); skipped offline.
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_collections_list_and_get_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )
    admin = httpx.Client(
        base_url=LIVE_URL,
        headers={"X-API-Key": LIVE_TOKEN},
        timeout=15.0,
    )

    name = f"py-sdk-coll-{int(time.time() * 1000)}"
    # Seed via the admin REST API (the SDK has no collection create).
    resp = admin.post(
        "/api/v1/api-tester/collections",
        json={"name": name, "namespace": "sandbox", "protocol": "http"},
    )
    if resp.status_code == 403:
        pytest.skip(f"api-tester feature unavailable (license): {resp.text}")
    assert resp.status_code in (200, 201), f"seed collection: {resp.status_code} {resp.text}"
    coll_id = resp.json().get("id")
    assert coll_id, f"seed returned no id: {resp.json()}"

    try:
        # get(id) -> Collection decodes the real wire shape (aliases included)
        got = client.collections.get(coll_id)
        assert got.id == coll_id, f"get returned id={got.id!r}, want {coll_id!r}"
        assert got.name == name, f"get returned name={got.name!r}, want {name!r}"
        assert got.protocol == "http", f"get returned protocol={got.protocol!r}, want 'http'"

        # list() includes the seeded collection
        listed = client.collections.list()
        assert any(c.id == coll_id for c in listed), (
            f"list() did not include {coll_id!r} (count={len(listed)})"
        )
    finally:
        admin.delete(f"/api/v1/api-tester/collections/{coll_id}")
        admin.close()
