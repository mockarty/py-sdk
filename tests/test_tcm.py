# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the TCM cases/case-runs/defects automation API."""

from __future__ import annotations

import httpx
import respx

from mockarty import MockartyClient

C = "/api/v1/namespaces/test-ns/test-cases"
T = "/api/v1/namespaces/test-ns/tcm"


def test_tcm_flow(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post(C).mock(return_value=httpx.Response(201, json={"id": "c1", "title": "Login"}))
    mock_api.get(f"{C}/c1").mock(return_value=httpx.Response(200, json={"id": "c1", "status": "active"}))
    mock_api.get(C).mock(return_value=httpx.Response(200, json={"test_cases": [{"id": "c1"}], "total": 1}))
    mock_api.put(f"{C}/c1").mock(return_value=httpx.Response(200, json={"id": "c1", "title": "t2"}))
    mock_api.post(f"{C}/c1/run").mock(return_value=httpx.Response(200, json={"runId": "r1", "status": "running"}))
    mock_api.get(f"{C}/c1/runs").mock(return_value=httpx.Response(200, json={"runs": [{"id": "r1"}]}))
    mock_api.get(f"{T}/case-runs/r1").mock(return_value=httpx.Response(200, json={"id": "r1", "status": "passed"}))
    mock_api.post(f"{T}/case-runs/r1/cancel").mock(return_value=httpx.Response(200))
    mock_api.post(f"{T}/defects").mock(return_value=httpx.Response(200, json={"id": "d1", "title": "bug"}))
    mock_api.get(f"{T}/defects").mock(return_value=httpx.Response(200, json={"defects": [{"id": "d1"}]}))
    mock_api.delete(f"{T}/defects/d1").mock(return_value=httpx.Response(200))
    mock_api.delete(f"{C}/c1").mock(return_value=httpx.Response(200))

    t = client.tcm
    assert t.create_case({"title": "Login"})["id"] == "c1"
    assert t.get_case("c1")["status"] == "active"
    assert len(t.list_cases()) == 1
    assert t.update_case("c1", {"title": "t2"})["title"] == "t2"
    assert t.run_case("c1")["runId"] == "r1"
    assert len(t.list_case_runs("c1")) == 1
    assert t.get_case_run("r1")["status"] == "passed"
    t.cancel_case_run("r1")
    assert t.create_defect({"title": "bug"})["id"] == "d1"
    assert len(t.list_defects()) == 1
    t.delete_defect("d1")
    t.delete_case("c1")
