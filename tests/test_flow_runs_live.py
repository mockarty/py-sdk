# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live smoke test for FlowRunsAPI against a running admin.

Gated by ``MOCKARTY_LIVE_TOKEN`` — set the env var to a fresh API key
from ``POST /api/v1/auth/tokens`` and the test exercises the full
client → server → scriptengine → http runner pipeline. Skipped
otherwise so the offline suite stays self-contained.
"""

from __future__ import annotations

import os

import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_flow_runs_execute_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )
    flow = {
        "ir_version": 1,
        "name": "py-sdk-live-smoke",
        "steps": [
            {
                "kind": "http",
                "name": "probe",
                "http": {
                    "method": "GET",
                    "path": f"{LIVE_URL}/health",
                    "expects": [{"kind": "status", "args": [200]}],
                },
            },
        ],
    }
    resp = client.flow_runs.execute(flow)
    assert resp.get("status") == "passed", f"live run failed: {resp}"
    assert isinstance(resp.get("durationMs"), int)
    assert resp.get("durationMs") >= 0
