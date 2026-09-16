# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Project-scoped delegated-credential models.

A delegated credential is the primitive for SHARED work. The issuer freezes

* the set of namespaces the credential may act in,
* the set of actions it may perform (read / write / delete),
* the instant it stops working,

and the holder has no path to widen any of the three. That is what separates it
from an API key, whose namespace is a DEFAULT its holder can change and which
carries no expiry of its own.

The field aliases below are the snake_case keys the server publishes in
``docs/swagger/swagger.json``. ``populate_by_name=True`` means a model accepts
either spelling, so a payload built by hand still validates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: Prefix that marks a delegated-credential bearer. Distinct from ``mk_`` (API
#: keys) and ``mki_`` (integration tokens), so every auth surface routes on the
#: prefix alone before touching a database.
DELEGATED_TOKEN_PREFIX = "mkd_"

#: The closed set of actions a delegated scope may name. The server rejects
#: anything outside it, so a caller can validate locally before a round-trip.
DELEGATED_ACTION_VOCABULARY = ("read", "write", "delete")

#: Mirror of the server's cap on how far ahead an expiry may be pinned. A
#: credential outliving a review cycle is the property this primitive exists to
#: prevent, so the cap is enforced on both sides.
DELEGATED_MAX_TTL = timedelta(days=365)


class DelegatedCredentialCreateRequest(BaseModel):
    """The create payload.

    Note what is NOT here: no issuer field, and nothing that could later extend
    a live credential. The issuer is taken from the authenticated principal and
    the scope is frozen at creation.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = ""
    description: str = ""
    #: Required. An unbounded delegated credential is an API key.
    namespaces: list[str] = Field(default_factory=list)
    #: Omit to grant the full vocabulary (read, write, delete), which is how
    #: the server reads an empty list.
    allowed_actions: list[str] = Field(default_factory=list)
    #: Required, and must be in the future.
    expires_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        """Render the body the server expects, with a RFC3339 UTC expiry."""
        if self.expires_at is None:
            raise ValueError(
                "expires_at is required — an unbounded delegated credential is an API key"
            )
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        body: dict[str, Any] = {
            "name": self.name,
            "namespaces": list(self.namespaces),
            "expires_at": expires.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        if self.description:
            body["description"] = self.description
        if self.allowed_actions:
            body["allowed_actions"] = list(self.allowed_actions)
        if self.metadata is not None:
            body["metadata"] = self.metadata
        return body


class DelegatedCredential(BaseModel):
    """One issued delegated credential.

    The stored bcrypt hash and sha256 index are never part of this payload, so
    no caller has to remember to strip them.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = ""
    name: str = ""
    description: str = ""
    namespaces: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    issuer_user_id: str = ""
    issuer_credential_id: str = ""
    issuer_user_role: str = ""
    issuer_user_email: str = ""
    issuer_user_login: str = ""
    #: Display label only: 8 characters of the base64 body, useless for
    #: authentication. Enough for an operator to match a listing row to a
    #: leaked-token report.
    token_prefix: str = ""
    metadata: dict[str, Any] | None = None

    @property
    def is_revoked(self) -> bool:
        """Revocation is terminal — there is no un-revoke."""
        return self.revoked_at is not None

    def is_expired(self, now: datetime | None = None) -> bool:
        """Whether the credential has lapsed at ``now`` (default: UTC now)."""
        if self.expires_at is None:
            # A credential whose expiry did not decode cannot be proven live.
            # Fail closed rather than treat a missing field as unbounded.
            return True
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return not moment < expires

    def has_namespace(self, namespace: str) -> bool:
        """Whether ``namespace`` is inside the frozen namespace set."""
        return bool(namespace) and namespace in self.namespaces

    def allows(self, action: str) -> bool:
        """Whether ``action`` is inside the frozen action set."""
        return action in self.allowed_actions


class DelegatedCredentialWithToken(BaseModel):
    """The create/rotate response — the ONLY place a plain bearer is returned.

    The row stores bcrypt + sha256, so the bearer cannot be read back. A caller
    that loses it must rotate.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    credential: DelegatedCredential = Field(default_factory=DelegatedCredential)
    token: str = ""
    message: str = ""


class DelegatedCredentialList(BaseModel):
    """The list response."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    credentials: list[DelegatedCredential] = Field(default_factory=list)
    count: int = 0
