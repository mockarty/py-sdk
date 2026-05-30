# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""SOAP facet — mirrors ``sdk/go-sdk/tester/soap.go``.

Uses httpx for transport (already core dep) and stdlib xml.etree for
XPath. The xml.etree XPath subset supports the namespace-agnostic
`{*}tag` form used by the Mockarty SOAP test convention. Examples:

    ./*[local-name()='Body']/*[local-name()='Response']/*[local-name()='id']/text()

is the Go form; in xml.etree we use the simpler

    .//{*}id

(matches any namespace). The shim accepts EITHER form to keep tests
that translate between languages working.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

from .interpolate import interpolate
from .tester import StepRecord, Tester


class SOAPFacet:
    def __init__(self, tester: Tester, endpoint: str) -> None:
        self._t = tester
        self._endpoint = endpoint

    def call(self, action: str, body: str) -> "SOAPStep":
        self._t._flush_pending()
        v = self._t._snapshot_vars()
        step = SOAPStep(
            self._t,
            endpoint=interpolate(self._endpoint, v),
            action=interpolate(action, v),
            body=_wrap_envelope(interpolate(body, v)),
        )
        self._t._set_pending(step)
        return step


def _wrap_envelope(body: str) -> str:
    """Pass through a full SOAP envelope; wrap a bare fragment in a
    minimal SOAP 1.1 envelope so callers don't repeat the boilerplate."""
    trimmed = body.strip()
    if trimmed.startswith("<?xml") or ":Envelope" in trimmed:
        return body
    return (
        '<?xml version="1.0"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body>" + body + "</soap:Body>"
        "</soap:Envelope>"
    )


class SOAPStep:
    def __init__(self, tester: Tester, endpoint: str, action: str, body: str) -> None:
        self._t = tester
        self._endpoint = endpoint
        self._action = action
        self._body = body
        self._headers: dict[str, str] = {}
        self._resp: Optional[httpx.Response] = None
        self._doc: Optional[ET.Element] = None
        self._sent = False
        self._committed = False
        self._abort = False
        self._started_at = 0.0
        self._ended_at = 0.0
        self._failures: list[str] = []

    def header(self, k: str, v: str) -> "SOAPStep":
        if self._sent:
            return self._fail("header() after send")
        self._headers[k] = interpolate(v, self._t._snapshot_vars())
        return self

    def expect_status(self, code: int) -> "SOAPStep":
        if not self._ensure_sent():
            return self
        if self._resp is not None and self._resp.status_code != code:
            self._fail(f"expect_status: want {code}, got {self._resp.status_code}")
        return self

    def expect_xpath(self, xpath_expr: str, want) -> "SOAPStep":
        if not self._ensure_sent():
            return self
        got = self._eval_xpath(xpath_expr)
        if got is None:
            return self._fail(f"expect_xpath {xpath_expr}: no match")
        want_str = str(want)
        if got != want_str:
            self._fail(f"expect_xpath {xpath_expr}: want {want_str!r}, got {got!r}")
        return self

    def expect_xpath_contains(self, xpath_expr: str, sub: str) -> "SOAPStep":
        if not self._ensure_sent():
            return self
        got = self._eval_xpath(xpath_expr)
        if got is None:
            return self._fail(f"expect_xpath_contains {xpath_expr}: no match")
        if sub not in got:
            self._fail(
                f"expect_xpath_contains {xpath_expr}: {sub!r} not found in {got!r}"
            )
        return self

    def expect_no_fault(self) -> "SOAPStep":
        if not self._ensure_sent():
            return self
        if self._doc is None:
            return self
        fault = _find_local(self._doc, "Fault")
        if fault is not None:
            code = _find_local_text(fault, "faultcode") or ""
            msg = _find_local_text(fault, "faultstring") or ""
            self._fail(f"expect_no_fault: {code} — {msg}")
        return self

    def expect_fault(self, fault_code: str = "") -> "SOAPStep":
        if not self._ensure_sent():
            return self
        if self._doc is None:
            return self._fail("expect_fault: no response")
        fault = _find_local(self._doc, "Fault")
        if fault is None:
            return self._fail("expect_fault: no <Fault> in response")
        if fault_code:
            code = _find_local_text(fault, "faultcode") or ""
            if fault_code not in code:
                self._fail(f"expect_fault: want code {fault_code!r}, got {code!r}")
        return self

    def extract(self, xpath_expr: str, name: str) -> "SOAPStep":
        if not self._ensure_sent():
            return self
        got = self._eval_xpath(xpath_expr)
        if got is None:
            return self._fail(f"extract {xpath_expr}: no match")
        self._t.set_var(name, got)
        return self

    def response_body(self) -> bytes:
        self._ensure_sent()
        return self._resp.content if self._resp else b""

    def done(self) -> Tester:
        self._commit()
        self._t._clear_pending(self)
        return self._t

    def _fail(self, msg: str) -> "SOAPStep":
        self._failures.append(msg)
        return self

    def _eval_xpath(self, expr: str) -> Optional[str]:
        if self._doc is None:
            return None
        # Translate Go-style local-name() probes into xml.etree's
        # namespace-agnostic {*} form so tests stay portable.
        norm = _normalize_xpath(expr)
        try:
            node = self._doc.find(norm)
        except (SyntaxError, KeyError):
            return None
        if node is None:
            return None
        text = (node.text or "").strip()
        return text

    def _ensure_sent(self) -> bool:
        if self._sent:
            return not self._abort
        self._sent = True
        if self._t._should_abort():
            self._abort = True
            return self._fail("skipped: fail-fast triggered by earlier step")._abort  # type: ignore

        url = self._endpoint
        if not url.startswith(("http://", "https://")):
            if self._t.base_url:
                if not url.startswith("/"):
                    url = "/" + url
                url = self._t.base_url + url

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": self._action,
            **self._t._default_headers,
            **self._headers,
        }
        try:
            self._started_at = time.time()
            self._resp = self._t._http.request(
                "POST",
                url,
                headers=headers,
                content=self._body.encode("utf-8"),
            )
            self._ended_at = time.time()
        except Exception as e:
            self._ended_at = time.time()
            self._fail(f"soap: {e}")
            self._abort = True
            return False
        try:
            self._doc = ET.fromstring(self._resp.content)
        except ET.ParseError as e:
            self._fail(f"soap: parse XML: {e}")
            return True
        return True

    def _commit(self) -> None:
        if self._committed:
            return
        self._committed = True
        if not self._sent:
            self._ensure_sent()
        rec = StepRecord(
            protocol="soap",
            method="POST",
            name=f"soap {self._action}",
            url=self._endpoint,
            status_or_code=self._resp.status_code if self._resp else 0,
            started_at=self._started_at,
            ended_at=self._ended_at,
            failures=list(self._failures),
        )
        self._t._record_step(rec)


# Pattern matching the Go-style probe so we can rewrite for xml.etree.
# Example: //*[local-name()='Body']/*[local-name()='Tag']/text() →
# .//{*}Body/{*}Tag (etree picks text via .text on the matched node).
_LOCAL_NAME_RE = re.compile(r"\*\[local-name\(\)='([^']+)'\]")


def _normalize_xpath(expr: str) -> str:
    if "local-name()" in expr:
        # Translate each `*[local-name()='X']` → `{*}X`
        out = _LOCAL_NAME_RE.sub(r"{*}\1", expr)
        # Strip `/text()` — etree returns the node, .text gives the value.
        if out.endswith("/text()"):
            out = out[: -len("/text()")]
        # Strip leading // → .// for etree's relative search.
        if out.startswith("//"):
            out = "." + out
        return out
    return expr


def _find_local(root: ET.Element, local_name: str) -> Optional[ET.Element]:
    return root.find(f".//{{*}}{local_name}")


def _find_local_text(root: ET.Element, local_name: str) -> Optional[str]:
    node = _find_local(root, local_name)
    if node is None:
        return None
    return (node.text or "").strip()
