# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for MockAPI against a running admin.

The other mock tests (test_api_mocks.py) use respx with hand-written expected
responses — they verify the SDK's own decoding, not that it matches the real
admin's wire shape. This test exercises the full create -> get -> resolve ->
list -> delete round-trip against a live server, so a drift between the Python
SDK and the admin's actual JSON (the parity hole) fails here.

Gated by ``MOCKARTY_LIVE_TOKEN`` (same convention as test_flow_runs_live.py);
skipped otherwise so the offline suite stays self-contained.
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_mocks_crud_and_resolve_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    mock_id = f"py-sdk-live-{int(time.time() * 1000)}"
    route = f"/pysdk/live/{mock_id}"
    payload = {"ok": True, "id": mock_id}
    spec = {
        "id": mock_id,
        "http": {"route": route, "httpMethod": "GET"},
        "response": {"statusCode": 200, "payload": payload},
    }

    # create -> SaveMockResponse{id, mock, isNew}
    try:
        created = client.mocks.create(spec)
    except Exception as exc:  # license/quota gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"mock feature unavailable (license/quota): {exc}")
        raise
    assert created.id == mock_id, f"create returned id={created.id!r}, want {mock_id!r}"

    try:
        # get -> Mock with the same id + route (wire shape decodes cleanly)
        got = client.mocks.get(mock_id)
        assert got.id == mock_id
        assert got.http is not None and got.http.route == route, (
            f"get returned http={got.http!r}, want route={route!r}"
        )

        # resolve through the actual stub engine — the mock really serves
        resolved = httpx.get(f"{LIVE_URL}/stubs/sandbox{route}", timeout=10.0)
        assert resolved.status_code == 200, f"stub resolve: {resolved.status_code} {resolved.text}"
        assert resolved.json() == payload, f"stub body {resolved.json()!r} != {payload!r}"

        # list (active default) includes the new mock
        page = client.mocks.list(namespace="sandbox", search=mock_id, limit=50)
        assert any(m.id == mock_id for m in page.items), (
            f"list(search={mock_id!r}) did not include the mock (total={page.total}, "
            f"got={[m.id for m in page.items]})"
        )
    finally:
        # delete always runs so a failed assertion doesn't leak the mock
        client.mocks.delete(mock_id)

    # after delete, the stub no longer resolves
    gone = httpx.get(f"{LIVE_URL}/stubs/sandbox{route}", timeout=10.0)
    assert gone.status_code == 404, f"after delete, stub should 404, got {gone.status_code}"
