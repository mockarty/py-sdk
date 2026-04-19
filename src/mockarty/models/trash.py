# Copyright (c) 2026 Mockarty. All rights reserved.

"""Recycle Bin / Soft-Delete models.

Wire formats match the JSON projections in
``internal/webui/integration_routes_trash*.go`` (snake_case for list items
and bulk envelopes, camelCase for the RestoreResult response that mirrors
``internal/model.RestoreResult``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Exact confirmation phrase accepted by the server-side bulk-purge endpoint.
#: Mirrors ``internal/webui.TrashPurgeConfirmationPhrase``.
TRASH_PURGE_CONFIRMATION_PHRASE = "I understand this is permanent"


# ---------------------------------------------------------------------------
# Item / list
# ---------------------------------------------------------------------------


class TrashItem(BaseModel):
    """A single soft-deleted entity row as returned by the list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    namespace: str
    entity_type: str = Field(alias="entity_type")
    closed_at: datetime = Field(alias="closed_at")
    closed_by: Optional[str] = Field(default=None, alias="closed_by")
    closed_reason: Optional[str] = Field(default=None, alias="closed_reason")
    cascade_group_id: Optional[str] = Field(default=None, alias="cascade_group_id")
    numeric_id: Optional[int] = Field(default=None, alias="numeric_id")
    restore_available: bool = Field(alias="restore_available")


class TrashListResult(BaseModel):
    """Envelope returned by list_trash / admin_list_trash."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[TrashItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TrashSummaryCount(BaseModel):
    """One row of the per-entity-type aggregate."""

    model_config = ConfigDict(populate_by_name=True)

    entity_type: str = Field(alias="entity_type")
    count: int


class TrashSummary(BaseModel):
    """Per-entity-type counts used for badge rendering."""

    model_config = ConfigDict(populate_by_name=True)

    counts: list[TrashSummaryCount]
    total: int


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TrashSettings(BaseModel):
    """Retention settings for a namespace or the global default."""

    model_config = ConfigDict(populate_by_name=True)

    scope: str
    retention_days: int = Field(alias="retention_days")
    enabled: bool
    namespace: Optional[str] = None
    inherited: Optional[bool] = None
    updated_at: Optional[str] = Field(default=None, alias="updated_at")
    updated_by: Optional[str] = Field(default=None, alias="updated_by")


class TrashSettingsUpdate(BaseModel):
    """Body accepted by the settings PUT endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    retention_days: int = Field(alias="retention_days")
    enabled: bool


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------


class RestoreResult(BaseModel):
    """Result of a single cascade restore (mirrors server camelCase shape)."""

    model_config = ConfigDict(populate_by_name=True)

    cascade_group_id: str = Field(alias="cascadeGroupId")
    restored_count: int = Field(alias="restoredCount")
    missing_count: Optional[int] = Field(default=None, alias="missingCount")
    parent_deleted: Optional[bool] = Field(default=None, alias="parentDeleted")


class BulkRestoreOutcome(BaseModel):
    """Outcome of a single cascade group in a bulk restore."""

    model_config = ConfigDict(populate_by_name=True)

    cascade_group_id: str = Field(alias="cascade_group_id")
    entity_type: Optional[str] = Field(default=None, alias="entity_type")
    restored_count: int = Field(default=0, alias="restored_count")
    error: Optional[str] = None


class BulkRestoreResult(BaseModel):
    """Envelope returned by the bulk-restore endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    restored: list[BulkRestoreOutcome]
    failed: list[BulkRestoreOutcome]
    not_found: list[str] = Field(default_factory=list, alias="not_found")


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------


class BulkPurgeOutcome(BaseModel):
    """Outcome of a single cascade group in a bulk purge."""

    model_config = ConfigDict(populate_by_name=True)

    cascade_group_id: str = Field(alias="cascade_group_id")
    entity_type: Optional[str] = Field(default=None, alias="entity_type")
    rows_deleted: int = Field(default=0, alias="rows_deleted")
    error: Optional[str] = None


class BulkPurgeResult(BaseModel):
    """Envelope returned by the bulk-purge endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    purged: list[BulkPurgeOutcome]
    failed: list[BulkPurgeOutcome]
    not_found: list[str] = Field(default_factory=list, alias="not_found")


class PurgeNowResult(BaseModel):
    """Response of the manual retention-scheduler tick."""

    model_config = ConfigDict(populate_by_name=True)

    status: str
    purged_total: int = Field(alias="purged_total")
    namespaces_scanned: int = Field(alias="namespaces_scanned")
    message: Optional[str] = None
