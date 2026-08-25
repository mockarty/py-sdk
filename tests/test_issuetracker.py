# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the issue-tracker task-automation API."""

from __future__ import annotations

import httpx
import respx

from mockarty import MockartyClient

B = "/api/v1/namespaces/test-ns/issuetracker"


def test_issue_flow(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post(f"{B}/issues").mock(return_value=httpx.Response(201, json={"id": "u1", "issueKey": "MK-1"}))
    mock_api.get(f"{B}/issues/u1").mock(return_value=httpx.Response(200, json={"id": "u1", "status": "open"}))
    mock_api.get(f"{B}/issues/by-key/MK-1").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    mock_api.get(f"{B}/issues").mock(return_value=httpx.Response(200, json={"issues": [{"id": "u1"}]}))
    mock_api.get(f"{B}/issues/next").mock(return_value=httpx.Response(200, json={"id": "u1", "issueKey": "MK-1"}))
    mock_api.put(f"{B}/issues/u1").mock(return_value=httpx.Response(200, json={"id": "u1", "title": "x2"}))
    mock_api.post(f"{B}/issues/u1/move").mock(return_value=httpx.Response(200, json={"id": "u1", "status": "done"}))
    mock_api.post(f"{B}/issues/u1/comments").mock(return_value=httpx.Response(200, json={"id": "c1", "body": "hi"}))
    mock_api.get(f"{B}/issues/u1/comments").mock(return_value=httpx.Response(200, json={"comments": [{"id": "c1"}]}))
    mock_api.post(f"{B}/issues/bulk/assign").mock(return_value=httpx.Response(200))
    mock_api.delete(f"{B}/issues/u1").mock(return_value=httpx.Response(200))
    mock_api.get(f"{B}/projects").mock(return_value=httpx.Response(200, json={"projects": [{"id": "p1"}]}))
    mock_api.get(f"{B}/sprints").mock(return_value=httpx.Response(200, json={"sprints": [{"id": "s1"}]}))

    it = client.issue_tracker
    assert it.create_issue({"title": "Bug"})["issueKey"] == "MK-1"
    assert it.get_issue("u1")["status"] == "open"
    assert it.get_issue_by_key("MK-1")["id"] == "u1"
    assert len(it.list_issues(status="open")) == 1
    assert it.next_issue(assigneeId="me")["issueKey"] == "MK-1"
    assert it.update_issue("u1", {"title": "x2"})["title"] == "x2"
    assert it.move_issue("u1", "done", resolution="fixed")["status"] == "done"
    assert it.add_comment("u1", "hi")["body"] == "hi"
    assert len(it.list_comments("u1")) == 1
    it.bulk_assign(["u1"], "me")
    assert len(it.list_projects()) == 1
    assert len(it.list_sprints()) == 1
    it.delete_issue("u1")
