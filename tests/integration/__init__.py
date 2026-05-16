# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live integration tests for the Python SDK.

Tests in this package require a running Mockarty admin node reachable
via ``MOCKARTY_BASE_URL``. They skip cleanly when the server is
unavailable so the offline ``tests/`` suite keeps passing.

See ``conftest.py`` for the auto-skip wiring.
"""
