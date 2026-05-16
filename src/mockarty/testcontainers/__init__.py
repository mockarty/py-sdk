# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mockarty testcontainers wrapper -- Wave 4 SDK addition.

A thin :mod:`testcontainers`-backed wrapper around the canonical
``mockarty/cli:latest-mock`` image. Drop-in replacement for
WireMockContainer / MockoonContainer in user integration tests.

Quick start::

    from mockarty.testcontainers import MockartyContainer

    with MockartyContainer() as c:
        c.apply({"http": {"request": {"method": "GET", "path": "/ping"}},
                 "response": {"status": 200, "body": "pong"}})
        r = httpx.get(c.url() + "/ping")
        assert r.text == "pong"

The :mod:`testcontainers` package is an *optional* dependency. Import
this module only from tests that need it; production callers never
have to install it.
"""

from __future__ import annotations

from mockarty.testcontainers.mockarty import (
    DEFAULT_IMAGE,
    FORMAT_AUTO,
    FORMAT_MOCKARTY,
    FORMAT_MOCKOON,
    FORMAT_WIREMOCK,
    METRICS_PORT,
    MOCK_PORT,
    STUBS_MOUNT,
    MockartyContainer,
)

__all__ = [
    "DEFAULT_IMAGE",
    "FORMAT_AUTO",
    "FORMAT_MOCKARTY",
    "FORMAT_MOCKOON",
    "FORMAT_WIREMOCK",
    "METRICS_PORT",
    "MOCK_PORT",
    "STUBS_MOUNT",
    "MockartyContainer",
]
