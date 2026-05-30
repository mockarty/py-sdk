# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Tester — fluent, multi-protocol test builder.

Mirrors ``sdk/go-sdk/tester/tester.go``. Lazy step execution + chain
commit on next chain start or ``finish()``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional, Protocol

import httpx


@dataclass
class StepRecord:
    """One executed step. Mirrors Go's ``StepRecord``."""

    # Same anti-collection sentinel as Tester (StepRecord doesn't start
    # with "Test" so pytest won't grab it, but kept for parity).
    __test__ = False

    protocol: str = ""
    method: str = ""
    name: str = ""
    url: str = ""
    status_or_code: int = 0
    started_at: float = 0.0
    ended_at: float = 0.0
    failures: list[str] = field(default_factory=list)


class _Committable(Protocol):
    def _commit(self) -> None: ...


class Tester:
    """Fluent test builder. Use ``.http()``, ``.graphql()`` etc. to chain
    protocol calls; call ``.finish()`` at the end of a test."""

    # Pytest collects classes whose name starts with "Test"; tell it
    # this is not one — Tester is the SDK entry point, not a test case.
    __test__ = False

    def __init__(
        self,
        *,
        base_url: str = "",
        http_client: Optional[httpx.Client] = None,
        default_headers: Optional[dict[str, str]] = None,
        fail_fast: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=30.0)
        self._owns_http = http_client is None
        self._default_headers = dict(default_headers or {})
        self._fail_fast = fail_fast
        self._vars: dict[str, str] = {}
        self._steps: list[StepRecord] = []
        self._errs: list[str] = []
        self._pending: Optional[_Committable] = None
        self._lock = threading.Lock()

    # ── public api ────────────────────────────────────────────────────

    def http(self):  # -> HTTPFacet
        # Lazy import to avoid circular imports.
        from .http import HTTPFacet

        return HTTPFacet(self)

    def graphql(self, endpoint: str):  # -> GraphQLFacet
        from .graphql import GraphQLFacet

        return GraphQLFacet(self, endpoint)

    def sse(self, endpoint: str):  # -> SSEFacet
        from .sse import SSEFacet

        return SSEFacet(self, endpoint)

    def kafka(self, broker):  # -> KafkaFacet
        from .kafka import KafkaFacet

        return KafkaFacet(self, broker)

    def rabbitmq(self, broker):  # -> RabbitMQFacet
        from .rabbitmq import RabbitMQFacet

        return RabbitMQFacet(self, broker)

    def soap(self, endpoint: str):  # -> SOAPFacet
        from .soap import SOAPFacet

        return SOAPFacet(self, endpoint)

    def db(self, conn):  # -> DBFacet
        from .db import DBFacet

        return DBFacet(self, conn)

    def s3(self, client):  # -> S3Facet
        from .s3 import S3Facet

        return S3Facet(self, client)

    def smtp(self, sender):  # -> SMTPFacet
        from .smtp import SMTPFacet

        return SMTPFacet(self, sender)

    def socketio(self, url: str):  # -> SocketIOFacet
        from .socketio import SocketIOFacet

        return SocketIOFacet(self, url)

    def set_var(self, name: str, value: str) -> None:
        with self._lock:
            self._vars[name] = value

    def vars(self) -> dict[str, str]:
        with self._lock:
            return dict(self._vars)

    def ok(self) -> bool:
        self._flush_pending()
        with self._lock:
            return not self._errs

    def errors(self) -> list[str]:
        self._flush_pending()
        with self._lock:
            return list(self._errs)

    def report(self) -> list[StepRecord]:
        self._flush_pending()
        with self._lock:
            return list(self._steps)

    def finish(self) -> "Tester":
        self._flush_pending()
        return self

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> "Tester":
        return self

    def __exit__(self, *args) -> None:
        self.finish()
        self.close()

    # ── chain machinery (used by facets) ──────────────────────────────

    def _snapshot_vars(self) -> dict[str, str]:
        with self._lock:
            return dict(self._vars)

    def _should_abort(self) -> bool:
        if not self._fail_fast:
            return False
        with self._lock:
            return bool(self._errs)

    def _set_pending(self, s: _Committable) -> None:
        with self._lock:
            self._pending = s

    def _clear_pending(self, s: _Committable) -> None:
        with self._lock:
            if self._pending is s:
                self._pending = None

    def _flush_pending(self) -> None:
        with self._lock:
            p = self._pending
            self._pending = None
        if p is not None:
            p._commit()

    def _record_step(self, rec: StepRecord) -> None:
        with self._lock:
            self._steps.append(rec)
            for f in rec.failures:
                self._errs.append(f"{rec.name}: {f}")
