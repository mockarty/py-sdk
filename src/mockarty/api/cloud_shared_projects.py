"""Public Cloud proxy for Shared SaaS project CRUD."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _path(space_id: str, project_id: str = "") -> str:
    if not space_id:
        raise ValueError("space_id is required")
    path = f"/api/v1/cloud/spaces/{quote(space_id, safe='')}/shared/projects"
    return path + (f"/{quote(project_id, safe='')}" if project_id else "")


def _mutation_headers(request_id: str | None) -> dict[str, str]:
    value = request_id or str(uuid4())
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("request_id must be a canonical UUID") from exc
    if str(parsed) != value:
        raise ValueError("request_id must be a canonical UUID")
    return {"X-Request-ID": value}


class CloudSharedProjectsAPI(SyncAPIBase):
    def list(self, space_id: str, cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit if 1 <= limit <= 100 else 50}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", _path(space_id), params=params).json()

    def get(self, space_id: str, project_id: str) -> dict[str, Any]:
        return self._request("GET", _path(space_id, project_id)).json()

    def create(self, space_id: str, name: str, body: Any, request_id: str | None = None) -> dict[str, Any]:
        """Create a project; reuse request_id only for the exact ambiguous retry."""
        return self._request("POST", _path(space_id), json={"name": name, "body": body},
                             headers=_mutation_headers(request_id)).json()

    def update(self, space_id: str, project_id: str, name: str, body: Any, revision: int,
               request_id: str | None = None) -> dict[str, Any]:
        return self._request("PUT", _path(space_id, project_id), json={"name": name, "body": body, "revision": revision},
                             headers=_mutation_headers(request_id)).json()

    def delete(self, space_id: str, project_id: str, revision: int, request_id: str | None = None) -> None:
        if revision < 1:
            raise ValueError("revision must be positive")
        self._request("DELETE", _path(space_id, project_id), params={"revision": revision},
                      headers=_mutation_headers(request_id))


class AsyncCloudSharedProjectsAPI(AsyncAPIBase):
    async def list(self, space_id: str, cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit if 1 <= limit <= 100 else 50}
        if cursor:
            params["cursor"] = cursor
        return (await self._request("GET", _path(space_id), params=params)).json()

    async def get(self, space_id: str, project_id: str) -> dict[str, Any]:
        return (await self._request("GET", _path(space_id, project_id))).json()

    async def create(self, space_id: str, name: str, body: Any, request_id: str | None = None) -> dict[str, Any]:
        return (await self._request("POST", _path(space_id), json={"name": name, "body": body},
                                    headers=_mutation_headers(request_id))).json()

    async def update(self, space_id: str, project_id: str, name: str, body: Any, revision: int,
                     request_id: str | None = None) -> dict[str, Any]:
        return (await self._request("PUT", _path(space_id, project_id), json={"name": name, "body": body, "revision": revision},
                                    headers=_mutation_headers(request_id))).json()

    async def delete(self, space_id: str, project_id: str, revision: int, request_id: str | None = None) -> None:
        if revision < 1:
            raise ValueError("revision must be positive")
        await self._request("DELETE", _path(space_id, project_id), params={"revision": revision},
                            headers=_mutation_headers(request_id))
