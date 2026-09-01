# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Canonical, explicit-Space Mockarty Cloud collaboration API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _space_path(space_id: str) -> str:
    if not space_id or not space_id.strip():
        raise ValueError("space_id is required")
    return f"/api/v1/cloud/spaces/{quote(space_id, safe='')}"


def _mutation_headers(etag: str, idempotency_key: str) -> dict[str, str]:
    if not etag or not etag.strip() or not idempotency_key or not idempotency_key.strip():
        raise ValueError("Space ETag and idempotency_key are required")
    return {"If-Match": etag, "Idempotency-Key": idempotency_key}


def _page_params(cursor: str, limit: int) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if cursor:
        params["cursor"] = cursor
    if limit > 0:
        params["limit"] = limit
    return params


class CloudSpacesAPI(SyncAPIBase):
    def list(self, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return self._request("GET", "/api/v1/cloud/spaces", params=_page_params(cursor, limit)).json()

    def get(self, space_id: str) -> dict[str, Any]:
        return self._request("GET", _space_path(space_id)).json()

    def rename(self, space_id: str, name: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("Space name is required")
        return self._request("PATCH", _space_path(space_id), json={"name": name},
                             headers=_mutation_headers(etag, idempotency_key)).json()

    def list_members(self, space_id: str, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return self._request("GET", _space_path(space_id) + "/members", params=_page_params(cursor, limit)).json()

    def list_invites(self, space_id: str, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return self._request("GET", _space_path(space_id) + "/invites", params=_page_params(cursor, limit)).json()

    def preview_invite(self, token: str) -> dict[str, Any]:
        if not token or not token.strip():
            raise ValueError("invite token is required")
        return self._request("GET", "/api/v1/cloud/invites/" + quote(token, safe="")).json()

    def create_invite(self, space_id: str, email: str, role: str, etag: str,
                      idempotency_key: str, expires_in_hours: int = 0) -> dict[str, Any]:
        body: dict[str, Any] = {"email": email, "role": role}
        if expires_in_hours:
            body["expires_in_hours"] = expires_in_hours
        return self._request("POST", _space_path(space_id) + "/invites", json=body,
                             headers=_mutation_headers(etag, idempotency_key)).json()

    def revoke_invite(self, space_id: str, invite_id: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        return self._request("DELETE", _space_path(space_id) + "/invites/" + quote(invite_id, safe=""),
                             headers=_mutation_headers(etag, idempotency_key)).json()

    def accept_invite(self, token: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/cloud/invites/" + quote(token, safe="") + "/accept", json={},
                             headers=_mutation_headers(etag, idempotency_key)).json()

    def update_member_role(self, space_id: str, member_id: str, role: str, etag: str,
                           idempotency_key: str) -> dict[str, Any]:
        return self._request("PATCH", _space_path(space_id) + "/members/" + quote(member_id, safe=""),
                             json={"role": role}, headers=_mutation_headers(etag, idempotency_key)).json()

    def remove_member(self, space_id: str, member_id: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        return self._request("DELETE", _space_path(space_id) + "/members/" + quote(member_id, safe=""),
                             headers=_mutation_headers(etag, idempotency_key)).json()


class AsyncCloudSpacesAPI(AsyncAPIBase):
    async def list(self, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return (await self._request("GET", "/api/v1/cloud/spaces", params=_page_params(cursor, limit))).json()

    async def get(self, space_id: str) -> dict[str, Any]:
        return (await self._request("GET", _space_path(space_id))).json()

    async def rename(self, space_id: str, name: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("Space name is required")
        return (await self._request("PATCH", _space_path(space_id), json={"name": name},
                                    headers=_mutation_headers(etag, idempotency_key))).json()

    async def list_members(self, space_id: str, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return (await self._request("GET", _space_path(space_id) + "/members", params=_page_params(cursor, limit))).json()

    async def list_invites(self, space_id: str, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return (await self._request("GET", _space_path(space_id) + "/invites", params=_page_params(cursor, limit))).json()

    async def preview_invite(self, token: str) -> dict[str, Any]:
        if not token or not token.strip():
            raise ValueError("invite token is required")
        return (await self._request("GET", "/api/v1/cloud/invites/" + quote(token, safe=""))).json()

    async def create_invite(self, space_id: str, email: str, role: str, etag: str,
                            idempotency_key: str, expires_in_hours: int = 0) -> dict[str, Any]:
        body: dict[str, Any] = {"email": email, "role": role}
        if expires_in_hours:
            body["expires_in_hours"] = expires_in_hours
        return (await self._request("POST", _space_path(space_id) + "/invites", json=body,
                                    headers=_mutation_headers(etag, idempotency_key))).json()

    async def revoke_invite(self, space_id: str, invite_id: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        return (await self._request("DELETE", _space_path(space_id) + "/invites/" + quote(invite_id, safe=""),
                                    headers=_mutation_headers(etag, idempotency_key))).json()

    async def accept_invite(self, token: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        return (await self._request("POST", "/api/v1/cloud/invites/" + quote(token, safe="") + "/accept", json={},
                                    headers=_mutation_headers(etag, idempotency_key))).json()

    async def update_member_role(self, space_id: str, member_id: str, role: str, etag: str,
                                 idempotency_key: str) -> dict[str, Any]:
        return (await self._request("PATCH", _space_path(space_id) + "/members/" + quote(member_id, safe=""),
                                    json={"role": role}, headers=_mutation_headers(etag, idempotency_key))).json()

    async def remove_member(self, space_id: str, member_id: str, etag: str, idempotency_key: str) -> dict[str, Any]:
        return (await self._request("DELETE", _space_path(space_id) + "/members/" + quote(member_id, safe=""),
                                    headers=_mutation_headers(etag, idempotency_key))).json()
