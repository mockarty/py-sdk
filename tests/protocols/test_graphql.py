"""Unit tests for mockarty.protocols.graphql.

Network round-trips are stubbed via ``respx`` (already a dev dep)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty.protocols.graphql import GraphQLClient, GraphQLError
from mockarty.protocols.telemetry import AccumulatingRecorder


def _client(rec=None):
    return GraphQLClient("http://test/graphql", recorder=rec)


def test_init_empty_url_rejected():
    with pytest.raises(ValueError):
        GraphQLClient("")


def test_init_empty_query_rejected():
    with _client() as cli:
        with pytest.raises(ValueError):
            cli.execute("")


@respx.mock
def test_execute_records_passed_step():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"user": {"id": "u-1"}}}),
    )
    with _client(rec) as cli:
        resp = cli.execute("query GetUser { user { id } }")
    assert resp.ok
    assert resp.data == {"user": {"id": "u-1"}}
    assert resp.errors == []
    steps = rec.steps()
    assert len(steps) == 1
    assert steps[0]["status"] == "passed"
    assert steps[0]["name"] == "graphql:GetUser"
    assert steps[0]["parameters"]["operation"] == "GetUser"
    assert steps[0]["parameters"]["http_status"] == "200"
    assert steps[0]["parameters"]["error_count"] == "0"


@respx.mock
def test_execute_anonymous_operation_label():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"data": {}}),
    )
    with _client(rec) as cli:
        cli.execute("{ ping }")
    assert rec.steps()[0]["name"] == "graphql:anonymous"


@respx.mock
def test_execute_named_via_operation_name_param():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"data": {}}),
    )
    with _client(rec) as cli:
        cli.execute("query { ping }", operation_name="HealthCheck")
    assert rec.steps()[0]["name"] == "graphql:HealthCheck"


@respx.mock
def test_execute_errors_array_marks_failed():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "bad"}]}),
    )
    with _client(rec) as cli:
        resp = cli.execute("query X { x }")
    assert not resp.ok
    assert resp.errors == [{"message": "bad"}]
    steps = rec.steps()
    assert steps[0]["status"] == "failed"
    assert steps[0]["message"] == "bad"
    assert steps[0]["parameters"]["error_count"] == "1"


@respx.mock
def test_execute_raise_for_errors():
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "bad"}]}),
    )
    with _client() as cli:
        with pytest.raises(GraphQLError) as ei:
            cli.execute("query X { x }", raise_for_errors=True)
    assert ei.value.errors[0]["message"] == "bad"


@respx.mock
def test_execute_http_error_status_marks_failed():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(500, json={"data": None}),
    )
    with _client(rec) as cli:
        resp = cli.execute("query { x }")
    assert resp.status_code == 500
    assert rec.steps()[0]["status"] == "failed"
    assert "HTTP 500" in rec.steps()[0]["message"]


@respx.mock
def test_execute_transport_error_marks_broken():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(side_effect=httpx.ConnectError("boom"))
    with _client(rec) as cli:
        with pytest.raises(httpx.ConnectError):
            cli.execute("query { x }")
    assert rec.steps()[0]["status"] == "broken"
    assert "boom" in rec.steps()[0]["message"]


@respx.mock
def test_execute_json_parse_error_marks_broken():
    """Server returned 200 with a body that is NOT valid JSON.
    Review GAP — the broken classification on parse error was
    untested. Pin it so future refactors don't regress."""
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, content=b"not-json-at-all"),
    )
    with _client(rec) as cli:
        with pytest.raises(Exception):
            cli.execute("query X { x }")
    steps = rec.steps()
    assert steps[0]["status"] == "broken"


@respx.mock
def test_execute_step_keys_monotonic():
    rec = AccumulatingRecorder()
    respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"data": {}}),
    )
    with _client(rec) as cli:
        cli.execute("query Get { x }")
        cli.execute("query Get { x }")
    keys = [s["stepKey"] for s in rec.steps()]
    assert keys == ["graphql:Get#1", "graphql:Get#2"]


@respx.mock
def test_execute_variables_and_extra_headers():
    rec = AccumulatingRecorder()
    route = respx.post("http://test/graphql").mock(
        return_value=httpx.Response(200, json={"data": {}}),
    )
    with _client(rec) as cli:
        cli.execute(
            "query GetUser($id: ID!) { user(id: $id) { name } }",
            variables={"id": "u-1"},
            extra_headers={"Authorization": "Bearer t"},
        )
    sent = route.calls[0].request
    body = sent.read().decode("utf-8")
    # json.dumps default separators emit ', ' and ': ', so the
    # serialized payload looks like '{"variables": {"id": "u-1"}}'.
    # Round-trip through json.loads to assert on structure, not text shape.
    import json as _json
    parsed = _json.loads(body)
    assert parsed["variables"] == {"id": "u-1"}
    assert sent.headers["authorization"] == "Bearer t"
