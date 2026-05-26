# kitchen_sink — end-to-end Tester DSL showcase (Python)

Python mirror of the Go SDK's `examples/kitchen_sink`. One script that
exercises every Tester facet plus the reporting / upstream-tracker
side-channels you'd want in a CI pipeline.

## What it demonstrates

| Step | Facet | What it proves |
|------|-------|----------------|
| 1+2  | `t.http()` | Token chain: GET `/token-chain/issue` → extract → POST `/token-chain/validate` with `{{token}}` interpolation |
| 3    | `t.graphql()` | Query with variables + header, `expect_field` JSONPath |
| 4    | `t.http()` | Every `expect_*` kind on a single response |
| 5    | `wrap(t, ...)` | Group steps as one Allure parent |
| 6    | Jira mock | Auto-file a Bug on failure (no real Jira needed) |
| 7    | GitLab mock | Trigger pipeline + poll until success |
| 8    | `client.external_runs.report(...)` | Upload to Mockarty TCM as a synthetic case run |
| 9    | Exit code | Non-zero on failure → `set -e` friendly |

## Run it

```bash
# 1. testbackend on 18770 (provides token-chain + Jira/GitLab mocks)
mockarty-testbackend &

# 2. (optional) Mockarty admin on 5770 for the TCM upload
mockarty &

# 3. Run
TESTBACKEND_URL=http://127.0.0.1:18770 \
MOCKARTY_URL=http://127.0.0.1:5770 \
MOCKARTY_API_KEY=mk_... \
MOCKARTY_NAMESPACE=sandbox \
python kitchen_sink/main.py
```

Verified live: `kitchen-sink: ok` end-to-end against a running
testbackend. All steps green, ~150 ms total.

## Why a subdir?

`kitchen_sink/` is its own directory (`main.py` inside) so Python
doesn't pull `examples/collections.py` into `sys.path` when running
the script — a Py-specific gotcha that doesn't hit the Go layout.

## Environment variables

Same matrix as the Go SDK kitchen_sink — `TESTBACKEND_URL`,
`MOCKARTY_URL`, `MOCKARTY_API_KEY`, `MOCKARTY_NAMESPACE`,
`JIRA_PROJECT_KEY`, `GITLAB_PROJECT_ID`.
