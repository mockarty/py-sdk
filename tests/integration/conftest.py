# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live integration test fixtures.

Skips the whole package when ``MOCKARTY_BASE_URL`` is not set OR when
the admin node at that URL is unreachable. Mirrors the contract written
to ``/tmp/stage3-admin/STATE.md`` for the Stage 3 sweep:

* Admin URL: ``http://localhost:5770`` (default).
* API token in ``MOCKARTY_API_KEY`` (or ``/tmp/stage3-admin/api-token.txt`` fallback).
* Authentication header: ``Authorization: Bearer <token>`` — admin's
  combined middleware accepts the long-lived API token via either
  ``Authorization: Bearer`` or ``X-API-Key`` for the REST surface the
  SDK uses (``/api/v1/mocks``, ``/api/v1/namespaces``, …).

These fixtures are session-scoped so we hit the admin once per pytest
invocation, not once per test.
"""

from __future__ import annotations

import os
import pathlib
import socket
from typing import Iterator
from urllib.parse import urlparse

import httpx
import pytest

from mockarty import MockartyClient


# Fallback used by the Stage 3 admin worktree. Tests still skip when
# neither this file nor the env var is present.
_FALLBACK_TOKEN_FILE = "/tmp/stage3-admin/api-token.txt"


def _resolve_base_url() -> str | None:
    url = os.environ.get("MOCKARTY_BASE_URL")
    return url.rstrip("/") if url else None


def _resolve_api_key() -> str | None:
    key = os.environ.get("MOCKARTY_API_KEY")
    if key:
        return key.strip()
    p = pathlib.Path(_FALLBACK_TOKEN_FILE)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return None


def _probe_admin(base_url: str, timeout: float = 2.0) -> tuple[bool, str]:
    """Best-effort liveness probe.

    Returns ``(alive, detail)`` — ``detail`` is a human-readable hint
    used in the skip reason when ``alive`` is False.
    """
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return False, f"tcp probe to {base_url} failed: {exc}"
    try:
        resp = httpx.get(f"{base_url}/health", timeout=timeout)
    except httpx.HTTPError as exc:
        return False, f"GET /health failed: {exc}"
    if resp.status_code != 200:
        return False, f"GET /health returned HTTP {resp.status_code}"
    return True, "ok"


# ── Session fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="session")
def live_admin_url() -> str:
    url = _resolve_base_url()
    if not url:
        pytest.skip("MOCKARTY_BASE_URL not set — live integration tests disabled")
    alive, detail = _probe_admin(url)
    if not alive:
        pytest.skip(f"admin at {url} unreachable: {detail}")
    return url


@pytest.fixture(scope="session")
def api_key() -> str:
    key = _resolve_api_key()
    if not key:
        pytest.skip(
            "no API key (MOCKARTY_API_KEY env or "
            f"{_FALLBACK_TOKEN_FILE}); live tests skipped",
        )
    return key


@pytest.fixture(scope="session")
def live_namespace() -> str:
    """Namespace tests should target. ``sandbox`` is always present on a
    fresh admin install; tests must NOT try to create other namespaces
    because that surface is licence-gated."""
    return os.environ.get("MOCKARTY_NS", "sandbox")


@pytest.fixture(scope="session")
def mockarty_client(
    live_admin_url: str, api_key: str, live_namespace: str
) -> Iterator[MockartyClient]:
    """Session-scoped client wired to the live admin.

    Closed on session teardown. Per-test cleanup is the test's
    responsibility (resource fixtures below).
    """
    c = MockartyClient(
        base_url=live_admin_url,
        api_key=api_key,
        namespace=live_namespace,
        timeout=15.0,
        max_retries=1,
    )
    try:
        yield c
    finally:
        c.close()


@pytest.fixture(scope="session")
def cli_path() -> str | None:
    """Path to mockarty-cli for ``local_spawn`` tests.

    Honours ``MOCKARTY_CLI`` env var; falls back to the well-known
    stage3 install location. Returns ``None`` when neither exists; the
    caller decides whether to skip.
    """
    candidate = os.environ.get("MOCKARTY_CLI") or "/tmp/mockarty-cli-stage3"
    if candidate and pathlib.Path(candidate).is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


# ── Per-test resource cleanup ─────────────────────────────────────────


@pytest.fixture
def mock_cleanup(mockarty_client: MockartyClient):
    """Track mock IDs created in a test; purge them on teardown.

    Uses ``purge`` (hard delete) so a re-run of the test against the
    same admin doesn't trip over a soft-deleted shell of the previous
    fixture.
    """
    created: list[str] = []

    def _track(mock_id: str) -> str:
        created.append(mock_id)
        return mock_id

    yield _track

    for mid in created:
        try:
            mockarty_client.mocks.purge(mid)
        except Exception:
            try:
                mockarty_client.mocks.delete(mid)
            except Exception:
                pass


# ── Marker auto-tagging ───────────────────────────────────────────────


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-tag every test in this package with ``@pytest.mark.integration``.

    Run only integration tests:  ``pytest -m integration``
    Skip integration:             ``pytest -m 'not integration'``
    """
    here = pathlib.Path(__file__).parent.resolve()
    integration = pytest.mark.integration
    for item in items:
        try:
            item_path = pathlib.Path(str(item.fspath)).resolve()
        except Exception:
            continue
        if here in item_path.parents or item_path == here:
            item.add_marker(integration)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live integration test (needs running Mockarty admin)",
    )
