# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Import result models for Postman/Insomnia collection imports."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ImportResult(BaseModel):
    """Result of importing a collection from an external tool."""

    collection_id: Optional[str] = Field(None, alias="collectionId")
    name: Optional[str] = None
    imported: Optional[int] = None
    message: Optional[str] = None

    model_config = {"populate_by_name": True}
