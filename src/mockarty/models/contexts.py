# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Request context models for all protocols supported by Mockarty.

Each context corresponds to a protocol-specific section of the Mock object.
JSON aliases exactly match the server-side Go struct tags.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from mockarty.models.condition import Condition


class HttpRequestContext(BaseModel):
    """HTTP/REST request matching context."""

    route: Optional[str] = Field(None, description="URL route pattern, e.g. /api/users/:id")
    route_pattern: Optional[str] = Field(None, alias="routePattern")
    http_method: Optional[str] = Field(None, alias="httpMethod")
    conditions: Optional[list[Condition]] = None
    query_params: Optional[list[Condition]] = Field(None, alias="queryParams")
    headers: Optional[list[Condition]] = Field(None, alias="header")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class GrpcRequestContext(BaseModel):
    """gRPC request matching context."""

    conditions: Optional[list[Condition]] = None
    meta: Optional[list[Condition]] = None
    service: Optional[str] = None
    method: Optional[str] = None
    method_type: Optional[str] = Field(
        None,
        alias="methodType",
        description="unary | server-stream | client-stream | bidirectional",
    )
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class MCPRequestContext(BaseModel):
    """MCP (Model Context Protocol) request matching context."""

    conditions: Optional[list[Condition]] = None
    headers: Optional[list[Condition]] = Field(None, alias="header")
    method: Optional[str] = Field(None, description="tools/call, resources/read, etc.")
    tool: Optional[str] = Field(None, description="Tool name for tools/call")
    resource: Optional[str] = Field(None, description="Resource URI for resources/read")
    description: Optional[str] = Field(None, description="Tool/resource description")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class SocketRequestContext(BaseModel):
    """WebSocket/TCP/UDP socket request matching context."""

    conditions: Optional[list[Condition]] = None
    server_name: Optional[str] = Field(None, alias="serverName")
    event: Optional[str] = None
    namespace: Optional[str] = None
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class SoapRequestContext(BaseModel):
    """SOAP/WSDL request matching context."""

    conditions: Optional[list[Condition]] = None
    headers: Optional[list[Condition]] = Field(None, alias="header")
    service: Optional[str] = None
    method: Optional[str] = None
    action: Optional[str] = Field(None, description="SOAPAction header value")
    path: Optional[str] = Field(None, description="URL path for identification")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class GraphQLRequestContext(BaseModel):
    """GraphQL request matching context."""

    conditions: Optional[list[Condition]] = None
    headers: Optional[list[Condition]] = Field(None, alias="header")
    operation: Optional[str] = Field(None, description="query, mutation, subscription")
    field: Optional[str] = None
    type: Optional[str] = Field(None, description="GraphQL type name")
    path: Optional[str] = Field(None, description="URL path for identification")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class SSERequestContext(BaseModel):
    """Server-Sent Events request matching context."""

    conditions: Optional[list[Condition]] = None
    header_conditions: Optional[list[Condition]] = Field(None, alias="headerConditions")
    event_path: Optional[str] = Field(None, alias="eventPath")
    event_name: Optional[str] = Field(None, alias="eventName")
    description: Optional[str] = None
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}


class KafkaRequestContext(BaseModel):
    """Kafka consumer/producer request matching context."""

    conditions: Optional[list[Condition]] = None
    headers: Optional[list[Condition]] = None
    topic: Optional[str] = None
    server_name: Optional[str] = Field(None, alias="serverName")
    consumer_group: Optional[str] = Field(None, alias="consumerGroup")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")
    # Output routing
    output_topic: Optional[str] = Field(None, alias="outputTopic")
    output_brokers: Optional[str] = Field(None, alias="outputBrokers")
    output_key: Optional[str] = Field(None, alias="outputKey")
    output_headers: Optional[dict[str, str]] = Field(None, alias="outputHeaders")

    model_config = {"populate_by_name": True}


class RabbitMQOutputProps(BaseModel):
    """AMQP 0-9-1 Basic.Properties for published response message."""

    delivery_mode: Optional[int] = Field(None, alias="deliveryMode")
    correlation_id: Optional[str] = Field(None, alias="correlationId")
    reply_to: Optional[str] = Field(None, alias="replyTo")
    content_type: Optional[str] = Field(None, alias="contentType")
    priority: Optional[int] = None
    message_id: Optional[str] = Field(None, alias="messageId")
    type: Optional[str] = None
    app_id: Optional[str] = Field(None, alias="appId")

    model_config = {"populate_by_name": True}


class RabbitMQRequestContext(BaseModel):
    """RabbitMQ consumer/producer request matching context."""

    conditions: Optional[list[Condition]] = None
    headers: Optional[list[Condition]] = None
    queue: Optional[str] = None
    exchange: Optional[str] = None
    routing_key: Optional[str] = Field(None, alias="routingKey")
    server_name: Optional[str] = Field(None, alias="serverName")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")
    # Output routing
    output_url: Optional[str] = Field(None, alias="outputURL")
    output_exchange: Optional[str] = Field(None, alias="outputExchange")
    output_routing_key: Optional[str] = Field(None, alias="outputRoutingKey")
    output_queue: Optional[str] = Field(None, alias="outputQueue")
    output_props: Optional[RabbitMQOutputProps] = Field(None, alias="outputProps")

    model_config = {"populate_by_name": True}


class SmtpRequestContext(BaseModel):
    """SMTP email request matching context."""

    server_name: Optional[str] = Field(None, alias="serverName")
    sender_conditions: Optional[list[Condition]] = Field(None, alias="senderConditions")
    recipient_conditions: Optional[list[Condition]] = Field(None, alias="recipientConditions")
    subject_conditions: Optional[list[Condition]] = Field(None, alias="subjectConditions")
    body_conditions: Optional[list[Condition]] = Field(None, alias="bodyConditions")
    header_conditions: Optional[list[Condition]] = Field(None, alias="headerConditions")
    apply_sort_array: Optional[bool] = Field(None, alias="sortArray")

    model_config = {"populate_by_name": True}
