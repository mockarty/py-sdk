# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test run models for test execution history."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class MergedTestRun(BaseModel):
    """A parent or source row in a merged test run aggregation (T-12).

    The server emits these with capitalised JSON keys because the underlying
    ``ActiveTestRunRow`` struct carries no json tags; both aliases and snake
    case are accepted here so downstream code can use idiomatic Python.
    """

    # populate_by_name lets tests construct via snake_case; the real payload
    # always uses the capitalised aliases.
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(None, alias="ID")
    namespace: Optional[str] = Field(None, alias="Namespace")
    node_id: Optional[str] = Field(None, alias="NodeID")
    run_type: Optional[str] = Field(None, alias="RunType")
    status: Optional[str] = Field(None, alias="Status")
    name: Optional[str] = Field(None, alias="Name")
    message: Optional[str] = Field(None, alias="Message")
    task_id: Optional[str] = Field(None, alias="TaskID")
    meta_json: Optional[str] = Field(None, alias="MetaJSON")
    mode: Optional[str] = Field(None, alias="Mode")
    reference_id: Optional[str] = Field(None, alias="ReferenceID")
    user_id: Optional[str] = Field(None, alias="UserID")
    progress: Optional[int] = Field(None, alias="Progress")
    started_at: Optional[str] = Field(None, alias="StartedAt")
    updated_at: Optional[str] = Field(None, alias="UpdatedAt")
    completed_at: Optional[str] = Field(None, alias="CompletedAt")


class MergedRunView(BaseModel):
    """Server response for merge create/get/list entries: parent + sources."""

    run: Optional[MergedTestRun] = None
    sources: List[MergedTestRun] = Field(default_factory=list)


class MergedRunList(BaseModel):
    """Paginated envelope returned by ``list_merged_runs``."""

    items: List[MergedRunView] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0
