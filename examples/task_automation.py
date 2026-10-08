# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Example: drive the issue tracker + TCM from the SDK.

Files a bug in the issue tracker, then creates a test case and runs it — the
kind of end-to-end automation a CI agent does.

Run:
    Set MOCKARTY_SERVER, MOCKARTY_API_KEY and MOCKARTY_NAMESPACE.
    From the SDK repository root: python -m examples.task_automation
"""

from __future__ import annotations

import os

from mockarty import MockartyAPIError, MockartyClient


def main() -> None:
    client = MockartyClient(
        base_url=os.environ.get("MOCKARTY_SERVER", "http://localhost:5770"),
        api_key=os.environ.get("MOCKARTY_API_KEY"),
        namespace=os.environ.get("MOCKARTY_NAMESPACE", "sandbox"),
    )

    it = client.issue_tracker
    projects = it.list_projects()
    if not projects:
        raise SystemExit("no projects in this namespace")
    pid = projects[0]["id"]

    issue = it.create_issue({"projectId": pid, "type": "bug", "title": "Checkout returns 500"})
    print(f"filed issue {issue.get('issueKey')}")
    try:
        comment = it.add_comment(issue["id"], "reproduced on staging")
    except MockartyAPIError as exc:
        if exc.state == "unknown":
            print("Comment outcome is unknown; keep handles without posting again:",
                  exc.operation_id, exc.capture_id)
        raise
    if comment.get("state") == "pending":
        print("Comment awaits confirmation; keep handles without posting again:",
              comment["operation_id"], comment["capture_id"])
    it.move_issue(issue["id"], "in_progress")

    tcm = client.tcm
    case = tcm.create_case({"name": "Checkout smoke"})
    run = tcm.run_case(case["id"])
    print(f"case run started: {run.get('runId')}")


if __name__ == "__main__":
    main()
