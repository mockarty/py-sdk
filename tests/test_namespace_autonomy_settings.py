"""Autonomy namespace retention SDK contract."""

import asyncio
import json

import httpx
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_namespace_autonomy_settings_round_trip(client: MockartyClient) -> None:
    respx.get("http://localhost:5770/api/v1/autotester/settings").mock(
        return_value=httpx.Response(
            200,
            headers={"ETag": '"' + "a" * 64 + '"'},
            json={
                "defaultAutonomy": "auto",
                "defaultBudget": {"tokensTotal": 10},
                "defaultContextRefs": [],
                "journalEventRetentionDays": 90,
                "journalPayloadRetentionDays": 30,
                "runWindowMinutes": 480,
                "updatedAt": "2026-08-23T00:00:00Z",
            },
        )
    )
    route = respx.put("http://localhost:5770/api/v1/autotester/settings").mock(
        return_value=httpx.Response(
            200,
            json={
                "defaultAutonomy": "propose",
                "defaultBudget": {},
                "defaultContextRefs": [],
                "journalEventRetentionDays": 365,
                "journalPayloadRetentionDays": None,
            },
        )
    )
    got = client.namespace_settings.save_autonomy_settings(
        {
            "defaultAutonomy": "propose",
            "defaultBudget": {},
            "defaultContextRefs": [],
            "journalEventRetentionDays": 365,
        },
        request_id="stable-python-save-1",
    )
    assert got["journalEventRetentionDays"] == 365
    assert route.calls.last.request.headers["X-Namespace"] == client.namespace
    assert route.calls.last.request.headers["Idempotency-Key"] == "stable-python-save-1"
    assert route.calls.last.request.headers["If-Match"] == '"' + "a" * 64 + '"'
    body = json.loads(route.calls.last.request.content)
    assert body["journalPayloadRetentionDays"] == 30
    assert body["runWindowMinutes"] == 480

    client.namespace_settings.clear_autonomy_retention(
        clear_payload=True, request_id="stable-python-clear-1"
    )
    body = json.loads(route.calls.last.request.content)
    assert body["journalPayloadRetentionDays"] is None
    assert route.calls.last.request.headers["Idempotency-Key"] == "stable-python-clear-1"

    client.namespace_settings.clear_autonomy_run_window(request_id="stable-window-clear-1")
    body = json.loads(route.calls.last.request.content)
    assert body["runWindowMinutes"] is None


def test_namespace_autonomy_clear_requires_selection(client: MockartyClient) -> None:
    try:
        client.namespace_settings.clear_autonomy_retention()
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("clear without a selected override must fail")


@respx.mock
def test_async_get_namespace_autonomy_settings(base_url: str, api_key: str) -> None:
    respx.get(f"{base_url}/api/v1/autotester/settings").mock(
        return_value=httpx.Response(200, json={"journalEventRetentionDays": None})
    )
    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key) as client:
            got = await client.namespace_settings.get_autonomy_settings()
            assert got["journalEventRetentionDays"] is None

    asyncio.run(run())
