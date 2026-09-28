# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the TCM cases/case-runs/defects automation API."""

from __future__ import annotations

import json
import asyncio

import httpx
import respx
import pytest

from mockarty import MockartyClient

C = "/api/v1/namespaces/test-ns/test-cases"
T = "/api/v1/namespaces/test-ns/tcm"


def test_tcm_flow(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post(C).mock(return_value=httpx.Response(201, json={"id": "c1", "name": "Login"}))
    mock_api.get(f"{C}/c1").mock(return_value=httpx.Response(200, json={"id": "c1", "status": "active"}))
    mock_api.get(C).mock(return_value=httpx.Response(200, json={"test_cases": [{"id": "c1"}], "total": 1}))
    mock_api.put(f"{C}/c1").mock(return_value=httpx.Response(200, json={"id": "c1", "name": "t2"}))
    mock_api.post(f"{C}/c1/run").mock(return_value=httpx.Response(200, json={"runId": "r1", "status": "running"}))
    mock_api.get(f"{C}/c1/runs").mock(return_value=httpx.Response(200, json={"runs": [{"id": "r1"}]}))
    mock_api.get(f"{T}/case-runs/r1").mock(return_value=httpx.Response(200, json={"id": "r1", "status": "passed"}))
    mock_api.post(f"{T}/case-runs/r1/cancel").mock(return_value=httpx.Response(200))
    mock_api.post(f"{T}/defects").mock(return_value=httpx.Response(200, json={"id": "d1", "title": "bug"}))
    mock_api.get(f"{T}/defects").mock(return_value=httpx.Response(200, json={"defects": [{"id": "d1"}]}))
    mock_api.delete(f"{T}/defects/d1").mock(return_value=httpx.Response(200))
    mock_api.delete(f"{C}/c1").mock(return_value=httpx.Response(200))

    t = client.tcm
    assert t.create_case({"name": "Login"})["id"] == "c1"
    assert json.loads(mock_api.calls.last.request.content)["name"] == "Login"
    assert t.get_case("c1")["status"] == "active"
    assert len(t.list_cases()) == 1
    assert t.update_case("c1", {"name": "t2"})["name"] == "t2"
    assert t.run_case("c1")["runId"] == "r1"
    assert len(t.list_case_runs("c1")) == 1
    assert t.get_case_run("r1")["status"] == "passed"
    t.cancel_case_run("r1")
    assert t.create_defect({"title": "bug"})["id"] == "d1"
    assert len(t.list_defects()) == 1
    t.delete_defect("d1")
    t.delete_case("c1")


def test_case_steps_read_edit_save(client, mock_api):
    base = C + "/case-1/versions"
    mock_api.get(base).mock(return_value=httpx.Response(200, json={"versions":[{"id":"version-1"}]}))
    mock_api.get(base + "/version-1").mock(return_value=httpx.Response(200, json={"id":"version-1","steps":[{"stepUid":"login","mode":"manual","executorType":"manual","action":"Login","expectedResult":"Home"}]}))
    route = mock_api.post(base).mock(side_effect=[httpx.Response(201, json={"id":"version-2","version":2}),httpx.Response(200,json={"id":"version-2","version":2,"dedupSkipped":True})])
    assert client.tcm.list_case_versions("case-1")[0]["id"] == "version-1"
    version = client.tcm.get_case_version("case-1", "version-1")
    version["steps"][0]["expectedResult"] = "Dashboard"
    first = client.tcm.save_case_steps("case-1", version["steps"], notes="updated expectation")
    second = client.tcm.save_case_steps("case-1", version["steps"], notes="updated expectation")
    assert second["id"] == first["id"] and second["dedupSkipped"]
    assert json.loads(route.calls[0].request.content) == {"steps":version["steps"],"notes":"updated expectation"}


def test_tcm_workflow_preserves_custom_fields_png_and_run(client, mock_api):
    png = b"\x89PNG\r\n\x1a\n\x00\x01\x02"
    filename = 'before "login".png'
    create = mock_api.post(C).mock(return_value=httpx.Response(201, json={"id": "c1"}))
    mock_api.get(f"{C}/c1").mock(return_value=httpx.Response(200, json={"id": "c1", "steps": [{"action": "Pay"}]}))
    mock_api.get(C).mock(return_value=httpx.Response(200, json={"test_cases": [{"id": "c1"}]}))
    upload = mock_api.post(f"{T}/attachments/upload").mock(return_value=httpx.Response(201, json={"id": "a1"}))
    mock_api.get(f"{T}/attachments").mock(return_value=httpx.Response(200, json={"items": [{"id": "a1"}]}))
    mock_api.get(f"{T}/attachments/a1/raw").mock(return_value=httpx.Response(200, content=png))
    mock_api.post(f"{C}/c1/run").mock(return_value=httpx.Response(202, json={"id": "r1", "status": "running"}))
    mock_api.get(f"{T}/case-runs/r1").mock(return_value=httpx.Response(200, json={"id": "r1", "status": "running"}))

    api = client.tcm
    assert api.create_case({"name": "Payment", "externalId": "testit:100", "customFields": [{"name": "Component", "value": "payments"}], "steps": [{"action": "Pay", "expectedResult": "Accepted"}]})["id"] == "c1"
    payload = json.loads(create.calls[0].request.content)
    assert payload["externalId"] == "testit:100"
    assert payload["customFields"][0]["value"] == "payments"
    assert payload["steps"][0]["action"] == "Pay"
    assert api.get_case("c1")["steps"][0]["action"] == "Pay"
    assert len(api.list_cases()) == 1
    assert api.upload_attachment("tcm_case", "c1", filename, png, media_type="image/png")["id"] == "a1"
    sent = upload.calls[0].request
    assert sent.url.params["parentKind"] == "tcm_case" and sent.url.params["parentId"] == "c1"
    assert png in sent.content and b"image/png" in sent.content
    assert b'filename="before \\"login\\".png"' in sent.content
    assert len(api.list_attachments("tcm_case", "c1")) == 1
    assert api.download_attachment("a1") == png
    assert api.run_case("c1", {"mode": "manual"})["id"] == "r1"
    assert api.get_case_run("r1")["status"] == "running"


def test_tcm_attachment_rejects_unsafe_multipart_metadata(client):
    for filename in ("", "bad\r\nname.png", "bad\x00name.png", "bad\tname.png"):
        with pytest.raises(ValueError):
            client.tcm.upload_attachment("tcm_case", "c1", filename, b"x", media_type="image/png")
    with pytest.raises(ValueError):
        client.tcm.upload_attachment("tcm_case", "c1", "good.png", b"x", media_type="image/png\r\nInjected: yes")


def test_async_case_steps_read_edit_save():
    from mockarty import AsyncMockartyClient
    async def journey():
        base = "http://test/api/v1/namespaces/qa/test-cases/case-1/versions"
        with respx.mock as router:
            router.get(base).mock(return_value=httpx.Response(200,json={"versions":[{"id":"version-1"}]}))
            router.get(base+"/version-1").mock(return_value=httpx.Response(200,json={"steps":[]}))
            save=router.post(base).mock(return_value=httpx.Response(200,json={"id":"version-1","dedupSkipped":True}))
            upload=router.post("http://test/api/v1/namespaces/qa/tcm/attachments/upload").mock(return_value=httpx.Response(201,json={"id":"a1"}))
            png=b"\x89PNG\r\n\x1a\n\x00"
            router.get("http://test/api/v1/namespaces/qa/tcm/attachments/a1/raw").mock(return_value=httpx.Response(200,content=png))
            async with AsyncMockartyClient(base_url="http://test",namespace="qa") as client:
                assert len(await client.tcm.list_case_versions("case-1")) == 1
                version=await client.tcm.get_case_version("case-1","version-1")
                assert (await client.tcm.save_case_steps("case-1",version["steps"],notes="unchanged"))["dedupSkipped"]
                assert (await client.tcm.upload_attachment("tcm_case","case-1",'before "login".png',png,media_type="image/png"))["id"]=="a1"
                assert await client.tcm.download_attachment("a1")==png
            assert json.loads(save.calls[0].request.content)=={"steps":[],"notes":"unchanged"}
            assert b'filename="before \\"login\\".png"' in upload.calls[0].request.content
    asyncio.run(journey())
