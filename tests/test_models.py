# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for Pydantic model serialization/deserialization and alias handling."""

from __future__ import annotations

import json
from typing import Any

import pytest

from mockarty.models.condition import AssertAction, Condition
from mockarty.models.contexts import (
    GraphQLRequestContext,
    GrpcRequestContext,
    HttpRequestContext,
    KafkaRequestContext,
    MCPRequestContext,
    RabbitMQRequestContext,
    SmtpRequestContext,
    SoapRequestContext,
    SocketRequestContext,
    SSERequestContext,
)
from mockarty.models.mock import (
    Callback,
    ContentResponse,
    Extract,
    Mock,
    OneOf,
    Proxy,
    SaveMockResponse,
    SOAPFault,
    SSEEvent,
    SSEEventChain,
)
from mockarty.models.common import (
    Collection,
    ErrorResponse,
    HealthResponse,
    MockLogs,
    Page,
    PerfConfig,
    PerfResult,
    PerfTask,
    RequestLog,
    TestRunResult,
)
from mockarty.models.fuzzing import FuzzingConfig, FuzzingResult, QuarantineEntry
from mockarty.models.store import DeleteFromStoreRequest, StoreData, StoreEntry


# ── AssertAction enum ─────────────────────────────────────────────────


class TestAssertAction:
    """Test AssertAction StrEnum values."""

    def test_all_values(self) -> None:
        assert AssertAction.EQUALS == "equals"
        assert AssertAction.CONTAINS == "contains"
        assert AssertAction.NOT_EQUALS == "not_equals"
        assert AssertAction.NOT_CONTAINS == "not_contains"
        assert AssertAction.ANY == "any"
        assert AssertAction.NOT_EMPTY == "notEmpty"
        assert AssertAction.EMPTY == "empty"
        assert AssertAction.MATCHES == "matches"

    def test_from_string(self) -> None:
        assert AssertAction("equals") is AssertAction.EQUALS
        assert AssertAction("notEmpty") is AssertAction.NOT_EMPTY


# ── Condition model ───────────────────────────────────────────────────


class TestCondition:
    """Test Condition model serialization and deserialization."""

    def test_create_with_python_names(self) -> None:
        cond = Condition(
            path="$.body.name",
            assert_action=AssertAction.EQUALS,
            value="John",
        )
        assert cond.path == "$.body.name"
        assert cond.assert_action == AssertAction.EQUALS
        assert cond.value == "John"

    def test_serialize_to_json_aliases(self) -> None:
        cond = Condition(
            path="$.body.name",
            assert_action=AssertAction.EQUALS,
            value="John",
            apply_sort_array=True,
        )
        data = cond.model_dump(by_alias=True, exclude_none=True)
        assert data["assertAction"] == "equals"
        assert data["sortArray"] is True
        assert "apply_sort_array" not in data

    def test_deserialize_from_json_aliases(self) -> None:
        raw = {
            "path": "$.body.id",
            "assertAction": "contains",
            "value": "abc",
            "sortArray": False,
            "valueFromFile": "/tmp/data.json",
        }
        cond = Condition.model_validate(raw)
        assert cond.assert_action == AssertAction.CONTAINS
        assert cond.apply_sort_array is False
        assert cond.value_from_file == "/tmp/data.json"

    def test_roundtrip(self) -> None:
        original = Condition(
            path="$.x",
            assert_action=AssertAction.MATCHES,
            value="^test.*",
            decode="base64",
        )
        serialized = original.model_dump(by_alias=True, exclude_none=True)
        deserialized = Condition.model_validate(serialized)
        assert deserialized.path == original.path
        assert deserialized.assert_action == original.assert_action
        assert deserialized.value == original.value
        assert deserialized.decode == original.decode


# ── Context models ────────────────────────────────────────────────────


