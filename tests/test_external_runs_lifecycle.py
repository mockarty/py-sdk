# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the streaming external-run lifecycle API."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient

BASE = "/api/v1/namespaces/test-ns/tcm/external-runs/lifecycle"


def test_lifecycle_flow(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post(BASE).mock(
        return_value=httpx.Response(
            200, json={"id": "run-1", "status": "running", "name": "checkout"}
        )
    )
    mock_api.post(f"{BASE}/run-1/steps").mock(
        return_value=httpx.Response(
            200, json={"id": "run-1", "status": "running", "step_count": 2}
        )
    )
    mock_api.get(f"{BASE}/run-1").mock(
        return_value=httpx.Response(
            200, json={"id": "run-1", "status": "running", "step_count": 2}
        )
    )
    mock_api.post(f"{BASE}/run-1/finish").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "run-1",
                "status": "passed",
                "resolved_case_id": "case-9",
                "resolved_run_id": "crun-9",
            },
        )
    )
    mock_api.get(BASE).mock(
        return_value=httpx.Response(200, json={"runs": [{"id": "run-1"}], "total": 1})
    )

    er = client.external_runs
    run = er.start_run({"name": "checkout", "framework": "custom"})
    assert run["id"] == "run-1" and run["status"] == "running"

    run = er.append_steps(
        "run-1",
        [
            {"step_key": "s1", "name": "login", "status": "passed"},
            {"step_key": "s2", "name": "pay", "status": "passed"},
        ],
    )
    assert run["step_count"] == 2

    got = er.get_run("run-1")
    assert got["step_count"] == 2

    fin = er.finish_run("run-1", "passed", summary="ok")
    assert fin["status"] == "passed" and fin["resolved_case_id"] == "case-9"

    runs = er.list_runs()
    assert len(runs) == 1 and runs[0]["id"] == "run-1"


def test_lifecycle_fenced_mutations_and_attachment(
    client: MockartyClient, mock_api: respx.MockRouter
) -> None:
    steps = mock_api.post(f"{BASE}/run-1/steps").mock(
        return_value=httpx.Response(
            200, json={"id": "run-1", "status": "running", "revision": 8}
        )
    )
    attachment = mock_api.post(f"{BASE}/run-1/attachments").mock(
        return_value=httpx.Response(
            200, json={"id": "run-1", "status": "running", "revision": 9}
        )
    )
    finish = mock_api.post(f"{BASE}/run-1/finish").mock(
        return_value=httpx.Response(
            200, json={"id": "run-1", "status": "passed", "revision": 11}
        )
    )

    run = client.external_runs.append_steps_at_revision(
        "run-1", 7, [{"step_key": "s1", "status": "passed"}]
    )
    assert run["revision"] == 8
    assert steps.calls.last.request.headers["If-Match"] == '"7"'

    run = client.external_runs.upload_attachment_at_revision(
        "run-1", 8, "evidence.txt", b"measured"
    )
    assert run["revision"] == 9
    assert attachment.calls.last.request.headers["If-Match"] == '"8"'
    assert (
        "multipart/form-data" in attachment.calls.last.request.headers["Content-Type"]
    )
    assert b"evidence.txt" in attachment.calls.last.request.content
    assert b"measured" in attachment.calls.last.request.content

    run = client.external_runs.finish_run_at_revision("run-1", 9, "passed")
    assert run["revision"] == 11
    assert finish.calls.last.request.headers["If-Match"] == '"9"'


@respx.mock
@pytest.mark.asyncio
async def test_async_lifecycle_fenced_mutations_and_attachment() -> None:
    base = "https://mockarty.test/api/v1/namespaces/sandbox/tcm/external-runs/lifecycle"
    steps = respx.post(f"{base}/run-1/steps").mock(
        return_value=httpx.Response(200, json={"id": "run-1", "revision": 8})
    )
    attachment = respx.post(f"{base}/run-1/attachments").mock(
        return_value=httpx.Response(200, json={"id": "run-1", "revision": 9})
    )
    finish = respx.post(f"{base}/run-1/finish").mock(
        return_value=httpx.Response(200, json={"id": "run-1", "revision": 10})
    )
    async with AsyncMockartyClient(
        base_url="https://mockarty.test", namespace="sandbox", max_retries=0
    ) as client:
        run = await client.external_runs.append_steps_at_revision(
            "run-1", 7, [{"step_key": "s1", "status": "passed"}]
        )
        run = await client.external_runs.upload_attachment_at_revision(
            "run-1", run["revision"], "evidence.txt", b"measured"
        )
        run = await client.external_runs.finish_run_at_revision(
            "run-1", run["revision"], "passed"
        )

    assert run["revision"] == 10
    assert steps.calls.last.request.headers["If-Match"] == '"7"'
    assert attachment.calls.last.request.headers["If-Match"] == '"8"'
    assert finish.calls.last.request.headers["If-Match"] == '"9"'
    assert b"evidence.txt" in attachment.calls.last.request.content


def test_lifecycle_rejects_unsafe_attachment_names_before_network(
    client: MockartyClient,
) -> None:
    with pytest.raises(ValueError, match="single-line"):
        client.external_runs.upload_attachment(
            "run-1", "evidence\r\nX-Injected: true", b""
        )
