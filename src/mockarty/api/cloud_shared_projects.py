"""Public Cloud proxy for Shared SaaS project CRUD."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _path(space_id: str, project_id: str = "") -> str:
    if not space_id:
        raise ValueError("space_id is required")
    path = f"/api/v1/cloud/spaces/{quote(space_id, safe='')}/shared/projects"
    return path + (f"/{quote(project_id, safe='')}" if project_id else "")


class CloudSharedProjectsAPI(SyncAPIBase):
    def list(self, space_id: str, cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit if 1 <= limit <= 100 else 50}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", _path(space_id), params=params).json()

    def get(self, space_id: str, project_id: str) -> dict[str, Any]:
        return self._request("GET", _path(space_id, project_id)).json()

    def create(self, space_id: str, name: str, body: Any) -> dict[str, Any]:
        return self._request("POST", _path(space_id), json={"name": name, "body": body}).json()

    def update(self, space_id: str, project_id: str, name: str, body: Any, revision: int) -> dict[str, Any]:
        return self._request("PUT", _path(space_id, project_id), json={"name": name, "body": body, "revision": revision}).json()

    def delete(self, space_id: str, project_id: str, revision: int) -> None:
        if revision < 1:
            raise ValueError("revision must be positive")
        self._request("DELETE", _path(space_id, project_id), params={"revision": revision})


class AsyncCloudSharedProjectsAPI(AsyncAPIBase):
    async def list(self, space_id: str, cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit if 1 <= limit <= 100 else 50}
        if cursor:
            params["cursor"] = cursor
        return (await self._request("GET", _path(space_id), params=params)).json()

    async def get(self, space_id: str, project_id: str) -> dict[str, Any]:
        return (await self._request("GET", _path(space_id, project_id))).json()

    async def create(self, space_id: str, name: str, body: Any) -> dict[str, Any]:
        return (await self._request("POST", _path(space_id), json={"name": name, "body": body})).json()

    async def update(self, space_id: str, project_id: str, name: str, body: Any, revision: int) -> dict[str, Any]:
        return (await self._request("PUT", _path(space_id, project_id), json={"name": name, "body": body, "revision": revision})).json()

    async def delete(self, space_id: str, project_id: str, revision: int) -> None:
        if revision < 1:
            raise ValueError("revision must be positive")
        await self._request("DELETE", _path(space_id, project_id), params={"revision": revision})
