# Copyright (c) 2026 Mockarty. All rights reserved.

"""Agent tasks API resource for AI-assisted mock generation."""

from __future__ import annotations

from typing import Any

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
