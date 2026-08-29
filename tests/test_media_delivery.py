import json

import httpx
import respx

from mockarty import MockartyClient


@respx.mock
def test_media_delivery_queue_and_reconciliation(client: MockartyClient) -> None:
    queue = respx.get("http://localhost:5770/api/v1/transcribe/jobs/fenced").mock(
        return_value=httpx.Response(200, json={"fenced": [], "count": 0})
    )
    reconcile = respx.post("http://localhost:5770/api/v1/tts/jobs/job%2F1/reconcile-delivery").mock(
        return_value=httpx.Response(200, json={"status": "reconciled"})
    )

    assert client.media_delivery.list_fenced("transcribe")["count"] == 0
    client.media_delivery.reconcile("tts", "job/1", "runner-1", "not_started")
    assert queue.calls.last.request.url.params["namespace"] == "test-ns"
    assert reconcile.calls.last.request.url.params["namespace"] == "test-ns"
    assert json.loads(reconcile.calls.last.request.content) == {"runnerId": "runner-1", "outcome": "not_started"}


def test_media_delivery_refuses_guesses(client: MockartyClient) -> None:
    try:
        client.media_delivery.reconcile("tts", "job-1", "runner-1", "maybe")
    except ValueError as exc:
        assert "outcome" in str(exc)
    else:
        raise AssertionError("unknown outcome accepted")
