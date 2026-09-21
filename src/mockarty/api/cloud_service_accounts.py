"""Cloud service-account management and msa_ workload APIs."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _management_path(space_id: str, *segments: str) -> str:
    if not space_id or not space_id.strip():
        raise ValueError("space_id is required")
    path = f"/api/v1/cloud/spaces/{quote(space_id, safe='')}/service-accounts"
    for segment in segments:
        if not segment or not segment.strip():
            raise ValueError("service-account path segment is required")
        path += f"/{quote(segment, safe='')}"
    return path


def _workload_path(space_id: str, project_id: str = "") -> str:
    if not space_id or not space_id.strip():
        raise ValueError("space_id is required")
    path = f"/api/v1/cloud/service-account/spaces/{quote(space_id, safe='')}/shared/projects"
    return path + (f"/{quote(project_id, safe='')}" if project_id else "")


def _run_path(space_id: str, run_id: str = "", *, cancel: bool = False) -> str:
    if not space_id or not space_id.strip():
        raise ValueError("space_id is required")
    path = f"/api/v1/cloud/service-account/spaces/{quote(space_id, safe='')}/shared/runs"
    if run_id:
        path += f"/{quote(run_id, safe='')}"
    if cancel:
        if not run_id:
            raise ValueError("run_id is required")
        path += "/cancel"
    return path


def _idempotency_headers(key: str) -> dict[str, str]:
    value = key.strip() if key else ""
    if not value:
        raise ValueError("idempotency_key is required")
    return {"Idempotency-Key": value}


class CloudServiceAccountsAPI(SyncAPIBase):
    """Manage machine principals using a human Cloud principal."""

    def list(self, space_id: str) -> dict[str, Any]:
        return self._request("GET", _management_path(space_id)).json()

    def get(self, space_id: str, account_id: str) -> dict[str, Any]:
        return self._request("GET", _management_path(space_id, account_id)).json()

    def create(self, space_id: str, name: str, capabilities: list[str], idempotency_key: str,
               *, issue_credential: bool = False, credential_ttl_seconds: int = 0) -> dict[str, Any]:
        return self._request("POST", _management_path(space_id), json={
            "name": name, "capabilities": capabilities, "issue_credential": issue_credential,
            "credential_ttl_seconds": credential_ttl_seconds,
        }, headers=_idempotency_headers(idempotency_key)).json()

    def bind(self, space_id: str, account_id: str, target_space_id: str,
             capabilities: list[str], idempotency_key: str) -> dict[str, Any]:
        return self._request("POST", _management_path(space_id, account_id, "bindings"),
                             json={"space_id": target_space_id, "capabilities": capabilities},
                             headers=_idempotency_headers(idempotency_key)).json()

    def issue_credential(self, space_id: str, account_id: str, idempotency_key: str,
                         *, ttl_seconds: int = 0) -> dict[str, Any]:
        return self._credential(space_id, account_id, idempotency_key, ttl_seconds, False)

    def rotate_credential(self, space_id: str, account_id: str, idempotency_key: str,
                          *, ttl_seconds: int = 0) -> dict[str, Any]:
        return self._credential(space_id, account_id, idempotency_key, ttl_seconds, True)

    def _credential(self, space_id: str, account_id: str, idempotency_key: str,
                    ttl_seconds: int, rotate: bool) -> dict[str, Any]:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must not be negative")
        segments = (account_id, "credentials", "rotate") if rotate else (account_id, "credentials")
        return self._request("POST", _management_path(space_id, *segments), json={"ttl_seconds": ttl_seconds},
                             headers=_idempotency_headers(idempotency_key)).json()

    def revoke(self, space_id: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        return self._request("DELETE", _management_path(space_id, account_id),
                             headers=_idempotency_headers(idempotency_key)).json()


class CloudServiceAccountAPI(SyncAPIBase):
    """Identity, authorization and Shared project workload for one msa_ credential."""

    def self(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/cloud/service-account/self").json()

    def authorize(self, space_id: str, capability: str) -> dict[str, Any]:
        if not capability or not capability.strip():
            raise ValueError("capability is required")
        return self._request("GET", f"/api/v1/cloud/service-account/spaces/{quote(space_id, safe='')}/authorize",
                             params={"capability": capability}).json()

    def list_projects(self, space_id: str, cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit if 1 <= limit <= 100 else 50}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", _workload_path(space_id), params=params).json()

    def get_project(self, space_id: str, project_id: str) -> dict[str, Any]:
        return self._request("GET", _workload_path(space_id, project_id)).json()

    def create_project(self, space_id: str, name: str, body: Any, idempotency_key: str) -> dict[str, Any]:
        return self._request("POST", _workload_path(space_id), json={"name": name, "body": body},
                             headers=_idempotency_headers(idempotency_key)).json()

    def update_project(self, space_id: str, project_id: str, name: str, body: Any, revision: int,
                       idempotency_key: str) -> dict[str, Any]:
        return self._request("PUT", _workload_path(space_id, project_id),
                             json={"name": name, "body": body, "revision": revision},
                             headers=_idempotency_headers(idempotency_key)).json()

    def delete_project(self, space_id: str, project_id: str, revision: int, idempotency_key: str) -> None:
        if revision < 1:
            raise ValueError("revision must be positive")
        self._request("DELETE", _workload_path(space_id, project_id), params={"revision": revision},
                      headers=_idempotency_headers(idempotency_key))

    def dispatch_run(self, space_id: str, *, deadline: str, capability: str, run_class: str,
                     project_id: str, idempotency_key: str, payload: Any = None) -> dict[str, Any]:
        body = {"deadline": deadline, "capability": capability, "class": run_class, "project_id": project_id}
        if payload is not None:
            body["payload"] = payload
        return self._request("POST", _run_path(space_id), json=body,
                             headers=_idempotency_headers(idempotency_key)).json()

    def get_run(self, space_id: str, run_id: str) -> dict[str, Any]:
        return self._request("GET", _run_path(space_id, run_id)).json()

    def cancel_run(self, space_id: str, run_id: str, revision: int, idempotency_key: str) -> dict[str, Any]:
        if revision < 1:
            raise ValueError("revision must be positive")
        return self._request("POST", _run_path(space_id, run_id, cancel=True), json={"revision": revision},
                             headers=_idempotency_headers(idempotency_key)).json()


class AsyncCloudServiceAccountsAPI(AsyncAPIBase):
    async def list(self, space_id: str) -> dict[str, Any]:
        return (await self._request("GET", _management_path(space_id))).json()

    async def get(self, space_id: str, account_id: str) -> dict[str, Any]:
        return (await self._request("GET", _management_path(space_id, account_id))).json()

    async def create(self, space_id: str, name: str, capabilities: list[str], idempotency_key: str,
                     *, issue_credential: bool = False, credential_ttl_seconds: int = 0) -> dict[str, Any]:
        return (await self._request("POST", _management_path(space_id), json={
            "name": name, "capabilities": capabilities, "issue_credential": issue_credential,
            "credential_ttl_seconds": credential_ttl_seconds,
        }, headers=_idempotency_headers(idempotency_key))).json()

    async def bind(self, space_id: str, account_id: str, target_space_id: str,
                   capabilities: list[str], idempotency_key: str) -> dict[str, Any]:
        return (await self._request("POST", _management_path(space_id, account_id, "bindings"),
                                    json={"space_id": target_space_id, "capabilities": capabilities},
                                    headers=_idempotency_headers(idempotency_key))).json()

    async def issue_credential(self, space_id: str, account_id: str, idempotency_key: str,
                               *, ttl_seconds: int = 0) -> dict[str, Any]:
        return await self._credential(space_id, account_id, idempotency_key, ttl_seconds, False)

    async def rotate_credential(self, space_id: str, account_id: str, idempotency_key: str,
                                *, ttl_seconds: int = 0) -> dict[str, Any]:
        return await self._credential(space_id, account_id, idempotency_key, ttl_seconds, True)

    async def _credential(self, space_id: str, account_id: str, idempotency_key: str,
                          ttl_seconds: int, rotate: bool) -> dict[str, Any]:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must not be negative")
        segments = (account_id, "credentials", "rotate") if rotate else (account_id, "credentials")
        return (await self._request("POST", _management_path(space_id, *segments), json={"ttl_seconds": ttl_seconds},
                                    headers=_idempotency_headers(idempotency_key))).json()

    async def revoke(self, space_id: str, account_id: str, idempotency_key: str) -> dict[str, Any]:
        return (await self._request("DELETE", _management_path(space_id, account_id),
                                    headers=_idempotency_headers(idempotency_key))).json()


class AsyncCloudServiceAccountAPI(AsyncAPIBase):
    async def self(self) -> dict[str, Any]:
        return (await self._request("GET", "/api/v1/cloud/service-account/self")).json()

    async def authorize(self, space_id: str, capability: str) -> dict[str, Any]:
        if not capability or not capability.strip():
            raise ValueError("capability is required")
        return (await self._request("GET", f"/api/v1/cloud/service-account/spaces/{quote(space_id, safe='')}/authorize",
                                    params={"capability": capability})).json()

    async def list_projects(self, space_id: str, cursor: str = "", limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit if 1 <= limit <= 100 else 50}
        if cursor:
            params["cursor"] = cursor
        return (await self._request("GET", _workload_path(space_id), params=params)).json()

    async def get_project(self, space_id: str, project_id: str) -> dict[str, Any]:
        return (await self._request("GET", _workload_path(space_id, project_id))).json()

    async def create_project(self, space_id: str, name: str, body: Any, idempotency_key: str) -> dict[str, Any]:
        return (await self._request("POST", _workload_path(space_id), json={"name": name, "body": body},
                                    headers=_idempotency_headers(idempotency_key))).json()

    async def update_project(self, space_id: str, project_id: str, name: str, body: Any, revision: int,
                             idempotency_key: str) -> dict[str, Any]:
        return (await self._request("PUT", _workload_path(space_id, project_id),
                                    json={"name": name, "body": body, "revision": revision},
                                    headers=_idempotency_headers(idempotency_key))).json()

    async def delete_project(self, space_id: str, project_id: str, revision: int, idempotency_key: str) -> None:
        if revision < 1:
            raise ValueError("revision must be positive")
        await self._request("DELETE", _workload_path(space_id, project_id), params={"revision": revision},
                            headers=_idempotency_headers(idempotency_key))

    async def dispatch_run(self, space_id: str, *, deadline: str, capability: str, run_class: str,
                           project_id: str, idempotency_key: str, payload: Any = None) -> dict[str, Any]:
        body = {"deadline": deadline, "capability": capability, "class": run_class, "project_id": project_id}
        if payload is not None:
            body["payload"] = payload
        return (await self._request("POST", _run_path(space_id), json=body,
                                    headers=_idempotency_headers(idempotency_key))).json()

    async def get_run(self, space_id: str, run_id: str) -> dict[str, Any]:
        return (await self._request("GET", _run_path(space_id, run_id))).json()

    async def cancel_run(self, space_id: str, run_id: str, revision: int, idempotency_key: str) -> dict[str, Any]:
        if revision < 1:
            raise ValueError("revision must be positive")
        return (await self._request("POST", _run_path(space_id, run_id, cancel=True), json={"revision": revision},
                                    headers=_idempotency_headers(idempotency_key))).json()
