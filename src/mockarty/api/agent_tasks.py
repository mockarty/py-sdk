# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Agent tasks API resource for AI-assisted mock generation."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class AgentTaskAPI(SyncAPIBase):
    """Synchronous Agent Task API resource."""

    def list(self) -> list[dict[str, Any]]:
        """List all agent tasks."""
        resp = self._request("GET", "/api/v1/agent-tasks")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("tasks") or []
        return []

    def get(self, task_id: str) -> dict[str, Any]:
        """Get an agent task by ID."""
        resp = self._request("GET", f"/api/v1/agent-tasks/{task_id}")
        return resp.json()

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        """Submit a new agent task."""
        resp = self._request("POST", "/api/v1/agent-tasks", json=task)
        return resp.json()

    def cancel(self, task_id: str) -> None:
        """Cancel a running agent task."""
        self._request("POST", f"/api/v1/agent-tasks/{task_id}/cancel")

    def delete(self, task_id: str) -> None:
        """Delete an agent task."""
        self._request("DELETE", f"/api/v1/agent-tasks/{task_id}")

    def clear_all(self) -> None:
        """Delete all agent tasks."""
        self._request("DELETE", "/api/v1/agent-tasks")

    def rerun(self, task_id: str) -> dict[str, Any]:
        """Re-run a completed agent task."""
        resp = self._request("POST", f"/api/v1/agent-tasks/{task_id}/rerun")
        return resp.json()

    def export(self, task_id: str) -> bytes:
        """Export an agent task result as raw bytes."""
        resp = self._request("GET", f"/api/v1/agent-tasks/{task_id}/export")
        return resp.content


class AsyncAgentTaskAPI(AsyncAPIBase):
    """Asynchronous Agent Task API resource."""

    async def list(self) -> list[dict[str, Any]]:
        """List all agent tasks."""
        resp = await self._request("GET", "/api/v1/agent-tasks")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("tasks") or []
        return []

    async def get(self, task_id: str) -> dict[str, Any]:
        """Get an agent task by ID."""
        resp = await self._request("GET", f"/api/v1/agent-tasks/{task_id}")
        return resp.json()

    async def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        """Submit a new agent task."""
        resp = await self._request("POST", "/api/v1/agent-tasks", json=task)
        return resp.json()

    async def cancel(self, task_id: str) -> None:
        """Cancel a running agent task."""
        await self._request("POST", f"/api/v1/agent-tasks/{task_id}/cancel")

    async def delete(self, task_id: str) -> None:
        """Delete an agent task."""
        await self._request("DELETE", f"/api/v1/agent-tasks/{task_id}")

    async def clear_all(self) -> None:
        """Delete all agent tasks."""
        await self._request("DELETE", "/api/v1/agent-tasks")

    async def rerun(self, task_id: str) -> dict[str, Any]:
        """Re-run a completed agent task."""
        resp = await self._request("POST", f"/api/v1/agent-tasks/{task_id}/rerun")
        return resp.json()

    async def export(self, task_id: str) -> bytes:
        """Export an agent task result as raw bytes."""
        resp = await self._request("GET", f"/api/v1/agent-tasks/{task_id}/export")
        return resp.content
