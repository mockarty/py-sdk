# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the streaming external-run lifecycle API."""

from __future__ import annotations

import json

import httpx
import respx

from mockarty import MockartyClient

BASE = "/api/v1/namespaces/test-ns/tcm/external-runs/lifecycle"


def test_lifecycle_flow(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post(BASE).mock(return_value=httpx.Response(200, json={"id": "run-1", "status": "running", "name": "checkout"}))
    mock_api.post(f"{BASE}/run-1/steps").mock(return_value=httpx.Response(200, json={"id": "run-1", "status": "running", "step_count": 2}))
    mock_api.get(f"{BASE}/run-1").mock(return_value=httpx.Response(200, json={"id": "run-1", "status": "running", "step_count": 2}))
    mock_api.post(f"{BASE}/run-1/finish").mock(return_value=httpx.Response(200, json={"id": "run-1", "status": "passed", "resolved_case_id": "case-9", "resolved_run_id": "crun-9"}))
    mock_api.get(BASE).mock(return_value=httpx.Response(200, json={"runs": [{"id": "run-1"}], "total": 1}))

    er = client.external_runs
    run = er.start_run({"name": "checkout", "framework": "custom"})
    assert run["id"] == "run-1" and run["status"] == "running"

    run = er.append_steps("run-1", [{"step_key": "s1", "name": "login", "status": "passed"},
                                     {"step_key": "s2", "name": "pay", "status": "passed"}])
    assert run["step_count"] == 2

    got = er.get_run("run-1")
    assert got["step_count"] == 2

    fin = er.finish_run("run-1", "passed", summary="ok")
    assert fin["status"] == "passed" and fin["resolved_case_id"] == "case-9"

    runs = er.list_runs()
    assert len(runs) == 1 and runs[0]["id"] == "run-1"
