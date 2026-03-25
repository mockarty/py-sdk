# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Admin models for user management, backups, licensing, and system administration."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """A Mockarty user account."""

    id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None  # admin, support, user
    enabled: Optional[bool] = None
    created_at: Optional[int] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class CreateUserRequest(BaseModel):
    """Request payload for creating a new user."""

    username: str
    email: str
    password: str
    role: Optional[str] = None


class UpdateUserRequest(BaseModel):
    """Request payload for updating an existing user."""

    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class AdminNamespace(BaseModel):
    """Namespace with administrative metadata."""

    name: str
    mock_count: Optional[int] = Field(None, alias="mockCount")
    user_count: Optional[int] = Field(None, alias="userCount")
    created_at: Optional[int] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class NamespaceUser(BaseModel):
    """A user's association with a namespace."""

    user_id: Optional[str] = Field(None, alias="userId")
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None

    model_config = {"populate_by_name": True}


class BackupConfig(BaseModel):
    """Backup schedule configuration."""

    id: Optional[str] = None
    name: Optional[str] = None
    schedule: Optional[str] = None
    retention: Optional[int] = None
    enabled: Optional[bool] = None


class Backup(BaseModel):
    """A completed backup entry."""

    id: Optional[str] = None
    config_id: Optional[str] = Field(None, alias="configId")
    status: Optional[str] = None
    size: Optional[int] = None
    created_at: Optional[int] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class LicenseStatus(BaseModel):
    """Current license status information."""

    active: bool = False
    type: Optional[str] = None
    expires_at: Optional[int] = Field(None, alias="expiresAt")
    max_users: Optional[int] = Field(None, alias="maxUsers")
    max_mocks: Optional[int] = Field(None, alias="maxMocks")

    model_config = {"populate_by_name": True}


class LicenseUsage(BaseModel):
    """Current resource usage under the license."""

    users: Optional[int] = None
    mocks: Optional[int] = None
    namespaces: Optional[int] = None


class LicenseLimits(BaseModel):
    """License feature limits and flags."""

    max_users: Optional[int] = Field(None, alias="maxUsers")
    max_mocks: Optional[int] = Field(None, alias="maxMocks")
    max_namespaces: Optional[int] = Field(None, alias="maxNamespaces")
    ai_enabled: Optional[bool] = Field(None, alias="aiEnabled")
    perf_enabled: Optional[bool] = Field(None, alias="perfEnabled")
    fuzz_enabled: Optional[bool] = Field(None, alias="fuzzEnabled")

    model_config = {"populate_by_name": True}


class CleanupPolicy(BaseModel):
    """System cleanup policy configuration."""

    mock_retention_days: Optional[int] = Field(None, alias="mockRetentionDays")
    log_retention_days: Optional[int] = Field(None, alias="logRetentionDays")
    test_run_retention_days: Optional[int] = Field(None, alias="testRunRetentionDays")
    auto_cleanup: Optional[bool] = Field(None, alias="autoCleanup")

    model_config = {"populate_by_name": True}


class DatabaseHealth(BaseModel):
    """Database health and statistics."""

    status: Optional[str] = None
    size: Optional[int] = None
    tables: Optional[int] = None
    connections: Optional[int] = None
