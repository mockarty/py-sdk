# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Shared logic for sync and async Mockarty clients."""

from __future__ import annotations

import os
from typing import Any

import httpx

from mockarty.errors import (
    MockartyAPIError,
    MockartyConflictError,
    MockartyConnectionError,
    MockartyError,
    MockartyForbiddenError,
    MockartyNotFoundError,
    MockartyRateLimitError,
    MockartyServerError,
    MockartyTimeoutError,
    MockartyUnauthorizedError,
)

# Maps HTTP status codes to specific exception classes.
_STATUS_EXCEPTION_MAP: dict[int, type[MockartyAPIError]] = {
    401: MockartyUnauthorizedError,
    403: MockartyForbiddenError,
    404: MockartyNotFoundError,
    409: MockartyConflictError,
    429: MockartyRateLimitError,
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


def raise_for_status(response: httpx.Response) -> None:
    """Inspect an httpx response and raise the appropriate SDK exception."""
    if response.is_success:
        return

    status = response.status_code
    request_id = response.headers.get("X-Request-Id")

    # Try to extract error message from JSON body
    try:
        body = response.json()
        message = body.get("error", response.text)
    except Exception:
        message = response.text or f"HTTP {status}"

    exc_cls = _STATUS_EXCEPTION_MAP.get(status)
    if exc_cls is not None:
        raise exc_cls(status_code=status, message=message, request_id=request_id)

    if status >= 500:
        raise MockartyServerError(
            status_code=status, message=message, request_id=request_id
        )

    raise MockartyAPIError(
        status_code=status, message=message, request_id=request_id
    )


def wrap_transport_error(exc: Exception) -> MockartyError:  # type: ignore[return]
    """Convert httpx transport errors into SDK exceptions."""
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
