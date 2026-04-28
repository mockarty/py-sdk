# Copyright (c) 2026 Mockarty. All rights reserved.

"""Aggregate several existing test runs into a single "merged" run.

Useful when a release gate combines heterogeneous executions (functional +
fuzz + chaos) into one artifact for a dashboard or wiki page. The merge
parent row tracks the sources live; downloading the unified JSON report
gives you a language-neutral envelope, markdown is Slack-ready.

Configuration via environment variables:

    MOCKARTY_URL        -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY    -- token with namespace scope
    MOCKARTY_NAMESPACE  -- namespace slug
    SOURCE_RUN_IDS      -- comma-separated list of existing run UUIDs
    MERGE_NAME          -- optional label for the merge (default "Release gate")
"""

from __future__ import annotations

import os
import sys

from mockarty import MockartyClient
from mockarty.api.testruns import (
    MERGED_RUN_REPORT_FORMAT_MARKDOWN,
    MERGED_RUN_REPORT_FORMAT_UNIFIED,
)


def main() -> int:
    raw_ids = os.environ.get("SOURCE_RUN_IDS", "").strip()
    if not raw_ids:
        sys.stderr.write("SOURCE_RUN_IDS is required (comma-separated UUIDs)\n")
        return 2
    source_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
    if len(source_ids) < 1:
        sys.stderr.write("At least one source run id is required\n")
        return 2

    with MockartyClient(
        base_url=os.environ.get("MOCKARTY_URL", "http://localhost:5770"),
        api_key=os.environ["MOCKARTY_API_KEY"],
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "default"),
    ) as client:
        name = os.environ.get("MERGE_NAME", "Release gate")
        view = client.test_runs.merge_runs(name=name, source_ids=source_ids)
        merged_id = view.run.id if view.run else ""
        print(f"Created merged run {merged_id} with {len(view.sources)} sources")

        # Immediately fetch the latest snapshot — terminal-transition hook may
        # have already rolled up final totals.
        latest = client.test_runs.get_merged_run(merged_id)
        print(f"Status: {latest.run.status if latest.run else 'unknown'}")

        # List merges in the namespace — newest first, server caps at 500.
        page = client.test_runs.list_merged_runs(limit=10)
        print(f"Namespace has {page.total} merged runs; page size {page.limit}")

        # Download both report formats.
        unified = client.test_runs.get_merged_run_report(
            merged_id, format=MERGED_RUN_REPORT_FORMAT_UNIFIED
        )
        markdown = client.test_runs.get_merged_run_report(
            merged_id, format=MERGED_RUN_REPORT_FORMAT_MARKDOWN
        )
        print(f"Unified report: {len(unified)} bytes; markdown: {len(markdown)} bytes")

        # Cleanup (optional): delete the parent; source runs are untouched.
        if os.environ.get("DELETE_AFTER") == "1":
            client.test_runs.delete_merged_run(merged_id)
            print(f"Deleted merged run {merged_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
