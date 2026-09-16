# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Project-scoped delegated credentials (ledger item C-D-05).

An issuer — a Space owner, or one of their automation principals — freezes a
credential's namespace set, action set and expiry, and the holder cannot widen
any of the three. Use this instead of handing a contractor, a CI job or an MCP
client an API key.

The three properties are enforced by the server, not by this client: the scope
is read from the credential's stored row on every request, a namespace header
or query parameter cannot widen it, and the row itself rejects any write to the
scope columns. This client therefore validates only what a round-trip cannot
fix — a missing namespace set, a missing expiry, a past expiry, a TTL past the
server cap, an unknown action — and surfaces every server refusal verbatim.

It deliberately never NARROWS a requested scope: a request that would exceed
the caller's own authority is the server's refusal to make, and silently
shrinking it here would hand the caller a credential that does not do what it
asked for, with the escalation attempt invisible in the audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.delegated_credentials import (
    DELEGATED_ACTION_VOCABULARY,
    DELEGATED_MAX_TTL,
    DelegatedCredential,
    DelegatedCredentialCreateRequest,
    DelegatedCredentialList,
    DelegatedCredentialWithToken,
)

_BASE_PATH = "/api/v1/auth/delegated-credentials"


def _credential_path(credential_id: str) -> str:
    if not credential_id or not credential_id.strip():
        raise ValueError("a delegated credential id is required")
    return f"{_BASE_PATH}/{quote(credential_id, safe='')}"


def _as_request(
    request: DelegatedCredentialCreateRequest | dict[str, Any],
) -> DelegatedCredentialCreateRequest:
    if isinstance(request, DelegatedCredentialCreateRequest):
        return request
    return DelegatedCredentialCreateRequest.model_validate(request)


def _validate_scope(
    request: DelegatedCredentialCreateRequest, now: datetime
) -> None:
    if not [ns for ns in request.namespaces if ns.strip()]:
        raise ValueError(
            "at least one namespace is required — an unscoped delegated "
            "credential is an API key"
        )
    if any(not ns.strip() for ns in request.namespaces):
        raise ValueError("namespace entries must not be blank")
    if request.expires_at is None:
        raise ValueError(
            "expires_at is required — an unbounded delegated credential is an API key"
        )
    expires = request.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not expires > now:
        raise ValueError("expires_at must be in the future")
    if expires - now > DELEGATED_MAX_TTL:
        raise ValueError(
            f"expires_at may be at most {DELEGATED_MAX_TTL.days} days ahead"
        )
    unknown = [a for a in request.allowed_actions if a not in DELEGATED_ACTION_VOCABULARY]
    if unknown:
        raise ValueError(
            f"{unknown[0]!r} is not a known action "
            f"(want one of {', '.join(DELEGATED_ACTION_VOCABULARY)})"
        )


class DelegatedCredentialsAPI(SyncAPIBase):
    """Synchronous issuer-owned delegated-credential lifecycle."""

    def create(
        self,
        request: DelegatedCredentialCreateRequest | dict[str, Any],
    ) -> DelegatedCredentialWithToken:
        """Issue a delegated credential and return its plain bearer ONCE."""
        req = _as_request(request)
        _validate_scope(req, datetime.now(timezone.utc))
        response = self._request("POST", _BASE_PATH, json=req.to_wire())
        return DelegatedCredentialWithToken.model_validate(response.json() or {})

    def list(self) -> DelegatedCredentialList:
        """List the credentials THIS caller may manage.

        A user session sees the credentials it issued; a delegated credential
        sees only the ones it minted itself, never its issuer's.
        """
        response = self._request("GET", _BASE_PATH)
        return DelegatedCredentialList.model_validate(response.json() or {})

    def get(self, credential_id: str) -> DelegatedCredential:
        """Read one credential.

        A credential outside the caller's authority is reported as not-found
        rather than forbidden, so a delegated credential cannot enumerate its
        issuer's credentials by probing ids.
        """
        response = self._request("GET", _credential_path(credential_id))
        return DelegatedCredential.model_validate(response.json() or {})

    def revoke(self, credential_id: str) -> None:
        """Permanently disable a credential.

        Idempotent: revoking an already revoked credential is a no-op rather
        than an error, because the terminal state the caller wanted is the
        state that holds.
        """
        self._request("DELETE", _credential_path(credential_id))

    def rotate(self, credential_id: str) -> DelegatedCredentialWithToken:
        """Issue a fresh bearer, leaving the frozen scope untouched.

        The operation to reach for when a secret leaked but the work must
        continue. The previous bearer stops working as soon as this returns.
        Rotation is deliberately NOT a scope change: changing a live
        credential's authority means re-issuing, so the change is a new
        credential with its own audit trail rather than a silent edit.
        """
        response = self._request("POST", f"{_credential_path(credential_id)}/rotate")
        return DelegatedCredentialWithToken.model_validate(response.json() or {})


class AsyncDelegatedCredentialsAPI(AsyncAPIBase):
    """Asynchronous issuer-owned delegated-credential lifecycle."""

    async def create(
        self,
        request: DelegatedCredentialCreateRequest | dict[str, Any],
    ) -> DelegatedCredentialWithToken:
        req = _as_request(request)
        _validate_scope(req, datetime.now(timezone.utc))
        response = await self._request("POST", _BASE_PATH, json=req.to_wire())
        return DelegatedCredentialWithToken.model_validate(response.json() or {})

    async def list(self) -> DelegatedCredentialList:
        response = await self._request("GET", _BASE_PATH)
        return DelegatedCredentialList.model_validate(response.json() or {})

    async def get(self, credential_id: str) -> DelegatedCredential:
        response = await self._request("GET", _credential_path(credential_id))
        return DelegatedCredential.model_validate(response.json() or {})

    async def revoke(self, credential_id: str) -> None:
        await self._request("DELETE", _credential_path(credential_id))

    async def rotate(self, credential_id: str) -> DelegatedCredentialWithToken:
        response = await self._request(
            "POST", f"{_credential_path(credential_id)}/rotate"
        )
        return DelegatedCredentialWithToken.model_validate(response.json() or {})


__all__ = ["AsyncDelegatedCredentialsAPI", "DelegatedCredentialsAPI"]
