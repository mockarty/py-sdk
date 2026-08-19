# Copyright (c) 2026 Mockarty. All rights reserved.

"""Example: kick off a Mockarty Security Agent scan from CI/CD.

Starts a passive scan, polls until completion, downloads the SARIF
report, then exits non-zero if any critical finding is present so the
CI pipeline fails the job.

Usage:
    export MOCKARTY_BASE_URL=http://localhost:5770
    export MOCKARTY_API_KEY=mk_xxx
    export MOCKARTY_NAMESPACE=production
    export SCAN_TARGET=https://api.example.com
    python examples/security_scan.py
"""

from __future__ import annotations

import os
import sys
import time

from mockarty import MockartyClient


def main() -> int:
    target = os.environ.get("SCAN_TARGET", "https://api.example.com")
    namespace = os.environ.get("MOCKARTY_NAMESPACE", "sandbox")
    sarif_path = os.environ.get("SARIF_OUTPUT", "mockarty-security.sarif.json")

    with MockartyClient(namespace=namespace) as client:
        # 1) Start a passive scan. Use ``safe-active`` for routine CI,
        #    ``intrusive`` for pre-prod, ``destructive`` for ephemeral
        #    test environments only.
        report = client.security.start_scan(
            namespace=namespace,
            target=target,
            persona="web_pentester",
            intensity="passive",
            title="ci-nightly",
            max_cost_usd_micros=5_000_000,  # 5 USD ceiling
        )
        report_id = report["id"]
        print(f"started: report {report_id} (status={report.get('status')})")

        # 2) Poll until terminal state.
        for _ in range(180):  # 30 minutes max @ 10s intervals
            time.sleep(10)
            got = client.security.get_test_run_report(report_id)
            status = got.get("status")
            print(
                f"  status={status} tokens={got.get('costTokens')} "
                f"cost_usd_micros={got.get('costUsdMicros')}"
            )
            if status in {"done", "failed", "cancelled"}:
                report = got
                break
        else:
            client.security.cancel_scan(report_id)
            print("timeout — scan cancelled", file=sys.stderr)
            return 124

        if report.get("status") != "done":
            print(f"scan ended in non-success state: {report.get('status')}", file=sys.stderr)
            return 1

        # 3) Pull severities of interest.
        highs = client.security.list_findings(report_id, severity="high")
        crits = client.security.list_findings(report_id, severity="critical")
        print(f"findings: {len(highs)} high, {len(crits)} critical")

        # 4) Persist SARIF for the CI step that uploads to Code Scanning.
        sarif_bytes = client.security.export_report(report_id, format="sarif")
        with open(sarif_path, "wb") as fh:
            fh.write(sarif_bytes)
        print(f"wrote {sarif_path} ({len(sarif_bytes)} bytes)")

        # 5) CI gate: critical = fail the pipeline.
        return 2 if crits else 0


if __name__ == "__main__":
    sys.exit(main())
