# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Shared logic for sync and async Mockarty clients."""

from __future__ import annotations

import json
import os
from typing import Any, NoReturn
from uuid import UUID

import httpx

from mockarty.errors import (
    MockartyAPIError,
    MockartyConflictError,
    MockartyConnectionError,
    MockartyExternalError,
    MockartyForbiddenError,
    MockartyNotFoundError,
    MockartyRateLimitError,
    MockartyServerError,
    MockartyTimeoutError,
    MockartyUnauthorizedError,
    MockartyUnavailableError,
    MockartyValidationError,
)

# Maps the server's stable "code" field to a specific exception class. This is
# the primary dispatch path — the HTTP status is only used as a fallback for
# legacy servers that don't yet emit the code field.
_CODE_EXCEPTION_MAP: dict[str, type[MockartyAPIError]] = {
    "validation": MockartyValidationError,
    "unauthorized": MockartyUnauthorizedError,
    "forbidden": MockartyForbiddenError,
    "not_found": MockartyNotFoundError,
    "conflict": MockartyConflictError,
    "rate_limit": MockartyRateLimitError,
    "unavailable": MockartyUnavailableError,
    "external": MockartyExternalError,
    "internal": MockartyServerError,
}

# Fallback mapping by HTTP status code, used when the server's response does
# not carry a "code" field (older servers, unrecognized 4xx/5xx).
_STATUS_EXCEPTION_MAP: dict[int, type[MockartyAPIError]] = {
    400: MockartyValidationError,
    401: MockartyUnauthorizedError,
    403: MockartyForbiddenError,
    404: MockartyNotFoundError,
    409: MockartyConflictError,
    429: MockartyRateLimitError,
    502: MockartyExternalError,
    503: MockartyUnavailableError,
}

DEFAULT_BASE_URL = "http://localhost:5770"
DEFAULT_NAMESPACE = "sandbox"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3


def resolve_base_url(base_url: str | None) -> str:
    """Resolve the base URL from the argument or the environment."""
    if base_url is not None:
        return base_url.rstrip("/")
    return os.environ.get("MOCKARTY_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def resolve_api_key(api_key: str | None) -> str | None:
    """Resolve the API key from the argument or the environment."""
    if api_key is not None:
        return api_key
    return os.environ.get("MOCKARTY_API_KEY")


def build_headers(api_key: str | None, namespace: str) -> dict[str, str]:
    """Build default headers for every request."""
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Namespace": namespace,
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _comment_capture_id(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = UUID(value)
        return parsed.int != 0 and str(parsed) == value
    except ValueError:
        return False


def _comment_capture_metadata(response: httpx.Response) -> dict[str, str]:
    """Retain opaque handles, never authority, only from the exact error shape."""
    if response.status_code != 503 or len(response.content) > 2048:
        return {}

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate capture error key")
            result[key] = value
        return result

    try:
        body = json.loads(response.content, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError):
        return {}
    required = {"error", "state", "operation_id", "capture_id"}
    if not isinstance(body, dict) or set(body) not in (required, required | {"code"}):
        return {}
    if (
        body["error"] != "collaboration_capture_outcome_unknown"
        or body["state"] != "unknown"
        or body.get("code", "") not in ("", "unavailable")
        or not _comment_capture_id(body["operation_id"])
        or not _comment_capture_id(body["capture_id"])
    ):
        return {}
    return {"operation_id": body["operation_id"], "capture_id": body["capture_id"], "state": "unknown"}


def raise_for_status(response: httpx.Response) -> None:
    """Inspect an httpx response and raise the appropriate SDK exception.

    Parses the uniform error envelope emitted by Mockarty::

        {"error": "human message", "code": "not_found", "request_id": "..."}

    When the ``code`` field is present it drives exception dispatch; otherwise
    the HTTP status is used as a fallback. ``request_id`` from the body wins
    over the ``X-Request-Id`` header (both should match, but the body is the
    canonical source in the new envelope).
    """
    if response.is_success:
        return

    status = response.status_code
    request_id: str | None = response.headers.get("X-Request-Id")
    code: str | None = None
    reason: str | None = None
    run_id: str | None = None
    message: str
    capture_metadata = _comment_capture_metadata(response)

    # Try to parse the JSON error envelope. Fall back to raw text if the body
    # is not JSON or is empty (old servers, transport-level errors).
    try:
        body = response.json()
        if isinstance(body, dict):
            message = body.get("error") or body.get("message") or response.text
            raw_reason = body.get("reason")
            if isinstance(raw_reason, str) and raw_reason:
                reason = raw_reason
            raw_run_id = body.get("runId")
            if isinstance(raw_run_id, str) and raw_run_id:
                run_id = raw_run_id
            raw_code = body.get("code")
            if isinstance(raw_code, str) and raw_code:
                code = raw_code
            body_req_id = body.get("request_id")
            if isinstance(body_req_id, str) and body_req_id:
                request_id = body_req_id
        else:
            message = response.text or f"HTTP {status}"
    except Exception:
        message = response.text or f"HTTP {status}"

    # Primary dispatch: by stable code field.
    if code:
        exc_cls = _CODE_EXCEPTION_MAP.get(code)
        if exc_cls is not None:
            raise exc_cls(
                status_code=status,
                message=message,
                request_id=request_id,
                code=code,
                reason=reason,
                run_id=run_id,
                **capture_metadata,
            )

    # Fallback: by HTTP status.
    exc_cls = _STATUS_EXCEPTION_MAP.get(status)
    if exc_cls is not None:
        raise exc_cls(
            status_code=status,
            message=message,
            request_id=request_id,
            code=code,
            reason=reason,
            run_id=run_id,
            **capture_metadata,
        )

    if status >= 500:
        raise MockartyServerError(
            status_code=status,
            message=message,
            request_id=request_id,
            code=code,
            reason=reason,
            run_id=run_id,
            **capture_metadata,
        )

    raise MockartyAPIError(
        status_code=status,
        message=message,
        request_id=request_id,
        code=code,
        reason=reason,
        run_id=run_id,
        **capture_metadata,
    )


def wrap_transport_error(exc: Exception) -> NoReturn:
    """Convert an httpx transport error into the matching SDK exception.

    Always raises — the return annotation is ``NoReturn`` so static
    analysers know callers that propagate via ``raise
    wrap_transport_error(...)`` can't reach a missing-return branch.
    Removes the previous ``type: ignore[return]`` hack.
    """
    if isinstance(exc, httpx.TimeoutException):
        raise MockartyTimeoutError(str(exc)) from exc
    if isinstance(exc, httpx.ConnectError):
        raise MockartyConnectionError(str(exc)) from exc
    if isinstance(exc, (httpx.HTTPStatusError, httpx.HTTPError)):
        raise MockartyConnectionError(str(exc)) from exc
    raise MockartyConnectionError(str(exc)) from exc


def build_transport(max_retries: int) -> httpx.HTTPTransport:
    """Build an httpx transport with retry configuration."""
    return httpx.HTTPTransport(retries=max_retries)


def build_async_transport(max_retries: int) -> httpx.AsyncHTTPTransport:
    """Build an async httpx transport with retry configuration."""
    return httpx.AsyncHTTPTransport(retries=max_retries)


def serialize_body(obj: Any) -> Any:
    """Serialize a Pydantic model or dict to a JSON-compatible dict."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True, exclude_none=True)
    return obj
