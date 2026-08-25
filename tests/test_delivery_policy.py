import httpx
import respx

from mockarty import MockartyClient


@respx.mock
def test_delivery_policy_environment_mutations_forward_preconditions(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/admin/delivery-policy/environments"
    create = respx.post(base).mock(return_value=httpx.Response(201, json={"id": "staging", "etag": '"dp-env:staging:1:a"'}))
    advance = respx.put(f"{base}/staging").mock(return_value=httpx.Response(200, json={"id": "staging", "etag": '"dp-env:staging:2:b"'}))
    revoke = respx.delete(f"{base}/staging").mock(return_value=httpx.Response(204))
    body = {"id": "staging", "projectId": "project-a", "class": "staging", "profile": "standard", "auditId": "audit-a", "evidenceId": "evidence-a"}

    created = client.delivery_policy.create(body, "create-a")
    assert created["id"] == "staging"
    assert create.calls.last.request.headers["Idempotency-Key"] == "create-a"
    assert create.calls.last.request.url.params["namespace"] == "test-ns"
    body.pop("id")
    client.delivery_policy.advance("staging", body, '"dp-env:staging:1:a"', "advance-a")
    assert advance.calls.last.request.headers["If-Match"] == '"dp-env:staging:1:a"'
    assert advance.calls.last.request.headers["Idempotency-Key"] == "advance-a"
    assert advance.calls.last.request.url.params["namespace"] == "test-ns"
    client.delivery_policy.revoke("staging", '"dp-env:staging:2:b"')
    assert revoke.calls.last.request.headers["If-Match"] == '"dp-env:staging:2:b"'
    assert revoke.calls.last.request.url.params["namespace"] == "test-ns"
