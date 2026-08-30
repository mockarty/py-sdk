import json

import httpx
import respx

from mockarty import MockartyClient


@respx.mock
def test_effect_reconciliation_list_and_no_effect(client: MockartyClient) -> None:
    queue = respx.get("http://localhost:5770/api/v1/admin/effects/reconciliation").mock(
        return_value=httpx.Response(200, json={"items": [], "nextCursor": "next"})
    )
    reconcile = respx.post("http://localhost:5770/api/v1/admin/effects/reconciliation/reconcile").mock(
        return_value=httpx.Response(200, json={"executionId": "effect-1", "status": "no_effect"})
    )

    assert client.effect_reconciliation.list_queue(effect_family="llm.chat", min_age_seconds=60, limit=25)["nextCursor"] == "next"
    assert client.effect_reconciliation.reconcile_no_effect("effect-1", "invoice-1", "provider_invoice")["status"] == "no_effect"
    assert queue.calls.last.request.url.params["namespace"] == "test-ns"
    assert queue.calls.last.request.url.params["family"] == "llm.chat"
    assert json.loads(reconcile.calls.last.request.content) == {
        "namespace": "test-ns", "executionId": "effect-1", "decision": "no_effect",
        "autoClaim": True, "providerReference": "invoice-1", "evidenceSource": "provider_invoice",
    }
