# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Recorded UI test API resource — save / run / poll / export.

The SDK orchestrates UI tests on the platform's browser-runner / companion; it
never embeds a browser (matching the perf/functional pattern). Author a
``UITest`` (or generate one from a recording), ``create`` it, ``run`` it and
poll the result.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.builders.uitest_builder import UITest

_TERMINAL = {"passed", "failed", "broken", "skipped", "cancelled", "error", "completed"}


def _payload(ui: "UITest | dict[str, Any]") -> dict[str, Any]:
    return ui.to_dict() if isinstance(ui, UITest) else dict(ui)


def _run_body(opts: Optional[dict[str, Any]]) -> dict[str, Any]:
    return dict(opts) if opts else {}


class UITestAPI(SyncAPIBase):
    """Synchronous recorded-UI-test API."""

    def _ns(self) -> Optional[dict[str, str]]:
        return {"namespace": self._namespace} if self._namespace else None

    def create(self, ui: "UITest | dict[str, Any]") -> dict[str, Any]:
        """Save a UI test (POST /api/v1/ui-tests). Returns the stored record."""
        return self._request("POST", "/api/v1/ui-tests", json=_payload(ui), params=self._ns()).json()

    def list(self) -> list[dict[str, Any]]:
        """List saved UI tests in the namespace."""
        data = self._request("GET", "/api/v1/ui-tests", params=self._ns()).json()
        return data.get("uiTests", []) if isinstance(data, dict) else []

    def get(self, ui_test_id: str) -> dict[str, Any]:
        """Get a saved UI test by id."""
        return self._request("GET", f"/api/v1/ui-tests/{ui_test_id}", params=self._ns()).json()

    def run(self, ui_test_id: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Dispatch a replay on a runner. Returns {taskId, statusPath, ...}.
        options may carry browser / viewport / envVars / platform / etc."""
        return self._request("POST", f"/api/v1/ui-tests/{ui_test_id}/run",
                             json=_run_body(options), params=self._ns()).json()

    def run_status(self, task_id: str) -> dict[str, Any]:
        """Read a dispatched replay's status (GET /api/v1/runner-tasks/:taskId)."""
        return self._request("GET", f"/api/v1/runner-tasks/{task_id}").json()

    def wait_for_run(self, task_id: str, *, interval: float = 2.0,
                     timeout: Optional[float] = None) -> dict[str, Any]:
        """Poll run_status until the replay is terminal (or timeout)."""
        deadline = None if timeout is None else time.time() + timeout
        while True:
            st = self.run_status(task_id)
            if str(st.get("status", "")).lower() in _TERMINAL:
                return st
            if deadline is not None and time.time() >= deadline:
                return st
            time.sleep(interval if interval > 0 else 2.0)

    def export(self, ui_test_id: str, lang: str = "go") -> str:
        """Export the recording as source ("go"|"python"|"java"|"playwright"|"appium")."""
        params = {"format": lang}
        if self._namespace:
            params["namespace"] = self._namespace
        return self._request("GET", f"/api/v1/ui-tests/{ui_test_id}/export", params=params).text


class AsyncUITestAPI(AsyncAPIBase):
    """Asynchronous recorded-UI-test API."""

    def _ns(self) -> Optional[dict[str, str]]:
        return {"namespace": self._namespace} if self._namespace else None

    async def create(self, ui: "UITest | dict[str, Any]") -> dict[str, Any]:
        resp = await self._request("POST", "/api/v1/ui-tests", json=_payload(ui), params=self._ns())
        return resp.json()

    async def list(self) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/api/v1/ui-tests", params=self._ns())
        data = resp.json()
        return data.get("uiTests", []) if isinstance(data, dict) else []

    async def get(self, ui_test_id: str) -> dict[str, Any]:
        resp = await self._request("GET", f"/api/v1/ui-tests/{ui_test_id}", params=self._ns())
        return resp.json()

    async def run(self, ui_test_id: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        resp = await self._request("POST", f"/api/v1/ui-tests/{ui_test_id}/run",
                                   json=_run_body(options), params=self._ns())
        return resp.json()

    async def run_status(self, task_id: str) -> dict[str, Any]:
        resp = await self._request("GET", f"/api/v1/runner-tasks/{task_id}")
        return resp.json()

    async def wait_for_run(self, task_id: str, *, interval: float = 2.0,
                           timeout: Optional[float] = None) -> dict[str, Any]:
        deadline = None if timeout is None else time.time() + timeout
        while True:
            st = await self.run_status(task_id)
            if str(st.get("status", "")).lower() in _TERMINAL:
                return st
            if deadline is not None and time.time() >= deadline:
                return st
            await asyncio.sleep(interval if interval > 0 else 2.0)

    async def export(self, ui_test_id: str, lang: str = "go") -> str:
        params = {"format": lang}
        if self._namespace:
            params["namespace"] = self._namespace
        resp = await self._request("GET", f"/api/v1/ui-tests/{ui_test_id}/export", params=params)
        return resp.text
