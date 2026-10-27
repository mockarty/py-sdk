# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Device-mesh SDK contract.

The responses below are LITERAL server JSON (camelCase, as the routes emit it),
not a payload this test produced itself: a test that round-trips the SDK's own
model agrees with itself whatever the server sends, which is how a naming
mismatch shipped once already.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient

BASE = "http://localhost:5770"
MESH = BASE + "/api/v1/namespaces/team-a/device-mesh"

DEVICE_JSON = {
    "deviceId": "desk-1",
    "namespace": "team-a",
    "kind": "desktop",
    "state": "online",
    "ownerUserId": "user-1",
    "capabilities": ["api_test"],
    "labels": {"os": "linux"},
    "heartbeatAt": "2026-10-27T10:00:00Z",
}

COMMAND_JSON = {
    "id": "cmd-1",
    "namespace": "team-a",
    "kind": "api_test.collection",
    "state": "queued",
    "targetDeviceId": "desk-1",
    "requiredCapabilities": ["api_test"],
    "queuedAt": "2026-10-27T10:00:00Z",
    "payload": {"collectionId": "11111111-1111-4111-8111-111111111111"},
}


@pytest.fixture()
def client() -> MockartyClient:
    return MockartyClient(BASE, namespace="team-a")


@respx.mock
def test_list_devices_parses_the_served_shape(client: MockartyClient) -> None:
    route = respx.get(MESH + "/devices").mock(
        return_value=httpx.Response(200, json={"devices": [DEVICE_JSON]})
    )
    devices = client.device_mesh.list_devices()

    assert route.called
    assert devices[0].device_id == "desk-1"
    assert devices[0].capabilities == ["api_test"]
    assert devices[0].labels == {"os": "linux"}


@respx.mock
def test_submit_carries_the_idempotency_key_and_reports_replay(client: MockartyClient) -> None:
    route = respx.post(MESH + "/commands").mock(
        return_value=httpx.Response(202, json={"command": COMMAND_JSON, "replayed": True})
    )
    result = client.device_mesh.submit(
        kind="api_test.collection",
        payload={"collectionId": "11111111-1111-4111-8111-111111111111"},
        target_device_id="desk-1",
        required_capabilities=["api_test"],
        idempotency_key="ci-run-42",
    )

    sent = route.calls[0].request
    body = sent.read().decode()
    assert "ci-run-42" in body, "the idempotency key must reach the server"
    assert "desk-1" in body
    assert result.replayed is True, "a replayed key must be reported, not hidden"
    assert result.command.id == "cmd-1"


@respx.mock
def test_report_sends_the_device_as_a_query_parameter(client: MockartyClient) -> None:
    route = respx.post(MESH + "/commands/cmd-1/report").mock(
        return_value=httpx.Response(200, json={**COMMAND_JSON, "state": "failed", "failureReason": "engine exited 2"})
    )
    command = client.device_mesh.report(
        "cmd-1", device_id="desk-1", state="failed",
        result_summary="0 of 3 passed", failure_reason="engine exited 2",
    )

    assert "deviceId=desk-1" in str(route.calls[0].request.url)
    assert command.state == "failed"
    assert command.failure_reason == "engine exited 2"


@respx.mock
def test_receipts_are_read_by_command(client: MockartyClient) -> None:
    route = respx.get(MESH + "/reports").mock(
        return_value=httpx.Response(200, json={"reports": [{
            "id": "rep-1", "ref": "devicemesh.command:cmd-1", "deviceId": "desk-1",
            "state": "failed", "failureCode": "engine exited 2",
            "recordedAt": "2026-10-27T10:00:00Z",
        }]})
    )
    reports = client.device_mesh.list_reports("cmd-1")

    assert "commandId=cmd-1" in str(route.calls[0].request.url)
    assert reports[0].failure_code == "engine exited 2"


@respx.mock
def test_drain_sends_the_flag(client: MockartyClient) -> None:
    route = respx.post(MESH + "/devices/desk-1/drain").mock(
        return_value=httpx.Response(200, json={**DEVICE_JSON, "state": "draining"})
    )
    device = client.device_mesh.set_drain("desk-1", draining=True, reason="maintenance")

    assert '"draining":true' in route.calls[0].request.read().decode()
    assert device.state == "draining"


def test_missing_namespace_is_refused_before_any_request() -> None:
    bare = MockartyClient(BASE, namespace="")
    with pytest.raises(ValueError):
        bare.device_mesh.list_devices()
