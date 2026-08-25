# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Ready-to-use Model Context Protocol (MCP) client.

Speaks to a Mockarty MCP endpoint (the admin node's streamable-HTTP ``/mcp``)
so SDK users can discover and call the same agent-facing tool surface an AI
agent would — ``list_tools`` then ``call_tool`` — programmatically. Auth reuses
the SDK client's credentials; feature/licence gating is enforced server-side.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.errors import MockartyError

_PROTOCOL_VERSION = "2025-03-26"
_MCP_ACCEPT = "application/json, text/event-stream"


@dataclass
class MCPTool:
    """A tool advertised by the MCP server."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "MCPTool":
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            input_schema=d.get("inputSchema") or {},
        )


@dataclass
class MCPToolResult:
    """Structured result of a ``call_tool``."""

    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False

    @property
    def text(self) -> str:
        """Concatenated text of every text content block — the common case for
        a Mockarty tool returning a JSON string."""
        return "".join(c.get("text", "") for c in self.content if c.get("type") == "text")

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "MCPToolResult":
        return cls(content=d.get("content") or [], is_error=bool(d.get("isError")))


class MockartyMCPError(MockartyError):
    """Raised when the MCP server returns a JSON-RPC error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"mcp: rpc error {code}: {message}")
        self.code = code


def _parse_frame(resp: httpx.Response) -> dict[str, Any]:
    """Parse one JSON-RPC frame from a /mcp response, handling both direct
    ``application/json`` and ``text/event-stream`` (SSE) framing."""
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        data_parts: list[str] = []
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                data_parts.append(line[len("data:") :].strip())
            elif not line and data_parts:
                break
        body = "".join(data_parts)
        if not body:
            raise MockartyError("mcp: empty SSE response")
        return json.loads(body)
    return resp.json()


def _result_or_raise(frame: dict[str, Any]) -> Any:
    if isinstance(frame, dict) and frame.get("error"):
        err = frame["error"]
        raise MockartyMCPError(int(err.get("code", 0)), str(err.get("message", "")))
    return frame.get("result") if isinstance(frame, dict) else None


class MCPClient(SyncAPIBase):
    """Synchronous MCP client. Performs the ``initialize`` handshake lazily on
    first use and reuses the negotiated session for its lifetime."""

    def __init__(self, client: httpx.Client, namespace: str) -> None:
        super().__init__(client, namespace)
        self._initialized = False
        self._session_id: str | None = None
        self._next_id = 0

    def initialize(self) -> None:
        """Perform the MCP handshake explicitly. Called automatically by
        ``list_tools`` / ``call_tool`` — use it to fail fast on a bad token."""
        self._ensure_init()

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._call(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mockarty-py-sdk", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True

    def list_tools(self) -> list[MCPTool]:
        """Return every tool the MCP server advertises."""
        self._ensure_init()
        result = self._call("tools/list", {})
        return [MCPTool._from_dict(t) for t in (result or {}).get("tools", [])]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        """Invoke a tool by name and return its structured result."""
        self._ensure_init()
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        return MCPToolResult._from_dict(result or {})

    def _headers(self) -> dict[str, str]:
        h = {"Accept": _MCP_ACCEPT}
        # The MCP streamable-HTTP transport reads the per-request namespace
        # override from X-Mockarty-Namespace ONLY (not the REST X-Namespace),
        # so send it here or calls silently run in the token-pinned namespace.
        if self._namespace:
            h["X-Mockarty-Namespace"] = self._namespace
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _call(self, method: str, params: dict[str, Any]) -> Any:
        self._next_id += 1
        body = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        resp = self._request("POST", "/mcp", json=body, headers=self._headers())
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        return _result_or_raise(_parse_frame(resp))

    def _notify(self, method: str) -> None:
        body = {"jsonrpc": "2.0", "method": method}
        resp = self._request("POST", "/mcp", json=body, headers=self._headers())
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid


class AsyncMCPClient(AsyncAPIBase):
    """Asynchronous mirror of :class:`MCPClient`."""

    def __init__(self, client: httpx.AsyncClient, namespace: str) -> None:
        super().__init__(client, namespace)
        self._initialized = False
        self._session_id: str | None = None
        self._next_id = 0

    async def initialize(self) -> None:
        await self._ensure_init()

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        await self._call(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mockarty-py-sdk", "version": "1.0.0"},
            },
        )
        await self._notify("notifications/initialized")
        self._initialized = True

    async def list_tools(self) -> list[MCPTool]:
        await self._ensure_init()
        result = await self._call("tools/list", {})
        return [MCPTool._from_dict(t) for t in (result or {}).get("tools", [])]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        await self._ensure_init()
        result = await self._call("tools/call", {"name": name, "arguments": arguments or {}})
        return MCPToolResult._from_dict(result or {})

    def _headers(self) -> dict[str, str]:
        h = {"Accept": _MCP_ACCEPT}
        # The MCP streamable-HTTP transport reads the per-request namespace
        # override from X-Mockarty-Namespace ONLY (not the REST X-Namespace),
        # so send it here or calls silently run in the token-pinned namespace.
        if self._namespace:
            h["X-Mockarty-Namespace"] = self._namespace
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        self._next_id += 1
        body = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        resp = await self._request("POST", "/mcp", json=body, headers=self._headers())
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
        return _result_or_raise(_parse_frame(resp))

    async def _notify(self, method: str) -> None:
        body = {"jsonrpc": "2.0", "method": method}
        resp = await self._request("POST", "/mcp", json=body, headers=self._headers())
        sid = resp.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid
