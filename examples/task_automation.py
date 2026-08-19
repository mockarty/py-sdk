# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Example: drive the issue tracker + TCM from the SDK.

Files a bug in the issue tracker, then creates a test case and runs it — the
kind of end-to-end automation a CI agent does.

Run:
    MOCKARTY_SERVER=http://localhost:5770 MOCKARTY_API_KEY=mk_... python task_automation.py
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

    it = client.issue_tracker
    projects = it.list_projects()
    if not projects:
        raise SystemExit("no projects in this namespace")
    pid = projects[0]["id"]

    issue = it.create_issue({"projectId": pid, "type": "bug", "title": "Checkout returns 500"})
    print(f"filed issue {issue.get('issueKey')}")
    it.add_comment(issue["id"], "reproduced on staging")
    it.move_issue(issue["id"], "in_progress")

    tcm = client.tcm
    case = tcm.create_case({"title": "Checkout smoke"})
    run = tcm.run_case(case["id"])
    print(f"case run started: {run.get('runId')}")


if __name__ == "__main__":
    main()