class TestHttpRequestContext:
    def test_serialize_aliases(self) -> None:
        ctx = HttpRequestContext(
            route="/api/users/:id",
            http_method="GET",
            apply_sort_array=True,
        )
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["httpMethod"] == "GET"
        assert data["sortArray"] is True
        assert "http_method" not in data

    def test_deserialize_from_server_json(self) -> None:
        raw = {
            "route": "/api/orders",
            "httpMethod": "POST",
            "conditions": [
                {"path": "$.body.amount", "assertAction": "notEmpty"}
            ],
            "queryParams": [
                {"path": "status", "assertAction": "equals", "value": "active"}
            ],
            "header": [
                {"path": "Authorization", "assertAction": "notEmpty"}
            ],
        }
        ctx = HttpRequestContext.model_validate(raw)
        assert ctx.http_method == "POST"
        assert len(ctx.conditions) == 1
        assert ctx.conditions[0].assert_action == AssertAction.NOT_EMPTY
        assert len(ctx.query_params) == 1
        assert len(ctx.headers) == 1


class TestGrpcRequestContext:
    def test_serialize(self) -> None:
        ctx = GrpcRequestContext(
            service="user.UserService",
            method="GetUser",
            method_type="unary",
        )
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["methodType"] == "unary"

    def test_deserialize(self) -> None:
        raw = {"service": "svc", "method": "Method", "methodType": "server-stream"}
        ctx = GrpcRequestContext.model_validate(raw)
        assert ctx.method_type == "server-stream"


class TestMCPRequestContext:
    def test_serialize(self) -> None:
        ctx = MCPRequestContext(tool="get_weather", method="tools/call")
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["tool"] == "get_weather"
        assert data["method"] == "tools/call"


class TestSoapRequestContext:
    def test_roundtrip(self) -> None:
        ctx = SoapRequestContext(service="MyService", method="DoSomething", action="urn:DoSomething")
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        restored = SoapRequestContext.model_validate(data)
        assert restored.service == "MyService"
        assert restored.action == "urn:DoSomething"


class TestGraphQLRequestContext:
    def test_roundtrip(self) -> None:
        ctx = GraphQLRequestContext(operation="query", field="users", type="User")
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        restored = GraphQLRequestContext.model_validate(data)
        assert restored.operation == "query"
        assert restored.type == "User"


class TestSSERequestContext:
    def test_aliases(self) -> None:
        ctx = SSERequestContext(event_path="/events/test", event_name="test")
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["eventPath"] == "/events/test"
        assert data["eventName"] == "test"


class TestKafkaRequestContext:
    def test_output_fields(self) -> None:
        ctx = KafkaRequestContext(
            topic="input-topic",
            output_topic="output-topic",
            output_brokers="broker:9092",
            output_key="my-key",
            output_headers={"trace-id": "abc"},
        )
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["outputTopic"] == "output-topic"
        assert data["outputBrokers"] == "broker:9092"
        assert data["outputHeaders"]["trace-id"] == "abc"


class TestRabbitMQRequestContext:
    def test_output_fields(self) -> None:
        ctx = RabbitMQRequestContext(
            queue="input-q",
            routing_key="rk",
            output_url="amqp://localhost",
            output_exchange="out-ex",
        )
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["routingKey"] == "rk"
        assert data["outputURL"] == "amqp://localhost"
        assert data["outputExchange"] == "out-ex"


class TestSmtpRequestContext:
    def test_aliases(self) -> None:
        ctx = SmtpRequestContext(
            server_name="smtp-server",
            sender_conditions=[Condition(path="from", assert_action=AssertAction.CONTAINS, value="test")],
        )
        data = ctx.model_dump(by_alias=True, exclude_none=True)
        assert data["serverName"] == "smtp-server"
        assert data["senderConditions"][0]["assertAction"] == "contains"


# ── ContentResponse ──────────────────────────────────────────────────


