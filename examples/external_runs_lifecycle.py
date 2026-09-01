# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Example: stream a long test's results incrementally via the lifecycle API.

Unlike ``report`` (one-shot upload of a finished run), the lifecycle API reports
as the suite runs: ``start_run`` → ``append_steps`` (repeatedly) → ``finish_run``.
The finished view carries the resolved TCM case/run ids the ingest matched.

Run:
    MOCKARTY_SERVER=http://localhost:5770 \
      MOCKARTY_API_KEY=mk_... python external_runs_lifecycle.py
"""

from __future__ import annotations

import os

from mockarty import MockartyClient


def main() -> None:
    client = MockartyClient(
        base_url=os.environ.get("MOCKARTY_SERVER", "http://localhost:5770"),
        api_key=os.environ.get("MOCKARTY_API_KEY"),
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "sandbox"),
    )
    er = client.external_runs

    run = er.start_run(
        {
            "name": "checkout smoke",
            "framework": "custom",
            "full_name": "suites.checkout.smoke",
        }
    )
    run_id = run["id"]
    print(f"started run {run_id}")

    for step in [
        {"step_key": "login", "name": "log in", "status": "passed", "duration_ms": 120},
        {
            "step_key": "cart",
            "name": "add to cart",
            "status": "passed",
            "duration_ms": 80,
        },
        {
            "step_key": "pay",
            "name": "pay",
            "status": "failed",
            "message": "gateway 500",
            "duration_ms": 210,
        },
    ]:
        run = er.append_steps_at_revision(run_id, run["revision"], [step])

    fin = er.finish_run_at_revision(
        run_id, run["revision"], "failed", summary="payment gateway returned 500"
    )
    print(
        f"finished: status={fin.get('status')} "
        f"case={fin.get('resolved_case_id')} run={fin.get('resolved_run_id')}"
    )


if __name__ == "__main__":
    main()
