# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the fluent MockBuilder API."""

from __future__ import annotations

import pytest

from mockarty import AssertAction, MockBuilder
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
from mockarty.models.mock import Callback, ContentResponse, Extract, Mock, OneOf, Proxy


# ── HTTP Builder ──────────────────────────────────────────────────────


class TestHttpBuilder:
    """Test building HTTP mocks."""

    def test_minimal_http_mock(self) -> None:
        mock = MockBuilder.http("/api/test", "GET").build()
        assert mock.http is not None
        assert mock.http.route == "/api/test"
        assert mock.http.http_method == "GET"

    def test_http_with_id_and_namespace(self) -> None:
        mock = (
            MockBuilder.http("/api/users", "POST")
            .id("create-user")
            .namespace("production")
            .build()
        )
        assert mock.id == "create-user"
        assert mock.namespace == "production"

    def test_http_with_tags_and_priority(self) -> None:
        mock = (
            MockBuilder.http("/api/v2/items", "GET")
            .tags("items", "v2", "stable")
            .priority(10)
            .build()
        )
        assert mock.tags == ["items", "v2", "stable"]
        assert mock.priority == 10

    def test_http_with_ttl_and_limiter(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "GET")
            .ttl(3600)
            .use_limiter(100)
            .build()
        )
        assert mock.ttl == 3600
        assert mock.use_limiter == 100

    def test_http_with_body_conditions(self) -> None:
        mock = (
            MockBuilder.http("/api/orders", "POST")
            .condition("$.body.amount", AssertAction.NOT_EMPTY)
            .condition("$.body.currency", AssertAction.EQUALS, "USD")
            .build()
        )
        assert mock.http.conditions is not None
        assert len(mock.http.conditions) == 2
        assert mock.http.conditions[0].path == "$.body.amount"
        assert mock.http.conditions[0].assert_action == AssertAction.NOT_EMPTY
        assert mock.http.conditions[1].value == "USD"

    def test_http_with_header_conditions(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "GET")
            .header_condition("Authorization", AssertAction.NOT_EMPTY)
            .header_condition("Content-Type", AssertAction.CONTAINS, "json")
            .build()
        )
        assert mock.http.headers is not None
        assert len(mock.http.headers) == 2
        assert mock.http.headers[0].path == "Authorization"

    def test_http_with_query_conditions(self) -> None:
        mock = (
            MockBuilder.http("/api/search", "GET")
            .query_condition("q", AssertAction.NOT_EMPTY)
            .query_condition("page", AssertAction.EQUALS, "1")
            .build()
        )
        assert mock.http.query_params is not None
        assert len(mock.http.query_params) == 2

    def test_http_with_response(self) -> None:
        mock = (
            MockBuilder.http("/api/users/:id", "GET")
            .respond(
                200,
                body={"id": "$.pathParam.id", "name": "$.fake.FirstName"},
                headers={"X-Custom": ["value"]},
                delay=500,
            )
            .build()
        )
        assert mock.response is not None
        assert mock.response.status_code == 200
        assert mock.response.payload["name"] == "$.fake.FirstName"
        assert mock.response.headers["X-Custom"] == ["value"]
        assert mock.response.delay == 500

    def test_http_with_error_response(self) -> None:
        mock = (
            MockBuilder.http("/api/fail", "GET")
            .respond(500, error="Internal Server Error")
            .build()
        )
        assert mock.response.status_code == 500
        assert mock.response.error == "Internal Server Error"

    def test_http_respond_zero_delay_excluded(self) -> None:
        """Delay of 0 is not included in response (None instead)."""
        mock = MockBuilder.http("/test", "GET").respond(200, delay=0).build()
        assert mock.response.delay is None

    def test_http_with_template_response(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "GET")
            .respond_with_template(200, "/templates/response.json")
            .build()
        )
        assert mock.response.payload_template_path == "/templates/response.json"

    def test_http_with_proxy(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "GET")
            .proxy_to("https://real-api.example.com")
            .build()
        )
        assert mock.proxy is not None
        assert mock.proxy.target == "https://real-api.example.com"

    def test_http_with_callback(self) -> None:
        mock = (
            MockBuilder.http("/api/orders", "POST")
            .respond(201, body={"status": "created"})
            .callback(
                "https://webhook.example.com",
                method="POST",
                body={"event": "order.created"},
                headers={"X-Secret": "abc"},
                timeout=10,
                retry_count=3,
                retry_delay=5,
                trigger="on_success",
            )
            .build()
        )
        assert mock.callbacks is not None
        assert len(mock.callbacks) == 1
        cb = mock.callbacks[0]
        assert cb.type == "http"
        assert cb.url == "https://webhook.example.com"
        assert cb.retry_count == 3
        assert cb.trigger == "on_success"

    def test_http_with_multiple_callbacks(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "POST")
            .callback("https://hook1.com")
            .callback("https://hook2.com", method="PUT")
            .build()
        )
        assert len(mock.callbacks) == 2

    def test_http_with_extract(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "POST")
            .respond(200)
            .extract(
                g_store={"last_id": "$.req.id"},
                c_store={"step": "processed"},
                m_store={"local": "$.req.data"},
            )
            .build()
        )
        assert mock.extract is not None
        assert mock.extract.g_store["last_id"] == "$.req.id"
        assert mock.extract.c_store["step"] == "processed"
        assert mock.extract.m_store["local"] == "$.req.data"

    def test_http_with_mock_store(self) -> None:
        mock = (
            MockBuilder.http("/api/test", "GET")
            .mock_store({"counter": 0, "flag": True})
            .build()
        )
        assert mock.mock_store == {"counter": 0, "flag": True}

    def test_http_with_chain_id(self) -> None:
        mock = (
            MockBuilder.http("/api/step1", "POST")
            .chain_id("order-flow")
            .build()
        )
        assert mock.chain_id == "order-flow"

    def test_http_with_path_prefix(self) -> None:
        mock = MockBuilder.http("/test", "GET").path_prefix("/v2").build()
        assert mock.path_prefix == "/v2"

    def test_http_with_server_name(self) -> None:
        mock = MockBuilder.http("/test", "GET").server_name("staging").build()
        assert mock.server_name == "staging"

    def test_http_with_folder_id(self) -> None:
        mock = MockBuilder.http("/test", "GET").folder_id("folder-123").build()
        assert mock.folder_id == "folder-123"


