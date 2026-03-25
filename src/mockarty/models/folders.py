# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Mock folder models for hierarchical mock organization."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MockFolder(BaseModel):
    """A folder for organizing mocks in a hierarchy."""

    id: Optional[str] = None
    name: Optional[str] = None
    namespace: Optional[str] = None
    parent_id: Optional[str] = Field(None, alias="parentId")
    mock_count: Optional[int] = Field(None, alias="mockCount")
    created_at: Optional[int] = Field(None, alias="createdAt")
    updated_at: Optional[int] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}
