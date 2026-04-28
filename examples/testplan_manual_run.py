#!/usr/bin/env python3
# Copyright (c) 2026 Mockarty. All rights reserved.

"""Example: trigger a manual Test Plan, resolve every pending step, fetch the
report. Mirrors the Go SDK example under sdk/go-sdk/examples/testplans/manual_run/.

Run with::

    MOCKARTY_BASE_URL=http://localhost:5770 \\
    MOCKARTY_API_KEY=mk_xxx \\
    MOCKARTY_PLAN_ID='#42' \\
    python sdk/py-sdk/examples/testplan_manual_run.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from mockarty import MockartyClient


def main() -> int:
    plan_id = os.environ.get("MOCKARTY_PLAN_ID")
    if not plan_id:
        print("MOCKARTY_PLAN_ID is required", file=sys.stderr)
        return 2

    namespace = os.environ.get("MOCKARTY_NAMESPACE", "sandbox")

    with MockartyClient(namespace=namespace) as client:
        # 1. Trigger a manual run.
        run = client.test_plans.run_manual(
            plan_id,
            execution_mode_override="manual",
            record_detailed=True,
            notify_on_completion=True,
            notify_emails=["qa-lead@example.com"],
        )
        print(f"Triggered run {run.id} (status={run.status})")

        # 2 + 3. Poll the bell counter, resolve every pending step with pass.
        deadline = time.monotonic() + 4 * 60
        resolved: set[str] = set()
        while time.monotonic() < deadline:
            am = client.me.awaiting_manual()
            if am.get("count", 0) == 0:
                # Either run finished or nothing pending right now.
                status = client.test_plans.get_run_status(run.id)
                if status.status in ("completed", "failed", "cancelled"):
                    break
                time.sleep(2)
                continue
            for item in am.get("items", []):
                step_run = item.get("stepRunId")
                if step_run in resolved or item.get("planRunId") != run.id:
                    continue
                client.test_plans.resolve_step(
                    item["runId"],
                    item["stepUid"],
                    resolution="pass",
                    note="auto-resolved by CI manual_run example",
                    note_fmt="plain",
                    namespace=item["namespace"],
                )
                resolved.add(step_run)
                print(f"Resolved step {item['stepUid']} (case-run {item['runId']})")
            time.sleep(1)

        # 4. Download the standalone HTML report.
        out = client.test_plans.get_report(run.id, format="html")
        Path("report.html").write_bytes(out)
        print("Saved report.html")

    return 0


if __name__ == "__main__":
    sys.exit(main())
