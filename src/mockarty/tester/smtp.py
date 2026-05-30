# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""SMTP facet — mirrors ``sdk/go-sdk/tester/smtp.go``.

``SMTPSender`` is a protocol the user implements (or adapts an existing
client to). ``mockarty.protocols.smtp.Client`` satisfies it directly;
tests pass an in-memory fake so no real SMTP server is required.
"""

from __future__ import annotations

import time
from typing import Optional, Protocol

from ..protocols import smtp as smtpproto
from .interpolate import interpolate
from .tester import StepRecord, Tester


class SMTPSender(Protocol):
    """Minimal contract the SMTP facet needs."""

    def send(self, msg: "smtpproto.Message") -> "smtpproto.SendResult": ...


class SMTPFacet:
    def __init__(self, tester: Tester, sender: SMTPSender) -> None:
        self._t = tester
        self._sender = sender

    def send(self, from_addr: str, *to: str) -> "SMTPStep":
        self._t._flush_pending()
        v = self._t._snapshot_vars()
        step = SMTPStep(
            self._t,
            self._sender,
            smtpproto.Message(
                from_addr=interpolate(from_addr, v),
                to=[interpolate(r, v) for r in to],
            ),
        )
        self._t._set_pending(step)
        return step


class SMTPStep:
    def __init__(
        self, tester: Tester, sender: SMTPSender, msg: "smtpproto.Message"
    ) -> None:
        self._t = tester
        self._sender = sender
        self._msg = msg
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._err: Optional[Exception] = None
        self._result: Optional[smtpproto.SendResult] = None
        self._failures: list[str] = []

    # ── builders ──────────────────────────────────────────────────────

    def subject(self, subj: str) -> "SMTPStep":
        if self._guard("subject"):
            return self
        self._msg.subject = interpolate(subj, self._t._snapshot_vars())
        return self

    def body(self, body: str) -> "SMTPStep":
        if self._guard("body"):
            return self
        self._msg.body = interpolate(body, self._t._snapshot_vars())
        return self

    def header(self, k: str, v: str) -> "SMTPStep":
        if self._guard("header"):
            return self
        self._msg.headers[k] = interpolate(v, self._t._snapshot_vars())
        return self

    # ── assertions ────────────────────────────────────────────────────

    def expect_accepted(self) -> "SMTPStep":
        if not self._ensure_sent():
            return self
        if self._err is not None:
            self._fail(f"expect_accepted: {self._err}")
        return self

    def expect_rejected(self) -> "SMTPStep":
        self._ensure_sent()
        if self._err is None:
            self._fail("expect_rejected: message was accepted")
        return self

    def expect_error_contains(self, sub: str) -> "SMTPStep":
        self._ensure_sent()
        if self._err is None:
            return self._fail("expect_error_contains: no error")
        if sub not in str(self._err):
            self._fail(f"expect_error_contains: {sub!r} not in: {self._err}")
        return self

    def raw(self) -> str:
        self._ensure_sent()
        return self._result.raw if self._result else ""

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    # ── internals ─────────────────────────────────────────────────────

    def _fail(self, msg: str) -> "SMTPStep":
        self._failures.append(msg)
        return self

    def _guard(self, method: str) -> bool:
        if self._sent:
            self._fail(f"{method}() called after send")
            return True
        return False

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            self._fail("skipped: fail-fast triggered by earlier step")
            return False
        self._started_at = time.time()
        try:
            self._result = self._sender.send(self._msg)
        except Exception as e:
            self._err = e
        self._ended_at = time.time()
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        status = 550 if self._err is not None else 250
        rec = StepRecord(
            protocol="smtp",
            method="send",
            name=f"smtp send {self._msg.from_addr} → {','.join(self._msg.to)}",
            url=",".join(self._msg.to),
            status_or_code=status,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)
