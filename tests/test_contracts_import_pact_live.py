# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live smoke test for the pact -> Mockarty contract import bridge.

Imports a small pact through the SDK and asserts a contract is created,
then cleans it up. Gated by MOCKARTY_LIVE_TOKEN (same convention as the
other *_live.py tests); skips offline.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from mockarty import MockartyClient

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_import_pact_live(tmp_path):
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    consumer = f"PyConsumer{int(time.time() * 1000)}"
    pact = {
        "consumer": {"name": consumer},
        "provider": {"name": "PyProvider"},
        "interactions": [
            {
                "description": "smoke",
                "request": {"method": "GET", "path": "/ping"},
                "response": {"status": 200, "body": {"ok": True}},
            }
        ],
        "metadata": {"pactSpecification": {"version": "3.0.0"}},
    }
    pact_file = tmp_path / "pyconsumer-pyprovider.json"
    pact_file.write_text(json.dumps(pact), encoding="utf-8")

    try:
        result = client.contracts.import_pact(str(pact_file), version="1.0.0-live")
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(
            s in msg
            for s in ("not licensed", "feature_not_licensed", "limit", "trial")
        ):
            pytest.skip(f"contract feature unavailable (license): {exc}")
        raise

    contract_id = result.get("id")
    assert contract_id, f"import_pact returned no id: {result!r}"
    assert result["consumer"]["name"] == consumer
    assert result["provider"]["name"] == "PyProvider"

    try:
        # The imported pact shows up in the namespace's pact list.
        pacts = client.contracts.list_pacts()
        assert any(p.get("id") == contract_id for p in pacts), (
            f"imported pact {contract_id!r} not in list_pacts()"
        )
    finally:
        client.contracts.delete_pact(contract_id)
