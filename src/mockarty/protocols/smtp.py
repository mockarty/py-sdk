# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Minimal SMTP test client — mirrors ``sdk/go-sdk/protocols/smtp``.

Sends a mail over SMTP (plain or AUTH) and reports the server's
acceptance so CI/CD test scripts can assert that a mock — or a real MTA
— accepted a message. Receipt-side assertions (did the mailbox get it?)
are done separately against whatever inbox the test target exposes; this
client owns the send side.

Built on the standard library :mod:`smtplib` — no extra dependency.

Out of scope: STARTTLS negotiation tuning, DKIM signing, bounce
parsing — the owner-rule for the SDK is "expose only the surface useful
from CI/CD scripts and tests".
"""

from __future__ import annotations

import smtplib
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Optional


@dataclass
class Message:
    from_addr: str = ""
    to: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class SendResult:
    raw: str = ""
    sent_at: float = 0.0


class SMTPSendError(Exception):
    """Raised when the SMTP server rejects the message or the send fails."""


class Client:
    """SMTP test client bound to a fixed server address.

    ``host`` / ``port`` address the server. Supply ``username`` /
    ``password`` to authenticate (AUTH). ``use_tls`` issues STARTTLS
    before AUTH when the server advertises it.
    """

    def __init__(
        self,
        host: str,
        port: int = 25,
        *,
        username: str = "",
        password: str = "",
        use_tls: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout = timeout

    def send(self, msg: Message) -> SendResult:
        if not msg.from_addr:
            raise SMTPSendError("mockarty smtp: empty from address")
        if not msg.to:
            raise SMTPSendError("mockarty smtp: no recipients")

        email = EmailMessage()
        email["From"] = msg.from_addr
        email["To"] = ", ".join(msg.to)
        if msg.subject:
            email["Subject"] = msg.subject
        for k, v in msg.headers.items():
            if k.lower() in ("from", "to", "subject"):
                continue
            email[k] = v
        email.set_content(msg.body)
        raw = email.as_string()

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as srv:
                srv.ehlo()
                if self._use_tls:
                    srv.starttls()
                    srv.ehlo()
                if self._username:
                    srv.login(self._username, self._password)
                srv.send_message(email, from_addr=msg.from_addr, to_addrs=msg.to)
        except (smtplib.SMTPException, OSError) as e:
            raise SMTPSendError(f"mockarty smtp: send: {e}") from e

        return SendResult(raw=raw, sent_at=time.time())
