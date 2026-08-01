# Copyright (c) 2026 Mockarty. All rights reserved.

"""Build one release-ready report over several existing test runs.

Useful when a release gate combines heterogeneous executions (functional +
fuzz + chaos) into a single artifact for a dashboard, a wiki page or a CI
summary. Nothing is persisted server-side: the report is recomputed from the
listed runs on every call, so there is no parent entity to keep in sync or to
clean up afterwards.

Formats: ``unified`` (language-neutral JSON envelope), ``markdown``
(Slack-ready), ``html`` (self-contained, print-to-PDF) and ``junit``
(CI-ingest XML).

Configuration via environment variables:

    MOCKARTY_URL        -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY    -- token with namespace scope
    MOCKARTY_NAMESPACE  -- namespace slug
    SOURCE_RUN_IDS      -- comma-separated list of existing run UUIDs
    REPORT_NAME         -- optional report title (default "Release gate")
    OUTPUT_DIR          -- where to write the downloaded files (default ".")
"""

from __future__ import annotations

import os
import sys

from mockarty import MockartyClient
from mockarty.api.testruns import (
    AGGREGATE_REPORT_FORMAT_HTML,
    AGGREGATE_REPORT_FORMAT_JUNIT,
    AGGREGATE_REPORT_FORMAT_MARKDOWN,
    AGGREGATE_REPORT_FORMAT_UNIFIED,
)

_EXTENSIONS = {
    AGGREGATE_REPORT_FORMAT_UNIFIED: "json",
    AGGREGATE_REPORT_FORMAT_MARKDOWN: "md",
    AGGREGATE_REPORT_FORMAT_HTML: "html",
    AGGREGATE_REPORT_FORMAT_JUNIT: "xml",
}


def main() -> int:
    raw_ids = os.environ.get("SOURCE_RUN_IDS", "").strip()
    if not raw_ids:
        sys.stderr.write("SOURCE_RUN_IDS is required (comma-separated UUIDs)\n")
        return 2
    source_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
    if not source_ids:
        sys.stderr.write("At least one source run id is required\n")
        return 2

    name = os.environ.get("REPORT_NAME", "Release gate")
    out_dir = os.environ.get("OUTPUT_DIR", ".")
    os.makedirs(out_dir, exist_ok=True)

    with MockartyClient(
        base_url=os.environ.get("MOCKARTY_URL", "http://localhost:5770"),
        api_key=os.environ["MOCKARTY_API_KEY"],
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "default"),
    ) as client:
        for fmt, ext in _EXTENSIONS.items():
            payload = client.test_runs.aggregate_runs_report(
                source_ids, format=fmt, name=name
            )
            path = os.path.join(out_dir, f"aggregate-report.{ext}")
            with open(path, "wb") as fh:
                fh.write(payload)
            print(f"{fmt:>8}: {len(payload):>8} bytes -> {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
