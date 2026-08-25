# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Agent tasks API resource for AI-assisted mock generation."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.errors import MockartyTaskError

# Terminal task statuses. Kept in sync with the Go/Java SDKs and the server's
# agent executor (internal/agent/executor.go).
_TASK_SUCCESS = frozenset({"completed", "done", "succeeded"})
_TASK_FAILED = frozenset({"failed", "error"})
_TASK_CANCELLED = frozenset({"cancelled", "canceled"})


def _terminal_task_error(task: dict[str, Any]) -> MockartyTaskError | None:
    """Return a MockartyTaskError if the task reached a non-success terminal
    state, or None if it is still running or completed successfully."""
    status = str(task.get("status", "")).lower()
    if status in _TASK_FAILED:
        return MockartyTaskError(f"agent task {task.get('id', '')} failed", task, status)
    if status in _TASK_CANCELLED:
        return MockartyTaskError(f"agent task {task.get('id', '')} cancelled", task, status)
    return None


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
            task = data["task"] or {}
            if isinstance(task, dict):
                task["toolReceipts"] = data.get("toolReceipts") or []
                task["canReconcileToolReceipts"] = data.get("canReconcileToolReceipts") is True
                task["toolReceiptRetryAllowed"] = data.get("toolReceiptRetryAllowed") is True
                task["toolReceiptReconcileBlockedReason"] = data.get("toolReceiptReconcileBlockedReason") or ""
            return task
        return data

    def reconcile_tool_receipt(
        self,
        task_id: str,
        receipt_key: str,
        *,
        expected_version: int,
        idempotency_key: str,
        decision: str,
        reason: str,
        result: str = "",
    ) -> dict[str, Any]:
        """Resolve one uncertain external action after inspecting the real target.

        ``decision`` is ``already_applied``, ``retry_once`` or ``mark_failed``.
        Keep ``idempotency_key`` stable when retrying the same HTTP request.
        ``reason`` is limited to 2000 encoded UTF-8 bytes and ``result`` to
        65536 encoded UTF-8 bytes.
        ``retry_once`` requires an empty result and permits exactly one new
        physical dispatch generation.
        """
        payload = {
            "expectedVersion": expected_version,
            "idempotencyKey": idempotency_key,
            "decision": decision,
            "reason": reason,
            "result": result,
        }
        data = self._request(
            "POST",
            f"/api/v1/agent/tasks/{task_id}/tool-receipts/{receipt_key}/reconcile",
            json=payload,
        ).json()
        return data.get("receipt", {}) if isinstance(data, dict) else data

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

    def list_legacy_sessions(self, limit: int = 50, cursor: str = "") -> dict[str, Any]:
        """List owner-only metadata for recoverable pre-namespace sessions."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/api/v1/agent/sessions/legacy", params=params).json()

    def claim_legacy_session(
        self,
        legacy_id: str,
        namespace: str,
        session_key: str | None = None,
        acknowledge_unknown_origin: bool = False,
    ) -> dict[str, Any]:
        """Move one recoverable session into a writable workspace."""
        payload: dict[str, Any] = {
            "namespace": namespace,
            "acknowledgeUnknownOrigin": acknowledge_unknown_origin,
        }
        if session_key:
            payload["sessionKey"] = session_key
        data = self._request(
            "POST", f"/api/v1/agent/sessions/legacy/{legacy_id}/claim", json=payload
        ).json()
        return data.get("session", {}) if isinstance(data, dict) else data

    def wait_for_result(self, task_id: str, poll_interval: float = 2.0) -> dict[str, Any]:
        """Poll a task until it reaches a terminal state, returning the finished
        task dict (with ``result``). Raises :class:`MockartyTaskError` on a
        ``failed`` / ``cancelled`` terminal state. Automation counterpart to
        :meth:`submit` — dispatch into the agent network and block for a result.
        """
        interval = poll_interval if poll_interval > 0 else 2.0
        while True:
            task = self.get(task_id)
            if str(task.get("status", "")).lower() in _TASK_SUCCESS:
                return task
            err = _terminal_task_error(task)
            if err is not None:
                raise err
            time.sleep(interval)

    def submit_and_wait(self, task: dict[str, Any], poll_interval: float = 2.0) -> dict[str, Any]:
        """Submit a task and block until it reaches a terminal state — the
        one-call entry point for 'run this in the agent network, give me the
        result'."""
        submitted = self.submit(task)
        task_id = submitted.get("id")
        if not task_id:
            raise MockartyTaskError("agent task submitted without an id", submitted)
        return self.wait_for_result(task_id, poll_interval)


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
            task = data["task"] or {}
            if isinstance(task, dict):
                task["toolReceipts"] = data.get("toolReceipts") or []
                task["canReconcileToolReceipts"] = data.get("canReconcileToolReceipts") is True
                task["toolReceiptRetryAllowed"] = data.get("toolReceiptRetryAllowed") is True
                task["toolReceiptReconcileBlockedReason"] = data.get("toolReceiptReconcileBlockedReason") or ""
            return task
        return data

    async def reconcile_tool_receipt(
        self,
        task_id: str,
        receipt_key: str,
        *,
        expected_version: int,
        idempotency_key: str,
        decision: str,
        reason: str,
        result: str = "",
    ) -> dict[str, Any]:
        """Async mirror of :meth:`AgentTaskAPI.reconcile_tool_receipt`."""
        payload = {
            "expectedVersion": expected_version,
            "idempotencyKey": idempotency_key,
            "decision": decision,
            "reason": reason,
            "result": result,
        }
        data = (await self._request(
            "POST",
            f"/api/v1/agent/tasks/{task_id}/tool-receipts/{receipt_key}/reconcile",
            json=payload,
        )).json()
        return data.get("receipt", {}) if isinstance(data, dict) else data

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

    async def list_legacy_sessions(self, limit: int = 50, cursor: str = "") -> dict[str, Any]:
        """Async mirror of :meth:`AgentTaskAPI.list_legacy_sessions`."""
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return (await self._request("GET", "/api/v1/agent/sessions/legacy", params=params)).json()

    async def claim_legacy_session(
        self,
        legacy_id: str,
        namespace: str,
        session_key: str | None = None,
        acknowledge_unknown_origin: bool = False,
    ) -> dict[str, Any]:
        """Async mirror of :meth:`AgentTaskAPI.claim_legacy_session`."""
        payload: dict[str, Any] = {
            "namespace": namespace,
            "acknowledgeUnknownOrigin": acknowledge_unknown_origin,
        }
        if session_key:
            payload["sessionKey"] = session_key
        data = (await self._request(
            "POST", f"/api/v1/agent/sessions/legacy/{legacy_id}/claim", json=payload
        )).json()
        return data.get("session", {}) if isinstance(data, dict) else data

    async def wait_for_result(self, task_id: str, poll_interval: float = 2.0) -> dict[str, Any]:
        """Async mirror of the sync ``wait_for_result``."""
        interval = poll_interval if poll_interval > 0 else 2.0
        while True:
            task = await self.get(task_id)
            if str(task.get("status", "")).lower() in _TASK_SUCCESS:
                return task
            err = _terminal_task_error(task)
            if err is not None:
                raise err
            await asyncio.sleep(interval)

    async def submit_and_wait(self, task: dict[str, Any], poll_interval: float = 2.0) -> dict[str, Any]:
        """Async mirror of the sync ``submit_and_wait``."""
        submitted = await self.submit(task)
        task_id = submitted.get("id")
        if not task_id:
            raise MockartyTaskError("agent task submitted without an id", submitted)
        return await self.wait_for_result(task_id, poll_interval)
