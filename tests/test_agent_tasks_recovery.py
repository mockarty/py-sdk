# Copyright (c) 2026 Mockarty. All rights reserved.

"""Legacy agent-session recovery API contract (sync + async)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


SESSION_ID = "00000000-0000-4000-8000-000000000501"


@respx.mock
def test_legacy_session_recovery_sync(client: MockartyClient) -> None:
    list_route = respx.get("http://localhost:5770/api/v1/agent/sessions/legacy").mock(
        return_value=httpx.Response(200, json={"sessions": [], "nextCursor": "next"})
    )
    page = client.agent_tasks.list_legacy_sessions(limit=25, cursor="cursor value")
    assert page["nextCursor"] == "next"
    assert list_route.calls.last.request.url.params["limit"] == "25"
    assert list_route.calls.last.request.url.params["cursor"] == "cursor value"

    export_route = respx.get(
        f"http://localhost:5770/api/v1/agent/sessions/legacy/{SESSION_ID}/export"
    ).mock(return_value=httpx.Response(200, json={"session": {"id": SESSION_ID}, "events": []}))
    exported = client.agent_tasks.export_legacy_session(SESSION_ID, limit=10, after_event_id=7)
    assert exported["session"]["id"] == SESSION_ID
    assert export_route.calls.last.request.url.params["afterEventId"] == "7"

    claim_route = respx.post(
        f"http://localhost:5770/api/v1/agent/sessions/legacy/{SESSION_ID}/claim"
    ).mock(return_value=httpx.Response(200, json={"session": {"id": "scoped"}}))
    claimed = client.agent_tasks.claim_legacy_session(
        SESSION_ID,
        namespace="payments",
        session_key="tab_1",
        acknowledge_unknown_origin=True,
    )
    assert claimed["id"] == "scoped"
    request_body = json.loads(claim_route.calls.last.request.read())
    assert request_body == {
        "namespace": "payments",
        "sessionKey": "tab_1",
        "acknowledgeUnknownOrigin": True,
    }
    assert claim_route.calls.last.request.url.path.endswith("/claim")


def test_legacy_session_recovery_rejects_invalid_input(client: MockartyClient) -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        client.agent_tasks.list_legacy_sessions(limit=0)
    with pytest.raises(ValueError, match="between 1 and 2000"):
        client.agent_tasks.export_legacy_session(SESSION_ID, limit=2001)
    with pytest.raises(ValueError, match="non-negative"):
        client.agent_tasks.export_legacy_session(SESSION_ID, after_event_id=-1)
    with pytest.raises(ValueError, match="must be true"):
        client.agent_tasks.claim_legacy_session(
            SESSION_ID,
            namespace="payments",
            acknowledge_unknown_origin=False,
        )


@pytest.mark.asyncio
@respx.mock
async def test_legacy_session_recovery_async(base_url: str, api_key: str) -> None:
    route = respx.post(
        f"{base_url}/api/v1/agent/sessions/legacy/{SESSION_ID}/claim"
    ).mock(return_value=httpx.Response(200, json={"session": {"namespace": "payments"}}))
    async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
        claimed = await client.agent_tasks.claim_legacy_session(
            SESSION_ID,
            namespace="payments",
            acknowledge_unknown_origin=True,
        )
    assert claimed["namespace"] == "payments"
    assert route.called
