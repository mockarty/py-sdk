# Copyright (c) 2026 Mockarty. All rights reserved.

"""Provider-side pact verifier.

Replays consumer-published pact interactions against a real provider
service, matches the actual response against the recorded expectation,
and (optionally) publishes the verification result back to a broker.

Designed to feel identical to the Go SDK ``pact.Verifier`` and the
Java SDK ``ru.mockarty.pact.verifier.Verifier``.

Quick start::

    from mockarty.pact import BrokerClient, Verifier

    def setup_user(state, params):
        # Seed the real DB so the interaction's expected response is reachable.
        db.users.insert({"id": params.get("id", 42)})

    broker = BrokerClient()
    verifier = (
        Verifier(provider_url="http://localhost:8080",
                 provider_name="OrderAPI",
                 provider_version=os.environ["GIT_COMMIT"])
        .with_broker(broker)
        .with_state_handler("user exists", setup_user)
    )
    result = verifier.verify_from_broker("OrderClient", "OrderAPI", "latest")
    assert result.ok, [ir.mismatches for ir in result.interactions if not ir.passed]
    verifier.publish_results("OrderClient", "OrderAPI", "1.0", result)
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import os
from typing import Any, Callable, Mapping

try:
    import urllib3
except ImportError as e:  # pragma: no cover
    raise ImportError("mockarty.pact.verifier requires urllib3") from e

from mockarty.pact.broker import BrokerClient
from mockarty.pact.matchers import Matcher


StateHandler = Callable[[str, Mapping[str, Any]], None]
RequestFilter = Callable[[dict[str, Any]], None]
"""Mutates a request dict in-place before the verifier sends it.

The dict has keys: ``method`` (str), ``url`` (str), ``headers``
(dict[str,str]), ``body`` (bytes or None). Returning is ignored — only
mutations are applied.
"""


@dataclasses.dataclass
class Mismatch:
    """A single per-field mismatch between expected and actual."""

    path: str
    reason: str
    expected: Any = None
    actual: Any = None


@dataclasses.dataclass
class InteractionResult:
    description: str
    state: str = ""
    status_code: int = 0
    passed: bool = False
    error: str = ""
    mismatches: list[Mismatch] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class VerificationResult:
    provider: str = ""
    started_at: _dt.datetime = dataclasses.field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc))
    finished_at: _dt.datetime | None = None
    interactions: list[InteractionResult] = dataclasses.field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` iff every interaction passed.

        An empty interaction list is vacuously ``True`` — matches the
        Go + Java SDK semantics, so a pact with no interactions does
        not fail the CI gate. Use ``not self.interactions`` to detect
        the empty case explicitly when you care.
        """
        return all(ir.passed for ir in self.interactions)


