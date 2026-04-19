# Copyright (c) 2026 Mockarty. All rights reserved.

"""Focused Test Plans TP-6b demo — namespace-scoped PATCH, ad-hoc run, report.

Runs the new TP-6b endpoints end-to-end against a live Mockarty server::

    create (base route) -> patch (namespace, with If-Match)
        -> ad-hoc run (single-call plan + run)
        -> poll run to terminal status
        -> fetch Allure JSON + download ZIP archive
        -> soft-delete the plan

All configuration comes from environment variables (no CLI flags / argparse)
so the script stays copy-paste friendly:

    MOCKARTY_URL       -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY   -- token with namespace scope (required)
    MOCKARTY_NAMESPACE -- namespace slug (default ``default``)
    COLLECTION_ID      -- UUID of an API Tester collection to attach

Exit codes::

    0 -- demo finished, all plans passed
    1 -- demo finished, plan run failed
    2 -- demo finished, plan run was cancelled
    64 -- missing required environment variables
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mockarty import (
    AdHocItem,
    CreateAdHocRunRequest,
    MockartyClient,
    PatchPlanRequest,
    PreconditionFailedError,
    RunCancelledError,
    RunFailedError,
    TestPlan,
    TestPlanItem,
)


def _client() -> MockartyClient:
    """Build a client from the standard MOCKARTY_* environment variables."""
    return MockartyClient(
        base_url=os.environ.get("MOCKARTY_URL", "http://localhost:5770"),
        api_key=os.environ["MOCKARTY_API_KEY"],
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "default"),
    )


def main() -> int:
    collection_id = os.environ.get("COLLECTION_ID")
    if not collection_id:
        print("COLLECTION_ID env var is required (UUID of a collection)")
        return 64

    with _client() as client:
        ns = client.namespace

        # 1. Create a plan using the base route — any endpoint is fine here;
        #    TP-6b adds new surface without removing the legacy one.
        plan = client.test_plans.create(
            TestPlan(
                namespace=ns,
                name="TP-6b demo",
                description="Created by test_plans_demo.py",
                items=[
                    TestPlanItem(
                        order=0,
                        type="functional",
                        resource_id=collection_id,
                        name="Smoke",
                    )
                ],
            )
        )
        print(f"[1/6] Plan created: {plan.id} (#{plan.numeric_id})")

        # 2. PATCH with auto-fetched If-Match. For concurrent writers pass
        #    the etag from a prior snapshot via if_match=... .
        try:
            plan = client.test_plans.patch(
                plan.id,
                PatchPlanRequest(description="Patched via SDK demo"),
            )
            print("[2/6] Plan patched")
        except PreconditionFailedError as err:
            # Someone else touched the plan between create and patch.
            # Re-fetching + retrying is the canonical recovery path — shown
            # here for documentation even though a first-writer should not
            # hit it.
            print(f"[2/6] Etag mismatch ({err}); re-fetching and retrying")
            fresh = client.test_plans.get(plan.id)
            plan = client.test_plans.patch(
                fresh.id,
                PatchPlanRequest(description="Patched via SDK demo"),
                if_match=f'"{fresh.updated_at}"',
            )

        # 3. Kick off an ad-hoc master run — no persisted plan row is
        #    visible in the main catalogue; the server uses
        #    a hidden adhoc=true plan to drive the orchestrator.
        adhoc = client.test_plans.create_ad_hoc_run(
            CreateAdHocRunRequest(
                name="TP-6b demo ad-hoc",
                items=[
                    AdHocItem(type="functional", ref_id=collection_id, order=0),
                ],
            )
        )
        print(f"[3/6] Ad-hoc run dispatched: run={adhoc.run_id}")

        # 4. Poll the run until terminal. wait_for_run raises on fail /
        #    cancel so CI jobs can exit non-zero without branching.
        exit_code = 0
        try:
            run = client.test_plans.wait_for_run(adhoc.run_id, poll_interval=2.0)
            print(
                f"[4/6] Run completed: total={run.total_items} "
                f"failed={run.failed_items}"
            )
        except RunFailedError as err:
            print(f"[4/6] Run FAILED: {err}")
            exit_code = 1
        except RunCancelledError as err:
            print(f"[4/6] Run CANCELLED: {err}")
            exit_code = 2

        # 5. Fetch the merged Allure JSON. The raw body is also preserved
        #    on report.raw for callers that want a second decode pass.
        report = client.test_plans.get_run_report(adhoc.plan_id, adhoc.run_id)
        print(
            f"[5/6] Report: status={report.status} "
            f"items={len(report.items)}"
        )

        # 6. Download the ZIP archive (attachments + result.json).
        dest = Path("report.zip")
        with dest.open("wb") as fh:
            client.test_plans.get_run_report_zip(
                adhoc.plan_id, adhoc.run_id, fh
            )
        print(f"[6/6] ZIP archive saved to {dest.resolve()}")

        # Clean up the non-ad-hoc plan we created in step 1. The ad-hoc
        # plan is hidden and cleaned by the server's retention sweeper.
        client.test_plans.delete(plan.id)
        print(f"      Demo plan deleted")
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