class TestContentResponse:
    def test_serialize(self) -> None:
        resp = ContentResponse(
            status_code=200,
            payload={"id": "123", "name": "test"},
            delay=500,
            headers={"X-Custom": ["val1"]},
        )
        data = resp.model_dump(by_alias=True, exclude_none=True)
        assert data["statusCode"] == 200
        assert data["delay"] == 500
        assert data["payload"]["id"] == "123"

    def test_deserialize_with_sse_chain(self) -> None:
        raw = {
            "statusCode": 200,
            "sseEventChain": {
                "events": [{"eventName": "msg", "data": "hello", "delay": 100}],
                "loop": True,
                "loopDelay": 1000,
            },
        }
        resp = ContentResponse.model_validate(raw)
        assert resp.sse_event_chain is not None
        assert resp.sse_event_chain.loop is True
        assert len(resp.sse_event_chain.events) == 1
        assert resp.sse_event_chain.events[0].event_name == "msg"

    def test_deserialize_with_soap_fault(self) -> None:
        raw = {
            "statusCode": 500,
            "soapFault": {
                "faultCode": "soap:Server",
                "faultString": "Internal error",
                "httpStatus": 500,
            },
        }
        resp = ContentResponse.model_validate(raw)
        assert resp.soap_fault is not None
        assert resp.soap_fault.fault_code == "soap:Server"

    def test_deserialize_with_graphql_errors(self) -> None:
        raw = {
            "statusCode": 200,
            "payload": {"data": {"user": None}},
            "graphqlErrors": [
                {"message": "User not found", "path": ["user"]}
            ],
        }
        resp = ContentResponse.model_validate(raw)
        assert len(resp.graphql_errors) == 1
        assert resp.graphql_errors[0].message == "User not found"

    def test_mcp_is_error_flag(self) -> None:
        raw = {"statusCode": 200, "mcpIsError": True, "error": "tool failed"}
        resp = ContentResponse.model_validate(raw)
        assert resp.mcp_is_error is True


# ── OneOf ─────────────────────────────────────────────────────────────


class TestOneOf:
    def test_serialize(self) -> None:
        one_of = OneOf(
            order="random",
            offset=2,
            responses=[
                ContentResponse(status_code=200, payload="ok"),
                ContentResponse(status_code=500, error="fail"),
            ],
        )
        data = one_of.model_dump(by_alias=True, exclude_none=True)
        assert data["order"] == "random"
        assert data["offset"] == 2
        assert len(data["responses"]) == 2


# ── Callback ──────────────────────────────────────────────────────────


class TestCallback:
    def test_http_callback(self) -> None:
        cb = Callback(
            type="http",
            url="https://example.com/webhook",
            method="POST",
            headers={"X-Key": "val"},
            body={"event": "created"},
            retry_count=3,
            retry_delay=5,
            async_=True,
            trigger="on_success",
        )
        data = cb.model_dump(by_alias=True, exclude_none=True)
        assert data["retryCount"] == 3
        assert data["retryDelay"] == 5
        assert data["async"] is True
        assert data["trigger"] == "on_success"

    def test_kafka_callback(self) -> None:
        cb = Callback(
            type="kafka",
            kafka_brokers="broker:9092",
            kafka_topic="events",
            kafka_key="my-key",
            body={"event": "test"},
        )
        data = cb.model_dump(by_alias=True, exclude_none=True)
        assert data["kafkaBrokers"] == "broker:9092"
        assert data["kafkaTopic"] == "events"

    def test_rabbitmq_callback(self) -> None:
        cb = Callback(
            type="rabbitmq",
            rabbit_url="amqp://localhost",
            rabbit_exchange="my-ex",
            rabbit_routing_key="rk",
            body={"msg": "hello"},
        )
        data = cb.model_dump(by_alias=True, exclude_none=True)
        assert data["rabbitURL"] == "amqp://localhost"
        assert data["rabbitExchange"] == "my-ex"


# ── Mock ──────────────────────────────────────────────────────────────


