# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the agent-task submit-and-wait automation helpers."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient, MockartyTaskError


def test_wait_for_result_completed(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    statuses = iter(["running", "running", "completed"])

    def responder(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        result = {"summary": "done"} if status == "completed" else None
        return httpx.Response(200, json={"task": {"id": "t1", "status": status, "result": result}})

    mock_api.get("/api/v1/agent/tasks/t1").mock(side_effect=responder)
    task = client.agent_tasks.wait_for_result("t1", poll_interval=0.001)
    assert task["status"] == "completed"
    assert task["result"] == {"summary": "done"}


def test_wait_for_result_failed(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/v1/agent/tasks/t1").mock(
        return_value=httpx.Response(200, json={"task": {"id": "t1", "status": "failed"}})
    )
    with pytest.raises(MockartyTaskError) as exc:
        client.agent_tasks.wait_for_result("t1", poll_interval=0.001)
    assert exc.value.status == "failed"
    assert exc.value.task["id"] == "t1"


def test_wait_for_result_cancelled(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.get("/api/v1/agent/tasks/t1").mock(
        return_value=httpx.Response(200, json={"task": {"id": "t1", "status": "cancelled"}})
    )
    with pytest.raises(MockartyTaskError) as exc:
        client.agent_tasks.wait_for_result("t1", poll_interval=0.001)
    assert exc.value.status == "cancelled"


def test_submit_and_wait(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post("/api/v1/agent/tasks").mock(
        return_value=httpx.Response(200, json={"task": {"id": "t9", "status": "queued"}})
    )
    mock_api.get("/api/v1/agent/tasks/t9").mock(
        return_value=httpx.Response(200, json={"task": {"id": "t9", "status": "completed", "result": "ok"}})
    )
    task = client.agent_tasks.submit_and_wait({"title": "audit", "prompt": "do it"}, poll_interval=0.001)
    assert task["status"] == "completed"
    assert task["result"] == "ok"