class Verifier:
    """Pact provider verifier — see module docstring for usage."""

    def __init__(
        self,
        *,
        provider_url: str,
        provider_name: str = "",
        provider_version: str = "",
        provider_branch: str = "",
        timeout: float = 30.0,
        pool: urllib3.PoolManager | None = None,
    ) -> None:
        if not provider_url.strip():
            raise ValueError("provider_url is required")
        self.provider_url = provider_url.rstrip("/")
        self.provider_name = provider_name
        self.provider_version = provider_version
        self.provider_branch = provider_branch
        self.timeout = timeout
        self._pool = pool or urllib3.PoolManager()
        self._state_handlers: dict[str, StateHandler] = {}
        self._state_setup_url: str = ""
        self._broker: BrokerClient | None = None
        self._request_filter: RequestFilter | None = None
        self._message_producers: dict[str, Any] = {}
        self._strict_states: bool = False

    # ------------------------------------------------------------------
    # fluent config
    # ------------------------------------------------------------------

    def with_state_handler(self, state: str, fn: StateHandler) -> Verifier:
        self._state_handlers[state] = fn
        return self

    def with_state_setup_url(self, url: str) -> Verifier:
        self._state_setup_url = url
        return self

    def with_broker(self, broker: BrokerClient) -> Verifier:
        self._broker = broker
        return self

    def with_request_filter(self, fn: RequestFilter) -> Verifier:
        self._request_filter = fn
        return self

    def with_strict_states(self, strict: bool = True) -> Verifier:
        """When enabled, a provider-state with no registered handler
        AND no configured ``with_state_setup_url`` is treated as a
        verification failure (typo / forgot-to-wire detector). Default
        is OFF — pact V3 allows informational states.
        """
        self._strict_states = strict
        return self

    def with_message_producer(
        self, description: str,
        fn: Callable[[str, list[dict[str, Any]]], tuple[bytes, Mapping[str, str]]],
    ) -> Verifier:
        """Register a per-description message producer for message-pact
        verification. The verifier calls ``fn(description, states)`` and
        expects ``(bytes, metadata)``; bytes are matched against the
        recorded message contents.
        """
        self._message_producers[description] = fn
        return self

    def verify_message_pact_bytes(self, raw: bytes) -> VerificationResult:
        """Verify a message-pact (Asynchronous/Messages) document."""
        from mockarty.pact.message import parse_message_pact_doc

        out = VerificationResult(provider=self.provider_name)
        messages = parse_message_pact_doc(raw)
        for msg in messages:
            ir = InteractionResult(description=msg.description)
            if msg.states:
                ir.state = str(msg.states[0].get("name", ""))
            try:
                for st in msg.states:
                    self._setup_state(st)
            except Exception as e:  # noqa: BLE001
                ir.error = f"state setup: {e}"
                out.interactions.append(ir)
                continue
            producer = self._message_producers.get(msg.description)
            if producer is None:
                ir.error = f"no MessageProducer registered for description {msg.description!r}"
                out.interactions.append(ir)
                continue
            try:
                body, _meta = producer(msg.description, msg.states)
            except Exception as e:  # noqa: BLE001
                ir.error = f"producer: {e}"
                out.interactions.append(ir)
                continue
            ir.mismatches = _body_mismatches(msg.content, body)
            ir.passed = not ir.mismatches
            out.interactions.append(ir)
        out.finished_at = _dt.datetime.now(_dt.timezone.utc)
        return out

    # ------------------------------------------------------------------
    # entry points
    # ------------------------------------------------------------------

    def verify_pact_bytes(self, raw: bytes) -> VerificationResult:
        from mockarty.pact.message import MESSAGE_INTERACTION_TYPE

        doc = _parse_pact_doc(raw)
        # Filter out V4 Asynchronous/Messages — those go through
        # verify_message_pact_bytes(). Treat missing/empty `type` as
        # HTTP (V3 docs have no type discriminator).
        http_only = [
            ix for ix in doc["interactions"]
            if str(ix.get("type", "")) != MESSAGE_INTERACTION_TYPE
        ]
        return self._verify_interactions(http_only)

    def verify_pact_file(self, path: str | os.PathLike[str]) -> VerificationResult:
        with open(path, "rb") as f:
            return self.verify_pact_bytes(f.read())

    def verify_from_broker(self, consumer: str, provider: str, version: str) -> VerificationResult:
        if self._broker is None:
            raise RuntimeError("verify_from_broker requires .with_broker(...)")
        body = self._broker.fetch(consumer, provider, version)
        return self.verify_pact_bytes(body)

    def publish_results(
        self,
        consumer: str,
        provider: str,
        version: str,
        result: VerificationResult,
    ) -> None:
        if self._broker is None:
            raise RuntimeError("publish_results requires .with_broker(...)")
        if not self.provider_version:
            raise RuntimeError("publish_results requires provider_version")
        payload: dict[str, Any] = {
            "success": result.ok,
            "providerApplicationVersion": self.provider_version,
            "verifiedBy": {
                "implementation": "mockarty-py-sdk",
                "version": "1",
            },
            "testResults": [_serialise_interaction(ir) for ir in result.interactions],
        }
        if self.provider_branch:
            payload["branch"] = self.provider_branch
        path = (
            f"/pacts/provider/{_quote(provider)}"
            f"/consumer/{_quote(consumer)}"
            f"/pact-version/{_quote(version)}/verification-results"
        )
        url = self._broker.base_url + path
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self._broker.auth_headers(),
        }
        resp = self._pool.request(
            "POST", url, body=body, headers=headers, timeout=self.timeout
        )
        if resp.status >= 400:
            raise RuntimeError(
                f"publish_results: HTTP {resp.status}: "
                f"{resp.data.decode('utf-8', errors='replace')}"
            )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _verify_interactions(self, interactions: list[dict[str, Any]]) -> VerificationResult:
        out = VerificationResult(provider=self.provider_name)
        for ix in interactions:
            out.interactions.append(self._verify_one(ix))
        out.finished_at = _dt.datetime.now(_dt.timezone.utc)
        return out

    def _verify_one(self, ix: dict[str, Any]) -> InteractionResult:
        ir = InteractionResult(description=str(ix.get("description", "")))
        states = ix.get("providerStates")
        if not isinstance(states, list):
            single = ix.get("providerState")
            if isinstance(single, str) and single:
                states = [{"name": single, "params": {}}]
            else:
                states = []
        if states:
            ir.state = str(states[0].get("name", ""))
        try:
            for st in states:
                self._setup_state(st)
        except Exception as e:  # noqa: BLE001 — surface as interaction error
            ir.error = f"state setup: {e}"
            return ir

        req = ix.get("request") or {}
        method = str(req.get("method", "GET")).upper()
        path = str(req.get("path", "/"))
        query_str = _build_query(req.get("query"))
        url = self.provider_url + path + (("?" + query_str) if query_str else "")
        headers = _flatten_headers(req.get("headers"))
        body_bytes = _body_to_bytes(req.get("body"))
        if body_bytes is not None and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        request_dict = {
            "method": method,
            "url": url,
            "headers": headers,
            "body": body_bytes,
        }
        if self._request_filter is not None:
            try:
                self._request_filter(request_dict)
            except Exception as e:  # noqa: BLE001
                ir.error = f"request filter: {e}"
                return ir

        try:
            resp = self._pool.request(
                request_dict["method"],
                request_dict["url"],
                body=request_dict["body"],
                headers=request_dict["headers"],
                timeout=self.timeout,
                redirect=False,
            )
        except Exception as e:  # noqa: BLE001
            ir.error = f"transport: {e}"
            return ir

        ir.status_code = resp.status
        expected = ix.get("response") or {}
        ir.mismatches = _compare_response(expected, resp.status, resp.headers, resp.data)
        ir.passed = not ir.mismatches and not ir.error
        return ir

    def _setup_state(self, state: dict[str, Any]) -> None:
        name = str(state.get("name", ""))
        params = state.get("params") or {}
        handler = self._state_handlers.get(name)
        if handler is not None:
            handler(name, params)
            return
        if self._state_setup_url:
            body = json.dumps({"state": name, "params": params, "action": "setup"}).encode()
            resp = self._pool.request(
                "POST",
                self._state_setup_url,
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            if resp.status >= 400:
                raise RuntimeError(
                    f"state-setup HTTP {resp.status}: "
                    f"{resp.data.decode('utf-8', errors='replace')}"
                )
            return
        if self._strict_states:
            raise RuntimeError(
                f"no handler or state-setup URL configured for "
                f"providerState {name!r} (strict mode)"
            )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _parse_pact_doc(raw: bytes) -> dict[str, Any]:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"pact is not valid JSON: {e}") from e
    if not isinstance(doc, dict):
        raise ValueError("pact root must be a JSON object")
    interactions = doc.get("interactions")
    if not isinstance(interactions, list):
        interactions = []
    # Coerce non-dict interaction entries into empty dicts so the
    # verifier surfaces them as failed rather than crashing.
    coerced = [ix if isinstance(ix, dict) else {} for ix in interactions]
    return {"interactions": coerced}


