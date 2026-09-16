# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Delegated-credential SDK contract (ledger item C-D-05).

The client is generated from what ``docs/swagger/swagger.json`` publishes, so
its parsing is exercised against LITERAL server JSON rather than against a
payload it produced itself: a test that round-trips the SDK's own model would
agree with itself no matter what the server sends, which is exactly how a
camelCase/snake_case mismatch shipped once already.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient
from mockarty.models.delegated_credentials import (
    DELEGATED_MAX_TTL,
    DelegatedCredential,
    DelegatedCredentialCreateRequest,
)

BASE = "http://localhost:5770"
PATH = BASE + "/api/v1/auth/delegated-credentials"

#: The response body the server actually emits, key for key.
CREDENTIAL_JSON = {
    "created_at": "2026-09-16T12:00:00Z",
    "updated_at": "2026-09-16T12:00:00Z",
    "expires_at": "2026-09-17T12:00:00Z",
    "revoked_at": "2026-09-16T13:00:00Z",
    "last_used_at": "2026-09-16T12:30:00Z",
    "metadata": {"ticket": "C-D-05"},
    "id": "cred-1",
    "name": "ci-reader",
    "description": "read-only CI credential",
    "issuer_user_id": "user-1",
    "issuer_credential_id": "cred-parent",
    "namespaces": ["alpha", "beta"],
    "allowed_actions": ["read"],
    "token_prefix": "mkd_abcd1234…",
    "issuer_user_role": "admin",
    "issuer_user_email": "owner@example.com",
    "issuer_user_login": "owner",
}


def future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=30)


# ── Wire contract ──────────────────────────────────────────────────────────


@respx.mock
def test_response_decodes_the_frozen_scope(client: MockartyClient) -> None:
    """Every frozen field must survive the trip, in snake_case.

    Before the server's json tags were restored this decoded a credential with
    no expiry, no issuer and no id — the half of the scope the credential is
    issued TO constrain.
    """
    respx.get(PATH + "/cred-1").mock(return_value=httpx.Response(200, json=CREDENTIAL_JSON))

    cred = client.delegated_credentials.get("cred-1")

    assert isinstance(cred, DelegatedCredential)
    assert cred.id == "cred-1"
    assert cred.name == "ci-reader"
    assert cred.description == "read-only CI credential"
    assert cred.issuer_user_id == "user-1"
    assert cred.issuer_user_role == "admin"
    assert cred.issuer_user_email == "owner@example.com"
    assert cred.issuer_user_login == "owner"
    assert cred.issuer_credential_id == "cred-parent"
    assert cred.token_prefix == "mkd_abcd1234…"
    assert cred.namespaces == ["alpha", "beta"]
    assert cred.allowed_actions == ["read"]
    assert cred.metadata == {"ticket": "C-D-05"}
    # A missing expiry would make these None and the assertions below vacuous,
    # so the timestamps are asserted to have decoded at all first.
    assert cred.expires_at is not None and cred.created_at is not None
    assert cred.expires_at == datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    assert cred.revoked_at is not None and cred.last_used_at is not None


@respx.mock
def test_scope_helpers_answer_from_the_decoded_row(client: MockartyClient) -> None:
    respx.get(PATH + "/cred-1").mock(return_value=httpx.Response(200, json=CREDENTIAL_JSON))
    cred = client.delegated_credentials.get("cred-1")

    assert cred.has_namespace("beta") is True
    assert cred.has_namespace("gamma") is False
    assert cred.has_namespace("") is False
    assert cred.allows("read") is True
    assert cred.allows("delete") is False
    assert cred.is_revoked is True
    assert cred.is_expired(datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc)) is False
    assert cred.is_expired(datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)) is True


def test_a_credential_without_an_expiry_fails_closed() -> None:
    """A row whose expiry did not decode must not read as unbounded."""
    assert DelegatedCredential(id="x").is_expired() is True


# ── Lifecycle ──────────────────────────────────────────────────────────────


@respx.mock
def test_lifecycle_uses_exact_paths_and_snake_case_body(client: MockartyClient) -> None:
    create = respx.post(PATH).mock(
        return_value=httpx.Response(
            201, json={"credential": CREDENTIAL_JSON, "token": "mkd_plainbearer", "message": "created"}
        )
    )
    listed = respx.get(PATH).mock(
        return_value=httpx.Response(200, json={"credentials": [CREDENTIAL_JSON], "count": 1})
    )
    rotate = respx.post(PATH + "/cred-1/rotate").mock(
        return_value=httpx.Response(
            200, json={"credential": CREDENTIAL_JSON, "token": "mkd_rotated", "message": "rotated"}
        )
    )
    revoke = respx.delete(PATH + "/cred-1").mock(
        return_value=httpx.Response(200, json={"message": "revoked"})
    )

    issued = client.delegated_credentials.create(
        DelegatedCredentialCreateRequest(
            name="ci-reader",
            description="read-only CI credential",
            namespaces=["alpha"],
            allowed_actions=["read"],
            expires_at=future(),
        )
    )
    assert issued.token == "mkd_plainbearer"
    assert issued.credential.id == "cred-1"

    body = json.loads(create.calls.last.request.content)
    assert set(body) == {"name", "description", "namespaces", "allowed_actions", "expires_at"}
    assert body["namespaces"] == ["alpha"]
    assert body["allowed_actions"] == ["read"]
    # RFC3339, and never a camelCase twin that the server would ignore.
    assert body["expires_at"].endswith("Z")
    assert "expiresAt" not in body
    datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))

    page = client.delegated_credentials.list()
    assert page.count == 1
    assert page.credentials[0].id == "cred-1"

    assert client.delegated_credentials.rotate("cred-1").token == "mkd_rotated"
    assert client.delegated_credentials.revoke("cred-1") is None

    assert create.called and listed.called and rotate.called and revoke.called