class TestMock:
    def test_minimal_http_mock(self) -> None:
        mock = Mock(
            id="test-1",
            http=HttpRequestContext(route="/test", http_method="GET"),
            response=ContentResponse(status_code=200, payload="ok"),
        )
        data = mock.model_dump(by_alias=True, exclude_none=True)
        assert data["id"] == "test-1"
        assert data["http"]["route"] == "/test"
        assert data["http"]["httpMethod"] == "GET"
        assert data["response"]["statusCode"] == 200

    def test_full_mock_serialization(self) -> None:
        mock = Mock(
            id="full-mock",
            chain_id="chain-1",
            namespace="production",
            path_prefix="/v2",
            server_name="my-server",
            http=HttpRequestContext(
                route="/api/users",
                http_method="POST",
                conditions=[Condition(path="$.body.name", assert_action=AssertAction.NOT_EMPTY)],
            ),
            response=ContentResponse(
                status_code=201,
                payload={"id": "$.fake.UUID"},
                delay=100,
            ),
            callbacks=[Callback(type="http", url="https://hook.example.com", method="POST")],
            ttl=3600,
            use_limiter=100,
            priority=10,
            tags=["users", "v2"],
            folder_id="folder-abc",
            extract=Extract(
                g_store={"last_user": "$.req.name"},
                c_store={"step": "create"},
            ),
            mock_store={"counter": 0},
        )
        data = mock.model_dump(by_alias=True, exclude_none=True)
        assert data["chainId"] == "chain-1"
        assert data["pathPrefix"] == "/v2"
        assert data["serverName"] == "my-server"
        assert data["useLimiter"] == 100
        assert data["folderId"] == "folder-abc"
        assert data["webhooks"][0]["url"] == "https://hook.example.com"
        assert data["extract"]["gStore"]["last_user"] == "$.req.name"
        assert data["mStore"]["counter"] == 0

    def test_deserialize_from_server_response(self) -> None:
        raw = {
            "id": "server-mock",
            "chainId": "ch-1",
            "namespace": "sandbox",
            "http": {
                "route": "/api/items",
                "httpMethod": "GET",
                "header": [{"path": "Accept", "assertAction": "contains", "value": "json"}],
            },
            "response": {"statusCode": 200, "payload": {"items": []}},
            "webhooks": [{"type": "http", "url": "https://cb.example.com"}],
            "ttl": 1800,
            "useLimiter": 50,
            "useCounter": 10,
            "priority": 5,
            "tags": ["items"],
            "createdAt": 1700000000,
            "lastUse": 1700000100,
        }
        mock = Mock.model_validate(raw)
        assert mock.id == "server-mock"
        assert mock.chain_id == "ch-1"
        assert mock.http.headers[0].assert_action == AssertAction.CONTAINS
        assert mock.use_limiter == 50
        assert mock.use_counter == 10
        assert mock.created_at == 1700000000
        assert mock.callbacks[0].url == "https://cb.example.com"

    def test_grpc_mock(self) -> None:
        mock = Mock(
            id="grpc-1",
            grpc=GrpcRequestContext(
                service="user.UserService",
                method="GetUser",
                method_type="unary",
                meta=[Condition(path="auth-token", assert_action=AssertAction.NOT_EMPTY)],
            ),
            response=ContentResponse(status_code=200, payload={"name": "Alice"}),
        )
        data = mock.model_dump(by_alias=True, exclude_none=True)
        assert data["grpc"]["service"] == "user.UserService"
        assert data["grpc"]["methodType"] == "unary"
        assert data["grpc"]["meta"][0]["assertAction"] == "notEmpty"

    def test_multiple_protocols_not_set(self) -> None:
        """A mock can have only one protocol context."""
        mock = Mock(id="http-only", http=HttpRequestContext(route="/test"))
        assert mock.grpc is None
        assert mock.mcp is None
        assert mock.soap is None


class TestSaveMockResponse:
    def test_deserialize(self) -> None:
        raw = {
            "overwritten": True,
            "mock": {
                "id": "saved-mock",
                "http": {"route": "/api/test", "httpMethod": "GET"},
                "response": {"statusCode": 200},
            },
        }
        result = SaveMockResponse.model_validate(raw)
        assert result.overwritten is True
        assert result.mock.id == "saved-mock"