def _resolve_matchers(v: Any) -> Any:
    if isinstance(v, Matcher):
        return _resolve_matchers(v.example)
    if isinstance(v, dict):
        return {k: _resolve_matchers(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_resolve_matchers(x) for x in v]
    return v


def _flatten_headers(h: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(h, dict):
        return out
    for k, v in h.items():
        if isinstance(v, str):
            out[str(k)] = v
        elif isinstance(v, list):
            out[str(k)] = ",".join(str(x) for x in v if isinstance(x, str))
    return out


def _build_query(q: Any) -> str:
    if not q:
        return ""
    from urllib.parse import urlencode

    pairs: list[tuple[str, str]] = []
    if isinstance(q, dict):
        for k, v in q.items():
            if isinstance(v, list):
                for item in v:
                    pairs.append((str(k), str(item)))
            else:
                pairs.append((str(k), str(v)))
    elif isinstance(q, str):
        return q  # caller pre-encoded
    return urlencode(pairs)


def _body_to_bytes(b: Any) -> bytes | None:
    if b is None:
        return None
    if isinstance(b, bytes):
        return b
    if isinstance(b, str):
        return b.encode("utf-8")
    return json.dumps(_resolve_matchers(b)).encode("utf-8")


def _compare_response(
    expected: Mapping[str, Any],
    actual_status: int,
    actual_headers: Mapping[str, str],
    actual_body: bytes,
) -> list[Mismatch]:
    miss: list[Mismatch] = []
    exp_status = expected.get("status")
    if isinstance(exp_status, (int, float)) and int(exp_status) != actual_status:
        miss.append(Mismatch(
            path="$.status", reason="status mismatch",
            expected=int(exp_status), actual=actual_status,
        ))
    exp_headers = expected.get("headers") or {}
    if isinstance(exp_headers, dict):
        for k, v in exp_headers.items():
            actual_val = _header_lookup(actual_headers, str(k))
            if not actual_val:
                miss.append(Mismatch(
                    path=f"$.headers.{k}", reason="expected header missing",
                    expected=v, actual=None,
                ))
                continue
            wanted = [v] if isinstance(v, str) else [str(x) for x in v if isinstance(x, str)]
            for w in wanted:
                if w not in actual_val:
                    miss.append(Mismatch(
                        path=f"$.headers.{k}", reason="header value mismatch",
                        expected=w, actual=actual_val,
                    ))
    if "body" in expected and expected["body"] is not None:
        miss.extend(_body_mismatches(expected["body"], actual_body))
    return miss


def _header_lookup(h: Mapping[str, str], key: str) -> str:
    for k, v in h.items():
        if k.lower() == key.lower():
            return v
    return ""


def _body_mismatches(expected: Any, actual_bytes: bytes) -> list[Mismatch]:
    if not actual_bytes:
        return [Mismatch(path="$.body", reason="empty body where one was expected",
                         expected=expected, actual=None)]
    try:
        actual = json.loads(actual_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return [Mismatch(path="$.body", reason=f"actual body is not valid JSON: {e}",
                         expected=expected, actual=actual_bytes.decode("utf-8", errors="replace"))]
    result: list[Mismatch] = []
    _strict_match(_resolve_matchers(expected), actual, "$.body", result)
    return result


def _strict_match(expected: Any, actual: Any, path: str, out: list[Mismatch]) -> None:
    if isinstance(expected, Matcher):
        expected = _resolve_matchers(expected)
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            out.append(Mismatch(path=path, reason="expected object",
                                expected=expected, actual=actual))
            return
        for k, ev in expected.items():
            sub = f"{path}.{k}"
            if k not in actual:
                out.append(Mismatch(path=sub, reason="key missing",
                                    expected=ev, actual=None))
                continue
            _strict_match(ev, actual[k], sub, out)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            out.append(Mismatch(path=path, reason="expected array",
                                expected=expected, actual=actual))
            return
        if len(expected) != len(actual):
            out.append(Mismatch(path=path, reason="array length mismatch",
                                expected=len(expected), actual=len(actual)))
            return
        for i, ev in enumerate(expected):
            _strict_match(ev, actual[i], f"{path}[{i}]", out)
        return
    if expected != actual:
        out.append(Mismatch(path=path, reason="value mismatch",
                            expected=expected, actual=actual))


def _serialise_interaction(ir: InteractionResult) -> dict[str, Any]:
    row: dict[str, Any] = {
        "interactionDescription": ir.description,
        "success": ir.passed,
    }
    if ir.state:
        row["providerState"] = ir.state
    if ir.error:
        row["error"] = ir.error
    if ir.mismatches:
        row["mismatches"] = [
            {
                "path": m.path, "reason": m.reason,
                "expected": m.expected, "actual": m.actual,
            }
            for m in ir.mismatches
        ]
    return row


def _quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


__all__ = [
    "InteractionResult",
    "Mismatch",
    "RequestFilter",
    "StateHandler",
    "VerificationResult",
    "Verifier",
]
