"""Existing AddComment delivery contract; controlled HTTP boundaries, no live mutations."""
import asyncio
import json
import sys

import httpx
import pytest
import respx
from mockarty import MockartyClient, AsyncMockartyClient
from mockarty.errors import MockartyAPIError, MockartyConnectionError

BASE = "http://127.0.0.1:5770"
PATH = "/api/v1/namespaces/sandbox/issuetracker/issues/issue/comments"
OPERATION = "33333333-3333-4333-8333-333333333333"
CAPTURE = "44444444-4444-4444-8444-444444444444"
UNKNOWN = {"error": "collaboration_capture_outcome_unknown", "state": "unknown", "operation_id": OPERATION, "capture_id": CAPTURE}

@pytest.mark.parametrize("status", [201, 202])
def test_comment_delivery_legacy_and_pending(status):
    body = {"id": "native-comment", "body": "Owned body"} if status == 201 else {"state": "pending", "operation_id": OPERATION, "capture_id": CAPTURE}
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=2) as client:
        route = router.post(PATH).mock(return_value=httpx.Response(status, json=body))
        assert client.issue_tracker.add_comment("issue", "Owned body") == body
        assert route.call_count == 1

def test_comment_delivery_unknown_preserves_handles_without_retry():
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=2) as client:
        route = router.post(PATH).mock(return_value=httpx.Response(503, json=UNKNOWN))
        with pytest.raises(MockartyAPIError) as failure:
            client.issue_tracker.add_comment("issue", "Owned body")
        assert route.call_count == 1
        assert getattr(failure.value, "operation_id", None) == OPERATION, "unknown comment error discarded capture handles"
        assert getattr(failure.value, "capture_id", None) == CAPTURE
        assert getattr(failure.value, "state", None) == "unknown"

async def _async_unknown_preserves_handles_without_retry():
    with respx.mock(base_url=BASE) as router:
        route = router.post(PATH).mock(return_value=httpx.Response(503, json=UNKNOWN))
        async with AsyncMockartyClient(BASE, namespace="sandbox", max_retries=2) as client:
            with pytest.raises(MockartyAPIError) as failure:
                await client.issue_tracker.add_comment("issue", "Owned body")
        assert route.call_count == 1
        assert getattr(failure.value, "operation_id", None) == OPERATION, "async unknown comment error discarded capture handles"
        assert getattr(failure.value, "capture_id", None) == CAPTURE
        assert getattr(failure.value, "state", None) == "unknown"

def test_comment_delivery_async_unknown_preserves_handles_without_retry():
    asyncio.run(_async_unknown_preserves_handles_without_retry())

def test_comment_delivery_lost_response_is_not_automatically_replayed():
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=2) as client:
        route = router.post(PATH).mock(side_effect=httpx.ReadError("response lost"))
        with pytest.raises(MockartyConnectionError):
            client.issue_tracker.add_comment("issue", "Owned body")
        assert route.call_count == 1

@pytest.mark.parametrize("patch", [{"operation_id": 42}, {"operation_id": " "}, {"capture_id": "x" * 257}, {"capture_id": "44444444-4444-4444-8444-44444444444A"}, {"state": "pending"}, {"error": "transient"}, {"actor_id": "other"}, {"extra": True}, {"code": "conflict"}])
def test_comment_delivery_invalid_unknown_has_no_partial_metadata(patch):
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
        router.post(PATH).mock(return_value=httpx.Response(503, json={**UNKNOWN, **patch}))
        with pytest.raises(MockartyAPIError) as failure:
            client.issue_tracker.add_comment("issue", "Owned body")
        assert getattr(failure.value, "operation_id", None) is None
        assert getattr(failure.value, "capture_id", None) is None
        assert getattr(failure.value, "state", None) is None

def test_comment_delivery_duplicate_unknown_metadata_has_no_partial_handles():
    raw = json.dumps(UNKNOWN)[:-1] + ',"state":"unknown"}'
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
        router.post(PATH).mock(return_value=httpx.Response(503, text=raw))
        with pytest.raises(MockartyAPIError) as failure:
            client.issue_tracker.add_comment("issue", "Owned body")
        assert failure.value.operation_id is None
        assert failure.value.capture_id is None
        assert failure.value.state is None

@pytest.mark.parametrize("code", ["", "unavailable"])
def test_comment_delivery_optional_unavailable_code_preserves_handles(code):
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
        router.post(PATH).mock(return_value=httpx.Response(503, json={**UNKNOWN, "code": code}))
        with pytest.raises(MockartyAPIError) as failure:
            client.issue_tracker.add_comment("issue", "Owned body")
        assert failure.value.operation_id == OPERATION
        assert failure.value.capture_id == CAPTURE
        assert failure.value.state == "unknown"

@pytest.mark.parametrize("status,body", [(500, UNKNOWN), (400, UNKNOWN), (503, {"error": "collaboration_capture_outcome_unknown"})])
def test_comment_delivery_other_error_shapes_have_no_handles(status, body):
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
        router.post(PATH).mock(return_value=httpx.Response(status, json=body))
        with pytest.raises(MockartyAPIError) as failure:
            client.issue_tracker.add_comment("issue", "Owned body")
        assert failure.value.operation_id is None
        assert failure.value.capture_id is None
        assert failure.value.state is None

@pytest.mark.parametrize("size", [2048, 2049])
def test_comment_delivery_unknown_envelope_byte_boundary(size):
    raw = json.dumps(UNKNOWN).encode()
    raw += b' ' * (size - len(raw))
    assert len(raw) == size
    with respx.mock(base_url=BASE) as router, MockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
        router.post(PATH).mock(return_value=httpx.Response(503, content=raw))
        with pytest.raises(MockartyAPIError) as failure:
            client.issue_tracker.add_comment("issue", "Owned body")
        assert failure.value.operation_id == (OPERATION if size == 2048 else None)
        assert failure.value.capture_id == (CAPTURE if size == 2048 else None)
        assert failure.value.state == ("unknown" if size == 2048 else None)

@pytest.mark.parametrize("asynchronous", [False, True])
def test_comment_delivery_nested_error_respects_stdlib_fallback_runtime_budget(monkeypatch, asynchronous):
    # Current CPython3.14's C scanner accepts this depth. Exercise the actual
    # stdlib Python scanner (used without the accelerator), with a scoped
    # recursion budget; do not inject a synthetic parser exception.
    raw = b'[' * 1000 + b'0' + b']' * 1000
    assert len(raw) == 2001
    prior_limit = sys.getrecursionlimit()
    monkeypatch.setattr(json.scanner, "make_scanner", json.scanner.py_make_scanner)
    try:
        sys.setrecursionlimit(256)
        with pytest.raises(RecursionError):
            json.loads(raw, object_pairs_hook=dict)
        with respx.mock(base_url=BASE) as router:
            route = router.post(PATH).mock(return_value=httpx.Response(503, content=raw))
            with pytest.raises(MockartyAPIError) as failure:
                if asynchronous:
                    async def send():
                        async with AsyncMockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
                            await client.issue_tracker.add_comment("issue", "Owned body")
                    asyncio.run(send())
                else:
                    with MockartyClient(BASE, namespace="sandbox", max_retries=0) as client:
                        client.issue_tracker.add_comment("issue", "Owned body")
            assert failure.value.status_code == 503
            assert failure.value.operation_id is None
            assert failure.value.capture_id is None
            assert failure.value.state is None
            assert route.call_count == 1
    finally:
        sys.setrecursionlimit(prior_limit)
