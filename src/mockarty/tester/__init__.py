# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Mockarty Tester — fluent, multi-protocol test DSL.

Each chain call records one Allure step and accumulates assertions.

Example::

    from mockarty.tester import Tester

    t = Tester(base_url="http://localhost:8080")
    (t.http().get("/api/v1/users/42")
        .expect_status(200)
        .expect_json_path("$.name", "Alice")
        .extract("$.token", "token"))
    (t.http().post("/api/v1/orders")
        .header("X-Auth", "Bearer {{token}}")
        .json({"userId": 42})
        .expect_status(201))
    t.finish()
    assert t.ok(), t.errors()

The Go SDK in ``sdk/go-sdk/tester`` is the reference implementation;
this Python port mirrors the same vocabulary so test suites translate
1:1 across languages.
"""

from .tester import Tester, StepRecord  # noqa: F401
from .http import HTTPFacet, HTTPStep  # noqa: F401
from .graphql import GraphQLFacet, GraphQLStep  # noqa: F401
from .sse import SSEFacet, SSEStep, SSEEvent  # noqa: F401
from .kafka import (  # noqa: F401
    KafkaFacet, KafkaProduceStep, KafkaConsumeStep,
    KafkaBroker, ConsumeOptions, ConsumedMessage,
)
from .rabbitmq import (  # noqa: F401
    RabbitMQFacet, RabbitMQPublishStep, RabbitMQConsumeStep,
    RabbitMQBroker, RabbitConsumeOptions, RabbitConsumedMessage,
)
from .soap import SOAPFacet, SOAPStep  # noqa: F401
from .db import DBFacet, DBStep, SQLConn, DBExecResult, DBRow  # noqa: F401
from .ergonomics import wrap, eventually, parallel  # noqa: F401
from .external_run import to_report_kwargs  # noqa: F401

__all__ = [
    "Tester",
    "StepRecord",
    "HTTPFacet",
    "HTTPStep",
    "GraphQLFacet",
    "GraphQLStep",
    "SSEFacet",
    "SSEStep",
    "SSEEvent",
    "KafkaFacet",
    "KafkaProduceStep",
    "KafkaConsumeStep",
    "KafkaBroker",
    "ConsumeOptions",
    "ConsumedMessage",
    "RabbitMQFacet",
    "RabbitMQPublishStep",
    "RabbitMQConsumeStep",
    "RabbitMQBroker",
    "RabbitConsumeOptions",
    "RabbitConsumedMessage",
    "SOAPFacet",
    "SOAPStep",
    "DBFacet",
    "DBStep",
    "SQLConn",
    "DBExecResult",
    "DBRow",
    "wrap",
    "eventually",
    "parallel",
    "to_report_kwargs",
]
