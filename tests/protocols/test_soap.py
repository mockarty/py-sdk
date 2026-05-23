"""Unit tests for mockarty.protocols.soap."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty.protocols.soap import SoapClient
from mockarty.protocols.telemetry import AccumulatingRecorder


SOAP11_OK = (
    '<?xml version="1.0"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soap:Body><GetUserResponse><id>u-1</id></GetUserResponse></soap:Body>"
    "</soap:Envelope>"
).encode()

SOAP11_FAULT = (
    '<?xml version="1.0"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soap:Body><soap:Fault>"
    "<faultcode>Server</faultcode>"
    "<faultstring>bad input</faultstring>"
    "</soap:Fault></soap:Body>"
    "</soap:Envelope>"
).encode()

SOAP12_FAULT = (
    '<?xml version="1.0"?>'
    '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">'
    "<soap:Body><soap:Fault>"
    "<soap:Code><soap:Value>Sender</soap:Value></soap:Code>"
    "<soap:Reason><soap:Text>oops</soap:Text></soap:Reason>"
    "</soap:Fault></soap:Body>"
    "</soap:Envelope>"
).encode()


def test_init_empty_url_rejected():
    with pytest.raises(ValueError):
        SoapClient("")


def test_init_bad_version_rejected():
    with pytest.raises(ValueError):
        SoapClient("http://x", version="2.0")


@respx.mock
def test_call_records_passed_step():
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP11_OK))
    with SoapClient("http://test/svc", soap_action="GetUser", recorder=rec) as cli:
        resp = cli.call("GetUser", "<GetUser><id>u-1</id></GetUser>")
    assert resp.status_code == 200
    assert resp.fault is None
    root = resp.root()
    assert root is not None
    assert rec.steps()[0]["status"] == "passed"
    assert rec.steps()[0]["name"] == "soap:GetUser"
    assert rec.steps()[0]["parameters"]["operation"] == "GetUser"


@respx.mock
def test_call_soap11_fault_marks_failed():
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP11_FAULT))
    with SoapClient("http://test/svc", recorder=rec) as cli:
        resp = cli.call("GetUser", "<GetUser/>")
    assert resp.fault == {"code": "Server", "string": "bad input"}
    s = rec.steps()[0]
    assert s["status"] == "failed"
    assert "bad input" in s["message"]
    assert s["parameters"]["fault_string"] == "bad input"


@respx.mock
def test_call_soap12_fault_parsed():
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP12_FAULT))
    with SoapClient("http://test/svc", version="1.2", recorder=rec) as cli:
        resp = cli.call("GetUser", "<GetUser/>")
    assert resp.fault == {"code": "Sender", "string": "oops"}
    assert rec.steps()[0]["status"] == "failed"


@respx.mock
def test_call_http_500_marks_failed():
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(return_value=httpx.Response(500, content=b""))
    with SoapClient("http://test/svc", recorder=rec) as cli:
        resp = cli.call("X", "<X/>")
    assert resp.status_code == 500
    assert rec.steps()[0]["status"] == "failed"
    assert "HTTP 500" in rec.steps()[0]["message"]


@respx.mock
def test_call_transport_error_marks_broken():
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(side_effect=httpx.ConnectError("boom"))
    with SoapClient("http://test/svc", recorder=rec) as cli:
        with pytest.raises(httpx.ConnectError):
            cli.call("X", "<X/>")
    assert rec.steps()[0]["status"] == "broken"


@respx.mock
def test_call_includes_envelope_in_request():
    route = respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP11_OK))
    with SoapClient("http://test/svc", soap_action="GetUser") as cli:
        cli.call("GetUser", "<GetUser><id>u-1</id></GetUser>")
    sent = route.calls[0].request.read().decode()
    assert "<soap:Envelope" in sent
    assert "<GetUser><id>u-1</id></GetUser>" in sent


@respx.mock
def test_call_content_type_differs_by_version():
    route = respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP11_OK))
    with SoapClient("http://test/svc", version="1.2") as cli:
        cli.call("X", "<X/>")
    assert route.calls[0].request.headers["content-type"].startswith("application/soap+xml")


@respx.mock
def test_call_step_keys_monotonic():
    """Step keys must increment per-call so retries server-side de-dup
    on (namespace, run, step_key). The Go SDK + Java SDK use the same
    `<name>#<seq>` shape — pin it here so the contract holds."""
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP11_OK))
    with SoapClient("http://test/svc", recorder=rec) as cli:
        cli.call("GetUser", "<GetUser/>")
        cli.call("GetUser", "<GetUser/>")
        cli.call("GetUser", "<GetUser/>")
    keys = [s["stepKey"] for s in rec.steps()]
    assert keys == ["soap:GetUser#1", "soap:GetUser#2", "soap:GetUser#3"], keys


SOAP11_EMPTY_FAULT = (
    '<?xml version="1.0"?>'
    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
    "<soap:Body><soap:Fault></soap:Fault></soap:Body>"
    "</soap:Envelope>"
).encode()


@respx.mock
def test_call_empty_fault_uses_synthetic_marker():
    """Review fix: previously a Fault with no children returned
    {'code': 'fault'} — looked like a real fault code 'fault'. The
    fix surfaces {'empty_fault': '1'} so the caller can pattern-match
    without being misled."""
    rec = AccumulatingRecorder()
    respx.post("http://test/svc").mock(return_value=httpx.Response(200, content=SOAP11_EMPTY_FAULT))
    with SoapClient("http://test/svc", recorder=rec) as cli:
        resp = cli.call("X", "<X/>")
    assert resp.fault == {"empty_fault": "1"}
    assert rec.steps()[0]["status"] == "failed"
    assert rec.steps()[0]["parameters"]["fault_empty_fault"] == "1"
