# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Kitchen-sink — end-to-end Mockarty Python SDK Tester showcase.

Python mirror of `sdk/go-sdk/examples/kitchen_sink/`. One script that
exercises every major Tester facet plus the reporting / upstream-tracker
side-channels you'd want in a real CI pipeline.

Run it:

    # 1. testbackend on 18770 (includes Jira + GitLab mock endpoints)
    mockarty-testbackend &

    # 2. (optional) Mockarty admin on 5770
    mockarty &

    # 3. Run the example
    TESTBACKEND_URL=http://127.0.0.1:18770 \\
    MOCKARTY_URL=http://127.0.0.1:5770 \\
    MOCKARTY_API_KEY=mk_... \\
    MOCKARTY_NAMESPACE=sandbox \\
    python kitchen_sink.py

What each step demonstrates:

  1+2. HTTP    — issue token → reuse via {{token}} interpolation
                (testbackend /api/v1/token-chain/{issue,validate})
  3.   GraphQL — typed query with variables + header
  4.   HTTP    — every Expect* on a single endpoint
  5.   Wrap    — group child steps as one Allure parent
  6.   Jira    — auto-file a Bug on failure (testbackend mock)
  7.   GitLab  — trigger pipeline + poll until success (mock)
  8.   TCM     — upload via client.external_runs.report
  9.   Exit    — non-zero on failure → set -e friendly
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from mockarty import MockartyClient
from mockarty.tester import Tester, wrap
from mockarty.tester.external_run import to_report_kwargs


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


CFG = {
    "testbackend": env("TESTBACKEND_URL", "http://127.0.0.1:18770"),
    "mockarty": env("MOCKARTY_URL", ""),
    "api_key": env("MOCKARTY_API_KEY", ""),
    "namespace": env("MOCKARTY_NAMESPACE", "sandbox"),
    "jira_project": env("JIRA_PROJECT_KEY", "QA"),
    "gitlab_project": env("GITLAB_PROJECT_ID", "1"),
}


def file_jira_ticket(errors: list[str]) -> None:
    """File a Bug to the testbackend Jira mock on failure.

    In production swap the URL + drop the auth header from your team's
    secret store. Endpoint shape mirrors the real Jira REST API v2.
    """
    payload = {
        "fields": {
            "project": {"key": CFG["jira_project"]},
            "summary": f"kitchen-sink run failed: {'; '.join(errors)[:80]}",
            "issuetype": {"name": "Bug"},
        }
    }
    r = httpx.post(f"{CFG['testbackend']}/rest/api/2/issue", json=payload, timeout=10.0)
    if r.status_code == 201:
        print(f"jira: filed {r.json()['key']} for {len(errors)} failure(s)")
    else:
        print(f"jira: {r.status_code} {r.text[:120]}", file=sys.stderr)


def trigger_gitlab_pipeline() -> None:
    """Kick the GitLab mock pipeline endpoint and poll until terminal.

    The mock's state machine advances pending → running → success on
    each fetch, so a real-world poll loop converges quickly.
    """
    pid = CFG["gitlab_project"]
    url = f"{CFG['testbackend']}/api/v4/projects/{pid}/trigger/pipeline?{urlencode({'ref': 'main'})}"
    r = httpx.post(url, timeout=10.0)
    if r.status_code != 201:
        print(f"gitlab trigger: {r.status_code}", file=sys.stderr)
        return
    pipeline = r.json()
    for _ in range(5):
        if pipeline["status"] in {"success", "failed"}:
            break
        time.sleep(0.1)
        poll = httpx.get(
            f"{CFG['testbackend']}/api/v4/projects/{pid}/pipelines/{pipeline['id']}",
            timeout=10.0,
        )
        pipeline = poll.json()
    print(f"gitlab pipeline #{pipeline['id']} → {pipeline['status']}")


def upload_external_run(t: Tester) -> None:
    """Upload the aggregated run to Mockarty TCM via external_runs.report."""
    if not (CFG["mockarty"] and CFG["api_key"]):
        return
    with MockartyClient(
        base_url=CFG["mockarty"],
        api_key=CFG["api_key"],
        namespace=CFG["namespace"],
    ) as client:
        kwargs = to_report_kwargs(
            t,
            case_name="kitchen-sink",
            framework="mockarty-py-tester",
            auto_create=True,
            full_name="examples.kitchen_sink",
        )
        resp = client.external_runs.report(**kwargs, namespace=CFG["namespace"])
        print(f"mockarty TCM: {resp.get('status')} (run={resp.get('run_id')} case={resp.get('case_id')})")


def main() -> int:
    t = Tester(base_url=CFG["testbackend"])

    # 1+2. Token chain wrapped under one Allure parent.
    def token_flow() -> None:
        (
            t.http().get("/api/v1/token-chain/issue")
            .expect_status(200)
            .expect_json_path("$.token", "tok-abc123-deterministic")
            .extract("$.token", "token")
        )
        (
            t.http().post("/api/v1/token-chain/validate")
            .header("Authorization", "Bearer {{token}}")
            .json({"action": "ping"})
            .expect_status(200)
            .expect_json_path("$.authorization", "Bearer tok-abc123-deterministic")
        )

    wrap(t, "token issue + authorised validate", token_flow)

    # 3. GraphQL query with variables. testbackend's user(id:) resolver
    # is seeded with user-1 (Admin User).
    (
        t.graphql(f"{CFG['testbackend']}/graphql")
        .query(
            "query GetUser($id: ID!) { user(id: $id) { name email } }",
            variables={"id": "user-1"},
        )
        .header("Authorization", "Bearer {{token}}")
        .expect_status(200)
        .expect_no_errors()
        .expect_field("$.data.user.name", "Admin User")
    )

    # 4. Assertion variety. /api/v1/users returns {items: [...]}.
    (
        t.http().get("/api/v1/users")
        .expect_status(200)
        .expect_header("Content-Type", "application/json; charset=utf-8")
        .expect_body_contains("Admin User")
        .expect_json_path("$.items[0].name", "Admin User")
    )

    # 5. Finish the chain (drains pending sends, records timings).
    t.finish()

    # 6+7. Upstream tracker side-channels when run failed.
    if not t.ok():
        errs = list(t.errors())
        print(f"kitchen-sink: {len(errs)} failed step(s); filing tracker artefacts")
        file_jira_ticket(errs)
        try:
            trigger_gitlab_pipeline()
        except Exception as e:  # pragma: no cover — best-effort side-channel
            print(f"gitlab pipeline trigger: {e}", file=sys.stderr)

    # 8. Mockarty TCM upload.
    try:
        upload_external_run(t)
    except Exception as e:  # pragma: no cover
        print(f"mockarty TCM upload: {e}", file=sys.stderr)

    # 9. Exit code = run status.
    if not t.ok():
        return 1
    print("kitchen-sink: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
