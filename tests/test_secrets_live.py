# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for SecretsAPI (store + entry model) against a
running admin.

The Secrets Storage API is a namespace-scoped store-of-entries, NOT a flat
key/value map: create_store -> create_entry -> get_entry (decrypted) ->
list_entries (metadata only) -> rotate_entry -> delete_entry -> delete_store.
This drives that whole lifecycle through the SDK, asserting:
  * the store / entry envelopes unwrap correctly,
  * get_entry returns the decrypted value (round-trip),
  * list_entries NEVER includes the plaintext value (a security invariant),
  * rotate_entry actually changes the stored value.
Gated by MOCKARTY_LIVE_TOKEN (same convention as test_flow_runs_live.py); skips
offline.
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
def test_secrets_store_and_entry_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    store_name = f"py-sdk-store-{int(time.time() * 1000)}"
    key = "API_KEY"
    secret_value = "p4r1ty-v4lue"
    rotated_value = "r0t4ted-v4lue"

    try:
        store = client.secrets.create_store(store_name, backend="inline", namespace="sandbox")
    except Exception as exc:  # license / permission gating is correct behaviour
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial", "permission")):
            pytest.skip(f"secrets feature unavailable: {exc}")
        raise

    store_id = store.get("id")
    assert store_id, f"create_store returned no id: {store!r}"
    assert store.get("name") == store_name, (
        f"create_store returned name={store.get('name')!r}, want {store_name!r}"
    )

    try:
        # create an entry — the create response carries metadata, never the value
        entry = client.secrets.create_entry(store_id, key, secret_value, namespace="sandbox")
        assert entry.get("key") == key, f"create_entry returned key={entry.get('key')!r}"
        assert "value" not in entry, (
            f"SECURITY: create_entry response leaked the value: {entry!r}"
        )

        # get_entry returns the decrypted value (round-trip)
        fetched = client.secrets.get_entry(store_id, key, namespace="sandbox")
        assert fetched.get("value") == secret_value, (
            f"get_entry did not round-trip the value: {fetched.get('value')!r}"
        )

        # list_entries is metadata-only — the plaintext value must NOT appear
        entries = client.secrets.list_entries(store_id, namespace="sandbox")
        assert any(e.get("key") == key for e in entries), (
            f"list_entries did not include {key!r}: {entries!r}"
        )
        for e in entries:
            assert not e.get("value"), (
                f"SECURITY: list_entries leaked a value: {e!r}"
            )

        # rotate_entry replaces the stored value
        client.secrets.rotate_entry(store_id, key, rotated_value, namespace="sandbox")
        after = client.secrets.get_entry(store_id, key, namespace="sandbox")
        assert after.get("value") == rotated_value, (
            f"rotate_entry did not change the value: {after.get('value')!r}"
        )

        # delete_entry removes it
        client.secrets.delete_entry(store_id, key, namespace="sandbox")
        remaining = client.secrets.list_entries(store_id, namespace="sandbox")
        assert not any(e.get("key") == key for e in remaining), (
            f"entry {key!r} still listed after delete_entry"
        )
    finally:
        client.secrets.delete_store(store_id, namespace="sandbox")

    # store is gone from the listing after delete
    stores = client.secrets.list_stores(namespace="sandbox")
    assert not any(s.get("id") == store_id for s in stores), (
        f"store {store_id!r} still listed after delete_store"
    )
