# Copyright (c) 2026 Mockarty. All rights reserved.

"""Template file models for payload templates."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TemplateFile(BaseModel):
    """A payload template file stored on the server."""

    name: Optional[str] = None
    size: Optional[int] = None
    updated_at: Optional[int] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}
