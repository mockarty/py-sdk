# Copyright (c) 2026 Mockarty. All rights reserved.

"""Recorder models for traffic recording sessions."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RecorderSession(BaseModel):
    """A traffic recording session."""

    id: Optional[str] = None
    name: Optional[str] = None
    target_url: Optional[str] = Field(None, alias="targetUrl")
    status: Optional[str] = None  # idle, recording, stopped
    namespace: Optional[str] = None
    created_at: Optional[int] = Field(None, alias="createdAt")
    entry_count: Optional[int] = Field(None, alias="entryCount")

    model_config = {"populate_by_name": True}


class RecorderEntry(BaseModel):
    """A single recorded request/response entry."""

    id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    status_code: Optional[int] = Field(None, alias="statusCode")
    duration: Optional[int] = None
    timestamp: Optional[int] = None

    model_config = {"populate_by_name": True}
