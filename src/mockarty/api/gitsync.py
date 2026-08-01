# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Git-sync API resource — bind an autotest collection to a git repository.

Pull materialises the repo tree into Mockarty; push writes local edits back.
Git I/O runs server-side (go-git); the SDK just orchestrates. Great from CI:
pull the team's autotests and run them, or push what you recorded.
"""

from __future__ import annotations

from typing import Any, Optional

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _binding_body(
    repo_url: str,
    branch: str = "",
    subdir: str = "",
    kind: str = "",
    auth_username: str = "",
    auth_token: str = "",
    collection_id: str = "",
    enabled: Optional[bool] = None,
    auto_sync: Optional[bool] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"repoUrl": repo_url}
    if branch:
        body["branch"] = branch
    if subdir:
        body["subdir"] = subdir
    if kind:
        body["kind"] = kind
    if auth_username:
        body["authUsername"] = auth_username
    if auth_token:
        body["authToken"] = auth_token
    if collection_id:
        body["collectionId"] = collection_id
    if enabled is not None:
        body["enabled"] = enabled
    if auto_sync is not None:
        body["autoSync"] = auto_sync
    return body


class GitSyncAPI(SyncAPIBase):
    """Synchronous git-sync API."""

    def _ns(self) -> Optional[dict[str, str]]:
        return {"namespace": self._namespace} if self._namespace else None

    def create_binding(self, repo_url: str, *, branch: str = "", subdir: str = "",
                       kind: str = "", auth_username: str = "", auth_token: str = "",
                       collection_id: str = "", enabled: Optional[bool] = None,
                       auto_sync: Optional[bool] = None) -> dict[str, Any]:
        """Bind a repo (POST /api/v1/git-sync/bindings). Kind is api|ui|mixed."""
        body = _binding_body(repo_url, branch, subdir, kind, auth_username,
                             auth_token, collection_id, enabled, auto_sync)
        return self._request("POST", "/api/v1/git-sync/bindings", json=body, params=self._ns()).json()

    def list_bindings(self) -> list[dict[str, Any]]:
        """List the namespace's bindings."""
        data = self._request("GET", "/api/v1/git-sync/bindings", params=self._ns()).json()
        return data.get("bindings", []) if isinstance(data, dict) else []

    def get_binding(self, binding_id: str) -> dict[str, Any]:
        """Get a binding (with last-sync status) by id."""
        return self._request("GET", f"/api/v1/git-sync/bindings/{binding_id}", params=self._ns()).json()

    def delete_binding(self, binding_id: str) -> dict[str, Any]:
        """Remove a binding (already-synced tests stay in Mockarty)."""
        return self._request("DELETE", f"/api/v1/git-sync/bindings/{binding_id}", params=self._ns()).json()

    def pull(self, binding_id: str) -> dict[str, Any]:
        """Clone + materialise the tests. Returns {commit, uiTestsFound}."""
        return self._request("POST", f"/api/v1/git-sync/bindings/{binding_id}/pull", params=self._ns()).json()

    def push(self, binding_id: str, message: str = "") -> dict[str, Any]:
        """Serialise the namespace's tests + commit + push. Returns {commit}."""
        params = dict(self._ns() or {})
        if message:
            params["message"] = message
        return self._request("POST", f"/api/v1/git-sync/bindings/{binding_id}/push",
                             params=params or None).json()


class AsyncGitSyncAPI(AsyncAPIBase):
    """Asynchronous git-sync API."""

    def _ns(self) -> Optional[dict[str, str]]:
        return {"namespace": self._namespace} if self._namespace else None

    async def create_binding(self, repo_url: str, *, branch: str = "", subdir: str = "",
                            kind: str = "", auth_username: str = "", auth_token: str = "",
                            collection_id: str = "", enabled: Optional[bool] = None,
                            auto_sync: Optional[bool] = None) -> dict[str, Any]:
        body = _binding_body(repo_url, branch, subdir, kind, auth_username,
                             auth_token, collection_id, enabled, auto_sync)
        resp = await self._request("POST", "/api/v1/git-sync/bindings", json=body, params=self._ns())
        return resp.json()

    async def list_bindings(self) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/api/v1/git-sync/bindings", params=self._ns())
        data = resp.json()
        return data.get("bindings", []) if isinstance(data, dict) else []

    async def get_binding(self, binding_id: str) -> dict[str, Any]:
        resp = await self._request("GET", f"/api/v1/git-sync/bindings/{binding_id}", params=self._ns())
        return resp.json()

    async def delete_binding(self, binding_id: str) -> dict[str, Any]:
        resp = await self._request("DELETE", f"/api/v1/git-sync/bindings/{binding_id}", params=self._ns())
        return resp.json()

    async def pull(self, binding_id: str) -> dict[str, Any]:
        resp = await self._request("POST", f"/api/v1/git-sync/bindings/{binding_id}/pull", params=self._ns())
        return resp.json()

    async def push(self, binding_id: str, message: str = "") -> dict[str, Any]:
        params = dict(self._ns() or {})
        if message:
            params["message"] = message
        resp = await self._request("POST", f"/api/v1/git-sync/bindings/{binding_id}/push",
                                   params=params or None)
        return resp.json()
