# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Agent tasks API resource for AI-assisted mock generation."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class AgentTaskAPI(SyncAPIBase):
    """Synchronous Agent Task API resource."""

    def list(self) -> list[dict[str, Any]]:
        """List all agent tasks."""
        resp = self._request("GET", "/api/v1/agent/tasks")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("tasks") or []
        return []

    def get(self, task_id: str) -> dict[str, Any]:
        """Get an agent task by ID.

        Wire shape: server emits ``{task: <AgentTask>}`` envelope — unwrap.
        """
        resp = self._request("GET", f"/api/v1/agent/tasks/{task_id}")
        data = resp.json()
        if isinstance(data, dict) and "task" in data:
            return data["task"] or {}
        return data

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        """Submit a new agent task.

        Server requires ``title`` + ``prompt`` fields. Reply shape:
        ``{task: <AgentTask>, message: "..."}`` — unwrap inner task.
        """
        resp = self._request("POST", "/api/v1/agent/tasks", json=task)
        data = resp.json()
        if isinstance(data, dict) and "task" in data:
            return data["task"] or {}
        return data

    def cancel(self, task_id: str) -> None:
        """Cancel a running agent task."""
        self._request("POST", f"/api/v1/agent/tasks/{task_id}/cancel")

    def delete(self, task_id: str) -> None:
        """Delete an agent task."""
        self._request("DELETE", f"/api/v1/agent/tasks/{task_id}")

    def clear_all(self) -> None:
        """Delete all agent tasks."""
        self._request("DELETE", "/api/v1/agent/tasks")

    def rerun(self, task_id: str) -> dict[str, Any]:
        """Re-run a completed agent task. Wire reply: ``{task, message}`` — unwrap."""
        resp = self._request("POST", f"/api/v1/agent/tasks/{task_id}/rerun")
        data = resp.json()
        if isinstance(data, dict) and "task" in data:
            return data["task"] or {}
        return data

    def export(self, task_id: str) -> bytes:
        """Export an agent task result as raw bytes."""
        resp = self._request("GET", f"/api/v1/agent/tasks/{task_id}/export")
        return resp.content

    def list_legacy_sessions(self, *, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        """List an owner-scoped page of recoverable pre-namespace sessions."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", "/api/v1/agent/sessions/legacy", params=params)
        return resp.json()

    def export_legacy_session(
        self, session_id: str, *, limit: int = 500, after_event_id: int = 0
    ) -> dict[str, Any]:
        """Export one bounded page of a recoverable transcript."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not 1 <= limit <= 2000:
            raise ValueError("limit must be between 1 and 2000")
        if after_event_id < 0:
            raise ValueError("after_event_id must be non-negative")
        resp = self._request(
            "GET",
            f"/api/v1/agent/sessions/legacy/{quote(session_id, safe='')}/export",
            params={"limit": limit, "afterEventId": after_event_id},
        )
        return resp.json()

    def claim_legacy_session(
        self,
        session_id: str,
        *,
        namespace: str,
        acknowledge_unknown_origin: bool,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        """Claim a recoverable transcript into a write-authorized workspace."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not namespace.strip():
            raise ValueError("namespace is required")
        if not acknowledge_unknown_origin:
            raise ValueError("acknowledge_unknown_origin must be true")
        payload: dict[str, Any] = {
            "namespace": namespace,
            "acknowledgeUnknownOrigin": acknowledge_unknown_origin,
        }
        if session_key:
            payload["sessionKey"] = session_key
        resp = self._request(
            "POST",
            f"/api/v1/agent/sessions/legacy/{quote(session_id, safe='')}/claim",
            json=payload,
        )
        return resp.json().get("session", {})


class AsyncAgentTaskAPI(AsyncAPIBase):
    """Asynchronous Agent Task API resource."""

    async def list(self) -> list[dict[str, Any]]:
        """List all agent tasks."""
        resp = await self._request("GET", "/api/v1/agent/tasks")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("tasks") or []
        return []

    async def get(self, task_id: str) -> dict[str, Any]:
        """Async mirror — see sync ``get`` for envelope notes."""
        resp = await self._request("GET", f"/api/v1/agent/tasks/{task_id}")
        data = resp.json()
        if isinstance(data, dict) and "task" in data:
            return data["task"] or {}
        return data

    async def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        """Async mirror — see sync ``submit`` for required fields."""
        resp = await self._request("POST", "/api/v1/agent/tasks", json=task)
        data = resp.json()
        if isinstance(data, dict) and "task" in data:
            return data["task"] or {}
        return data

    async def cancel(self, task_id: str) -> None:
        """Cancel a running agent task."""
        await self._request("POST", f"/api/v1/agent/tasks/{task_id}/cancel")

    async def delete(self, task_id: str) -> None:
        """Delete an agent task."""
        await self._request("DELETE", f"/api/v1/agent/tasks/{task_id}")

    async def clear_all(self) -> None:
        """Delete all agent tasks."""
        await self._request("DELETE", "/api/v1/agent/tasks")

    async def rerun(self, task_id: str) -> dict[str, Any]:
        """Async mirror — unwraps ``{task, message}`` envelope."""
        resp = await self._request("POST", f"/api/v1/agent/tasks/{task_id}/rerun")
        data = resp.json()
        if isinstance(data, dict) and "task" in data:
            return data["task"] or {}
        return data

    async def export(self, task_id: str) -> bytes:
        """Export an agent task result as raw bytes."""
        resp = await self._request("GET", f"/api/v1/agent/tasks/{task_id}/export")
        return resp.content

    async def list_legacy_sessions(self, *, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        """List an owner-scoped page of recoverable pre-namespace sessions."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = await self._request("GET", "/api/v1/agent/sessions/legacy", params=params)
        return resp.json()

    async def export_legacy_session(
        self, session_id: str, *, limit: int = 500, after_event_id: int = 0
    ) -> dict[str, Any]:
        """Export one bounded page of a recoverable transcript."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not 1 <= limit <= 2000:
            raise ValueError("limit must be between 1 and 2000")
        if after_event_id < 0:
            raise ValueError("after_event_id must be non-negative")
        resp = await self._request(
            "GET",
            f"/api/v1/agent/sessions/legacy/{quote(session_id, safe='')}/export",
            params={"limit": limit, "afterEventId": after_event_id},
        )
        return resp.json()

    async def claim_legacy_session(
        self,
        session_id: str,
        *,
        namespace: str,
        acknowledge_unknown_origin: bool,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        """Claim a recoverable transcript into a write-authorized workspace."""
        if not session_id.strip():
            raise ValueError("session_id is required")
        if not namespace.strip():
            raise ValueError("namespace is required")
        if not acknowledge_unknown_origin:
            raise ValueError("acknowledge_unknown_origin must be true")
        payload: dict[str, Any] = {
            "namespace": namespace,
            "acknowledgeUnknownOrigin": acknowledge_unknown_origin,
        }
        if session_key:
            payload["sessionKey"] = session_key
        resp = await self._request(
            "POST",
            f"/api/v1/agent/sessions/legacy/{quote(session_id, safe='')}/claim",
            json=payload,
        )
        return resp.json().get("session", {})
