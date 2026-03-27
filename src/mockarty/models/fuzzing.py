# Copyright (c) 2026 Mockarty. All rights reserved.

"""Fuzzing models for API security and reliability testing."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FuzzingConfig(BaseModel):
    """Configuration for a fuzzing test."""

    id: Optional[str] = None
    name: Optional[str] = None
    target_url: Optional[str] = Field(None, alias="targetUrl")
    spec_url: Optional[str] = Field(None, alias="specUrl")
    spec: Optional[str] = None
    duration: Optional[str] = None
    workers: Optional[int] = None
    namespace: Optional[str] = None

    model_config = {"populate_by_name": True}


class FuzzingRun(BaseModel):
    """A running fuzzing test instance."""

    id: Optional[str] = None
    status: Optional[str] = None


class FuzzingResult(BaseModel):
    """Result of a completed fuzzing test."""

    id: Optional[str] = None
    config_id: Optional[str] = Field(None, alias="configId")
    status: Optional[str] = None
    started_at: Optional[int] = Field(None, alias="startedAt")
    finished_at: Optional[int] = Field(None, alias="finishedAt")
    total_requests: Optional[int] = Field(None, alias="totalRequests")
    findings: Optional[int] = None

    model_config = {"populate_by_name": True}
