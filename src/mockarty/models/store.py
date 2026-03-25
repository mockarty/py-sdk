# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Store models for Global, Chain, and Mock stores."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class StoreEntry(BaseModel):
    """A single key-value pair in a store."""

    key: str
    value: Any = None


class StoreData(BaseModel):
    """Container for store data returned by the API."""

    data: Optional[dict[str, Any]] = None


class DeleteFromStoreRequest(BaseModel):
    """Request payload for deleting keys from a store."""

    keys: list[str]