# ── Common models ─────────────────────────────────────────────────────


class TestHealthResponse:
    def test_deserialize(self) -> None:
        raw = {"status": "ok", "releaseId": "1.2.3", "uptime": "5h30m"}
        health = HealthResponse.model_validate(raw)
        assert health.status == "ok"
        assert health.release_id == "1.2.3"


class TestPage:
    def test_generic_page(self) -> None:
        page = Page[Mock](
            items=[Mock(id="m1"), Mock(id="m2")],
            total=100,
            offset=0,
            limit=50,
        )
        assert len(page.items) == 2
        assert page.total == 100


class TestErrorResponse:
    def test_deserialize(self) -> None:
        resp = ErrorResponse.model_validate({"error": "something went wrong"})
        assert resp.error == "something went wrong"


class TestRequestLog:
    def test_deserialize(self) -> None:
        raw = {
            "id": "log-1",
            "calledAt": "2024-01-01T00:00:00Z",
            "req": {"method": "GET"},
            "response": {"status": 200},
        }
        log = RequestLog.model_validate(raw)
        assert log.id == "log-1"
        assert log.called_at == "2024-01-01T00:00:00Z"


# ── Store models ──────────────────────────────────────────────────────


class TestStoreModels:
    def test_store_entry(self) -> None:
        entry = StoreEntry(key="counter", value=42)
        assert entry.key == "counter"
        assert entry.value == 42

    def test_delete_request(self) -> None:
        req = DeleteFromStoreRequest(keys=["a", "b", "c"])
        data = req.model_dump()
        assert data["keys"] == ["a", "b", "c"]

    def test_store_data(self) -> None:
        sd = StoreData(data={"key1": "val1", "key2": 42})
        assert sd.data["key1"] == "val1"


# ── Extract model ─────────────────────────────────────────────────────


class TestExtract:
    def test_serialize_aliases(self) -> None:
        ext = Extract(
            m_store={"local_val": "$.req.id"},
            c_store={"chain_step": "processed"},
            g_store={"global_count": "$.increment(counter)"},
        )
        data = ext.model_dump(by_alias=True, exclude_none=True)
        assert "mStore" in data
        assert "cStore" in data
        assert "gStore" in data
        assert data["gStore"]["global_count"] == "$.increment(counter)"

    def test_deserialize(self) -> None:
        raw = {"mStore": {"a": "1"}, "cStore": {"b": "2"}, "gStore": {"c": "3"}}
        ext = Extract.model_validate(raw)
        assert ext.m_store["a"] == "1"
        assert ext.c_store["b"] == "2"
        assert ext.g_store["c"] == "3"


# ── JSON roundtrip test (integration) ────────────────────────────────


class TestJSONRoundtrip:
    """Verify that a complex mock survives JSON serialization and deserialization."""

    def test_full_roundtrip(self) -> None:
        original = Mock(
            id="roundtrip-test",
            namespace="sandbox",
            http=HttpRequestContext(
                route="/api/orders/:id",
                http_method="PUT",
                conditions=[
                    Condition(path="$.body.status", assert_action=AssertAction.EQUALS, value="shipped"),
                ],
                query_params=[
                    Condition(path="force", assert_action=AssertAction.EQUALS, value="true"),
                ],
                headers=[
                    Condition(path="X-Trace-Id", assert_action=AssertAction.NOT_EMPTY),
                ],
            ),
            response=ContentResponse(
                status_code=200,
                payload={"id": "$.pathParam.id", "status": "shipped"},
                headers={"X-Updated": ["true"]},
                delay=50,
            ),
            callbacks=[
                Callback(
                    type="http",
                    url="https://webhook.example.com",
                    method="POST",
                    body={"orderId": "$.req.id"},
                    retry_count=2,
                    trigger="on_success",
                ),
            ],
            ttl=7200,
            priority=5,
            tags=["orders", "shipping"],
            extract=Extract(
                g_store={"last_order": "$.req.id"},
                c_store={"order_status": "shipped"},
            ),
        )

        # Serialize to JSON string
        json_str = json.dumps(
            original.model_dump(by_alias=True, exclude_none=True)
        )

        # Deserialize back
        restored = Mock.model_validate(json.loads(json_str))

        assert restored.id == original.id
        assert restored.http.route == original.http.route
        assert restored.http.http_method == original.http.http_method
        assert len(restored.http.conditions) == 1
        assert restored.http.conditions[0].value == "shipped"
        assert len(restored.http.query_params) == 1
        assert len(restored.http.headers) == 1
        assert restored.response.status_code == 200
        assert restored.response.delay == 50
        assert restored.callbacks[0].retry_count == 2
        assert restored.ttl == 7200
        assert restored.priority == 5
        assert restored.tags == ["orders", "shipping"]
        assert restored.extract.g_store["last_order"] == "$.req.id"


