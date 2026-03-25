# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Fluent builder API for constructing Mock objects."""

from __future__ import annotations

from typing import Any

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
)


class OneOfBuilder:
    """Builder for OneOf (multiple response variants)."""

    def __init__(self, parent: MockBuilder, order: str = "order") -> None:
        self._parent = parent
        self._order = order
        self._responses: list[ContentResponse] = []

    def add_response(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: dict[str, list[str]] | None = None,
        delay: int = 0,
        error: str | None = None,
    ) -> OneOfBuilder:
        """Add a response variant to the OneOf list."""
        resp = ContentResponse(
            status_code=status_code,
            payload=body,
            headers=headers,
            delay=delay if delay > 0 else None,
            error=error,
        )
        self._responses.append(resp)
        return self

    def done(self) -> MockBuilder:
        """Finish building OneOf and return to the parent MockBuilder."""
        one_of = OneOf(order=self._order, responses=self._responses)
        self._parent._mock_data["one_of"] = one_of
        return self._parent


class MockBuilder:
    """Fluent API for building Mock objects.

    Usage::

        mock = (
            MockBuilder.http("/api/users/:id", "GET")
            .id("user-get")
            .respond(200, body={"id": "$.pathParam.id"})
            .ttl(3600)
            .build()
        )
    """

    def __init__(self) -> None:
        self._mock_data: dict[str, Any] = {}
        self._conditions: list[Condition] = []
        self._header_conditions: list[Condition] = []
        self._query_conditions: list[Condition] = []
        self._meta_conditions: list[Condition] = []
        self._callbacks: list[Callback] = []
        self._protocol: str | None = None

    # ── Static factory methods ────────────────────────────────────────

    @staticmethod
    def http(route: str, method: str = "GET") -> MockBuilder:
        """Create a builder for an HTTP mock."""
        builder = MockBuilder()
        builder._protocol = "http"
        builder._mock_data["http"] = HttpRequestContext(
            route=route, http_method=method
        )
        return builder

    @staticmethod
    def grpc(service: str, method: str) -> MockBuilder:
        """Create a builder for a gRPC mock."""
        builder = MockBuilder()
        builder._protocol = "grpc"
        builder._mock_data["grpc"] = GrpcRequestContext(
            service=service, method=method
        )
        return builder

    @staticmethod
    def mcp(tool: str) -> MockBuilder:
        """Create a builder for an MCP mock."""
        builder = MockBuilder()
        builder._protocol = "mcp"
        builder._mock_data["mcp"] = MCPRequestContext(
            method="tools/call", tool=tool
        )
        return builder

    @staticmethod
    def soap(service: str, method: str) -> MockBuilder:
        """Create a builder for a SOAP mock."""
        builder = MockBuilder()
        builder._protocol = "soap"
        builder._mock_data["soap"] = SoapRequestContext(
            service=service, method=method
        )
        return builder

    @staticmethod
    def graphql(operation: str, field: str | None = None) -> MockBuilder:
        """Create a builder for a GraphQL mock."""
        builder = MockBuilder()
        builder._protocol = "graphql"
        builder._mock_data["graphql"] = GraphQLRequestContext(
            operation=operation, field=field
        )
        return builder

    @staticmethod
    def sse(event_path: str, event_name: str | None = None) -> MockBuilder:
        """Create a builder for an SSE mock."""
        builder = MockBuilder()
        builder._protocol = "sse"
        builder._mock_data["sse"] = SSERequestContext(
            event_path=event_path, event_name=event_name
        )
        return builder

    @staticmethod
    def kafka(topic: str) -> MockBuilder:
        """Create a builder for a Kafka mock."""
        builder = MockBuilder()
        builder._protocol = "kafka"
        builder._mock_data["kafka"] = KafkaRequestContext(topic=topic)
        return builder

    @staticmethod
    def rabbitmq(queue: str) -> MockBuilder:
        """Create a builder for a RabbitMQ mock."""
        builder = MockBuilder()
        builder._protocol = "rabbitmq"
        builder._mock_data["rabbitmq"] = RabbitMQRequestContext(queue=queue)
        return builder

    @staticmethod
    def socket(server_name: str, event: str | None = None) -> MockBuilder:
        """Create a builder for a WebSocket/Socket mock."""
        builder = MockBuilder()
        builder._protocol = "socket"
        builder._mock_data["socket"] = SocketRequestContext(
            server_name=server_name, event=event
        )
        return builder

    @staticmethod
    def smtp(server_name: str) -> MockBuilder:
        """Create a builder for an SMTP mock."""
        builder = MockBuilder()
        builder._protocol = "smtp"
        builder._mock_data["smtp"] = SmtpRequestContext(server_name=server_name)
        return builder

    # ── Common setters ────────────────────────────────────────────────

    def id(self, mock_id: str) -> MockBuilder:
        """Set the mock ID."""
        self._mock_data["id"] = mock_id
        return self

    def namespace(self, ns: str) -> MockBuilder:
        """Set the namespace."""
        self._mock_data["namespace"] = ns
        return self

    def chain_id(self, cid: str) -> MockBuilder:
        """Set the chain ID for linking related mocks."""
        self._mock_data["chain_id"] = cid
        return self

    def path_prefix(self, prefix: str) -> MockBuilder:
        """Set the path prefix for the mock."""
        self._mock_data["path_prefix"] = prefix
        return self

    def server_name(self, name: str) -> MockBuilder:
        """Set the server name for grouping mocks by environment."""
        self._mock_data["server_name"] = name
        return self

    def tags(self, *tags: str) -> MockBuilder:
        """Set tags for categorizing the mock."""
        self._mock_data["tags"] = list(tags)
        return self

    def priority(self, p: int) -> MockBuilder:
        """Set the mock priority (higher = matched first)."""
        self._mock_data["priority"] = p
        return self

    def ttl(self, seconds: int) -> MockBuilder:
        """Set the mock's time-to-live in seconds."""
        self._mock_data["ttl"] = seconds
        return self

    def use_limiter(self, max_uses: int) -> MockBuilder:
        """Set maximum number of times this mock can be used."""
        self._mock_data["use_limiter"] = max_uses
        return self

    def folder_id(self, fid: str) -> MockBuilder:
        """Set the folder ID for hierarchical organization."""
        self._mock_data["folder_id"] = fid
        return self

    # ── Conditions ────────────────────────────────────────────────────

    def condition(
        self, path: str, action: AssertAction, value: Any = None
    ) -> MockBuilder:
        """Add a body/payload condition."""
        cond = Condition(path=path, assert_action=action, value=value)
        self._conditions.append(cond)
        return self

    def header_condition(
        self, name: str, action: AssertAction, value: Any = None
    ) -> MockBuilder:
        """Add a header condition.

        For HTTP, this maps to the ``header`` field.
        For gRPC, this maps to the ``meta`` field.
        """
        cond = Condition(path=name, assert_action=action, value=value)
        self._header_conditions.append(cond)
        return self

    def query_condition(
        self, name: str, action: AssertAction, value: Any = None
    ) -> MockBuilder:
        """Add a query parameter condition (HTTP only)."""
        cond = Condition(path=name, assert_action=action, value=value)
        self._query_conditions.append(cond)
        return self

    def meta_condition(
        self, name: str, action: AssertAction, value: Any = None
    ) -> MockBuilder:
        """Add a metadata condition (gRPC only)."""
        cond = Condition(path=name, assert_action=action, value=value)
        self._meta_conditions.append(cond)
        return self

    # ── Response ──────────────────────────────────────────────────────

    def respond(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: dict[str, list[str]] | None = None,
        delay: int = 0,
        error: str | None = None,
    ) -> MockBuilder:
        """Set the mock response."""
        resp = ContentResponse(
            status_code=status_code,
            payload=body,
            headers=headers,
            delay=delay if delay > 0 else None,
            error=error,
        )
        self._mock_data["response"] = resp
        return self

    def respond_with_template(
        self, status_code: int = 200, template_path: str = ""
    ) -> MockBuilder:
        """Set the mock response to use a template file."""
        resp = ContentResponse(
            status_code=status_code,
            payload_template_path=template_path,
        )
        self._mock_data["response"] = resp
        return self

    def respond_with_one_of(self, order: str = "order") -> OneOfBuilder:
        """Start building a OneOf (multiple responses) definition.

        Returns a :class:`OneOfBuilder` -- call ``.done()`` to return here.
        """
        return OneOfBuilder(self, order=order)

    def proxy_to(self, target: str) -> MockBuilder:
        """Configure the mock to proxy requests to a real service."""
        self._mock_data["proxy"] = Proxy(target=target)
        return self

    # ── Callbacks ─────────────────────────────────────────────────────

    def callback(
        self,
        url: str,
        method: str = "POST",
        body: Any = None,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
        retry_count: int | None = None,
        retry_delay: int | None = None,
        trigger: str | None = None,
    ) -> MockBuilder:
        """Add an HTTP callback (webhook) to fire after mock resolution."""
        cb = Callback(
            type="http",
            url=url,
            method=method,
            body=body,
            headers=headers,
            timeout=timeout,
            retry_count=retry_count,
            retry_delay=retry_delay,
            trigger=trigger,
        )
        self._callbacks.append(cb)
        return self

    def kafka_callback(
        self,
        brokers: str,
        topic: str,
        body: Any = None,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> MockBuilder:
        """Add a Kafka callback to publish a message after mock resolution."""
        cb = Callback(
            type="kafka",
            body=body,
            headers=headers,
            kafka_brokers=brokers,
            kafka_topic=topic,
            kafka_key=key,
        )
        self._callbacks.append(cb)
        return self

    def rabbitmq_callback(
        self,
        rabbit_url: str,
        exchange: str = "",
        routing_key: str = "",
        body: Any = None,
    ) -> MockBuilder:
        """Add a RabbitMQ callback to publish a message after mock resolution."""
        cb = Callback(
            type="rabbitmq",
            body=body,
            rabbit_url=rabbit_url,
            rabbit_exchange=exchange,
            rabbit_routing_key=routing_key,
        )
        self._callbacks.append(cb)
        return self

    # ── Extract ───────────────────────────────────────────────────────

    def extract(
        self,
        m_store: dict[str, Any] | None = None,
        c_store: dict[str, Any] | None = None,
        g_store: dict[str, Any] | None = None,
    ) -> MockBuilder:
        """Configure value extraction from requests into stores."""
        self._mock_data["extract"] = Extract(
            m_store=m_store, c_store=c_store, g_store=g_store
        )
        return self

    def mock_store(self, data: dict[str, Any]) -> MockBuilder:
        """Set initial mock store data."""
        self._mock_data["mock_store"] = data
        return self

    # ── Build ─────────────────────────────────────────────────────────

    def build(self) -> Mock:
        """Build and return the Mock object."""
        # Apply accumulated conditions to the protocol context
        self._apply_conditions()

        # Apply callbacks
        if self._callbacks:
            self._mock_data["callbacks"] = self._callbacks

        return Mock.model_validate(self._mock_data)

    def _apply_conditions(self) -> None:
        """Merge accumulated conditions into the appropriate protocol context."""
        protocol = self._protocol
        if protocol is None:
            return

        ctx = self._mock_data.get(protocol)
        if ctx is None:
            return

        if self._conditions:
            existing = ctx.conditions or []
            ctx.conditions = existing + self._conditions

        if protocol == "http":
            assert isinstance(ctx, HttpRequestContext)
            if self._header_conditions:
                existing = ctx.headers or []
                ctx.headers = existing + self._header_conditions
            if self._query_conditions:
                existing = ctx.query_params or []
                ctx.query_params = existing + self._query_conditions
        elif protocol == "grpc":
            assert isinstance(ctx, GrpcRequestContext)
            if self._header_conditions or self._meta_conditions:
                existing = ctx.meta or []
                ctx.meta = existing + self._header_conditions + self._meta_conditions
        elif protocol in ("mcp", "soap", "graphql"):
            if self._header_conditions and hasattr(ctx, "headers"):
                existing = ctx.headers or []
                ctx.headers = existing + self._header_conditions
        elif protocol == "sse":
            assert isinstance(ctx, SSERequestContext)
            if self._header_conditions:
                existing = ctx.header_conditions or []
                ctx.header_conditions = existing + self._header_conditions
        elif protocol in ("kafka", "rabbitmq"):
            if self._header_conditions and hasattr(ctx, "headers"):
                existing = ctx.headers or []
                ctx.headers = existing + self._header_conditions
        elif protocol == "smtp":
            assert isinstance(ctx, SmtpRequestContext)
            if self._header_conditions:
                existing = ctx.header_conditions or []
                ctx.header_conditions = existing + self._header_conditions
