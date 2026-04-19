# Copyright (c) 2026 Mockarty. All rights reserved.

"""Fetch every available report format for a Test Plan run.

Given an existing run in a terminal state, downloads all five formats:

  * report.json          Allure-compatible JSON
  * report.zip           Allure directory as a zip
  * report.junit.xml     Standards-compliant JUnit XML
  * report.md            Markdown human summary
  * report.unified.json  Native Mockarty unified envelope

Configuration via environment variables:

    MOCKARTY_URL       -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY   -- token with namespace scope
    MOCKARTY_NAMESPACE -- namespace slug
    PLAN_REF           -- plan slug, UUID, or numeric id
    RUN_ID             -- run UUID (must be terminal)
"""

from __future__ import annotations

import os
import sys

from mockarty import MockartyClient


def main() -> int:
    plan_ref = os.environ.get("PLAN_REF")
    run_id = os.environ.get("RUN_ID")
    if not plan_ref or not run_id:
        sys.stderr.write("PLAN_REF and RUN_ID are required\n")
        return 2

    with MockartyClient(
        base_url=os.environ.get("MOCKARTY_URL", "http://localhost:5770"),
        api_key=os.environ["MOCKARTY_API_KEY"],
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "default"),
    ) as client:
        api = client.test_plans

        # 1. Allure JSON — strongly typed decode + raw bytes.
        allure = api.get_run_report(plan_ref, run_id)
        with open("report.json", "wb") as fh:
            fh.write(allure.raw or b"")
        print(f"wrote report.json (status={allure.status})")

        # 2. Allure ZIP — streams to disk chunk-by-chunk.
        with open("report.zip", "wb") as fh:
            api.get_run_report_zip(plan_ref, run_id, fh)
        print("wrote report.zip")

        # 3. JUnit XML — feed into Jenkins / GitLab / GitHub Actions.
        junit = api.get_run_report_junit(plan_ref, run_id)
        with open("report.junit.xml", "wb") as fh:
            fh.write(junit)
        print(f"wrote report.junit.xml ({len(junit)} bytes)")

        # 4. Markdown — Slack / email / wiki-ready.
        md = api.get_run_report_markdown(plan_ref, run_id)
        with open("report.md", "wb") as fh:
            fh.write(md)
        print(f"wrote report.md ({len(md)} bytes)")

        # 5. Unified JSON — native envelope, typed counts.
        unified = api.get_run_report_unified(plan_ref, run_id)
        with open("report.unified.json", "wb") as fh:
            fh.write(unified.raw or b"")
        counts = unified.counts
        print(
            f"wrote report.unified.json — plan={unified.plan_name!r} "
            f"run={unified.run_id} items={counts.total} "
            f"(passed={counts.passed} failed={counts.failed} "
            f"skipped={counts.skipped} broken={counts.broken}) "
            f"duration={unified.duration_ms}ms"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
