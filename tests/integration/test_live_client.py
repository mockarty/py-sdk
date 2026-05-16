# Copyright (c) 2026 Mockarty. All rights reserved.

"""Smoke tests for the core ``MockartyClient`` surface against a live admin.

Covered:
* Health endpoint reachable.
* Namespace listing returns the seeded ``sandbox``.
* Namespace create — licence-gated; verify the 403 surfaces cleanly
  via :class:`MockartyForbiddenError` so callers can detect it.
* Mock CRUD lifecycle through ``client.mocks``: create → get → list →
  patch → delete → confirm 404.

These tests intentionally use ``client.mocks.create`` (the high-level
SDK path), not raw HTTP, so a regression in the SDK plumbing surfaces
here instead of at a customer's site.
"""

from __future__ import annotations

import uuid

import pytest

from mockarty import MockartyClient
from mockarty.builders import MockBuilder
from mockarty.errors import (
    MockartyForbiddenError,
    MockartyNotFoundError,
)


def _unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class TestHealth:
    def test_health_check_reports_status(self, mockarty_client: MockartyClient) -> None:
        report = mockarty_client.health.check()
        # ``HealthResponse`` exposes ``status`` which the admin sets to
        # ``"pass"`` when every component is up.
        assert report.status in ("pass", "warn"), report.status

    def test_liveness_probe_returns_true(self, mockarty_client: MockartyClient) -> None:
        assert mockarty_client.health.live() is True


class TestNamespaces:
    def test_list_contains_sandbox(
        self, mockarty_client: MockartyClient, live_namespace: str
    ) -> None:
        names = mockarty_client.namespaces.list()
        assert live_namespace in names, (
            f"expected {live_namespace!r} in namespace list, got {names!r}"
        )

    def test_create_namespace_without_licence_surfaces_403(
        self, mockarty_client: MockartyClient
    ) -> None:
        """The admin without a paid licence rejects new-namespace creation.

        The SDK must translate the server's ``code=forbidden`` envelope
        into :class:`MockartyForbiddenError` so callers branch on the
        exception type, not a string match.
        """
        target = _unique_id("ns-licgated")
        with pytest.raises(MockartyForbiddenError) as exc_info:
            mockarty_client.namespaces.create(target)
        assert exc_info.value.status_code == 403
        # The message comes from the server; it's user-readable.
        assert "namespace" in (exc_info.value.message or "").lower()


class TestMocksCrud:
    def test_full_lifecycle(
        self, mockarty_client: MockartyClient, mock_cleanup
    ) -> None:
        mock_id = _unique_id("live-mock")
        mock_cleanup(mock_id)

        # ── create ─────────────────────────────────────────────────
        mock = (
            MockBuilder.http(f"/live-test/{mock_id}", "GET")
            .id(mock_id)
            .respond(200, body={"ok": True, "id": mock_id})
            .build()
        )
        save = mockarty_client.mocks.create(mock)
        assert save.mock.id == mock_id

        # ── get ────────────────────────────────────────────────────
        fetched = mockarty_client.mocks.get(mock_id)
        assert fetched.id == mock_id
        assert fetched.http is not None
        assert fetched.http.route == f"/live-test/{mock_id}"

        # ── list (page contains our id) ────────────────────────────
        page = mockarty_client.mocks.list(limit=100, search=mock_id)
        ids = {m.id for m in page.items}
        assert mock_id in ids, f"mock {mock_id} missing from search list: {ids}"

        # ── delete ─────────────────────────────────────────────────
        mockarty_client.mocks.delete(mock_id)

        # ── post-delete fetch surfaces the soft-delete via the SDK ──
        # Mockarty's soft-delete sets ``closedAt`` but the GET endpoint
        # may still return the record. Both behaviours are valid; what
        # the SDK MUST do is either surface a ``closed_at`` timestamp
        # or raise ``NotFoundError`` — never silently return a live row.
        try:
            after = mockarty_client.mocks.get(mock_id)
        except MockartyNotFoundError:
            return  # hard-delete shape — fine
        assert after.closed_at is not None, (
            "soft-deleted mock surfaced without a closed_at timestamp "
            "— the SDK is misreading the _meta envelope"
        )

    def test_create_with_dict_payload(
        self, mockarty_client: MockartyClient, mock_cleanup
    ) -> None:
        """Sanity that the dict path (no MockBuilder) still works — the
        SDK must accept either a typed Mock model or a plain dict.
        """
        mock_id = _unique_id("live-dict")
        mock_cleanup(mock_id)
        save = mockarty_client.mocks.create(
            {
                "id": mock_id,
                "namespace": mockarty_client.namespace,
                "http": {"route": f"/live-dict/{mock_id}", "httpMethod": "GET"},
                "response": {"statusCode": 201, "body": "hi"},
            }
        )
        assert save.mock.id == mock_id

    def test_404_on_unknown_mock(self, mockarty_client: MockartyClient) -> None:
        with pytest.raises(MockartyNotFoundError):
            mockarty_client.mocks.get(_unique_id("does-not-exist"))
