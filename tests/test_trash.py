# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the Recycle Bin / Soft-Delete API (sync and async)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import (
    TRASH_PURGE_CONFIRMATION_PHRASE,
    AsyncMockartyClient,
    BulkPurgeResult,
    BulkRestoreResult,
    MockartyClient,
    PurgeConfirmationError,
    PurgeNowResult,
    RestoreResult,
    TrashListResult,
    TrashSettings,
    TrashSummary,
)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestTrashList:
    @respx.mock
    def test_list_trash(self, client: MockartyClient) -> None:
        route = respx.get(
            "http://localhost:5770/api/v1/namespaces/production/trash"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "11111111-2222-3333-4444-555555555555",
                            "name": "users",
                            "namespace": "production",
                            "entity_type": "mock",
                            "closed_at": "2026-04-19T12:00:00Z",
                            "closed_by": "alice@example.com",
                            "cascade_group_id": "aaaa-bbbb-cccc",
                            "restore_available": True,
                        }
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )

        result = client.trash.list_trash(
            "production", entity_types=["mock", "store"], search="user", limit=50
        )
        assert isinstance(result, TrashListResult)
        assert result.total == 1
        assert result.items[0].restore_available is True
        assert route.calls.last.request.url.params["type"] == "mock,store"
        assert route.calls.last.request.url.params["q"] == "user"
        assert route.calls.last.request.url.params["limit"] == "50"

    @respx.mock
    def test_admin_list_trash(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/admin/trash").mock(
            return_value=httpx.Response(
                200, json={"items": [], "total": 3, "limit": 50, "offset": 0}
            )
        )
        result = client.trash.admin_list_trash()
        assert result.total == 3

    def test_list_requires_namespace(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError, match="namespace is required"):
            client.trash.list_trash("  ")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestTrashSummary:
    @respx.mock
    def test_summary(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/namespaces/team-a/trash/summary"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "counts": [{"entity_type": "mock", "count": 4}],
                    "total": 4,
                },
            )
        )
        summary = client.trash.summary("team-a")
        assert isinstance(summary, TrashSummary)
        assert summary.total == 4
        assert summary.counts[0].entity_type == "mock"

    @respx.mock
    def test_admin_summary(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/admin/trash/summary").mock(
            return_value=httpx.Response(200, json={"counts": [], "total": 42})
        )
        summary = client.trash.admin_summary()
        assert summary.total == 42


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestTrashSettings:
    @respx.mock
    def test_get_settings(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/namespaces/finance/trash/settings"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "scope": "namespace",
                    "namespace": "finance",
                    "retention_days": 7,
                    "enabled": True,
                    "inherited": True,
                },
            )
        )
        got = client.trash.get_settings("finance")
        assert isinstance(got, TrashSettings)
        assert got.inherited is True
        assert got.retention_days == 7

    @respx.mock
    def test_update_settings(self, client: MockartyClient) -> None:
        route = respx.put(
            "http://localhost:5770/api/v1/namespaces/ns1/trash/settings"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "scope": "namespace",
                    "namespace": "ns1",
                    "retention_days": 14,
                    "enabled": True,
                },
            )
        )
        got = client.trash.update_settings("ns1", retention_days=14, enabled=True)
        assert got.retention_days == 14
        body = route.calls.last.request.content.decode()
        assert '"retention_days":14' in body
        assert '"enabled":true' in body

    @respx.mock
    def test_global_settings_round_trip(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/admin/trash/settings/global").mock(
            return_value=httpx.Response(
                200, json={"scope": "global", "retention_days": 30, "enabled": True}
            )
        )
        respx.put("http://localhost:5770/api/v1/admin/trash/settings/global").mock(
            return_value=httpx.Response(
                200, json={"scope": "global", "retention_days": 60, "enabled": True}
            )
        )
        g = client.trash.get_global_settings()
        assert g.retention_days == 30
        u = client.trash.update_global_settings(retention_days=60, enabled=True)
        assert u.retention_days == 60


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


class TestTrashRestore:
    @respx.mock
    def test_restore_cascade(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/namespaces/prod/trash/restore-cascade/grp-1"
        ).mock(
            return_value=httpx.Response(
                200, json={"cascadeGroupId": "grp-1", "restoredCount": 5}
            )
        )
        got = client.trash.restore_cascade("prod", "grp-1")
        assert isinstance(got, RestoreResult)
        assert got.restored_count == 5
        assert got.cascade_group_id == "grp-1"

    def test_restore_cascade_requires_id(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError, match="cascade_group_id"):
            client.trash.restore_cascade("ns", "   ")

    @respx.mock
    def test_admin_restore_cascade(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/admin/trash/restore-cascade/g-admin"
        ).mock(
            return_value=httpx.Response(
                200, json={"cascadeGroupId": "g-admin", "restoredCount": 1}
            )
        )
        got = client.trash.admin_restore_cascade("g-admin")
        assert got.restored_count == 1

    @respx.mock
    def test_bulk_restore_partial(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/namespaces/ns/trash/restore").mock(
            return_value=httpx.Response(
                200,
                json={
                    "restored": [
                        {
                            "cascade_group_id": "g1",
                            "entity_type": "mock",
                            "restored_count": 2,
                        }
                    ],
                    "failed": [{"cascade_group_id": "g2", "error": "denied"}],
                    "not_found": ["g3"],
                },
            )
        )
        got = client.trash.bulk_restore(
            "ns", cascade_group_ids=["g1", "g2", "g3"], reason="fix"
        )
        assert isinstance(got, BulkRestoreResult)
        assert len(got.restored) == 1
        assert len(got.failed) == 1
        assert got.not_found == ["g3"]

    def test_bulk_restore_requires_ids(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError, match="cascade_group_ids"):
            client.trash.bulk_restore("ns", cascade_group_ids=[])


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------


