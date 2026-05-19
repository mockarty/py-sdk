"""GraphQL test client with auto-step capture.

Standard GraphQL-over-HTTP shape: POST a JSON envelope
``{"query": "...", "variables": {...}, "operationName": "..."}`` to
``/graphql`` (or whatever the user supplied). Response is
``{"data": ..., "errors": [...]}``; we treat any ``errors[]`` entry
as a failed step even when HTTP returned 200.
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from typing import Any, Optional

import httpx

from .telemetry import NopRecorder, Step, StepRecorder, new_step_key


class GraphQLError(RuntimeError):
    """Raised when the GraphQL response contains a non-empty ``errors``
    array AND the caller asked for ``raise_for_errors=True``. The
    original ``errors`` list is available on :attr:`errors`."""

    def __init__(self, errors: list[dict[str, Any]]):
        self.errors = errors
        message = errors[0].get("message", "graphql error") if errors else "graphql error"
        super().__init__(message)


class GraphQLResponse:
    """Parsed GraphQL response."""

    def __init__(self, status_code: int, data: Any, errors: list[dict[str, Any]], extensions: dict[str, Any]):
        self.status_code = status_code
        self.data = data
        self.errors = errors
        self.extensions = extensions

    @property
    def ok(self) -> bool:
        return self.status_code < 400 and not self.errors


class GraphQLClient:
    """Sync GraphQL client.

    Parameters
    ----------
    url:
        GraphQL endpoint (e.g. ``"http://localhost:5770/graphql"``).
    headers:
        Default headers applied to every request (e.g. ``Authorization``).
    recorder:
        Optional step recorder.
    timeout, payload_cap:
        See :class:`mockarty.protocols.soap.SoapClient` for semantics.
    client:
        Optional pre-built :class:`httpx.Client`. When supplied the
        SDK does not own its lifecycle.
    """

    def __init__(
        self,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        recorder: Optional[StepRecorder] = None,
        timeout: float = 30.0,
        payload_cap: int = 1024,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not url:
            raise ValueError("mockarty graphql: empty url")
        self._url = url
        self._headers = dict(headers or {})
        self._recorder = recorder if recorder is not None else NopRecorder()
        self._payload_cap = max(0, payload_cap)
        self._owned_client = client is None
        self._client = client or httpx.Client(timeout=timeout)
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._owned_client and self._client is not None:
            self._client.close()

    def __enter__(self) -> "GraphQLClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def execute(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        *,
        raise_for_errors: bool = False,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> GraphQLResponse:
        """POST a GraphQL document.

        When ``raise_for_errors=True``, a non-empty ``errors`` array
        raises :class:`GraphQLError`. Otherwise the caller inspects
        ``response.errors`` directly.
        """
        if not query:
            raise ValueError("mockarty graphql: empty query")
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        if operation_name:
            body["operationName"] = operation_name
        op_label = operation_name or _extract_operation_name(query) or "anonymous"
        step_name = f"graphql:{op_label}"
        headers = {"Content-Type": "application/json", **self._headers}
        if extra_headers:
            headers.update(extra_headers)
        body_bytes = json.dumps(body).encode("utf-8")

        started = time.time()
        try:
            resp = self._client.post(self._url, content=body_bytes, headers=headers)
        except httpx.HTTPError as exc:
            self._record(step_name, started, "broken", exc, {"operation": op_label})
            raise

        finished = time.time()
        try:
            parsed = resp.json() if resp.content else {}
        except json.JSONDecodeError as exc:
            self._record(step_name, started, "broken", exc, {
                "operation": op_label,
                "http_status": str(resp.status_code),
                "response": _truncate(resp.text, self._payload_cap),
            }, finished=finished)
            raise

        errors = parsed.get("errors") or []
        if not isinstance(errors, list):
            errors = []
        data = parsed.get("data")
        extensions = parsed.get("extensions") or {}

        status = "passed"
        message = ""
        if resp.status_code >= 400:
            status = "failed"
            message = f"HTTP {resp.status_code}"
        elif errors:
            status = "failed"
            message = errors[0].get("message", "graphql error") if isinstance(errors[0], dict) else "graphql error"

        params = {
            "operation": op_label,
            "http_status": str(resp.status_code),
            "request": _truncate(body_bytes, self._payload_cap),
            "response": _truncate(resp.text, self._payload_cap),
            "error_count": str(len(errors)),
        }
        self._record(step_name, started, status, None if status == "passed" else RuntimeError(message), params, finished=finished)

        response = GraphQLResponse(
            status_code=resp.status_code,
            data=data,
            errors=errors,
            extensions=extensions if isinstance(extensions, dict) else {},
        )
        if raise_for_errors and errors:
            raise GraphQLError(errors)
        return response

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


def _extract_operation_name(query: str) -> Optional[str]:
    """Best-effort: pull the operation name out of a GraphQL document.

    Skips leading whitespace + comments, then expects
    ``query|mutation|subscription <Name>``. Returns ``None`` for
    anonymous queries — the caller falls back to ``"anonymous"``.
    """
    if not query:
        return None
    lines = []
    for raw in query.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
        if len(lines) > 3:
            break
    if not lines:
        return None
    head = lines[0]
    for keyword in ("query", "mutation", "subscription"):
        if head.startswith(keyword + " "):
            rest = head[len(keyword) + 1:].strip()
            name = ""
            for ch in rest:
                if ch.isalnum() or ch == "_":
                    name += ch
                else:
                    break
            return name or None
    return None


def _truncate(data: Any, cap: int) -> str:
    if cap == 0:
        return ""
    if isinstance(data, bytes):
        s = data.decode("utf-8", errors="replace")
    else:
        s = str(data)
    if len(s) <= cap:
        return s
    return s[:cap] + f"…(truncated {len(s) - cap}B)"
