# Copyright (c) 2026 Mockarty. All rights reserved.

"""Sync a test-discovery manifest to the Mockarty TCM catalogue.

Discovery ships the full inventory of tests an SDK/CI adapter knows about
(including tests that did not run this session) so the TCM catalogue
mirrors the code base. New tests are created; existing tests keep their
human-authored metadata; tests absent from an authoritative manifest are
marked orphaned (never deleted) when ``prune_missing=True``.

    MOCKARTY_URL       -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY   -- token
    MOCKARTY_NAMESPACE -- namespace slug (default "sandbox")

Two ways to drive discovery:

1. Programmatically, via ``client.discovery.sync(...)`` — shown below.
   Build the case list however your harness enumerates tests.

2. Automatically, via the bundled pytest plugin — run your suite with:

       MOCKARTY_BASE_URL=... MOCKARTY_API_KEY=... \
           pytest --mockarty-discover --mockarty-discover-source pytest:auth-suite

   The plugin builds the manifest from every collected item on
   ``pytest_collection_finish`` and posts it for you. Add
   ``--mockarty-discover-prune`` to orphan tests removed from the code.
"""

from __future__ import annotations

import os
import sys

from mockarty import DiscoveryCase, MockartyClient


def main() -> int:
    url = os.environ.get("MOCKARTY_URL", "http://localhost:5770")
    api_key = os.environ.get("MOCKARTY_API_KEY")
    namespace = os.environ.get("MOCKARTY_NAMESPACE", "sandbox")
    if not api_key:
        print("MOCKARTY_API_KEY is required", file=sys.stderr)
        return 2

    # The full inventory your adapter knows about. `full_name` is the
    # deterministic per-test identity (here: pytest node ids) used to match
    # a discovered test across syncs and to later execution results.
    cases = [
        DiscoveryCase(
            full_name="tests/auth_test.py::test_login",
            name="test_login",
            suite="auth",
            description="Logs an existing user in with valid credentials.",
            source_ref="tests/auth_test.py:12",
            labels=["smoke", "auth"],
        ),
        DiscoveryCase(
            full_name="tests/auth_test.py::test_logout",
            name="test_logout",
            suite="auth",
            source_ref="tests/auth_test.py:30",
            labels=["auth"],
        ),
        # A mapping works too — handy when your harness already produces dicts.
        {
            "full_name": "tests/billing_test.py::test_invoice",
            "name": "test_invoice",
            "suite": "billing",
            "source_ref": "tests/billing_test.py:5",
        },
    ]

    with MockartyClient(url, api_key=api_key, namespace=namespace) as client:
        result = client.discovery.sync(
            source="pytest:auth-suite",
            cases=cases,
            framework="pytest",
            # Orphan tests previously discovered for this source but absent now.
            prune_missing=True,
        )

    print(
        f"discovery [{result.source}]: "
        f"{result.created} new, {result.updated} updated, "
        f"{result.orphaned} orphaned ({result.total} total)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
