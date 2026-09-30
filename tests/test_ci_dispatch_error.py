# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

import httpx
import pytest
import respx

from mockarty import AsyncMockartyClient, MockartyClient
from mockarty._base_client import raise_for_status
from mockarty.errors import MockartyAPIError


CASES = [(409, "ci_dispatch_uncertain"), (503, "ci_dispatch_failed")]
URL = "http://127.0.0.1:5770"


def saved_launch_response(status, reason):
    return httpx.Response(status, json={
        "error": "inspect saved launch",
        "code": "conflict" if status == 409 else "unavailable",
        "reason": reason,
        "runId": "saved-run",
        "request_id": "request-1",
    })


@respx.mock
@pytest.mark.parametrize("status,reason", CASES)
def test_saved_launch_error(status, reason):
    route = respx.post(f"{URL}/api/v1/test-plans/plan/run").mock(
        return_value=saved_launch_response(status, reason)
    )
    with MockartyClient(base_url=URL, max_retries=2) as client:
        with pytest.raises(MockartyAPIError) as caught:
            client.test_plans.run("plan")
    error = caught.value
    assert error.reason == reason
    assert error.run_id == "saved-run"
    assert error.request_id == "request-1"
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status,reason", CASES)
async def test_async_saved_launch_error(status, reason):
    route = respx.post(f"{URL}/api/v1/test-plans/plan/run").mock(
        return_value=saved_launch_response(status, reason)
    )
    async with AsyncMockartyClient(base_url=URL, max_retries=2) as client:
        with pytest.raises(MockartyAPIError) as caught:
            await client.test_plans.run("plan")
    assert caught.value.reason == reason
    assert caught.value.run_id == "saved-run"
    assert route.call_count == 1


def test_legacy_constructor_and_malformed_optional_context():
    error = MockartyAPIError(503, "old error", "request-1", "unavailable")
    assert error.reason is None and error.run_id is None
    with pytest.raises(MockartyAPIError) as caught:
        raise_for_status(httpx.Response(503, json={
            "error": "old error", "code": "unavailable", "reason": 23, "runId": {},
        }))
    assert caught.value.message == "old error"
    assert caught.value.code == "unavailable"
    assert caught.value.reason is None and caught.value.run_id is None
