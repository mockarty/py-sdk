# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty Software License Agreement.
# See LICENSE file in the project root for full license text.

"""CI Triggers API resource (Phase 4 of the Ephemeral Runners plan).

Exposes ONLY the surface useful from a CI/CD script's perspective
(per CLAUDE.md ``feedback_sdk_cli_scope.md``):

* ``list()`` — find a saved trigger by name to use as ``ci_trigger_id``.
* ``get(id)`` — read one trigger (auth secret returned as ``"***"``).
* ``get_run_by_task(task_id)`` — poll the linked CI run state.
* ``cancel_run(run_id)`` — best-effort cancel + fail the local task.

CRUD of trigger configurations (create / update / delete) is the
administrative UI's concern and intentionally NOT in the SDK. Adding
those is easier than removing — please discuss with the maintainers
before extending.
"""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class CITriggerAPI(SyncAPIBase):
    """Synchronous CI Triggers API."""

    def list(self, namespace: str | None = None) -> list[dict[str, Any]]:
        """List saved CI triggers in a namespace.

        Returns a list of dicts with ``id``, ``name``, ``namespace``,
        ``triggerUrl``, ``templateKind``, ``enabled``. The auth secret
        is omitted (server returns ``"***"`` regardless).
        """
        params: dict[str, str] = {}
        if namespace:
            params["namespace"] = namespace
        resp = self._request("GET", "/api/v1/ci/triggers", params=params)
        payload = resp.json() or {}
        return list(payload.get("triggers") or [])

    def get(self, trigger_id: str, namespace: str | None = None) -> dict[str, Any]:
        """Fetch a single trigger by ID.

        Cross-NS lookups are 404'd by the server (existence is hidden),
        not 403'd, so an unknown ID and a wrong-NS ID look identical
        to the caller — by design.
        """
        params: dict[str, str] = {}
        if namespace:
            params["namespace"] = namespace
        resp = self._request("GET", f"/api/v1/ci/triggers/{trigger_id}", params=params)
        payload = resp.json() or {}
        return dict(payload.get("trigger") or {})

    def get_run_by_task(self, task_id: str) -> dict[str, Any] | None:
        """Read the CI run linked to a Mockarty task.

        Returns the run dict on success, or ``None`` when no CI run is
        associated with that task. Useful in a CI script that fires a
        perf launch with ``ci_trigger_id`` and wants to poll the
        external CI job state.
        """
        resp = self._request("GET", "/api/v1/ci/runs", params={"taskId": task_id})
        if resp.status_code == 404:
            return None
        payload = resp.json() or {}
        return dict(payload.get("run") or {})

    def cancel_run(self, run_id: str) -> None:
        """Mark a CI run as cancelled + fail the linked Mockarty task.

        Best-effort — does NOT call any remote CI cancel API.
        Idempotent on already-terminal runs.
        """
        self._request("POST", f"/api/v1/ci/runs/{run_id}/cancel")


class AsyncCITriggerAPI(AsyncAPIBase):
    """Asynchronous CI Triggers API — mirrors :class:`CITriggerAPI`."""

    async def list(self, namespace: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if namespace:
            params["namespace"] = namespace
        resp = await self._request("GET", "/api/v1/ci/triggers", params=params)
        payload = resp.json() or {}
        return list(payload.get("triggers") or [])

    async def get(
        self, trigger_id: str, namespace: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if namespace:
            params["namespace"] = namespace
        resp = await self._request(
            "GET", f"/api/v1/ci/triggers/{trigger_id}", params=params
        )
        payload = resp.json() or {}
        return dict(payload.get("trigger") or {})

    async def get_run_by_task(self, task_id: str) -> dict[str, Any] | None:
        resp = await self._request("GET", "/api/v1/ci/runs", params={"taskId": task_id})
        if resp.status_code == 404:
            return None
        payload = resp.json() or {}
        return dict(payload.get("run") or {})

    async def cancel_run(self, run_id: str) -> None:
        await self._request("POST", f"/api/v1/ci/runs/{run_id}/cancel")