class TestTrashPurge:
    def test_purge_missing_confirmation(self, client: MockartyClient) -> None:
        with pytest.raises(PurgeConfirmationError):
            client.trash.bulk_purge("ns", cascade_group_ids=["g1"], confirmation="")

    def test_purge_wrong_confirmation(self, client: MockartyClient) -> None:
        with pytest.raises(PurgeConfirmationError):
            client.trash.bulk_purge(
                "ns", cascade_group_ids=["g1"], confirmation="YES DELETE"
            )

    def test_purge_empty_ids(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError, match="cascade_group_ids"):
            client.trash.bulk_purge(
                "ns",
                cascade_group_ids=[],
                confirmation=TRASH_PURGE_CONFIRMATION_PHRASE,
            )

    @respx.mock
    def test_purge_happy_path(self, client: MockartyClient) -> None:
        route = respx.post(
            "http://localhost:5770/api/v1/namespaces/ns/trash/purge"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "purged": [
                        {
                            "cascade_group_id": "g1",
                            "entity_type": "mock",
                            "rows_deleted": 7,
                        }
                    ],
                    "failed": [],
                    "not_found": [],
                },
            )
        )
        got = client.trash.bulk_purge(
            "ns",
            cascade_group_ids=["g1"],
            confirmation=TRASH_PURGE_CONFIRMATION_PHRASE,
            reason="GDPR",
        )
        assert isinstance(got, BulkPurgeResult)
        assert got.purged[0].rows_deleted == 7
        body = route.calls.last.request.content.decode()
        assert "I understand this is permanent" in body
        assert "GDPR" in body

    @respx.mock
    def test_admin_purge_forbidden(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/admin/trash/purge").mock(
            return_value=httpx.Response(
                403, json={"error": "support cannot purge", "code": "forbidden"}
            )
        )
        from mockarty.errors import MockartyForbiddenError

        with pytest.raises(MockartyForbiddenError):
            client.trash.admin_bulk_purge(
                cascade_group_ids=["g1"],
                confirmation=TRASH_PURGE_CONFIRMATION_PHRASE,
            )

    @respx.mock
    def test_admin_purge_now(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/admin/trash/purge-now").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "ok",
                    "purged_total": 123,
                    "namespaces_scanned": 4,
                },
            )
        )
        got = client.trash.admin_purge_now()
        assert isinstance(got, PurgeNowResult)
        assert got.purged_total == 123
        assert got.namespaces_scanned == 4


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class TestAsyncTrash:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_summary(self, base_url: str, api_key: str) -> None:
        respx.get(f"{base_url}/api/v1/namespaces/async-ns/trash/summary").mock(
            return_value=httpx.Response(200, json={"counts": [], "total": 7})
        )
        async with AsyncMockartyClient(
            base_url=base_url, api_key=api_key, namespace="async-ns", max_retries=0
        ) as c:
            got = await c.trash.summary("async-ns")
            assert got.total == 7

    @pytest.mark.asyncio
    async def test_async_purge_missing_confirmation(
        self, base_url: str, api_key: str
    ) -> None:
        async with AsyncMockartyClient(
            base_url=base_url, api_key=api_key, namespace="x", max_retries=0
        ) as c:
            with pytest.raises(PurgeConfirmationError):
                await c.trash.bulk_purge(
                    "x", cascade_group_ids=["g"], confirmation="nope"
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_bulk_restore(self, base_url: str, api_key: str) -> None:
        respx.post(f"{base_url}/api/v1/namespaces/x/trash/restore").mock(
            return_value=httpx.Response(
                200,
                json={
                    "restored": [
                        {"cascade_group_id": "g", "restored_count": 1}
                    ],
                    "failed": [],
                    "not_found": [],
                },
            )
        )
        async with AsyncMockartyClient(
            base_url=base_url, api_key=api_key, namespace="x", max_retries=0
        ) as c:
            got = await c.trash.bulk_restore("x", cascade_group_ids=["g"])
            assert len(got.restored) == 1