# ── OneOf Builder ─────────────────────────────────────────────────────


class TestOneOfBuilder:
    """Test OneOf (multiple response) building."""

    def test_one_of_ordered(self) -> None:
        mock = (
            MockBuilder.http("/api/flaky", "GET")
            .respond_with_one_of("order")
            .add_response(200, body={"status": "ok"})
            .add_response(500, error="server error")
            .add_response(200, body={"status": "recovered"})
            .done()
            .build()
        )
        assert mock.one_of is not None
        assert mock.one_of.order == "order"
        assert len(mock.one_of.responses) == 3
        assert mock.one_of.responses[0].status_code == 200
        assert mock.one_of.responses[1].status_code == 500
        assert mock.one_of.responses[2].payload["status"] == "recovered"

    def test_one_of_random(self) -> None:
        mock = (
            MockBuilder.http("/api/random", "GET")
            .respond_with_one_of("random")
            .add_response(200, body="a")
            .add_response(200, body="b")
            .done()
            .build()
        )
        assert mock.one_of.order == "random"
        assert len(mock.one_of.responses) == 2

    def test_one_of_with_delay(self) -> None:
        mock = (
            MockBuilder.http("/api/slow", "GET")
            .respond_with_one_of()
            .add_response(200, body="fast")
            .add_response(200, body="slow", delay=2000)
            .done()
            .build()
        )
        assert mock.one_of.responses[0].delay is None
        assert mock.one_of.responses[1].delay == 2000


# ── gRPC Builder ──────────────────────────────────────────────────────


