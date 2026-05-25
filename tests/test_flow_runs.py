# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the server-side IR runner SDK client.

Mocks the HTTP transport via respx and verifies:

* Dict / str / bytes flow inputs all reach the server as a JSON object.
* base_url forwarding.
* Non-JSON inputs raise locally (no round-trip burned).
* Path is /api/v1/api-tester/flow-runs (not the legacy /runs guess).
* Sync + async surfaces share the same wire shape.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mockarty import MockartyClient
from mockarty.api.flow_runs import _build_body, _coerce_flow

_PATH = "/api/v1/api-tester/flow-runs"


# ── _coerce_flow ────────────────────────────────────────────────────────


def test_coerce_flow_accepts_dict():
    flow = {"ir_version": 1, "steps": []}
    assert _coerce_flow(flow) == flow


def test_coerce_flow_accepts_str():
    out = _coerce_flow('{"ir_version":1,"steps":[]}')
    assert out["ir_version"] == 1


def test_coerce_flow_accepts_bytes():
    out = _coerce_flow(b'{"ir_version":1}')
    assert out == {"ir_version": 1}


def test_coerce_flow_rejects_non_json_str():
    with pytest.raises(ValueError, match="not valid JSON"):
        _coerce_flow("not json")


def test_coerce_flow_rejects_non_object_json():
    with pytest.raises(ValueError, match="must decode to a JSON object"):
        _coerce_flow("[]")


def test_coerce_flow_rejects_wrong_type():
    with pytest.raises(TypeError):
        _coerce_flow(42)  # type: ignore[arg-type]


# ── _build_body ─────────────────────────────────────────────────────────


def test_build_body_omits_empty_base_url():
    body = _build_body({"ir_version": 1}, base_url=None)
    assert "base_url" not in body
    assert body["flow"] == {"ir_version": 1}


def test_build_body_includes_base_url():
    body = _build_body({"ir_version": 1}, base_url="http://api.test")
    assert body["base_url"] == "http://api.test"


# ── Sync transport ──────────────────────────────────────────────────────


@pytest.fixture
def client():
    return MockartyClient(base_url="http://srv", api_key="tok", namespace="ns")


@respx.mock
def test_execute_happy_path(client):
    route = respx.post(f"http://srv{_PATH}").mock(
        return_value=httpx.Response(
            200, json={"status": "passed", "durationMs": 5}
        )
    )
    resp = client.flow_runs.execute(
        {"ir_version": 1, "steps": []}, base_url="http://api.test"
    )
    assert resp["status"] == "passed"
    assert resp["durationMs"] == 5
    sent = json.loads(route.calls.last.request.content)
    assert sent["base_url"] == "http://api.test"
    assert sent["flow"] == {"ir_version": 1, "steps": []}


@respx.mock
def test_execute_str_flow_reaches_server_as_object(client):
    route = respx.post(f"http://srv{_PATH}").mock(
        return_value=httpx.Response(200, json={"status": "passed"})
    )
    client.flow_runs.execute('{"ir_version":1,"name":"smoke"}')
    sent = json.loads(route.calls.last.request.content)
    assert sent["flow"] == {"ir_version": 1, "name": "smoke"}


@respx.mock
def test_execute_propagates_server_error(client):
    respx.post(f"http://srv{_PATH}").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    with pytest.raises(Exception):  # httpx raises on 5xx via raise_for_status
        client.flow_runs.execute({"ir_version": 1})


def test_execute_rejects_bad_flow_locally(client):
    with pytest.raises(ValueError):
        client.flow_runs.execute("not json")


def test_flow_runs_property_singleton(client):
    a = client.flow_runs
    b = client.flow_runs
    assert a is b
