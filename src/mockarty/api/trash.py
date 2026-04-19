# Copyright (c) 2026 Mockarty. All rights reserved.

"""Recycle Bin / Soft-Delete API resource.

Wraps the namespace- and admin-scoped endpoints defined in
``internal/webui/integration_routes_trash*.go``. Every bulk-purge call is
guarded client-side by the confirmation phrase to avoid ambiguous 400
responses when the caller forgets to set it.

Example (sync)::

    with MockartyClient() as c:
        summary = c.trash.summary("production")
        if summary.total > 0:
            items = c.trash.list_trash("production", limit=50)
            ids = [it.cascade_group_id for it in items.items if it.cascade_group_id]
            c.trash.bulk_restore("production", cascade_group_ids=ids[:5], reason="user request")
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.errors import MockartyError
from mockarty.models.trash import (
    TRASH_PURGE_CONFIRMATION_PHRASE,
    BulkPurgeResult,
    BulkRestoreResult,
    PurgeNowResult,
    RestoreResult,
    TrashListResult,
    TrashSettings,
    TrashSettingsUpdate,
    TrashSummary,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PurgeConfirmationError(MockartyError):
    """Raised by bulk_purge / admin_bulk_purge when the confirmation phrase
    is missing or does not match ``TRASH_PURGE_CONFIRMATION_PHRASE`` exactly.

    Caught client-side so we never dispatch a request the server will reject
    with an ambiguous 400.
    """


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


_ADMIN = "/api/v1/admin/trash"


def _ns(namespace: str) -> str:
    ns = (namespace or "").strip()
    if not ns:
        raise ValueError("namespace is required")
    return f"/api/v1/namespaces/{quote(ns, safe='')}/trash"


def _build_params(
    *,
    entity_types: Optional[Iterable[str]],
    search: Optional[str],
    closed_by: Optional[str],
    cascade_group_id: Optional[str],
    from_time: Optional[datetime],
    to_time: Optional[datetime],
    limit: Optional[int],
    offset: Optional[int],
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if entity_types:
        params["type"] = ",".join(entity_types)
    if search:
        params["q"] = search
    if closed_by:
        params["closed_by"] = closed_by
    if cascade_group_id:
        params["cascade"] = cascade_group_id
    if from_time is not None:
        params["from"] = from_time.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ") if from_time.tzinfo is None else from_time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if to_time is not None:
        params["to"] = to_time.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ") if to_time.tzinfo is None else to_time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if limit is not None and limit > 0:
        params["limit"] = int(limit)
    if offset is not None and offset > 0:
        params["offset"] = int(offset)
    return params


def _validate_purge_request(
    cascade_group_ids: Iterable[str],
    confirmation: str,
) -> list[str]:
    ids = [x for x in cascade_group_ids if x]
    if not ids:
        raise ValueError("cascade_group_ids is required")
    if confirmation != TRASH_PURGE_CONFIRMATION_PHRASE:
        raise PurgeConfirmationError(
            "bulk purge requires confirmation phrase "
            f"{TRASH_PURGE_CONFIRMATION_PHRASE!r}"
        )
    return ids


def _validate_restore_ids(cascade_group_ids: Iterable[str]) -> list[str]:
    ids = [x for x in cascade_group_ids if x]
    if not ids:
        raise ValueError("cascade_group_ids is required")
    return ids


# ---------------------------------------------------------------------------
# Synchronous
# ---------------------------------------------------------------------------


class TrashAPI(SyncAPIBase):
    """Synchronous Recycle Bin API resource."""

    # --- List ------------------------------------------------------------

    def list_trash(
        self,
        namespace: str,
        *,
        entity_types: Optional[Iterable[str]] = None,
        search: Optional[str] = None,
        closed_by: Optional[str] = None,
        cascade_group_id: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TrashListResult:
        """GET /api/v1/namespaces/:ns/trash."""
        params = _build_params(
            entity_types=entity_types,
            search=search,
            closed_by=closed_by,
            cascade_group_id=cascade_group_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
        )
        resp = self._request("GET", _ns(namespace), params=params)
        return TrashListResult.model_validate(resp.json())

    def admin_list_trash(
        self,
        *,
        entity_types: Optional[Iterable[str]] = None,
        search: Optional[str] = None,
        closed_by: Optional[str] = None,
        cascade_group_id: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TrashListResult:
        """GET /api/v1/admin/trash — platform-wide list (admin/support)."""
        params = _build_params(
            entity_types=entity_types,
            search=search,
            closed_by=closed_by,
            cascade_group_id=cascade_group_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
        )
        resp = self._request("GET", _ADMIN, params=params)
        return TrashListResult.model_validate(resp.json())

    # --- Summary ---------------------------------------------------------

    def summary(self, namespace: str) -> TrashSummary:
        """GET /api/v1/namespaces/:ns/trash/summary."""
        resp = self._request("GET", f"{_ns(namespace)}/summary")
        return TrashSummary.model_validate(resp.json())

    def admin_summary(self) -> TrashSummary:
        """GET /api/v1/admin/trash/summary."""
        resp = self._request("GET", f"{_ADMIN}/summary")
        return TrashSummary.model_validate(resp.json())

    # --- Settings --------------------------------------------------------

    def get_settings(self, namespace: str) -> TrashSettings:
        """GET /api/v1/namespaces/:ns/trash/settings."""
        resp = self._request("GET", f"{_ns(namespace)}/settings")
        return TrashSettings.model_validate(resp.json())

    def update_settings(
        self,
        namespace: str,
        *,
        retention_days: int,
        enabled: bool,
    ) -> TrashSettings:
        """PUT /api/v1/namespaces/:ns/trash/settings."""
        body = TrashSettingsUpdate(retention_days=retention_days, enabled=enabled)
        resp = self._request(
            "PUT",
            f"{_ns(namespace)}/settings",
            json=body.model_dump(by_alias=True),
        )
        return TrashSettings.model_validate(resp.json())

    def get_global_settings(self) -> TrashSettings:
        """GET /api/v1/admin/trash/settings/global."""
        resp = self._request("GET", f"{_ADMIN}/settings/global")
        return TrashSettings.model_validate(resp.json())

    def update_global_settings(
        self, *, retention_days: int, enabled: bool
    ) -> TrashSettings:
        """PUT /api/v1/admin/trash/settings/global (platform admin only)."""
        body = TrashSettingsUpdate(retention_days=retention_days, enabled=enabled)
        resp = self._request(
            "PUT",
            f"{_ADMIN}/settings/global",
            json=body.model_dump(by_alias=True),
        )
        return TrashSettings.model_validate(resp.json())

    # --- Single cascade restore -----------------------------------------

    def restore_cascade(self, namespace: str, cascade_group_id: str) -> RestoreResult:
        """POST /api/v1/namespaces/:ns/trash/restore-cascade/:cascade."""
        if not cascade_group_id or not cascade_group_id.strip():
            raise ValueError("cascade_group_id is required")
        path = f"{_ns(namespace)}/restore-cascade/{quote(cascade_group_id, safe='')}"
        resp = self._request("POST", path)
        return RestoreResult.model_validate(resp.json())

    def admin_restore_cascade(self, cascade_group_id: str) -> RestoreResult:
        """POST /api/v1/admin/trash/restore-cascade/:cascade."""
        if not cascade_group_id or not cascade_group_id.strip():
            raise ValueError("cascade_group_id is required")
        path = f"{_ADMIN}/restore-cascade/{quote(cascade_group_id, safe='')}"
        resp = self._request("POST", path)
        return RestoreResult.model_validate(resp.json())

    # --- Bulk restore ----------------------------------------------------

    def bulk_restore(
        self,
        namespace: str,
        *,
        cascade_group_ids: Iterable[str],
        reason: Optional[str] = None,
    ) -> BulkRestoreResult:
        """POST /api/v1/namespaces/:ns/trash/restore."""
        ids = _validate_restore_ids(cascade_group_ids)
        body: dict[str, Any] = {"cascade_group_ids": ids}
        if reason:
            body["reason"] = reason
        resp = self._request("POST", f"{_ns(namespace)}/restore", json=body)
        return BulkRestoreResult.model_validate(resp.json())

    def admin_bulk_restore(
        self,
        *,
        cascade_group_ids: Iterable[str],
        reason: Optional[str] = None,
    ) -> BulkRestoreResult:
        """POST /api/v1/admin/trash/restore."""
        ids = _validate_restore_ids(cascade_group_ids)
        body: dict[str, Any] = {"cascade_group_ids": ids}
        if reason:
            body["reason"] = reason
        resp = self._request("POST", f"{_ADMIN}/restore", json=body)
        return BulkRestoreResult.model_validate(resp.json())

    # --- Bulk purge (IRREVERSIBLE) --------------------------------------

    def bulk_purge(
        self,
        namespace: str,
        *,
        cascade_group_ids: Iterable[str],
        confirmation: str,
        reason: Optional[str] = None,
    ) -> BulkPurgeResult:
        """POST /api/v1/namespaces/:ns/trash/purge. Hard-deletes the groups.

        ``confirmation`` MUST equal ``TRASH_PURGE_CONFIRMATION_PHRASE`` —
        the SDK enforces this client-side.
        """
        ids = _validate_purge_request(cascade_group_ids, confirmation)
        body: dict[str, Any] = {
            "cascade_group_ids": ids,
            "confirmation": confirmation,
        }
        if reason:
            body["reason"] = reason
        resp = self._request("POST", f"{_ns(namespace)}/purge", json=body)
        return BulkPurgeResult.model_validate(resp.json())

    def admin_bulk_purge(
        self,
        *,
        cascade_group_ids: Iterable[str],
        confirmation: str,
        reason: Optional[str] = None,
    ) -> BulkPurgeResult:
        """POST /api/v1/admin/trash/purge (platform admin only)."""
        ids = _validate_purge_request(cascade_group_ids, confirmation)
        body: dict[str, Any] = {
            "cascade_group_ids": ids,
            "confirmation": confirmation,
        }
        if reason:
            body["reason"] = reason
        resp = self._request("POST", f"{_ADMIN}/purge", json=body)
        return BulkPurgeResult.model_validate(resp.json())

    def admin_purge_now(self) -> PurgeNowResult:
        """POST /api/v1/admin/trash/purge-now (leader only)."""
        resp = self._request("POST", f"{_ADMIN}/purge-now")
        return PurgeNowResult.model_validate(resp.json())


# ---------------------------------------------------------------------------
# Asynchronous
# ---------------------------------------------------------------------------


class AsyncTrashAPI(AsyncAPIBase):
    """Asynchronous Recycle Bin API resource (mirrors TrashAPI)."""

    async def list_trash(
        self,
        namespace: str,
        *,
        entity_types: Optional[Iterable[str]] = None,
        search: Optional[str] = None,
        closed_by: Optional[str] = None,
        cascade_group_id: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TrashListResult:
        params = _build_params(
            entity_types=entity_types,
            search=search,
            closed_by=closed_by,
            cascade_group_id=cascade_group_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
        )
        resp = await self._request("GET", _ns(namespace), params=params)
        return TrashListResult.model_validate(resp.json())

    async def admin_list_trash(
        self,
        *,
        entity_types: Optional[Iterable[str]] = None,
        search: Optional[str] = None,
        closed_by: Optional[str] = None,
        cascade_group_id: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> TrashListResult:
        params = _build_params(
            entity_types=entity_types,
            search=search,
            closed_by=closed_by,
            cascade_group_id=cascade_group_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
            offset=offset,
        )
        resp = await self._request("GET", _ADMIN, params=params)
        return TrashListResult.model_validate(resp.json())

    async def summary(self, namespace: str) -> TrashSummary:
        resp = await self._request("GET", f"{_ns(namespace)}/summary")
        return TrashSummary.model_validate(resp.json())

    async def admin_summary(self) -> TrashSummary:
        resp = await self._request("GET", f"{_ADMIN}/summary")
        return TrashSummary.model_validate(resp.json())

    async def get_settings(self, namespace: str) -> TrashSettings:
        resp = await self._request("GET", f"{_ns(namespace)}/settings")
        return TrashSettings.model_validate(resp.json())

    async def update_settings(
        self, namespace: str, *, retention_days: int, enabled: bool
    ) -> TrashSettings:
        body = TrashSettingsUpdate(retention_days=retention_days, enabled=enabled)
        resp = await self._request(
            "PUT",
            f"{_ns(namespace)}/settings",
            json=body.model_dump(by_alias=True),
        )
        return TrashSettings.model_validate(resp.json())

    async def get_global_settings(self) -> TrashSettings:
        resp = await self._request("GET", f"{_ADMIN}/settings/global")
        return TrashSettings.model_validate(resp.json())

    async def update_global_settings(
        self, *, retention_days: int, enabled: bool
    ) -> TrashSettings:
        body = TrashSettingsUpdate(retention_days=retention_days, enabled=enabled)
        resp = await self._request(
            "PUT",
            f"{_ADMIN}/settings/global",
            json=body.model_dump(by_alias=True),
        )
        return TrashSettings.model_validate(resp.json())

    async def restore_cascade(
        self, namespace: str, cascade_group_id: str
    ) -> RestoreResult:
        if not cascade_group_id or not cascade_group_id.strip():
            raise ValueError("cascade_group_id is required")
        path = f"{_ns(namespace)}/restore-cascade/{quote(cascade_group_id, safe='')}"
        resp = await self._request("POST", path)
        return RestoreResult.model_validate(resp.json())

    async def admin_restore_cascade(self, cascade_group_id: str) -> RestoreResult:
        if not cascade_group_id or not cascade_group_id.strip():
            raise ValueError("cascade_group_id is required")
        path = f"{_ADMIN}/restore-cascade/{quote(cascade_group_id, safe='')}"
        resp = await self._request("POST", path)
        return RestoreResult.model_validate(resp.json())

    async def bulk_restore(
        self,
        namespace: str,
        *,
        cascade_group_ids: Iterable[str],
        reason: Optional[str] = None,
    ) -> BulkRestoreResult:
        ids = _validate_restore_ids(cascade_group_ids)
        body: dict[str, Any] = {"cascade_group_ids": ids}
        if reason:
            body["reason"] = reason
        resp = await self._request("POST", f"{_ns(namespace)}/restore", json=body)
        return BulkRestoreResult.model_validate(resp.json())

    async def admin_bulk_restore(
        self, *, cascade_group_ids: Iterable[str], reason: Optional[str] = None
    ) -> BulkRestoreResult:
        ids = _validate_restore_ids(cascade_group_ids)
        body: dict[str, Any] = {"cascade_group_ids": ids}
        if reason:
            body["reason"] = reason
        resp = await self._request("POST", f"{_ADMIN}/restore", json=body)
        return BulkRestoreResult.model_validate(resp.json())

    async def bulk_purge(
        self,
        namespace: str,
        *,
        cascade_group_ids: Iterable[str],
        confirmation: str,
        reason: Optional[str] = None,
    ) -> BulkPurgeResult:
        ids = _validate_purge_request(cascade_group_ids, confirmation)
        body: dict[str, Any] = {
            "cascade_group_ids": ids,
            "confirmation": confirmation,
        }
        if reason:
            body["reason"] = reason
        resp = await self._request("POST", f"{_ns(namespace)}/purge", json=body)
        return BulkPurgeResult.model_validate(resp.json())

    async def admin_bulk_purge(
        self,
        *,
        cascade_group_ids: Iterable[str],
        confirmation: str,
        reason: Optional[str] = None,
    ) -> BulkPurgeResult:
        ids = _validate_purge_request(cascade_group_ids, confirmation)
        body: dict[str, Any] = {
            "cascade_group_ids": ids,
            "confirmation": confirmation,
        }
        if reason:
            body["reason"] = reason
        resp = await self._request("POST", f"{_ADMIN}/purge", json=body)
        return BulkPurgeResult.model_validate(resp.json())

    async def admin_purge_now(self) -> PurgeNowResult:
        resp = await self._request("POST", f"{_ADMIN}/purge-now")
        return PurgeNowResult.model_validate(resp.json())