class TestGrpcBuilder:
    """Test building gRPC mocks."""

    def test_minimal_grpc(self) -> None:
        mock = MockBuilder.grpc("user.UserService", "GetUser").build()
        assert mock.grpc is not None
        assert mock.grpc.service == "user.UserService"
        assert mock.grpc.method == "GetUser"

    def test_grpc_with_conditions(self) -> None:
        mock = (
            MockBuilder.grpc("svc.Service", "Method")
            .condition("$.id", AssertAction.NOT_EMPTY)
            .build()
        )
        assert len(mock.grpc.conditions) == 1

    def test_grpc_with_meta_conditions(self) -> None:
        mock = (
            MockBuilder.grpc("svc.Service", "Method")
            .meta_condition("auth-token", AssertAction.NOT_EMPTY)
            .header_condition("trace-id", AssertAction.NOT_EMPTY)
            .build()
        )
        # Both meta_condition and header_condition go into grpc.meta
        assert len(mock.grpc.meta) == 2

    def test_grpc_with_response(self) -> None:
        mock = (
            MockBuilder.grpc("user.UserService", "GetUser")
            .id("grpc-user")
            .respond(200, body={"id": "1", "name": "Alice"})
            .build()
        )
        assert mock.response.payload["name"] == "Alice"


# ── MCP Builder ───────────────────────────────────────────────────────


class TestMCPBuilder:
    """Test building MCP mocks."""

    def test_minimal_mcp(self) -> None:
        mock = MockBuilder.mcp("get_weather").build()
        assert mock.mcp is not None
        assert mock.mcp.tool == "get_weather"
        assert mock.mcp.method == "tools/call"

    def test_mcp_with_conditions(self) -> None:
        mock = (
            MockBuilder.mcp("get_weather")
            .condition("$.city", AssertAction.NOT_EMPTY)
            .respond(200, body={"temperature": 22})
            .build()
        )
        assert len(mock.mcp.conditions) == 1
        assert mock.response.payload["temperature"] == 22


# ── SOAP Builder ──────────────────────────────────────────────────────


class TestSOAPBuilder:
    def test_soap_mock(self) -> None:
        mock = (
            MockBuilder.soap("OrderService", "GetOrder")
            .id("soap-order")
            .respond(200, body="<order>...</order>")
            .build()
        )
        assert mock.soap is not None
        assert mock.soap.service == "OrderService"
        assert mock.soap.method == "GetOrder"


# ── GraphQL Builder ───────────────────────────────────────────────────


class TestGraphQLBuilder:
    def test_graphql_mock(self) -> None:
        mock = (
            MockBuilder.graphql("query", "users")
            .id("gql-users")
            .respond(200, body={"data": {"users": []}})
            .build()
        )
        assert mock.graphql is not None
        assert mock.graphql.operation == "query"
        assert mock.graphql.field == "users"


# ── SSE Builder ───────────────────────────────────────────────────────


class TestSSEBuilder:
    def test_sse_mock(self) -> None:
        mock = (
            MockBuilder.sse("/events/notifications", "notification")
            .id("sse-notif")
            .build()
        )
        assert mock.sse is not None
        assert mock.sse.event_path == "/events/notifications"
        assert mock.sse.event_name == "notification"

    def test_sse_header_conditions(self) -> None:
        mock = (
            MockBuilder.sse("/events/test")
            .header_condition("Authorization", AssertAction.NOT_EMPTY)
            .build()
        )
        assert mock.sse.header_conditions is not None
        assert len(mock.sse.header_conditions) == 1


# ── Kafka Builder ─────────────────────────────────────────────────────


class TestKafkaBuilder:
    def test_kafka_mock(self) -> None:
        mock = (
            MockBuilder.kafka("orders-topic")
            .id("kafka-orders")
            .condition("$.orderId", AssertAction.NOT_EMPTY)
            .respond(200, body={"status": "processed"})
            .build()
        )
        assert mock.kafka is not None
        assert mock.kafka.topic == "orders-topic"
        assert len(mock.kafka.conditions) == 1

    def test_kafka_callback(self) -> None:
        mock = (
            MockBuilder.kafka("input-topic")
            .kafka_callback("broker:9092", "output-topic", body={"done": True})
            .build()
        )
        assert len(mock.callbacks) == 1
        assert mock.callbacks[0].type == "kafka"
        assert mock.callbacks[0].kafka_brokers == "broker:9092"


# ── RabbitMQ Builder ──────────────────────────────────────────────────


