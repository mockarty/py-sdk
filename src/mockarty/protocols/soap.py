"""SOAP test client with auto-step capture.

Wire shape — SOAP 1.1 over HTTP POST::

    POST /endpoint HTTP/1.1
    Content-Type: text/xml; charset=utf-8
    SOAPAction: "{soap_action}"

    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>{body_xml}</soap:Body>
    </soap:Envelope>

The client wraps :class:`httpx.Client`; one client → one base URL +
default SOAPAction style. SOAP 1.2 (``application/soap+xml``) is
selected via :paramref:`SoapClient.version`. Air-gapped — uses stdlib
``xml.etree`` for response parsing; no lxml dependency.
"""

from __future__ import annotations

import itertools
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Optional

import httpx

from .telemetry import NopRecorder, Step, StepRecorder, cap_preview, new_step_key

_SOAP11_NS = "http://schemas.xmlsoap.org/soap/envelope/"
_SOAP12_NS = "http://www.w3.org/2003/05/soap-envelope"


class SoapResponse:
    """Parsed SOAP response. The body is exposed both as raw bytes and
    as an :class:`xml.etree.ElementTree.Element` so callers can mix
    raw assertions with XPath-style descents."""

    def __init__(self, status_code: int, headers: dict[str, str], body: bytes, fault: Optional[dict[str, str]]):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.fault = fault

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def root(self) -> Optional[ET.Element]:
        if not self.body:
            return None
        try:
            return ET.fromstring(self.body)
        except ET.ParseError:
            return None


class SoapClient:
    """Sync SOAP 1.1 / 1.2 client.

    Parameters
    ----------
    base_url:
        Endpoint URL the envelope is POSTed to.
    soap_action:
        Default ``SOAPAction`` header. Per-call ``call(...)`` can override.
    version:
        ``"1.1"`` (default) or ``"1.2"``.
    recorder:
        Optional step recorder. ``None`` → :class:`NopRecorder`.
    timeout:
        Per-request timeout (seconds). Default 30.
    payload_cap:
        Max bytes of request/response captured into step parameters.
        Default 1024.
    """

    def __init__(
        self,
        base_url: str,
        *,
        soap_action: str = "",
        version: str = "1.1",
        recorder: Optional[StepRecorder] = None,
        timeout: float = 30.0,
        payload_cap: int = 1024,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not base_url:
            raise ValueError("mockarty soap: empty base_url")
        if version not in ("1.1", "1.2"):
            raise ValueError("mockarty soap: version must be '1.1' or '1.2'")
        self._base_url = base_url
        self._soap_action = soap_action
        self._version = version
        self._recorder = recorder if recorder is not None else NopRecorder()
        self._payload_cap = max(0, payload_cap)
        self._owned_client = client is None
        self._client = client or httpx.Client(timeout=timeout)
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def close(self) -> None:
        """Close the underlying httpx client if this SoapClient owns it."""
        if self._owned_client and self._client is not None:
            self._client.close()

    def __enter__(self) -> "SoapClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    @property
    def base_url(self) -> str:
        return self._base_url

    def call(
        self,
        operation: str,
        body_xml: str,
        *,
        soap_action: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> SoapResponse:
        """Send one SOAP call.

        ``body_xml`` is the inner XML that gets wrapped in
        ``<soap:Envelope><soap:Body>…</soap:Body></soap:Envelope>``.
        Pass the operation element + namespaces directly; the
        client does not introspect WSDL.

        On HTTP non-2xx OR on a SOAP Fault inside the envelope, the
        recorded step is ``"failed"`` with the fault string. Network
        errors are ``"broken"``.
        """
        envelope = _wrap_envelope(body_xml, self._version)
        action = soap_action if soap_action is not None else self._soap_action
        content_type = "text/xml; charset=utf-8" if self._version == "1.1" else "application/soap+xml; charset=utf-8"
        headers = {"Content-Type": content_type, "SOAPAction": f'"{action}"'} if action else {"Content-Type": content_type}
        if extra_headers:
            headers.update(extra_headers)

        step_name = f"soap:{operation}"
        started = time.time()
        try:
            resp = self._client.post(self._base_url, content=envelope, headers=headers)
        except httpx.HTTPError as exc:
            self._record(step_name, started, "broken", exc, {"operation": operation})
            raise

        finished = time.time()
        body = resp.content
        fault = _extract_fault(body, self._version)
        status = "passed"
        message = ""
        if resp.status_code >= 400:
            status = "failed"
            message = f"HTTP {resp.status_code}"
        if fault:
            status = "failed"
            message = fault.get("string") or fault.get("code") or "soap fault"

        params: dict[str, str] = {
            "operation": operation,
            "http_status": str(resp.status_code),
            "request": cap_preview(envelope, self._payload_cap),
            "response": cap_preview(body, self._payload_cap),
        }
        if fault:
            for k, v in fault.items():
                params[f"fault_{k}"] = v
        self._record(step_name, started, status, None if status == "passed" else Exception(message), params, finished=finished)

        return SoapResponse(
            status_code=resp.status_code,
            headers={k.lower(): v for k, v in resp.headers.items()},
            body=body,
            fault=fault,
        )

    def _record(
        self,
        name: str,
        started: float,
        status: str,
        err: Optional[BaseException],
        params: dict[str, str],
        *,
        finished: Optional[float] = None,
    ) -> None:
        if finished is None:
            finished = time.time()
        with self._lock:
            seq = next(self._counter)
        step = Step(
            key=new_step_key(name, seq),
            name=name,
            status=status,
            started_at=started,
            finished_at=finished,
            duration_ms=max(0, int((finished - started) * 1000)),
            parameters=params,
            message=str(err) if err else "",
        )
        self._recorder.record(step)


def _wrap_envelope(body_xml: str, version: str) -> bytes:
    ns = _SOAP11_NS if version == "1.1" else _SOAP12_NS
    envelope = (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<soap:Envelope xmlns:soap="{ns}">'
        f"<soap:Body>{body_xml}</soap:Body>"
        f"</soap:Envelope>"
    )
    return envelope.encode("utf-8")


def _extract_fault(body: bytes, version: str) -> Optional[dict[str, str]]:
    if not body:
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    ns = _SOAP11_NS if version == "1.1" else _SOAP12_NS
    fault = root.find(f".//{{{ns}}}Fault")
    if fault is None:
        return None
    out: dict[str, str] = {}
    if version == "1.1":
        code = fault.find("faultcode")
        if code is not None and code.text:
            out["code"] = code.text
        s = fault.find("faultstring")
        if s is not None and s.text:
            out["string"] = s.text
    else:
        code = fault.find(f"{{{ns}}}Code/{{{ns}}}Value")
        if code is not None and code.text:
            out["code"] = code.text
        reason = fault.find(f"{{{ns}}}Reason/{{{ns}}}Text")
        if reason is not None and reason.text:
            out["string"] = reason.text
    if not out:
        # Fault element exists but had no children we recognise —
        # surface a synthetic marker the caller can still pattern-
        # match on without lying about a missing code/reason. The
        # previous {"code": "fault"} dict masqueraded as a real
        # fault code in step.parameters, which review flagged.
        return {"empty_fault": "1"}
    return out
