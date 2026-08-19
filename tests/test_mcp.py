# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tests for the ready-to-use MCP client."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mockarty import MockartyClient, MockartyMCPError


def _rpc_reply(request: httpx.Request, *, sse: bool) -> httpx.Response:
    req = json.loads(request.content)
    method = req.get("method")
    if method == "notifications/initialized":
        return httpx.Response(202)
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "serverInfo": {"name": "mockarty"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "list_mocks", "description": "List mocks"},
                            {"name": "create_mock", "description": "Create a mock"}]}
    elif method == "tools/call":
        name = req["params"]["name"]
        result = {"content": [{"type": "text", "text": json.dumps({"tool": name, "ok": True})}]}
    else:
        return httpx.Response(400, json={"error": "unknown"})
    frame = {"jsonrpc": "2.0", "id": req.get("id"), "result": result}
    if sse:
        return httpx.Response(200, headers={"content-type": "text/event-stream", "mcp-session-id": "s1"},
                              text=f"event: message\ndata: {json.dumps(frame)}\n\n")
    return httpx.Response(200, headers={"content-type": "application/json", "mcp-session-id": "s1"}, json=frame)


def test_mcp_list_and_call_json(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post("/mcp").mock(side_effect=lambda req: _rpc_reply(req, sse=False))
    tools = client.mcp.list_tools()
    assert [t.name for t in tools] == ["list_mocks", "create_mock"]
    res = client.mcp.call_tool("create_mock", {"name": "x"})
    assert json.loads(res.text)["tool"] == "create_mock"


def test_mcp_list_and_call_sse(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    mock_api.post("/mcp").mock(side_effect=lambda req: _rpc_reply(req, sse=True))
    tools = client.mcp.list_tools()
    assert len(tools) == 2
    res = client.mcp.call_tool("list_mocks")
    assert res.text != ""


def test_mcp_rpc_error(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        req = json.loads(request.content)
        if req.get("method") == "notifications/initialized":
            return httpx.Response(202)
        if req.get("method") == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": req["id"], "result": {}})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": req["id"],
                                         "error": {"code": -32601, "message": "method not found"}})

    mock_api.post("/mcp").mock(side_effect=responder)
    with pytest.raises(MockartyMCPError) as exc:
        client.mcp.call_tool("nope")
    assert exc.value.code == -32601


def test_mcp_sends_namespace_header(client: MockartyClient, mock_api: respx.MockRouter) -> None:
    """The MCP transport reads the per-request namespace from X-Mockarty-Namespace
    ONLY — the client must send it so calls don't silently run in the wrong tenant."""
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen["ns"] = request.headers.get("X-Mockarty-Namespace")
        req = json.loads(request.content)
        if req.get("method") == "notifications/initialized":
            return httpx.Response(202)
        result = {} if req["method"] == "initialize" else {"tools": []}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": req["id"], "result": result})

    mock_api.post("/mcp").mock(side_effect=responder)
    client.mcp.list_tools()
    assert seen["ns"] == "test-ns"  # conftest client uses namespace="test-ns"
