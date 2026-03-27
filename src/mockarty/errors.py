# Copyright (c) 2026 Mockarty. All rights reserved.

"""Exception hierarchy for Mockarty SDK."""

from __future__ import annotations


class MockartyError(Exception):
    """Base exception for all Mockarty SDK errors."""


class MockartyAPIError(MockartyError):
    """Raised when the Mockarty API returns an error response."""

    def __init__(
        self,
        status_code: int,
        message: str,
        request_id: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.request_id = request_id
        super().__init__(f"HTTP {status_code}: {message}")


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


class MockartyConnectionError(MockartyError):
    """Raised when the client cannot connect to the Mockarty server."""


class MockartyTimeoutError(MockartyError):
    """Raised when a request to the Mockarty server times out."""
