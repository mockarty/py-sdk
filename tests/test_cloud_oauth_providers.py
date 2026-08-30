from __future__ import annotations

import httpx
import respx

from mockarty.client import MockartyClient


@respx.mock
def test_cloud_oauth_provider_secret_reference_is_write_only(monkeypatch) -> None:
    route = respx.put("https://cloud.test/api/v1/cloud/operator/oauth/providers/github").mock(
        return_value=httpx.Response(200, json={"provider": "github", "client_id": "client",
                                               "config_revision": 1, "enabled": True,
                                               "secret_configured": True})
    )
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    monkeypatch.setenv("CLOUD_API_PROVIDER_SECRET_OAUTH_GITHUB", "write-only")
    ref = "env://CLOUD_API_PROVIDER_SECRET_OAUTH_GITHUB"
    response = client.cloud_oauth_providers.update("github", client_id="client", client_secret_ref=ref,
                                                    expected_revision=1, enabled=True,
                                                    idempotency_key="oauth-1")
    assert route.calls.last.request.headers["Idempotency-Key"] == "oauth-1"
    payload = __import__("json").loads(route.calls.last.request.content)
    assert payload["client_secret"] == "write-only"
    assert "client_secret_ref" not in payload
    assert "client_secret" not in response