class TestQuarantineEntry:
    """Verify QuarantineEntry alias handling and round-trip."""

    def test_from_camel_case(self) -> None:
        entry = QuarantineEntry.model_validate({
            "id": "q-1",
            "fingerprint": "injection|POST /api/users|<script>",
            "category": "injection",
            "endpointPattern": "POST /api/users",
            "title": "XSS false positive",
            "reason": "Sanitized by middleware",
            "createdAt": "2023-11-14T22:13:20Z",
        })
        assert entry.id == "q-1"
        assert entry.endpoint_pattern == "POST /api/users"
        assert entry.created_at == "2023-11-14T22:13:20Z"

    def test_from_snake_case(self) -> None:
        entry = QuarantineEntry(
            id="q-2",
            fingerprint="sqli|GET /search|1=1",
            endpoint_pattern="GET /search",
            reason="Safe",
        )
        assert entry.endpoint_pattern == "GET /search"

    def test_serialize_to_alias(self) -> None:
        entry = QuarantineEntry(
            id="q-3",
            endpoint_pattern="POST /api",
            created_at="2023-11-14T22:13:20Z",
        )
        dumped = entry.model_dump(by_alias=True, exclude_none=True)
        assert "endpointPattern" in dumped
        assert "createdAt" in dumped
        assert dumped["endpointPattern"] == "POST /api"

    def test_roundtrip(self) -> None:
        original = QuarantineEntry(
            id="q-rt",
            fingerprint="xss|POST /|<img>",
            category="xss",
            endpoint_pattern="POST /",
            title="Known FP",
            reason="Sanitized",
            created_at="2023-11-14T22:13:20Z",
        )
        json_str = json.dumps(original.model_dump(by_alias=True, exclude_none=True))
        restored = QuarantineEntry.model_validate(json.loads(json_str))
        assert restored.id == original.id
        assert restored.fingerprint == original.fingerprint
        assert restored.endpoint_pattern == original.endpoint_pattern
        assert restored.created_at == original.created_at


class TestFuzzingModels:
    """Verify FuzzingConfig and FuzzingResult alias handling."""

    def test_config_from_camel_case(self) -> None:
        config = FuzzingConfig.model_validate({
            "id": "cfg-1",
            "targetBaseUrl": "http://localhost:8080",
            "strategy": "smart",
        })
        assert config.target_base_url == "http://localhost:8080"
        assert config.strategy == "smart"

    def test_result_from_camel_case(self) -> None:
        result = FuzzingResult.model_validate({
            "id": "res-1",
            "configId": "cfg-1",
            "startedAt": "2023-11-14T22:13:20Z",
            "completedAt": "2023-11-14T22:18:20Z",
            "totalRequests": 5000,
            "totalFindings": 3,
        })
        assert result.config_id == "cfg-1"
        assert result.started_at == "2023-11-14T22:13:20Z"
        assert result.total_requests == 5000
