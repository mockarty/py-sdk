# Copyright (c) 2026 Mockarty. All rights reserved.

"""Offline mapping tests for the pact -> Mockarty contract import bridge.

These assert the deterministic pact-file -> wire-payload mapping
(``_build_pact_import``) without touching a server: version derivation,
consumer/provider validation, and file vs inline vs dict inputs. A live
smoke test lives in test_contracts_import_pact_live.py (gated).
"""

from __future__ import annotations

import json

import pytest

from mockarty.api.contracts import _build_pact_import

SAMPLE_PACT_V3 = {
    "consumer": {"name": "WebApp"},
    "provider": {"name": "UserService"},
    "interactions": [
        {
            "description": "a request for user 1",
            "request": {"method": "GET", "path": "/users/1"},
            "response": {"status": 200, "body": {"id": 1, "name": "Ada"}},
        }
    ],
    "metadata": {"pactSpecification": {"version": "3.0.0"}},
}


def test_version_derived_from_metadata():
    body, version = _build_pact_import(SAMPLE_PACT_V3, None)
    assert version == "3.0.0"
    assert body["version"] == "3.0.0"
    # pactContent is forwarded verbatim as JSON the server will re-parse.
    assert json.loads(body["pactContent"])["consumer"]["name"] == "WebApp"


def test_explicit_version_overrides_metadata():
    body, version = _build_pact_import(SAMPLE_PACT_V3, "git-sha-abc")
    assert version == "git-sha-abc"
    assert body["version"] == "git-sha-abc"


def test_accepts_inline_json_string():
    body, version = _build_pact_import(json.dumps(SAMPLE_PACT_V3), None)
    assert version == "3.0.0"
    assert json.loads(body["pactContent"])["provider"]["name"] == "UserService"


def test_accepts_file_path(tmp_path):
    p = tmp_path / "webapp-userservice.json"
    p.write_text(json.dumps(SAMPLE_PACT_V3), encoding="utf-8")
    body, version = _build_pact_import(str(p), None)
    assert version == "3.0.0"
    assert json.loads(body["pactContent"])["consumer"]["name"] == "WebApp"


def test_v4_pact_version():
    v4 = {
        "consumer": {"name": "C"},
        "provider": {"name": "P"},
        "interactions": [
            {
                "type": "Synchronous/HTTP",
                "description": "d",
                "request": {"method": "GET", "path": "/"},
                "response": {"status": 200},
            }
        ],
        "metadata": {"pactSpecification": {"version": "4.0"}},
    }
    _, version = _build_pact_import(v4, None)
    assert version == "4.0"


def test_no_version_omits_field():
    pact = {"consumer": {"name": "C"}, "provider": {"name": "P"}}
    body, version = _build_pact_import(pact, None)
    assert version is None
    assert "version" not in body


def test_missing_consumer_rejected():
    with pytest.raises(ValueError, match="consumer name is required"):
        _build_pact_import({"provider": {"name": "P"}}, None)


def test_missing_provider_rejected():
    with pytest.raises(ValueError, match="provider name is required"):
        _build_pact_import({"consumer": {"name": "C"}}, None)


def test_malformed_inline_json_rejected():
    with pytest.raises(ValueError, match="not valid pact JSON"):
        _build_pact_import("{not json", None)


def test_non_object_pact_rejected():
    with pytest.raises(ValueError, match="must be a JSON object"):
        _build_pact_import("[1, 2, 3]", None)
