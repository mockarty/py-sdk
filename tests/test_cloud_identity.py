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


def test_cloud_identity_email_change_requires_two_proofs() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer cloud-session"
        seen.append(f"{request.method} {request.url.path}")
        if request.method == "PATCH":
            assert b'"new_email":"new@example.test"' in request.read()
            return httpx.Response(202, json={"status": "verification_pending", "stage": "awaiting_current_email"})
        if request.method == "POST":
            assert b'"token":"proof"' in request.read()
            return httpx.Response(200, json={"status": "verification_pending", "stage": "awaiting_new_email"})
        return httpx.Response(200, json={"status": "cancelled"})

    with MockartyClient(base_url="https://cloud.example", api_key="cloud-session") as client:
        client._http._transport = httpx.MockTransport(handler)
        assert client.cloud_identity.request_email_change("new@example.test")["stage"] == "awaiting_current_email"
        client.cloud_identity.authorize_current_email("proof")
        client.cloud_identity.confirm_new_email("proof")
        client.cloud_identity.cancel_email_change()
    assert seen == ["PATCH /api/v1/cloud/email", "POST /api/v1/cloud/auth/email/change/authorize",
                    "POST /api/v1/cloud/auth/email/change/confirm", "DELETE /api/v1/cloud/email/pending"]
