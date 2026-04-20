# Copyright (c) 2026 Mockarty. All rights reserved.

"""Example: entity_search — resolve human-readable names into canonical IDs.

Powers the same picker the UI uses, so CI/CD scripts no longer have to
hard-code UUIDs. Run with::

    MOCKARTY_BASE_URL=http://localhost:5770 \\
    MOCKARTY_API_KEY=mk_xxx \\
    python entity_search.py
"""

from __future__ import annotations

import os

from mockarty import (
    ENTITY_SEARCH_DEFAULT_LIMIT,
    ENTITY_TYPE_MOCK,
    ENTITY_TYPE_TEST_PLAN,
    MockartyClient,
)


def main() -> None:
    namespace = os.environ.get("MOCKARTY_NAMESPACE", "production")
    with MockartyClient(namespace=namespace) as client:
        # Example 1 — find Test Plans whose name contains "smoke" (case-insensitive).
        plans = client.entity_search.search(
            entity_type=ENTITY_TYPE_TEST_PLAN,
            query="smoke",
            limit=25,
        )
        print(f"Test Plans matching 'smoke' ({plans.total} total):")
        for p in plans.items:
            numeric = f" (#{p.numeric_id})" if p.numeric_id is not None else ""
            print(f"  {p.name}{numeric}  ns={p.namespace}  created={p.created_at}")

        # Example 2 — paginate through every mock in the namespace.
        offset = 0
        while True:
            page = client.entity_search.search(
                entity_type=ENTITY_TYPE_MOCK,
                limit=ENTITY_SEARCH_DEFAULT_LIMIT,
                offset=offset,
            )
            for m in page.items:
                print(f"mock {m.name}  id={m.id}")
            offset += len(page.items)
            if not page.items or offset >= page.total:
                break


if __name__ == "__main__":
    main()
