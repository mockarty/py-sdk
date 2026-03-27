# Copyright (c) 2026 Mockarty. All rights reserved.

"""Undefined request models for unmatched traffic tracking."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class UndefinedRequest(BaseModel):
    """A request that did not match any mock."""

    id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    headers: Optional[dict[str, Any]] = None
    body: Optional[Any] = None
    namespace: Optional[str] = None
    ignored: Optional[bool] = None
    hit_count: Optional[int] = Field(None, alias="hitCount")
    first_seen: Optional[int] = Field(None, alias="firstSeen")
    last_seen: Optional[int] = Field(None, alias="lastSeen")

    model_config = {"populate_by_name": True}
