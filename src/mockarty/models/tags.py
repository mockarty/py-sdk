# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Tag models for mock organization."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """A tag used to categorize mocks."""

    id: Optional[str] = None
    name: Optional[str] = None
    namespace: Optional[str] = None
    mock_count: Optional[int] = Field(None, alias="mockCount")
    created_at: Optional[int] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}