@respx.mock
def test_create_omits_optional_keys_a_caller_did_not_set(client: MockartyClient) -> None:
    route = respx.post(PATH).mock(
        return_value=httpx.Response(201, json={"credential": CREDENTIAL_JSON, "token": "mkd_t"})
    )
    client.delegated_credentials.create(
        {"name": "minimal", "namespaces": ["alpha"], "expires_at": future()}
    )
    body = json.loads(route.calls.last.request.content)
    assert "description" not in body
    assert "metadata" not in body
    # An omitted action set is the server's full vocabulary, not an empty grant.
    assert "allowed_actions" not in body


# ── Local refusals ─────────────────────────────────────────────────────────


@respx.mock
def test_a_malformed_scope_is_refused_without_a_request(client: MockartyClient) -> None:
    route = respx.post(PATH).mock(return_value=httpx.Response(201, json={}))
    now = datetime.now(timezone.utc)

    cases = [
        ("no namespaces", {"namespaces": [], "expires_at": now + timedelta(hours=1)}),
        ("blank namespace", {"namespaces": ["  "], "expires_at": now + timedelta(hours=1)}),
        ("no expiry", {"namespaces": ["alpha"]}),
        ("expiry in the past", {"namespaces": ["alpha"], "expires_at": now - timedelta(hours=1)}),
        (
            "expiry beyond the cap",
            {"namespaces": ["alpha"], "expires_at": now + DELEGATED_MAX_TTL + timedelta(days=1)},
        ),
        (
            "unknown action",
            {"namespaces": ["alpha"], "expires_at": now + timedelta(hours=1), "allowed_actions": ["admin"]},
        ),
    ]
    for label, payload in cases:
        with pytest.raises(ValueError):
            client.delegated_credentials.create(payload)
        assert not route.called, f"{label}: a locally-refused create must not reach the server"


@respx.mock
@pytest.mark.parametrize("bad_id", ["", "   "])
def test_an_empty_id_is_refused_without_a_request(client: MockartyClient, bad_id: str) -> None:
    get = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        client.delegated_credentials.get(bad_id)
    with pytest.raises(ValueError):
        client.delegated_credentials.rotate(bad_id)
    with pytest.raises(ValueError):
        client.delegated_credentials.revoke(bad_id)
    assert not get.called


@respx.mock
def test_a_server_refusal_surfaces_as_an_api_error(client: MockartyClient) -> None:
    from mockarty.errors import MockartyAPIError

    respx.delete(PATH + "/cred-forbidden").mock(
        return_value=httpx.Response(
            403, json={"error": "requested scope exceeds this delegated credential's own scope"}
        )
    )
    with pytest.raises(MockartyAPIError) as exc:
        client.delegated_credentials.revoke("cred-forbidden")
    assert exc.value.status_code == 403


# ── Async parity ───────────────────────────────────────────────────────────


@respx.mock
def test_async_surface_is_equivalent(base_url: str, api_key: str) -> None:
    respx.get(PATH + "/cred-1").mock(return_value=httpx.Response(200, json=CREDENTIAL_JSON))
    respx.delete(PATH + "/cred-1").mock(return_value=httpx.Response(200, json={"message": "revoked"}))

    async def run() -> None:
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as aclient:
            cred = await aclient.delegated_credentials.get("cred-1")
            assert cred.id == "cred-1"
            assert cred.namespaces == ["alpha", "beta"]
            assert cred.expires_at == datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
            assert await aclient.delegated_credentials.revoke("cred-1") is None

    asyncio.run(run())


def test_the_pre_fix_go_field_name_shape_does_not_read_as_a_usable_credential() -> None:
    """A stale server must not be able to produce a silently-unbounded grant.

    Before the json tags were restored the server answered `CreatedAt`,
    `ExpiresAt`, `IssuerUserRole`, … — the Go field names — while the published
    contract promised snake_case. A client that ignored the expiry is a client
    that keeps working past the instant the issuer chose, so a payload in the
    old shape must leave the credential with no expiry and no issuer, and
    `is_expired()` must answer True rather than treating the missing field as
    "unbounded".
    """
    legacy = {
        "CreatedAt": "2026-09-16T12:00:00Z",
        "ExpiresAt": "2026-09-17T12:00:00Z",
        "ID": "cred-1",
        "IssuerUserID": "user-1",
        "IssuerUserRole": "admin",
        "Namespaces": ["alpha"],
        "allowed_actions": ["read"],
        "token_prefix": "mkd_abcd1234…",
    }
    cred = DelegatedCredential.model_validate(legacy)

    assert cred.id == "" and cred.expires_at is None and cred.issuer_user_id == ""
    assert cred.is_expired() is True, "a credential whose expiry did not decode must fail closed"
