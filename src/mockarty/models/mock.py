# Copyright (c) 2026 Mockarty. All rights reserved.

"""Core mock models matching the Mockarty server API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

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


class SSEEvent(BaseModel):
    """A single event in an SSE event chain."""

    event_name: Optional[str] = Field(None, alias="eventName")
    data: Optional[Any] = None
    delay: Optional[int] = None
    id: Optional[str] = None
    retry: Optional[int] = None
    template_path: Optional[str] = Field(None, alias="templatePath")

    model_config = {"populate_by_name": True}


class SSEEventChain(BaseModel):
    """Chain of SSE events for streaming responses."""

    events: Optional[list[SSEEvent]] = None
    loop: Optional[bool] = None
    loop_delay: Optional[int] = Field(None, alias="loopDelay")
    heartbeat: Optional[int] = None
    max_loops: Optional[int] = Field(None, alias="maxLoops")
    max_time: Optional[int] = Field(None, alias="maxTime")
    log_batch: Optional[int] = Field(None, alias="logBatch")

    model_config = {"populate_by_name": True}


class GraphQLErrorLocation(BaseModel):
    """Location of a GraphQL error in the query."""

    line: int = 0
    column: int = 0


class GraphQLError(BaseModel):
    """GraphQL error per the June 2018 spec."""

    message: str = ""
    path: Optional[list[Any]] = None
    locations: Optional[list[GraphQLErrorLocation]] = None
    extensions: Optional[dict[str, Any]] = None


class SOAPFault(BaseModel):
    """SOAP 1.1 fault structure."""

    fault_code: str = Field("", alias="faultCode")
    fault_string: str = Field("", alias="faultString")
    fault_actor: Optional[str] = Field(None, alias="faultActor")
    detail: Optional[str] = None
    http_status: Optional[int] = Field(None, alias="httpStatus")

    model_config = {"populate_by_name": True}


class ErrorDetails(BaseModel):
    """Structured error detail (gRPC rich error model)."""

    type: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class ContentResponse(BaseModel):
    """The response body and metadata a mock returns.

    Maps to the server ``ContentResponse`` struct.
    """

    headers: Optional[dict[str, list[str]]] = None
    status_code: Optional[int] = Field(None, alias="statusCode")
    decode: Optional[str] = None
    payload: Optional[Any] = None
    payload_template_path: Optional[str] = Field(None, alias="payloadTemplatePath")
    error: Optional[str] = None
    error_details: Optional[list[ErrorDetails]] = Field(None, alias="errorDetails")
    delay: Optional[int] = None
    sse_event_chain: Optional[SSEEventChain] = Field(None, alias="sseEventChain")
    graphql_errors: Optional[list[GraphQLError]] = Field(None, alias="graphqlErrors")
    soap_fault: Optional[SOAPFault] = Field(None, alias="soapFault")
    mcp_is_error: Optional[bool] = Field(None, alias="mcpIsError")

    model_config = {"populate_by_name": True}


class OneOf(BaseModel):
    """Multiple response variants returned in order or randomly."""

    order: str = "order"
    offset: int = Field(0, alias="offset")
    responses: Optional[list[ContentResponse]] = None

    model_config = {"populate_by_name": True}


class Proxy(BaseModel):
    """Proxy configuration to forward requests to a real service."""

    target: Optional[str] = None


class Callback(BaseModel):
    """Webhook / messaging callback triggered after mock resolution.

    Supports HTTP, Kafka, and RabbitMQ callback types.
    """

    type: Optional[str] = None
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    body: Optional[Any] = None
    timeout: Optional[int] = None
    retry_count: Optional[int] = Field(None, alias="retryCount")
    retry_delay: Optional[int] = Field(None, alias="retryDelay")
    async_: Optional[bool] = Field(None, alias="async")
    trigger: Optional[str] = None
    # Kafka-specific
    kafka_brokers: Optional[str] = Field(None, alias="kafkaBrokers")
    kafka_topic: Optional[str] = Field(None, alias="kafkaTopic")
    kafka_key: Optional[str] = Field(None, alias="kafkaKey")
    kafka_username: Optional[str] = Field(None, alias="kafkaUsername")
    kafka_password: Optional[str] = Field(None, alias="kafkaPassword")
    kafka_use_sasl: Optional[bool] = Field(None, alias="kafkaUseSASL")
    kafka_use_tls: Optional[bool] = Field(None, alias="kafkaUseTLS")
    # RabbitMQ-specific
    rabbit_url: Optional[str] = Field(None, alias="rabbitURL")
    rabbit_exchange: Optional[str] = Field(None, alias="rabbitExchange")
    rabbit_routing_key: Optional[str] = Field(None, alias="rabbitRoutingKey")
    rabbit_queue: Optional[str] = Field(None, alias="rabbitQueue")
    rabbit_mandatory: Optional[bool] = Field(None, alias="rabbitMandatory")

    model_config = {"populate_by_name": True}


class Extract(BaseModel):
    """Extract configuration for storing values from requests into stores."""

    m_store: Optional[dict[str, Any]] = Field(None, alias="mStore")
    c_store: Optional[dict[str, Any]] = Field(None, alias="cStore")
    g_store: Optional[dict[str, Any]] = Field(None, alias="gStore")

    model_config = {"populate_by_name": True}


class Mock(BaseModel):
    """The primary mock definition object.

    A mock pairs request-matching contexts (HTTP, gRPC, MCP, etc.) with
    response definitions and optional features such as TTL, priority,
    callbacks, and store extraction.

    JSON field aliases match the server API exactly.
    """

    id: Optional[str] = None
    chain_id: Optional[str] = Field(None, alias="chainId")
    namespace: Optional[str] = None
    path_prefix: Optional[str] = Field(None, alias="pathPrefix")
    server_name: Optional[str] = Field(None, alias="serverName")
    # Protocol contexts
    http: Optional[HttpRequestContext] = None
    grpc: Optional[GrpcRequestContext] = None
    mcp: Optional[MCPRequestContext] = None
    socket: Optional[SocketRequestContext] = None
    soap: Optional[SoapRequestContext] = None
    graphql: Optional[GraphQLRequestContext] = None
    sse: Optional[SSERequestContext] = None
    kafka: Optional[KafkaRequestContext] = None
    rabbitmq: Optional[RabbitMQRequestContext] = None
    smtp: Optional[SmtpRequestContext] = None
    # Response
    response: Optional[ContentResponse] = None
    one_of: Optional[OneOf] = Field(None, alias="oneOf")
    proxy: Optional[Proxy] = None
    callbacks: Optional[list[Callback]] = Field(None, alias="webhooks")
    # Lifecycle
    ttl: Optional[int] = None
    use_limiter: Optional[int] = Field(None, alias="useLimiter")
    use_counter: Optional[int] = Field(None, alias="useCounter")
    created_at: Optional[int] = Field(None, alias="createdAt")
    last_use: Optional[int] = Field(None, alias="lastUse")
    expire_at: Optional[int] = Field(None, alias="expireAt")
    closed_at: Optional[int] = Field(None, alias="closedAt")
    # Organization
    priority: Optional[int] = None
    tags: Optional[list[str]] = None
    folder_id: Optional[str] = Field(None, alias="folderId")
    # Stores
    extract: Optional[Extract] = None
    mock_store: Optional[dict[str, Any]] = Field(None, alias="mStore")

    model_config = {"populate_by_name": True}


class SaveMockResponse(BaseModel):
    """Response returned by the mock create/update endpoint."""

    overwritten: bool = False
    mock: Mock = Field(default_factory=Mock)
