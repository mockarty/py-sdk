"""Canonical Cloud Space SDK parity tests."""

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient


@respx.mock
def test_cloud_spaces_routes_and_preconditions(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/cloud/spaces"
    respx.get(base, params={"cursor": "next", "limit": 25}).mock(
        return_value=httpx.Response(200, json={"items": [{"id": "s1", "revision": 7}]})
    )
    get_space = respx.get(f"{base}/s1").mock(
        return_value=httpx.Response(200, json={"space": {"id": "s1", "revision": 7}})
    )
    members = respx.get(f"{base}/s1/members", params={"cursor": "members-next", "limit": 25}).mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    invites = respx.get(f"{base}/s1/invites", params={"cursor": "invites-next", "limit": 25}).mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    preview = respx.get("http://localhost:5770/api/v1/cloud/invites/token%2Fone").mock(
        return_value=httpx.Response(200, json={"etag": '"space-s1-r7"', "invite": {"workspace_id": "s1"}})
    )
    create = respx.post(f"{base}/s1/invites").mock(
        return_value=httpx.Response(201, json={"status": "created", "revision": 8})
    )
    revoke = respx.delete(f"{base}/s1/invites/i1").mock(
        return_value=httpx.Response(200, json={"status": "revoked", "revision": 8})
    )
    accept = respx.post("http://localhost:5770/api/v1/cloud/invites/token%2Fone/accept").mock(
        return_value=httpx.Response(200, json={"status": "accepted", "revision": 8})
    )
    role = respx.patch(f"{base}/s1/members/u1").mock(
        return_value=httpx.Response(200, json={"status": "updated", "revision": 8})
    )
    remove = respx.delete(f"{base}/s1/members/u1").mock(
        return_value=httpx.Response(200, json={"status": "removed", "revision": 8})
    )

    assert client.cloud_spaces.list("next", 25)["items"][0]["id"] == "s1"
    assert client.cloud_spaces.get("s1")["space"]["revision"] == 7
    client.cloud_spaces.list_members("s1", "members-next", 25)
    client.cloud_spaces.list_invites("s1", "invites-next", 25)
    assert client.cloud_spaces.preview_invite("token/one")["etag"] == '"space-s1-r7"'
    client.cloud_spaces.create_invite("s1", "new@example.test", "viewer", '"space-s1-r7"', "retry-1")
    client.cloud_spaces.revoke_invite("s1", "i1", '"space-s1-r7"', "retry-1")
    client.cloud_spaces.accept_invite("token/one", '"space-s1-r7"', "retry-1")
    client.cloud_spaces.update_member_role("s1", "u1", "editor", '"space-s1-r7"', "retry-1")
    client.cloud_spaces.remove_member("s1", "u1", '"space-s1-r7"', "retry-1")
    assert get_space.called and members.called and invites.called and preview.called
    for route in (create, revoke, accept, role, remove):
        assert route.calls.last.request.headers["Idempotency-Key"] == "retry-1"
        assert route.calls.last.request.headers["If-Match"] == '"space-s1-r7"'


def test_cloud_spaces_mutation_requires_explicit_revision_and_key(client: MockartyClient) -> None:
    try:
        client.cloud_spaces.remove_member("s1", "u1", "", "")
    except ValueError as exc:
        assert "etag" in str(exc).lower()
    else:
        raise AssertionError("mutation without ETag/key was accepted")


@respx.mock
def test_cloud_spaces_non_positive_limit_uses_server_default(client: MockartyClient) -> None:
    spaces = respx.get("http://localhost:5770/api/v1/cloud/spaces").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    members = respx.get("http://localhost:5770/api/v1/cloud/spaces/s1/members", params={"cursor": "next"}).mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    client.cloud_spaces.list(limit=0)
    client.cloud_spaces.list_members("s1", "next", -1)
    assert spaces.called and members.called
    assert spaces.calls.last.request.url.query == b""
    assert members.calls.last.request.url.query == b"cursor=next"


@pytest.mark.asyncio
@respx.mock
async def test_async_cloud_spaces_exact_surface(base_url: str, api_key: str) -> None:
    base = f"{base_url}/api/v1/cloud/spaces"
    respx.get(base).mock(return_value=httpx.Response(200, json={"items": []}))
    respx.get(f"{base}/s1").mock(return_value=httpx.Response(200, json={"space": {"id": "s1"}}))
    respx.get(f"{base}/s1/members").mock(return_value=httpx.Response(200, json={"items": []}))
    respx.get(f"{base}/s1/invites").mock(return_value=httpx.Response(200, json={"items": []}))
    preview = respx.get(f"{base_url}/api/v1/cloud/invites/token%2Fone").mock(
        return_value=httpx.Response(200, json={"etag": '"space-s1-r7"', "invite": {"workspace_id": "s1"}})
    )
    mutation_routes = [
        respx.post(f"{base}/s1/invites"),
        respx.delete(f"{base}/s1/invites/i1"),
        respx.post(f"{base_url}/api/v1/cloud/invites/token%2Fone/accept"),
        respx.patch(f"{base}/s1/members/u1"),
        respx.delete(f"{base}/s1/members/u1"),
    ]
    for route in mutation_routes:
        route.mock(return_value=httpx.Response(200, json={"status": "ok", "revision": 8}))

    async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
        await client.cloud_spaces.list()
        await client.cloud_spaces.get("s1")
        await client.cloud_spaces.list_members("s1")
        await client.cloud_spaces.list_invites("s1")
        assert (await client.cloud_spaces.preview_invite("token/one"))["etag"] == '"space-s1-r7"'
        await client.cloud_spaces.create_invite("s1", "new@example.test", "viewer", '"space-s1-r7"', "async-1")
        await client.cloud_spaces.revoke_invite("s1", "i1", '"space-s1-r7"', "async-1")
        await client.cloud_spaces.accept_invite("token/one", '"space-s1-r7"', "async-1")
        await client.cloud_spaces.update_member_role("s1", "u1", "editor", '"space-s1-r7"', "async-1")
        await client.cloud_spaces.remove_member("s1", "u1", '"space-s1-r7"', "async-1")

    for route in mutation_routes:
        assert route.calls.last.request.headers["If-Match"] == '"space-s1-r7"'
        assert route.calls.last.request.headers["Idempotency-Key"] == "async-1"
    assert preview.called