class TestRabbitMQBuilder:
    def test_rabbitmq_mock(self) -> None:
        mock = (
            MockBuilder.rabbitmq("orders-queue")
            .id("rmq-orders")
            .respond(200, body={"ack": True})
            .build()
        )
        assert mock.rabbitmq is not None
        assert mock.rabbitmq.queue == "orders-queue"

    def test_rabbitmq_callback(self) -> None:
        mock = (
            MockBuilder.rabbitmq("input-q")
            .rabbitmq_callback(
                "amqp://localhost", exchange="out-ex", routing_key="rk",
                body={"msg": "done"},
            )
            .build()
        )
        assert len(mock.callbacks) == 1
        assert mock.callbacks[0].type == "rabbitmq"
        assert mock.callbacks[0].rabbit_url == "amqp://localhost"


# ── Socket Builder ────────────────────────────────────────────────────


class TestSocketBuilder:
    def test_socket_mock(self) -> None:
        mock = (
            MockBuilder.socket("ws-server", "message")
            .id("ws-msg")
            .respond(200, body={"echo": True})
            .build()
        )
        assert mock.socket is not None
        assert mock.socket.server_name == "ws-server"
        assert mock.socket.event == "message"


# ── SMTP Builder ──────────────────────────────────────────────────────


class TestSmtpBuilder:
    def test_smtp_mock(self) -> None:
        mock = (
            MockBuilder.smtp("mail-server")
            .id("smtp-test")
            .header_condition("Subject", AssertAction.CONTAINS, "test")
            .build()
        )
        assert mock.smtp is not None
        assert mock.smtp.server_name == "mail-server"
        assert mock.smtp.header_conditions is not None
        assert len(mock.smtp.header_conditions) == 1


# ── Complex builder ──────────────────────────────────────────────────


class TestComplexBuilder:
    """Test building complex mocks with many features combined."""

    def test_full_featured_mock(self) -> None:
        mock = (
            MockBuilder.http("/api/orders", "POST")
            .id("create-order")
            .namespace("production")
            .chain_id("order-flow")
            .tags("orders", "v2")
            .priority(10)
            .ttl(7200)
            .use_limiter(1000)
            .condition("$.body.amount", AssertAction.NOT_EMPTY)
            .condition("$.body.currency", AssertAction.EQUALS, "USD")
            .header_condition("Authorization", AssertAction.NOT_EMPTY)
            .query_condition("dry_run", AssertAction.EQUALS, "false")
            .respond(
                201,
                body={
                    "orderId": "$.fake.UUID",
                    "amount": "$.req.amount",
                    "status": "created",
                },
                delay=100,
            )
            .callback(
                "https://webhook.example.com/orders",
                method="POST",
                body={"orderId": "$.fake.UUID", "event": "order.created"},
                retry_count=3,
            )
            .extract(
                g_store={"total_orders": "$.increment(total_orders)"},
                c_store={"order_step": "created"},
            )
            .mock_store({"attempt": 0})
            .build()
        )

        assert mock.id == "create-order"
        assert mock.namespace == "production"
        assert mock.chain_id == "order-flow"
        assert mock.tags == ["orders", "v2"]
        assert mock.priority == 10
        assert mock.ttl == 7200
        assert mock.use_limiter == 1000

        # Conditions
        assert len(mock.http.conditions) == 2
        assert len(mock.http.headers) == 1
        assert len(mock.http.query_params) == 1

        # Response
        assert mock.response.status_code == 201
        assert mock.response.delay == 100

        # Callback
        assert len(mock.callbacks) == 1
        assert mock.callbacks[0].retry_count == 3

        # Extract
        assert mock.extract.g_store["total_orders"] == "$.increment(total_orders)"

        # Mock store
        assert mock.mock_store["attempt"] == 0

    def test_serialization_matches_server_format(self) -> None:
        """Verify the builder output serializes to valid server JSON."""
        mock = (
            MockBuilder.http("/api/users/:id", "GET")
            .id("user-get")
            .respond(200, body={"id": "$.pathParam.id", "name": "$.fake.FirstName"})
            .build()
        )

        data = mock.model_dump(by_alias=True, exclude_none=True)

        # Verify camelCase aliases
        assert "http" in data
        assert "httpMethod" in data["http"]
        assert "statusCode" in data["response"]
        # Verify no snake_case keys leaked
        assert "http_method" not in data.get("http", {})
        assert "status_code" not in data.get("response", {})
