"""Versioned Workflow Definition SDK parity contract."""

import asyncio
import json

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


DEFINITION = {
    "contractVersion": "mockarty.workflow/v1",
    "namespace": "team-a",
    "id": "release-flow",
    "version": "1.0.0",
    "status": "draft",
    "entryNode": "start",
    "nodes": [],
    "transitions": [],
}


@respx.mock
def test_workflow_definition_lifecycle_uses_exact_paths_and_cas(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/namespaces/team-a/workflow-definitions"
    create = respx.post(base).mock(return_value=httpx.Response(201, json={"definition": DEFINITION, "revision": 1}))
    dry_run = respx.post(base + "/release-flow/versions/1.0.0/dry-run").mock(
        return_value=httpx.Response(200, json={"ready": True, "definitionDigest": "sha256:dry"})
    )
    publish = respx.post(base + "/release-flow/versions/1.0.0/publish").mock(
        return_value=httpx.Response(200, json={"definition": DEFINITION, "revision": 2})
    )
    listed = respx.get(base, params={"status": "published", "limit": "25"}).mock(
        return_value=httpx.Response(200, json={"definitions": [{"id": "release-flow"}]})
    )

    created = client.workflow_definitions.create_draft(DEFINITION)
    assert created["revision"] == 1
    assert client.workflow_definitions.dry_run("release-flow", "1.0.0", 1, namespace="team-a")["ready"] is True
    assert client.workflow_definitions.publish("release-flow", "1.0.0", 1, namespace="team-a")["revision"] == 2
    assert client.workflow_definitions.list(namespace="team-a", status="published", limit=25)["definitions"][0]["id"] == "release-flow"
    assert json.loads(create.calls.last.request.content)["namespace"] == "team-a"
    assert json.loads(dry_run.calls.last.request.content) == {"expectedRevision": 1}
    assert json.loads(publish.calls.last.request.content) == {"expectedRevision": 1}
    assert listed.called


@respx.mock
def test_create_draft_copies_default_namespace_into_body(client: MockartyClient) -> None:
    route = respx.post("http://localhost:5770/api/v1/namespaces/test-ns/workflow-definitions").mock(
        return_value=httpx.Response(201, json={"revision": 1})
    )
    definition = dict(DEFINITION)
    definition.pop("namespace")

    assert client.workflow_definitions.create_draft(definition)["revision"] == 1
    assert json.loads(route.calls.last.request.content)["namespace"] == "test-ns"
    assert "namespace" not in definition


@respx.mock
def test_async_workflow_definition_get_escapes_identity(base_url: str, api_key: str) -> None:
    route = respx.get(
        base_url + "/api/v1/namespaces/team-a/workflow-definitions/release%2Fflow/versions/1.0.0"
    ).mock(return_value=httpx.Response(200, json={"revision": 7}))

    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, namespace="team-a") as client:
            got = await client.workflow_definitions.get("release/flow", "1.0.0")
            assert got["revision"] == 7

    asyncio.run(run())
    assert route.called


@respx.mock
def test_async_namespace_change_rebuilds_workflow_definition_api(base_url: str, api_key: str) -> None:
    team_b = respx.get(
        base_url + "/api/v1/namespaces/team-b/workflow-definitions",
        params={"limit": "50"},
    ).mock(return_value=httpx.Response(200, json={"definitions": []}))

    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, namespace="team-a") as client:
            original = client.workflow_definitions
            client.namespace = "team-b"
            assert client.workflow_definitions is not original
            await client.workflow_definitions.list()

    asyncio.run(run())
    assert team_b.called


def test_workflow_revisions_must_be_positive_before_network(client: MockartyClient) -> None:
    with pytest.raises(ValueError, match="positive"):
        client.workflow_definitions.update_draft(DEFINITION, 0)
    with pytest.raises(ValueError, match="positive"):
        client.workflow_definitions.dry_run("release-flow", "1.0.0", -1)
    with pytest.raises(ValueError, match="positive"):
        client.workflow_definitions.publish("release-flow", "1.0.0", 0)
