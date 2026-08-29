"""Autonomous mission REST parity tests."""

import asyncio
import json
import math

import httpx
import pytest
import respx

from mockarty import (
    AsyncMockartyClient,
    AutonomousMissionBudgetHint,
    MissionStartRequest,
    MissionAnswerRequest,
    MissionCancelRequest,
    MissionRevisionReference,
    AutonomousMissionSubmitRequest,
    MockartyClient,
)


@respx.mock
def test_autonomous_missions_submit_and_supervise(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/autotester"
    submit = respx.post(f"{base}/intents").mock(
        return_value=httpx.Response(202, json={"missionId": "m-1", "status": "accepted"})
    )
    respx.get(f"{base}/missions", params={"status": "active", "limit": 25}).mock(
        return_value=httpx.Response(
            200,
            json={
                "missions": [
                    {"id": "m-1", "goal": "verify checkout", "status": "active"}
                ],
                "total": 1,
            },
        )
    )
    respx.get(f"{base}/missions/m-1").mock(
        return_value=httpx.Response(200, json={"id": "m-1", "goal": "verify checkout", "status": "active"})
    )
    respx.get(f"{base}/missions/m-1/flow").mock(
        return_value=httpx.Response(
            200,
            json={
                "mission": {
                    "id": "m-1",
                    "goal": "verify checkout",
                    "status": "done",
                },
                "steps": [],
                "artifacts": [],
            },
        )
    )

    accepted = client.autonomous_missions.submit(
        AutonomousMissionSubmitRequest(
            goal=" verify checkout ",
            product_url="https://shop.example",
            autonomy="auto",
            budget=AutonomousMissionBudgetHint(tokens_total=12000),
        )
    )
    assert accepted.mission_id == "m-1"
    payload = submit.calls.last.request.read().decode()
    assert '"productUrl":"https://shop.example"' in payload
    assert '"tokens_total":12000' in payload
    assert client.autonomous_missions.list(status="active", limit=25).total == 1
    assert client.autonomous_missions.get("m-1").id == "m-1"
    assert client.autonomous_missions.get_flow("m-1").mission.status == "done"


@respx.mock
def test_async_autonomous_missions(base_url: str, api_key: str) -> None:
    respx.get(f"{base_url}/api/v1/autotester/missions/m-1/flow").mock(
        return_value=httpx.Response(
            200,
            json={
                "mission": {"id": "m-1", "goal": "verify", "status": "done"},
                "steps": [],
                "artifacts": [],
            },
        )
    )

    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            assert (await client.autonomous_missions.get_flow("m-1")).mission.status == "done"

    asyncio.run(run())


def test_autonomous_missions_validate_before_network(client: MockartyClient) -> None:
    with pytest.raises(ValueError, match="goal"):
        AutonomousMissionSubmitRequest(goal=" ")
    with pytest.raises(ValueError, match="autonomy"):
        AutonomousMissionSubmitRequest(goal="x", autonomy="root")
    for kwargs in (
        {"tokens_total": -1},
        {"tokens_per_day": -1},
        {"usd_cap": -1},
        {"usd_cap": math.nan},
        {"usd_cap": math.inf},
        {"usd_cap": -math.inf},
    ):
        with pytest.raises(ValueError, match="budget"):
            AutonomousMissionBudgetHint(**kwargs)
    with pytest.raises(ValueError, match="mission_id"):
        client.autonomous_missions.get(" ")
    with pytest.raises(ValueError, match="limit"):
        client.autonomous_missions.list(limit=201)


@respx.mock
def test_unified_mission_settings_and_start(client: MockartyClient) -> None:
    digest = "sha256:" + "a" * 64
    preview = respx.get(
        "http://localhost:5770/api/v1/missions/settings/effective",
        params={"productId": "product/checkout", "runWindowMinutes": 90},
    ).mock(return_value=httpx.Response(200, json={
        "namespace": "team-a", "productId": "product/checkout", "settingsDigest": digest, "count": 1,
        "settings": [{"key": "mission_run_window_minutes", "value": "90", "layer": "mission", "builtin": "480", "runtimeApplied": True}],
    }))
    start = respx.post("http://localhost:5770/api/v1/missions").mock(
        return_value=httpx.Response(201, json={
            "created": True,
            "mission": {"id": "m-unified", "namespace": "team-a", "productId": "product/checkout", "kind": "testing", "goal": "ship checkout", "origin": "ui", "status": "queued", "pins": [{"kind": "repo", "id": "gitlab/mockarty", "revision": 41, "digest": digest}], "chain": []},
        })
    )
    cancel = respx.post("http://localhost:5770/api/v1/missions/m-unified/cancel").mock(
        return_value=httpx.Response(200, json={
            "mission": {"id": "m-unified", "namespace": "team-a", "kind": "testing", "goal": "ship checkout", "origin": "ui", "status": "canceled", "chain": []},
            "control": {"id": "control-1", "missionId": "m-unified", "idempotencyKey": "cancel-1", "action": "cancel", "phase": "committed", "outcome": "applied", "reason": "release withdrawn", "createdAt": "2026-08-27T00:00:00Z", "updatedAt": "2026-08-27T00:00:01Z"},
            "executionBindingsAvailable": True,
            "executionBindings": [{"id": "binding-1", "nodeId": "m-unified", "externalId": "runner-1", "kind": "runner_task", "state": "cancel_acknowledged", "graphRevision": 2, "generation": 1, "cancelEpoch": 3}],
        })
    )
    answer = respx.post("http://localhost:5770/api/v1/missions/m-unified/answer").mock(
        return_value=httpx.Response(200, json={
            "mission": {"id": "m-unified", "namespace": "team-a", "kind": "testing", "goal": "ship checkout", "origin": "ui", "status": "queued", "chain": []},
            "control": {"id": "control-2", "missionId": "m-unified", "idempotencyKey": "answer-1", "action": "answer", "phase": "committed", "outcome": "applied"},
        })
    )

    settings = client.autonomous_missions.get_effective_settings(
        product_id="product/checkout", run_window_minutes=90,
    )
    assert settings.settings_digest == digest
    assert settings.settings[0].runtime_applied is True
    started = client.autonomous_missions.start(MissionStartRequest(
        goal=" ship checkout ", product_id="product/checkout", expected_settings_digest=digest,
        targets=[MissionRevisionReference(kind="repo", id="gitlab/mockarty", revision=41, digest=digest)],
    ))
    assert started.created is True
    assert started.mission.id == "m-unified"
    assert started.mission.pins[0].revision == 41
    cancelled = client.autonomous_missions.cancel("m-unified", MissionCancelRequest(
        reason=" release withdrawn ", idempotency_key=" cancel-1 ",
    ))
    assert cancelled.mission.status == "canceled"
    assert cancelled.control.reason == "release withdrawn"
    assert cancelled.control.idempotency_key == "cancel-1"
    assert cancelled.execution_bindings_available is True
    assert cancelled.execution_bindings[0].state == "cancel_acknowledged"
    answered = client.autonomous_missions.answer("m-unified", MissionAnswerRequest(
        answer=" use sandbox account ", idempotency_key=" answer-1 ",
    ))
    assert answered.control.action == "answer"
    assert answered.control.reason == ""
    assert preview.called and start.called
    start_body = start.calls.last.request.read().decode()
    assert start_body.find(f'"expectedSettingsDigest":"{digest}"') >= 0
    assert '"targets":[{"kind":"repo","id":"gitlab/mockarty"' in start_body
    start_payload = json.loads(start_body)
    assert "kind" not in start_payload and "chain" not in start_payload
    cancel_body = cancel.calls.last.request.read().decode()
    assert '"reason":"release withdrawn"' in cancel_body
    assert '"idempotencyKey":"cancel-1"' in cancel_body
    answer_body = answer.calls.last.request.read().decode()
    assert '"answer":"use sandbox account"' in answer_body
    assert '"idempotencyKey":"answer-1"' in answer_body


@respx.mock
def test_async_unified_mission_settings_and_start(base_url: str, api_key: str) -> None:
    digest = "sha256:" + "b" * 64
    respx.get(f"{base_url}/api/v1/missions/settings/effective").mock(
        return_value=httpx.Response(200, json={"namespace": "default", "settingsDigest": digest, "count": 0, "settings": []})
    )
    respx.post(f"{base_url}/api/v1/missions").mock(
        return_value=httpx.Response(201, json={"created": True, "mission": {"id": "m-2", "namespace": "default", "kind": "testing", "goal": "verify", "origin": "ui", "status": "queued", "chain": []}})
    )
    respx.post(f"{base_url}/api/v1/missions/m-2/cancel").mock(return_value=httpx.Response(200, json={
        "mission": {"id": "m-2", "namespace": "default", "kind": "testing", "goal": "verify", "origin": "ui", "status": "canceled", "chain": []},
        "control": {"id": "control-2", "missionId": "m-2", "idempotencyKey": "cancel-2", "action": "cancel", "phase": "committed", "outcome": "applied", "reason": "stale", "createdAt": "2026-08-27T00:00:00Z", "updatedAt": "2026-08-27T00:00:01Z"},
    }))

    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            settings = await client.autonomous_missions.get_effective_settings()
            started = await client.autonomous_missions.start(MissionStartRequest(goal="verify", expected_settings_digest=settings.settings_digest))
            assert started.mission.id == "m-2"
            cancelled = await client.autonomous_missions.cancel("m-2", MissionCancelRequest(
                reason="stale", idempotency_key="cancel-2",
            ))
            assert cancelled.control.reason == "stale"

    asyncio.run(run())


def test_unified_mission_validation_before_network(client: MockartyClient) -> None:
    with pytest.raises(ValueError, match="run_window_minutes"):
        client.autonomous_missions.get_effective_settings(run_window_minutes=20161)
    with pytest.raises(ValueError, match="digest"):
        MissionStartRequest(goal="x", expected_settings_digest="sha256:bad")
    with pytest.raises(ValueError, match="goal"):
        MissionStartRequest(goal=" ")
    with pytest.raises(ValueError, match="mission_id"):
        client.autonomous_missions.cancel(" ")
    with pytest.raises(ValueError, match="answer"):
        MissionAnswerRequest(answer=" ")
