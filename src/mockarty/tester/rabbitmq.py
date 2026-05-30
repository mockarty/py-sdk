# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""RabbitMQ facet — mirrors ``sdk/go-sdk/tester/rabbitmq.go``.

RabbitMQBroker is a protocol the user implements. The SDK ships ZERO
AMQP client deps; the user adapts pika / aio-pika / a test fake.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .interpolate import interpolate
from .jsonpath import equal_json_scalar, resolve_jsonpath, JSONPathError
from .tester import StepRecord, Tester


@dataclass
class RabbitConsumedMessage:
    exchange: str = ""
    routing_key: str = ""
    body: bytes = b""
    content_type: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class RabbitConsumeOptions:
    queue: str = ""
    max_messages: int = 1
    auto_ack: bool = False


class RabbitMQBroker(Protocol):
    def publish(
        self,
        exchange: str,
        routing_key: str,
        payload: Any,
        headers: Optional[dict[str, str]] = None,
    ) -> None: ...

    def consume(self, opts: RabbitConsumeOptions) -> list[RabbitConsumedMessage]: ...


class RabbitMQFacet:
    def __init__(self, tester: Tester, broker: RabbitMQBroker) -> None:
        self._t = tester
        self._broker = broker

    def publish(self, exchange: str, routing_key: str) -> "RabbitMQPublishStep":
        self._t._flush_pending()
        v = self._t._snapshot_vars()
        step = RabbitMQPublishStep(
            self._t,
            self._broker,
            exchange=interpolate(exchange, v),
            routing_key=interpolate(routing_key, v),
        )
        self._t._set_pending(step)
        return step

    def consume(self, queue: str) -> "RabbitMQConsumeStep":
        self._t._flush_pending()
        step = RabbitMQConsumeStep(
            self._t,
            self._broker,
            RabbitConsumeOptions(
                queue=interpolate(queue, self._t._snapshot_vars()),
                max_messages=1,
            ),
        )
        self._t._set_pending(step)
        return step


class RabbitMQPublishStep:
    def __init__(
        self,
        tester: Tester,
        broker: RabbitMQBroker,
        exchange: str,
        routing_key: str,
    ) -> None:
        self._t = tester
        self._broker = broker
        self._exchange = exchange
        self._routing_key = routing_key
        self._headers: dict[str, str] = {}
        self._payload: bytes = b""
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._err: Optional[Exception] = None
        self._failures: list[str] = []

    def header(self, k: str, v: str) -> "RabbitMQPublishStep":
        if self._sent:
            return self._fail("header() after send")
        self._headers[k] = interpolate(v, self._t._snapshot_vars())
        return self

    def json(self, v: Any) -> "RabbitMQPublishStep":
        if self._sent:
            return self._fail("json() after send")
        try:
            raw = json.dumps(v)
        except (TypeError, ValueError) as e:
            self._abort = True
            return self._fail(f"marshal payload: {e}")
        self._payload = interpolate(raw, self._t._snapshot_vars()).encode()
        return self

    def bytes_(self, b: bytes) -> "RabbitMQPublishStep":
        if self._sent:
            return self._fail("bytes_() after send")
        self._payload = bytes(b)
        return self

    def expect_ok(self) -> "RabbitMQPublishStep":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            self._fail(f"expect_ok: {self._err}")
        return self

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    def _fail(self, msg: str) -> "RabbitMQPublishStep":
        self._failures.append(msg)
        return self

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            return self._fail("skipped: fail-fast triggered by earlier step")._abort  # type: ignore
        self._started_at = time.time()
        try:
            self._broker.publish(
                self._exchange,
                self._routing_key,
                self._payload,
                dict(self._headers),
            )
        except Exception as e:
            self._err = e
            self._ended_at = time.time()
            self._fail(f"publish: {e}")
            self._abort = True
            return False
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="rabbitmq",
            method="publish",
            name=f"publish {self._exchange}/{self._routing_key}",
            url=f"{self._exchange}/{self._routing_key}",
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)


