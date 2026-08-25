# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the agent-task submit-and-wait automation helpers."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient, MockartyTaskError


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


def test_get_external_action_receipt_capabilities(
    client: MockartyClient, mock_api: respx.MockRouter
) -> None:
    receipt_key = "sha256:" + "a" * 64
    mock_api.get("/api/v1/agent/tasks/t1").mock(return_value=httpx.Response(200, json={
        "task": {"id": "t1", "status": "running"},
        "toolReceipts": [{"receiptKey": receipt_key, "status": "awaiting_reconcile", "version": 4}],
        "canReconcileToolReceipts": False,
        "toolReceiptRetryAllowed": False,
        "toolReceiptReconcileBlockedReason": "task_active",
    }))
    task = client.agent_tasks.get("t1")
    assert task["toolReceipts"][0]["version"] == 4
    assert task["canReconcileToolReceipts"] is False
    assert task["toolReceiptRetryAllowed"] is False
    assert task["toolReceiptReconcileBlockedReason"] == "task_active"


def test_reconcile_external_action_receipt_wire_contract(
    client: MockartyClient, mock_api: respx.MockRouter
) -> None:
    receipt_key = "sha256:" + "a" * 64
    reconcile = mock_api.post(
        f"/api/v1/agent/tasks/t1/tool-receipts/{receipt_key}/reconcile"
    ).mock(return_value=httpx.Response(200, json={
        "receipt": {"receiptKey": receipt_key, "status": "done", "version": 5}
    }))
    receipt = client.agent_tasks.reconcile_tool_receipt(
        "t1", receipt_key, expected_version=4, idempotency_key="review-1",
        decision="already_applied", reason="verified in billing", result="invoice 42",
    )
    assert receipt["status"] == "done"
    sent = reconcile.calls.last.request.content
    assert b'"expectedVersion":4' in sent
    assert b'"idempotencyKey":"review-1"' in sent


@pytest.mark.asyncio
@respx.mock
async def test_async_reconcile_external_action_receipt() -> None:
    base_url = "http://127.0.0.1:5770"
    receipt_key = "sha256:" + "b" * 64
    route = respx.post(
        f"{base_url}/api/v1/agent/tasks/t1/tool-receipts/{receipt_key}/reconcile"
    ).mock(return_value=httpx.Response(200, json={
        "receipt": {"receiptKey": receipt_key, "status": "retry_permitted", "version": 8}
    }))
    async with AsyncMockartyClient(base_url=base_url, api_key="key", max_retries=0) as client:
        receipt = await client.agent_tasks.reconcile_tool_receipt(
            "t1", receipt_key, expected_version=7, idempotency_key="review-2",
            decision="retry_once", reason="target has no matching operation",
        )
    assert receipt["status"] == "retry_permitted"
    assert b'"result":""' in route.calls.last.request.content


def test_legacy_session_recovery(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    list_route = mock_api.get("/api/v1/agent/sessions/legacy").mock(
        return_value=httpx.Response(200, json={"sessions": [{"originalId": "legacy-1"}], "nextCursor": "next"})
    )
    claim_route = mock_api.post("/api/v1/agent/sessions/legacy/legacy-1/claim").mock(
        return_value=httpx.Response(200, json={"session": {"id": "session-1", "namespace": "payments"}})
    )
    page = client.agent_tasks.list_legacy_sessions(limit=10, cursor="next/value")
    assert page["sessions"][0]["originalId"] == "legacy-1"
    assert list_route.calls.last.request.url.params["limit"] == "10"
    assert list_route.calls.last.request.url.params["cursor"] == "next/value"
    session = client.agent_tasks.claim_legacy_session(
        "legacy-1", namespace="payments", acknowledge_unknown_origin=True
    )
    assert session == {"id": "session-1", "namespace": "payments"}
    assert b'"acknowledgeUnknownOrigin":true' in claim_route.calls.last.request.content


@pytest.mark.asyncio
@respx.mock
async def test_async_legacy_session_recovery() -> None:
    base_url = "http://127.0.0.1:5770"
    respx.get(f"{base_url}/api/v1/agent/sessions/legacy").mock(
        return_value=httpx.Response(200, json={"sessions": []})
    )
    respx.post(f"{base_url}/api/v1/agent/sessions/legacy/legacy-1/claim").mock(
        return_value=httpx.Response(200, json={"session": {"id": "session-1"}})
    )
    async with AsyncMockartyClient(base_url=base_url, api_key="key", max_retries=0) as client:
        assert (await client.agent_tasks.list_legacy_sessions())["sessions"] == []
        assert (await client.agent_tasks.claim_legacy_session(
            "legacy-1", namespace="payments", acknowledge_unknown_origin=True
        ))["id"] == "session-1"
