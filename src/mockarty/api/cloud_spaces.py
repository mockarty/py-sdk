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


def _team_key(idempotency_key: str) -> dict[str, str]:
    if not idempotency_key or not idempotency_key.strip():
        raise ValueError("idempotency_key is required for a Team mutation")
    return {"Idempotency-Key": idempotency_key}


def _team_space_body(team_id: str, name: str, audience: str, slug: str) -> dict[str, str]:
    if not team_id or not team_id.strip() or not name or not name.strip():
        raise ValueError("Team id and Space name are required")
    if audience not in ("team", "restricted"):
        raise ValueError("audience must be team or restricted")
    return {"team_id": team_id, "name": name, "audience": audience, "slug": slug}


def _team_invite_body(space_id: str, email: str, role: str) -> dict[str, str]:
    _space_path(space_id)
    if not email or not email.strip():
        raise ValueError("recipient email is required")
    if role not in ("member", "admin", "billing_manager"):
        raise ValueError("Team role must be member, admin or billing_manager")
    return {"space_id": space_id, "email": email, "role": role}


def _team_audit_params(space_id: str, before_id: str, limit: int) -> dict[str, Any]:
    _space_path(space_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0 or limit > 200:
        raise ValueError("Team audit limit must be 1..200, or zero for the server default")
    params: dict[str, Any] = {"space_id": space_id}
    if not isinstance(before_id, str):
        raise ValueError("before_id must be a positive decimal event id")
    if before_id:
        if (len(before_id) > 19 or not before_id.isascii() or
                not before_id.isdecimal() or int(before_id) < 1 or int(before_id) > 2**63 - 1):
            raise ValueError("before_id must be a positive decimal event id")
        params["before_id"] = before_id
    if limit:
        params["limit"] = limit
    return params


class CloudSpacesAPI(SyncAPIBase):
    def list(self, cursor: str = "", limit: int = 25) -> dict[str, Any]:
        return self._request("GET", "/api/v1/cloud/spaces", params=_page_params(cursor, limit)).json()

    def get(self, space_id: str) -> dict[str, Any]:
        return self._request("GET", _space_path(space_id)).json()

    def organization(self, space_id: str) -> dict[str, Any]:
        """Read the account as its owner, or the Team roster as an active admin."""
        _space_path(space_id)
        return self._request("GET", "/api/v1/cloud/organization", params={"space_id": space_id}).json()

    def preview_team_transition(self, token: str) -> dict[str, Any]:
        """Estimate the signed-in recipient's Personal Pro credit before joining."""
        if not token or not token.strip():
            raise ValueError("Team invite token is required")
        return self._request("GET", "/api/v1/cloud/team/invite-links/" + quote(token, safe="") +
                             "/transition").json()["transition"]

    def list_team_audit(self, space_id: str, before_id: str = "", limit: int = 0) -> dict[str, Any]:
        """Read redacted Team and Space events as a seated owner or billing manager.

        Pass next_before_id unchanged to read older events. Zero limit uses the
        server default of 50.
        """
        return self._request("GET", "/api/v1/cloud/team/audit",
                             params=_team_audit_params(space_id, before_id, limit)).json()

    def create_team_space(self, team_id: str, name: str, audience: str,
                          idempotency_key: str, slug: str = "") -> dict[str, Any]:
        """Add a Space to an active paid Team; reuse the key for an exact retry."""
        return self._request("POST", "/api/v1/cloud/team/spaces",
                             json=_team_space_body(team_id, name, audience, slug),
                             headers=_team_key(idempotency_key)).json()

    def invite_team_member(self, space_id: str, email: str, role: str,
                           idempotency_key: str) -> None:
        """Reserve a paid Seat and send an invitation without returning its token."""
        self._request("POST", "/api/v1/cloud/team/invites",
                      json=_team_invite_body(space_id, email, role),
                      headers=_team_key(idempotency_key))

    def revoke_team_invite(self, space_id: str, invite_id: str, idempotency_key: str) -> None:
        """Release one pending Team Seat; reuse the key after an uncertain response."""
        _space_path(space_id)
        if not invite_id or not invite_id.strip() or not idempotency_key or not idempotency_key.strip():
            raise ValueError("Team invite id and idempotency_key are required")
        self._request("DELETE", "/api/v1/cloud/team/invites/" + quote(invite_id, safe=""),
                      params={"space_id": space_id}, headers={"Idempotency-Key": idempotency_key})

    def remove_team_member(self, space_id: str, member_id: str, idempotency_key: str) -> None:
        """Release a Team Seat and Team access, retaining the member's Personal Spaces."""
        _space_path(space_id)
        if not member_id or not member_id.strip():
            raise ValueError("Team member id is required")
        self._request("DELETE", "/api/v1/cloud/team/members/" + quote(member_id, safe=""),
                      params={"space_id": space_id}, headers=_team_key(idempotency_key))

    def transfer_team_owner(self, space_id: str, successor_user_id: str, idempotency_key: str) -> None:
        """Appoint an active Team member without changing the payer or Space owners."""
        _space_path(space_id)
        if not successor_user_id or not successor_user_id.strip():
            raise ValueError("successor_user_id is required")
        self._request("POST", "/api/v1/cloud/team/owner-transfer",
                      json={"space_id": space_id, "successor_user_id": successor_user_id},
                      headers=_team_key(idempotency_key))

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

    async def organization(self, space_id: str) -> dict[str, Any]:
        """Read the account as its owner, or the Team roster as an active admin."""
        _space_path(space_id)
        return (await self._request("GET", "/api/v1/cloud/organization", params={"space_id": space_id})).json()

    async def preview_team_transition(self, token: str) -> dict[str, Any]:
        """Estimate the signed-in recipient's Personal Pro credit before joining."""
        if not token or not token.strip():
            raise ValueError("Team invite token is required")
        response = await self._request("GET", "/api/v1/cloud/team/invite-links/" + quote(token, safe="") +
                                       "/transition")
        return response.json()["transition"]

    async def list_team_audit(self, space_id: str, before_id: str = "", limit: int = 0) -> dict[str, Any]:
        """Read redacted Team and Space events as a seated owner or billing manager."""
        return (await self._request("GET", "/api/v1/cloud/team/audit",
                                    params=_team_audit_params(space_id, before_id, limit))).json()

    async def create_team_space(self, team_id: str, name: str, audience: str,
                                idempotency_key: str, slug: str = "") -> dict[str, Any]:
        """Add a Space to an active paid Team; reuse the key for an exact retry."""
        return (await self._request("POST", "/api/v1/cloud/team/spaces",
                                    json=_team_space_body(team_id, name, audience, slug),
                                    headers=_team_key(idempotency_key))).json()

    async def invite_team_member(self, space_id: str, email: str, role: str,
                                 idempotency_key: str) -> None:
        """Reserve a paid Seat and send an invitation without returning its token."""
        await self._request("POST", "/api/v1/cloud/team/invites",
                            json=_team_invite_body(space_id, email, role),
                            headers=_team_key(idempotency_key))

    async def revoke_team_invite(self, space_id: str, invite_id: str, idempotency_key: str) -> None:
        """Release one pending Team Seat; reuse the key after an uncertain response."""
        _space_path(space_id)
        if not invite_id or not invite_id.strip() or not idempotency_key or not idempotency_key.strip():
            raise ValueError("Team invite id and idempotency_key are required")
        await self._request("DELETE", "/api/v1/cloud/team/invites/" + quote(invite_id, safe=""),
                            params={"space_id": space_id}, headers={"Idempotency-Key": idempotency_key})

    async def remove_team_member(self, space_id: str, member_id: str, idempotency_key: str) -> None:
        """Release a Team Seat and Team access, retaining the member's Personal Spaces."""
        _space_path(space_id)
        if not member_id or not member_id.strip():
            raise ValueError("Team member id is required")
        await self._request("DELETE", "/api/v1/cloud/team/members/" + quote(member_id, safe=""),
                            params={"space_id": space_id}, headers=_team_key(idempotency_key))

    async def transfer_team_owner(self, space_id: str, successor_user_id: str, idempotency_key: str) -> None:
        """Appoint an active Team member without changing the payer or Space owners."""
        _space_path(space_id)
        if not successor_user_id or not successor_user_id.strip():
            raise ValueError("successor_user_id is required")
        await self._request("POST", "/api/v1/cloud/team/owner-transfer",
                            json={"space_id": space_id, "successor_user_id": successor_user_id},
                            headers=_team_key(idempotency_key))

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
