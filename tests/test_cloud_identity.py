from __future__ import annotations

import httpx

from mockarty.client import MockartyClient


def test_cloud_identity_step_up_cookie_and_unlink() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer cloud-session"
        seen.append(request.url.path)
        if request.url.path.endswith("/step-up"):
            assert request.read().find(b'"force_credential":true') >= 0
            return httpx.Response(200, json={"status": "verified", "action": "oauth_identity_unlink"},
                                  headers={"set-cookie": "mockarty_cloud_step_up=proof; Path=/api/v1/cloud; HttpOnly"})
        assert request.headers["Idempotency-Key"] == "unlink-1"
        assert "mockarty_cloud_step_up=proof" in request.headers.get("cookie", "")
        return httpx.Response(204)

    with MockartyClient(base_url="https://cloud.example", api_key="cloud-session") as client:
        client._http._transport = httpx.MockTransport(handler)
        client.cloud_identity.step_up("oauth_identity_unlink", credential="current", force_credential=True)
        client.cloud_identity.unlink("github", idempotency_key="unlink-1")
        assert client.cloud_identity.link_url("github").endswith("/api/v1/cloud/auth/oauth/github/link")
    assert len(seen) == 2
