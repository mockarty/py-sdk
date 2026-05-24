# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the MIT License. See LICENSE file for details.

"""Tests for Python Tester Kafka + RabbitMQ facets.

Both use protocol-based interfaces so we plug in an in-memory fake —
no live broker required.
"""

from __future__ import annotations

import json

from mockarty.tester import (
    ConsumedMessage,
    ConsumeOptions,
    RabbitConsumedMessage,
    RabbitConsumeOptions,
    Tester,
)


# ── Kafka fake ─────────────────────────────────────────────────────────


class FakeKafka:
    def __init__(self):
        self.topics: dict[str, list[ConsumedMessage]] = {}
        self.produce_err = None
        self.consume_err = None

    def produce(self, topic, key, payload, headers=None):
        if self.produce_err is not None:
            raise self.produce_err
        body = payload if isinstance(payload, bytes) else (
            payload.encode() if isinstance(payload, str)
            else json.dumps(payload).encode()
        )
        offset = len(self.topics.get(topic, []))
        self.topics.setdefault(topic, []).append(ConsumedMessage(
            topic=topic, key=key, value=body, offset=offset,
            headers=dict(headers or {}),
        ))

    def consume(self, opts: ConsumeOptions):
        if self.consume_err is not None:
            raise self.consume_err
        all_ = self.topics.get(opts.topic, [])
        start = max(opts.start_offset, 0)
        if start > len(all_):
            start = 0
        end = min(start + opts.max_messages, len(all_))
        return list(all_[start:end])


# ── Kafka tests ────────────────────────────────────────────────────────


def test_kafka_produce_consume_round_trip():
    b = FakeKafka()
    t = Tester()
    (t.kafka(b).produce("orders", "user-42")
        .json({"id": 1, "status": "created"})
        .expect_ok())
    (t.kafka(b).consume("orders")
        .max(5)
        .expect_count(1)
        .expect_first_offset_at_least(0)
        .expect_message_contains(0, "created")
        .expect_json_path(0, "$.id", 1)
        .extract(0, "$.status", "last_status"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["last_status"] == "created"


def test_kafka_produce_error_propagates():
    b = FakeKafka()
    b.produce_err = RuntimeError("broker unreachable")
    t = Tester()
    t.kafka(b).produce("orders", "k").json({"x": 1}).expect_ok()
    assert not t.ok()


def test_kafka_interpolation_across_chains():
    b = FakeKafka()
    t = Tester()
    t.set_var("user", "42")
    (t.kafka(b).produce("orders", "k-{{user}}")
        .header("X-User", "{{user}}")
        .json({"userID": "{{user}}"})
        .expect_ok())
    (t.kafka(b).consume("orders").max(1)
        .expect_count(1)
        .expect_header(0, "X-User", "42")
        .expect_json_path(0, "$.userID", "42"))
    t.finish()
    assert t.ok(), t.errors()
    msgs = b.consume(ConsumeOptions(topic="orders", max_messages=1))
    assert msgs[0].key == "k-42"


def test_kafka_start_offset_skips_history():
    b = FakeKafka()
    t = Tester()
    for i in range(5):
        t.kafka(b).produce("topic", "k").json({"i": i}).expect_ok()
    (t.kafka(b).consume("topic")
        .start_offset(3)
        .max(10)
        .expect_count(2)
        .expect_first_offset_at_least(3))
    t.finish()
    assert t.ok(), t.errors()


def test_kafka_index_out_of_range():
    b = FakeKafka()
    t = Tester()
    (t.kafka(b).consume("empty").max(1)
        .expect_message_contains(0, "x")
        .expect_header(0, "x", "y")
        .expect_json_path(0, "$.a", 1)
        .extract(0, "$.a", "v"))
    t.finish()
    assert not t.ok()
    assert len(t.errors()) >= 4


# ── RabbitMQ fake ──────────────────────────────────────────────────────


class FakeRabbit:
    def __init__(self):
        self.queues: dict[str, list[RabbitConsumedMessage]] = {}
        self.publish_err = None
        self.consume_err = None

    def publish(self, exchange, routing_key, payload, headers=None):
        if self.publish_err is not None:
            raise self.publish_err
        body = payload if isinstance(payload, bytes) else (
            payload.encode() if isinstance(payload, str)
            else json.dumps(payload).encode()
        )
        self.queues.setdefault(routing_key, []).append(RabbitConsumedMessage(
            exchange=exchange, routing_key=routing_key, body=body,
            content_type="application/json", headers=dict(headers or {}),
        ))

    def consume(self, opts: RabbitConsumeOptions):
        if self.consume_err is not None:
            raise self.consume_err
        all_ = self.queues.get(opts.queue, [])
        n = min(opts.max_messages, len(all_))
        out = list(all_[:n])
        # Non-AutoAck removes consumed messages (matches real RabbitMQ).
        self.queues[opts.queue] = all_[n:]
        return out


# ── RabbitMQ tests ─────────────────────────────────────────────────────


def test_rabbitmq_publish_consume_round_trip():
    b = FakeRabbit()
    t = Tester()
    (t.rabbitmq(b).publish("events", "user.updated")
        .json({"id": 1, "status": "ok"})
        .expect_ok())
    (t.rabbitmq(b).consume("user.updated").max(5)
        .expect_count(1)
        .expect_routing_key(0, "user.updated")
        .expect_message_contains(0, "ok")
        .expect_json_path(0, "$.id", 1)
        .extract(0, "$.status", "last_status"))
    t.finish()
    assert t.ok(), t.errors()
    assert t.vars()["last_status"] == "ok"


def test_rabbitmq_publish_error_propagates():
    b = FakeRabbit()
    b.publish_err = RuntimeError("connection refused")
    t = Tester()
    t.rabbitmq(b).publish("ex", "rk").json({"x": 1}).expect_ok()
    assert not t.ok()


def test_rabbitmq_consume_auto_ack_and_header():
    b = FakeRabbit()
    t = Tester()
    (t.rabbitmq(b).publish("ex", "q")
        .header("trace", "abc")
        .json({"x": 1})
        .expect_ok())
    (t.rabbitmq(b).consume("q").auto_ack(True).max(1)
        .expect_count(1)
        .expect_header(0, "trace", "abc"))
    t.finish()
    assert t.ok(), t.errors()


def test_rabbitmq_interpolation():
    b = FakeRabbit()
    t = Tester()
    t.set_var("user", "alice")
    (t.rabbitmq(b).publish("ex-{{user}}", "rk-{{user}}")
        .header("X-User", "{{user}}")
        .json({"name": "{{user}}"})
        .expect_ok())
    (t.rabbitmq(b).consume("rk-alice").max(1)
        .expect_count(1)
        .expect_header(0, "X-User", "alice")
        .expect_json_path(0, "$.name", "alice"))
    t.finish()
    assert t.ok(), t.errors()


def test_rabbitmq_index_out_of_range():
    b = FakeRabbit()
    t = Tester()
    (t.rabbitmq(b).consume("empty").max(1)
        .expect_message_contains(0, "x")
        .expect_header(0, "x", "y")
        .expect_routing_key(0, "z")
        .expect_json_path(0, "$.x", 1)
        .extract(0, "$.x", "v"))
    t.finish()
    assert not t.ok()
    assert len(t.errors()) >= 5
