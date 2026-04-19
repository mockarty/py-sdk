# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test run models for test execution history."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TestRun(BaseModel):
    """A test run execution record.

    Mode and reference_id (migration 033) identify which execution surface
    the run belongs to. Supported modes:
        "functional" — API-tester collection run (default; legacy shape)
        "load"       — performance/load run
        "fuzz"       — fuzz campaign (reference_id -> fuzz_configs.id)
        "chaos"      — chaos experiment (reference_id -> chaos_experiments.id)
        "contract"   — contract verification (reference_id -> contract_registry.id)
    """

    id: Optional[str] = None
    collection_id: Optional[str] = Field(None, alias="collectionId")
    mode: Optional[str] = None
    reference_id: Optional[str] = Field(None, alias="referenceId")
    status: Optional[str] = None
    total_tests: Optional[int] = Field(None, alias="totalTests")
    passed_tests: Optional[int] = Field(None, alias="passedTests")
    failed_tests: Optional[int] = Field(None, alias="failedTests")
    duration: Optional[int] = None
    started_at: Optional[str] = Field(None, alias="startedAt")
    completed_at: Optional[str] = Field(None, alias="completedAt")
    environment: Optional[str] = None

    model_config = {"populate_by_name": True}
