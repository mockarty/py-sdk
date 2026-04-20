# Copyright (c) 2026 Mockarty. All rights reserved.
"""Secrets Storage — create store, write/read/rotate/delete entries."""

from __future__ import annotations

from mockarty import MockartyClient


def main() -> None:
    with MockartyClient(api_key="your-api-key", namespace="sandbox") as client:
        store = client.secrets.create_store(
            name="payments",
            description="API keys for payment providers",
            backend="software",
        )
        print(f"[1] store {store['name']} id={store['id']}")

        try:
            client.secrets.create_entry(
                store["id"],
                key="stripe_api_key",
                value="sk_test_abc123",
                description="Stripe test-mode key",
            )
            print("[2] entry created")

            entry = client.secrets.get_entry(store["id"], "stripe_api_key")
            print(f"[3] v{entry['version']} value length={len(entry['value'])}")

            rotated = client.secrets.rotate_entry(store["id"], "stripe_api_key")
            print(f"[4] rotated to v{rotated['version']}")

            entries = client.secrets.list_entries(store["id"])
            print(f"[5] {len(entries)} entries in store")
        finally:
            client.secrets.delete_store(store["id"])
            print("[6] store cleaned up")


if __name__ == "__main__":
    main()
