# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Versioned Workflow Definition authoring API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _base(namespace: str) -> str:
    if not namespace or namespace == "*":
        raise ValueError("a concrete namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/workflow-definitions"


def _version_path(namespace: str, workflow_id: str, version: str) -> str:
    if not workflow_id or not version:
        raise ValueError("workflow_id and version are required")
    return f"{_base(namespace)}/{quote(workflow_id, safe='')}/versions/{quote(version, safe='')}"


def _revision(expected_revision: int) -> int:
    if expected_revision <= 0:
        raise ValueError("expected_revision must be positive")
    return expected_revision


class WorkflowDefinitionsAPI(SyncAPIBase):
    """Synchronous draft, dry-run and immutable-publish lifecycle."""

    def list(self, *, namespace: str | None = None, workflow_id: str = "",
             status: str = "", cursor: str = "", limit: int = 50) -> dict[str, Any]:
        ns = namespace or self._namespace
        params = {"limit": limit}
        if workflow_id:
            params["id"] = workflow_id
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        return dict(self._request("GET", _base(ns), params=params).json() or {})

    def create_draft(self, definition: dict[str, Any]) -> dict[str, Any]:
        namespace = str(definition.get("namespace") or self._namespace)
        body = dict(definition)
        body["namespace"] = namespace
        return dict(self._request("POST", _base(namespace), json=body).json() or {})

    def get(self, workflow_id: str, version: str, *, namespace: str | None = None) -> dict[str, Any]:
        return dict(self._request("GET", _version_path(namespace or self._namespace, workflow_id, version)).json() or {})

    def update_draft(self, definition: dict[str, Any], expected_revision: int) -> dict[str, Any]:
        expected_revision = _revision(expected_revision)
        namespace = str(definition.get("namespace") or self._namespace)
        normalized = dict(definition)
        normalized["namespace"] = namespace
        path = _version_path(namespace, str(normalized.get("id") or ""), str(normalized.get("version") or ""))
        body = {"definition": normalized, "expectedRevision": expected_revision}
        return dict(self._request("PUT", path, json=body).json() or {})

    def dry_run(self, workflow_id: str, version: str, expected_revision: int,
                *, namespace: str | None = None) -> dict[str, Any]:
        expected_revision = _revision(expected_revision)
        path = _version_path(namespace or self._namespace, workflow_id, version)
        return dict(self._request("POST", f"{path}/dry-run", json={"expectedRevision": expected_revision}).json() or {})

    def publish(self, workflow_id: str, version: str, expected_revision: int,
                *, namespace: str | None = None) -> dict[str, Any]:
        expected_revision = _revision(expected_revision)
        path = _version_path(namespace or self._namespace, workflow_id, version)
        return dict(self._request("POST", f"{path}/publish", json={"expectedRevision": expected_revision}).json() or {})


class AsyncWorkflowDefinitionsAPI(AsyncAPIBase):
    """Asynchronous parity for :class:`WorkflowDefinitionsAPI`."""

    async def list(self, *, namespace: str | None = None, workflow_id: str = "",
                   status: str = "", cursor: str = "", limit: int = 50) -> dict[str, Any]:
        ns = namespace or self._namespace
        params = {"limit": limit}
        if workflow_id:
            params["id"] = workflow_id
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        return dict((await self._request("GET", _base(ns), params=params)).json() or {})

    async def create_draft(self, definition: dict[str, Any]) -> dict[str, Any]:
        namespace = str(definition.get("namespace") or self._namespace)
        body = dict(definition)
        body["namespace"] = namespace
        return dict((await self._request("POST", _base(namespace), json=body)).json() or {})

    async def get(self, workflow_id: str, version: str, *, namespace: str | None = None) -> dict[str, Any]:
        return dict((await self._request("GET", _version_path(namespace or self._namespace, workflow_id, version))).json() or {})

    async def update_draft(self, definition: dict[str, Any], expected_revision: int) -> dict[str, Any]:
        expected_revision = _revision(expected_revision)
        namespace = str(definition.get("namespace") or self._namespace)
        normalized = dict(definition)
        normalized["namespace"] = namespace
        path = _version_path(namespace, str(normalized.get("id") or ""), str(normalized.get("version") or ""))
        body = {"definition": normalized, "expectedRevision": expected_revision}
        return dict((await self._request("PUT", path, json=body)).json() or {})

    async def dry_run(self, workflow_id: str, version: str, expected_revision: int,
                      *, namespace: str | None = None) -> dict[str, Any]:
        expected_revision = _revision(expected_revision)
        path = _version_path(namespace or self._namespace, workflow_id, version)
        return dict((await self._request("POST", f"{path}/dry-run", json={"expectedRevision": expected_revision})).json() or {})

    async def publish(self, workflow_id: str, version: str, expected_revision: int,
                      *, namespace: str | None = None) -> dict[str, Any]:
        expected_revision = _revision(expected_revision)
        path = _version_path(namespace or self._namespace, workflow_id, version)
        return dict((await self._request("POST", f"{path}/publish", json={"expectedRevision": expected_revision})).json() or {})
