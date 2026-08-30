from __future__ import annotations

import httpx
import respx

from mockarty.client import MockartyClient


@respx.mock
def test_cloud_connectors_write_only_secret_lifecycle() -> None:
    route = respx.put("https://cloud.test/api/v1/cloud/operator/connectors/oauth/github").mock(
        return_value=httpx.Response(200, json={"key": "oauth/github", "revision": 2,
                                               "secret_configured": True})
    )
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    response = client.cloud_connectors.update(
        "oauth", "github", config={"client_id": "client"},
        secrets={"client_secret": "write-only"}, expected_revision=1,
        enabled=True, idempotency_key="connector-1",
    )
    request = route.calls.last.request
    assert request.headers["Idempotency-Key"] == "connector-1"
    assert __import__("json").loads(request.content)["secrets"]["client_secret"] == "write-only"
    assert "secrets" not in response


def test_cloud_connectors_reject_unknown_or_incomplete_key() -> None:
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    for key in [("custom", "github", ""), ("oauth", "../github", ""), ("payment", "stripe", "")]:
        try:
            client.cloud_connectors.update(key[0], key[1], slot=key[2], config={},
                                           expected_revision=1, idempotency_key="key")
        except ValueError:
            continue
        raise AssertionError(f"unsafe connector key accepted: {key}")
