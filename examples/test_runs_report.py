# Copyright (c) 2026 Mockarty. All rights reserved.

"""Fetch the unified test-run report in every supported format.

Works for any mode (functional / load / fuzz / chaos / contract / merged).

    MOCKARTY_URL       -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY   -- token
    MOCKARTY_NAMESPACE -- namespace slug
    RUN_ID             -- run UUID
"""

from __future__ import annotations

import os
import sys

from mockarty import MockartyClient
from mockarty.api.testruns import (
    TEST_RUN_REPORT_FORMAT_ALLURE_JSON,
    TEST_RUN_REPORT_FORMAT_ALLURE_ZIP,
    TEST_RUN_REPORT_FORMAT_HTML,
    TEST_RUN_REPORT_FORMAT_JUNIT,
    TEST_RUN_REPORT_FORMAT_MARKDOWN,
    TEST_RUN_REPORT_FORMAT_UNIFIED_JSON,
)


def main() -> int:
    url = os.environ.get("MOCKARTY_URL", "http://localhost:5770")
    api_key = os.environ.get("MOCKARTY_API_KEY")
    namespace = os.environ.get("MOCKARTY_NAMESPACE", "default")
    run_id = os.environ.get("RUN_ID")
    if not api_key or not run_id:
        print("MOCKARTY_API_KEY and RUN_ID are required", file=sys.stderr)
        return 2

    client = MockartyClient(url, api_key=api_key, namespace=namespace)
    api = client.test_runs

    targets = [
        (TEST_RUN_REPORT_FORMAT_UNIFIED_JSON, "run.unified.json"),
        (TEST_RUN_REPORT_FORMAT_ALLURE_JSON, "run.allure.json"),
        (TEST_RUN_REPORT_FORMAT_ALLURE_ZIP, "run.allure.zip"),
        (TEST_RUN_REPORT_FORMAT_JUNIT, "run.junit.xml"),
        (TEST_RUN_REPORT_FORMAT_MARKDOWN, "run.md"),
        (TEST_RUN_REPORT_FORMAT_HTML, "run.html"),
    ]
    for fmt, out in targets:
        data = api.get_report(run_id, format=fmt)
        with open(out, "wb") as fh:
            fh.write(data)
        print(f"wrote {out} ({len(data)} bytes, format={fmt})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
