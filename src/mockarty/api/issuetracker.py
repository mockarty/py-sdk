# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Issue-tracker task-automation API.

Create/read/update/transition issues, comment, search, claim the next issue,
and manage projects/sprints over Mockarty's built-in tracker. Issue payloads are
rich and evolve, so this API uses loosely-typed dict I/O (mirrored by the Go map
and Java JsonNode SDKs). Every method takes an optional ``namespace`` (falls back
to the client default).
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _base(namespace: str) -> str:
    if not namespace:
        raise ValueError("namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/issuetracker"


def _clean_params(params: Optional[dict[str, str]]) -> dict[str, str]:
    return {k: v for k, v in (params or {}).items() if v}


class IssueTrackerAPI(SyncAPIBase):
    """Synchronous issue-tracker API."""

    def create_issue(self, issue: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Create an issue (fields: ``projectId``, ``type``, ``title``, … )."""
        ns = namespace or self._namespace
        return self._request("POST", f"{_base(ns)}/issues", json=issue).json()

    def get_issue(self, issue_id: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Fetch an issue by its UUID."""
        ns = namespace or self._namespace
        return self._request("GET", f"{_base(ns)}/issues/{quote(issue_id, safe='')}").json()

    def get_issue_by_key(self, key: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Fetch an issue by its human key (e.g. ``MK-42``)."""
        ns = namespace or self._namespace
        return self._request("GET", f"{_base(ns)}/issues/by-key/{quote(key, safe='')}").json()

    def list_issues(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        """List issues, optionally filtered via query params (``status=open``)."""
        ns = namespace or self._namespace
        resp = self._request("GET", f"{_base(ns)}/issues", params=_clean_params(filters))
        return resp.json().get("issues", [])

    def search_issues(self, query: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        """Text-search over issues."""
        ns = namespace or self._namespace
        resp = self._request("GET", f"{_base(ns)}/issues/search", params={"q": query})
        return resp.json().get("issues", [])

    def next_issue(self, *, namespace: Optional[str] = None, **params: str) -> dict[str, Any]:
        """Return the next issue available to work on (agent claim flow)."""
        ns = namespace or self._namespace
        return self._request("GET", f"{_base(ns)}/issues/next", params=_clean_params(params)).json()

    def update_issue(self, issue_id: str, fields: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Apply a partial update to an issue."""
        ns = namespace or self._namespace
        return self._request("PUT", f"{_base(ns)}/issues/{quote(issue_id, safe='')}", json=fields).json()

    def move_issue(self, issue_id: str, status: str, *, resolution: str = "", namespace: Optional[str] = None) -> dict[str, Any]:
        """Transition an issue to a new workflow status. ``resolution`` is
        required when moving into a terminal (closed) status."""
        ns = namespace or self._namespace
        body: dict[str, Any] = {"status": status}
        if resolution:
            body["resolution"] = resolution
        return self._request("POST", f"{_base(ns)}/issues/{quote(issue_id, safe='')}/move", json=body).json()

    def delete_issue(self, issue_id: str, *, namespace: Optional[str] = None) -> None:
        """Soft-delete an issue."""
        ns = namespace or self._namespace
        self._request("DELETE", f"{_base(ns)}/issues/{quote(issue_id, safe='')}")

    def add_comment(self, issue_id: str, body: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Post a comment to an issue."""
        ns = namespace or self._namespace
        return self._request("POST", f"{_base(ns)}/issues/{quote(issue_id, safe='')}/comments", json={"body": body}).json()

    def list_comments(self, issue_id: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        """List an issue's comments."""
        ns = namespace or self._namespace
        resp = self._request("GET", f"{_base(ns)}/issues/{quote(issue_id, safe='')}/comments")
        return resp.json().get("comments", [])

    def bulk_assign(self, issue_ids: list[str], assignee_id: str, *, namespace: Optional[str] = None) -> None:
        """Assign many issues to one assignee in a single call."""
        ns = namespace or self._namespace
        self._request("POST", f"{_base(ns)}/issues/bulk/assign", json={"ids": issue_ids, "assigneeId": assignee_id})

    def list_projects(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        """List the tracker's projects."""
        ns = namespace or self._namespace
        return self._request("GET", f"{_base(ns)}/projects").json().get("projects", [])

    def create_project(self, project: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Create a project."""
        ns = namespace or self._namespace
        return self._request("POST", f"{_base(ns)}/projects", json=project).json()

    def list_sprints(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        """List sprints, optionally filtered (``projectId=...``)."""
        ns = namespace or self._namespace
        resp = self._request("GET", f"{_base(ns)}/sprints", params=_clean_params(filters))
        return resp.json().get("sprints", [])

    def create_sprint(self, sprint: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        """Create a sprint."""
        ns = namespace or self._namespace
        return self._request("POST", f"{_base(ns)}/sprints", json=sprint).json()


class AsyncIssueTrackerAPI(AsyncAPIBase):
    """Asynchronous mirror of :class:`IssueTrackerAPI`."""

    async def create_issue(self, issue: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_base(ns)}/issues", json=issue)).json()

    async def get_issue(self, issue_id: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_base(ns)}/issues/{quote(issue_id, safe='')}")).json()

    async def get_issue_by_key(self, key: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_base(ns)}/issues/by-key/{quote(key, safe='')}")).json()

    async def list_issues(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request("GET", f"{_base(ns)}/issues", params=_clean_params(filters))
        return resp.json().get("issues", [])

    async def search_issues(self, query: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request("GET", f"{_base(ns)}/issues/search", params={"q": query})
        return resp.json().get("issues", [])

    async def next_issue(self, *, namespace: Optional[str] = None, **params: str) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_base(ns)}/issues/next", params=_clean_params(params))).json()

    async def update_issue(self, issue_id: str, fields: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("PUT", f"{_base(ns)}/issues/{quote(issue_id, safe='')}", json=fields)).json()

    async def move_issue(self, issue_id: str, status: str, *, resolution: str = "", namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        body: dict[str, Any] = {"status": status}
        if resolution:
            body["resolution"] = resolution
        return (await self._request("POST", f"{_base(ns)}/issues/{quote(issue_id, safe='')}/move", json=body)).json()

    async def delete_issue(self, issue_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("DELETE", f"{_base(ns)}/issues/{quote(issue_id, safe='')}")

    async def add_comment(self, issue_id: str, body: str, *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_base(ns)}/issues/{quote(issue_id, safe='')}/comments", json={"body": body})).json()

    async def list_comments(self, issue_id: str, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request("GET", f"{_base(ns)}/issues/{quote(issue_id, safe='')}/comments")
        return resp.json().get("comments", [])

    async def bulk_assign(self, issue_ids: list[str], assignee_id: str, *, namespace: Optional[str] = None) -> None:
        ns = namespace or self._namespace
        await self._request("POST", f"{_base(ns)}/issues/bulk/assign", json={"ids": issue_ids, "assigneeId": assignee_id})

    async def list_projects(self, *, namespace: Optional[str] = None) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        return (await self._request("GET", f"{_base(ns)}/projects")).json().get("projects", [])

    async def create_project(self, project: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_base(ns)}/projects", json=project)).json()

    async def list_sprints(self, *, namespace: Optional[str] = None, **filters: str) -> list[dict[str, Any]]:
        ns = namespace or self._namespace
        resp = await self._request("GET", f"{_base(ns)}/sprints", params=_clean_params(filters))
        return resp.json().get("sprints", [])

    async def create_sprint(self, sprint: dict[str, Any], *, namespace: Optional[str] = None) -> dict[str, Any]:
        ns = namespace or self._namespace
        return (await self._request("POST", f"{_base(ns)}/sprints", json=sprint)).json()
