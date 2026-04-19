# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test Plans end-to-end example.

This single script demonstrates the three canonical Test Plan scenarios:

  1. **basic_run**    -- create a plan, trigger it, poll until done
  2. **sse_stream**   -- subscribe to the live SSE event stream for a run
  3. **ci_integration** -- attach a webhook, trigger, wait, download Allure zip

Select the scenario with ``python testplans.py <basic|stream|ci>``. All
configuration is read from environment variables:

    MOCKARTY_URL       -- server URL (default http://localhost:5770)
    MOCKARTY_API_KEY   -- token with namespace scope
    MOCKARTY_NAMESPACE -- namespace slug
    PLAN_ID            -- existing plan id (for stream / ci scenarios)
    RUN_ID             -- existing run id (for stream scenario)
    CI_WEBHOOK_URL     -- CI integration endpoint (for ci scenario)
    CI_WEBHOOK_SECRET  -- HMAC secret for CI integration
"""

from __future__ import annotations

import os
import sys

from mockarty import (
    MockartyClient,
    RunCancelledError,
    RunFailedError,
    TestPlan,
    TestPlanItem,
    Webhook,
)


def _client() -> MockartyClient:
    return MockartyClient(
        base_url=os.environ.get("MOCKARTY_URL", "http://localhost:5770"),
        api_key=os.environ["MOCKARTY_API_KEY"],
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "default"),
    )


def scenario_basic() -> int:
    """Create a plan from a single functional collection and run it."""
    with _client() as client:
        plan = TestPlan(
            namespace=client.namespace,
            name="SDK Example Smoke",
            description="Created by the Python SDK example",
            items=[
                TestPlanItem(
                    order=0,
                    type="functional",
                    resource_id=os.environ["COLLECTION_ID"],
                    name="Smoke",
                )
            ],
        )
        created = client.test_plans.create(plan)
        print(f"Plan created: {created.id} (#{created.numeric_id})")

        run = client.test_plans.run(created.id)
        print(f"Triggered run: {run.id}")

        try:
            final = client.test_plans.wait_for_run(run.id, poll_interval=2.0)
            print(
                f"Run completed ok: total={final.total_items} "
                f"failed={final.failed_items}"
            )
            return 0
        except RunFailedError as err:
            print(f"Run failed: {err}")
            return 1
        except RunCancelledError as err:
            print(f"Run cancelled: {err}")
            return 2


def scenario_stream() -> int:
    """Attach to the SSE stream of an existing run."""
    run_id = os.environ["RUN_ID"]
    with _client() as client:
        for event in client.test_plans.stream_run(run_id):
            print(f"[{event.kind}] {event.data}")
    return 0


def scenario_ci() -> int:
    """Full CI pipeline: attach webhook, trigger, wait, download report."""
    plan_id = os.environ["PLAN_ID"]
    with _client() as client:
        try:
            client.test_plans.add_webhook(
                plan_id,
                Webhook(
                    url=os.environ["CI_WEBHOOK_URL"],
                    events=["run.completed", "run.failed"],
                    secret=os.environ.get("CI_WEBHOOK_SECRET"),
                    enabled=True,
                ),
            )
        except Exception as err:  # noqa: BLE001 -- example code
            print(f"attach webhook: {err} (continuing)")

        run = client.test_plans.run(plan_id)
        print(f"Triggered run {run.id}")

        exit_code = 0
        try:
            final = client.test_plans.wait_for_run(run.id, poll_interval=5.0)
            print(f"Final: PASS ({final.failed_items}/{final.total_items} failed)")
        except RunFailedError:
            print("Final: FAIL")
            exit_code = 1
        except RunCancelledError:
            print("Final: CANCELLED")
            exit_code = 2

        with open("report.zip", "wb") as out:
            client.test_plans.download_report_zip(run.id, out)
        print("Saved ./report.zip")
        return exit_code


def main() -> int:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "basic"
    if scenario == "basic":
        return scenario_basic()
    if scenario == "stream":
        return scenario_stream()
    if scenario == "ci":
        return scenario_ci()
    print(f"unknown scenario: {scenario!r} (use basic | stream | ci)")
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
