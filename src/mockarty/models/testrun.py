# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test run models for test execution history."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TestRun(BaseModel):
    """A test run execution record."""

    id: Optional[str] = None
    collection_id: Optional[str] = Field(None, alias="collectionId")
    status: Optional[str] = None
    total_tests: Optional[int] = Field(None, alias="totalTests")
    passed_tests: Optional[int] = Field(None, alias="passedTests")
    failed_tests: Optional[int] = Field(None, alias="failedTests")
    duration: Optional[int] = None
    started_at: Optional[str] = Field(None, alias="startedAt")
    completed_at: Optional[str] = Field(None, alias="completedAt")
    environment: Optional[str] = None

    model_config = {"populate_by_name": True}