class RabbitMQConsumeStep:
    def __init__(
        self,
        tester: Tester,
        broker: RabbitMQBroker,
        opts: RabbitConsumeOptions,
    ) -> None:
        self._t = tester
        self._broker = broker
        self._opts = opts
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._msgs: list[RabbitConsumedMessage] = []
        self._err: Optional[Exception] = None
        self._failures: list[str] = []

    def max(self, n: int) -> "RabbitMQConsumeStep":
        if self._sent:
            return self._fail("max() after send")
        if n > 0:
            self._opts.max_messages = n
        return self

    def auto_ack(self, b: bool) -> "RabbitMQConsumeStep":
        if self._sent:
            return self._fail("auto_ack() after send")
        self._opts.auto_ack = bool(b)
        return self

    def expect_count(self, n: int) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        if len(self._msgs) != n:
            self._fail(f"expect_count: want {n}, got {len(self._msgs)}")
        return self

    def expect_at_least(self, n: int) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        if len(self._msgs) < n:
            self._fail(f"expect_at_least: want >={n}, got {len(self._msgs)}")
        return self

    def expect_message_contains(self, idx: int, sub: str) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        if idx < 0 or idx >= len(self._msgs):
            return self._fail(
                f"expect_message_contains[{idx}]: index out of range (len={len(self._msgs)})"
            )
        if sub.encode() not in self._msgs[idx].body:
            self._fail(f"expect_message_contains[{idx}]: {sub!r} not found")
        return self

    def expect_header(self, idx: int, k: str, v: str) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        if idx < 0 or idx >= len(self._msgs):
            return self._fail(
                f"expect_header[{idx}]: index out of range (len={len(self._msgs)})"
            )
        got = self._msgs[idx].headers.get(k, "")
        if got != v:
            self._fail(f"expect_header[{idx}] {k}: want {v!r}, got {got!r}")
        return self

    def expect_routing_key(self, idx: int, want: str) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        if idx < 0 or idx >= len(self._msgs):
            return self._fail(
                f"expect_routing_key[{idx}]: index out of range (len={len(self._msgs)})"
            )
        if self._msgs[idx].routing_key != want:
            self._fail(
                f"expect_routing_key[{idx}]: want {want!r}, got {self._msgs[idx].routing_key!r}"
            )
        return self

    def expect_json_path(self, idx: int, path: str, want: Any) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_at(idx, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"expect_json_path[{idx}] {path}: {e}")
        if not equal_json_scalar(got, want):
            self._fail(f"expect_json_path[{idx}] {path}: want {want!r}, got {got!r}")
        return self

    def extract(self, idx: int, path: str, name: str) -> "RabbitMQConsumeStep":
        if not self._ensure_sent():
            return self
        try:
            got = self._eval_at(idx, path)
        except (JSONPathError, ValueError) as e:
            return self._fail(f"extract[{idx}] {path}: {e}")
        from .http import _stringify

        self._t.set_var(name, _stringify(got))
        return self

    def messages(self) -> list[RabbitConsumedMessage]:
        self._ensure_sent()
        return list(self._msgs)

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    def _fail(self, msg: str) -> "RabbitMQConsumeStep":
        self._failures.append(msg)
        return self

    def _eval_at(self, idx: int, path: str):
        if idx < 0 or idx >= len(self._msgs):
            raise ValueError(f"index out of range (len={len(self._msgs)})")
        doc = json.loads(self._msgs[idx].body)
        return resolve_jsonpath(doc, path)

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            return self._fail("skipped: fail-fast triggered by earlier step")._abort  # type: ignore
        self._started_at = time.time()
        try:
            self._msgs = self._broker.consume(self._opts)
        except Exception as e:
            self._err = e
            self._ended_at = time.time()
            self._fail(f"consume: {e}")
            return True
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="rabbitmq",
            method="consume",
            name=f"consume {self._opts.queue}",
            url=self._opts.queue,
            status_or_code=len(self._msgs),
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)
