# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Generator models for OpenAPI/Swagger/GraphQL mock generation."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from mockarty.models.mock import Mock


class GeneratorRequest(BaseModel):
    """Request payload for generating mocks from a specification."""

    spec: Optional[str] = None
    url: Optional[str] = None
    namespace: Optional[str] = None
    path_prefix: Optional[str] = Field(None, alias="pathPrefix")
    server_name: Optional[str] = Field(None, alias="serverName")
    graphql_url: Optional[str] = Field(None, alias="graphqlUrl")

    model_config = {"populate_by_name": True}


class GeneratorPreview(BaseModel):
    """Preview of mocks that would be generated from a specification."""

    mocks: list[Mock] = []
    count: int = 0


class GeneratorResponse(BaseModel):
    """Response after generating and creating mocks."""

    created: int = 0
    mocks: list[Mock] = []
    message: Optional[str] = None
