# Copyright (c) 2026 Mockarty. All rights reserved.

"""Exception hierarchy for Mockarty SDK.

The Mockarty server emits a uniform JSON envelope for every error:

    {"error": "human message", "code": "not_found", "request_id": "..."}

The ``code`` field is the stable, machine-readable identifier for the error
category and should be preferred over HTTP status codes when branching on
errors. See ``internal/errors.Kind`` in the server source for the full list.
"""

from __future__ import annotations


class MockartyError(Exception):
    """Base exception for all Mockarty SDK errors."""


class MockartyAPIError(MockartyError):
    """Raised when the Mockarty API returns an error response.

    Attributes:
        status_code: HTTP status code (e.g. 404).
        message: Sanitized human-readable message from the server. Never
            contains SQL, stack traces, or internal paths.
        code: Stable machine-readable error identifier (e.g. ``"not_found"``).
            Empty when talking to an older server without the code field.
        request_id: Server-side correlation ID. Include it in bug reports.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        request_id: str | None = None,
        code: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.request_id = request_id
        self.code = code
        parts = [f"HTTP {status_code}"]
        if code:
            parts.append(code)
        super().__init__(f"{' '.join(parts)}: {message}")


class MockartyValidationError(MockartyAPIError):
    """Raised when the request fails server-side validation (HTTP 400)."""


class MockartyNotFoundError(MockartyAPIError):
    """Raised when a requested resource is not found (HTTP 404)."""


class MockartyUnauthorizedError(MockartyAPIError):
    """Raised when authentication fails (HTTP 401)."""


class MockartyForbiddenError(MockartyAPIError):
    """Raised when the user lacks permission (HTTP 403)."""


class MockartyConflictError(MockartyAPIError):
    """Raised when a resource conflict occurs (HTTP 409)."""


class MockartyRateLimitError(MockartyAPIError):
    """Raised when the rate limit is exceeded (HTTP 429)."""


class MockartyServerError(MockartyAPIError):
    """Raised when the server returns a 5xx error."""


class MockartyUnavailableError(MockartyAPIError):
    """Raised when a server dependency is unavailable (HTTP 503)."""


class MockartyExternalError(MockartyAPIError):
    """Raised when an external system called by Mockarty fails (HTTP 502)."""


class MockartyConnectionError(MockartyError):
    """Raised when the client cannot connect to the Mockarty server."""


class MockartyTimeoutError(MockartyError):
    """Raised when a request to the Mockarty server times out."""
