# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Generator models for OpenAPI/Swagger/GraphQL mock generation."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from mockarty.models.mock import Mock


class GeneratorRequest(BaseModel):
    """Request payload for generating mocks from a specification.

    Wire field renamed: the server reads ``content`` (inline spec body),
    NOT ``spec``. Older SDK builds sent ``spec`` and every generator
    call 400'd with 'either url or content must be provided'. The
    Python-friendly ``spec=`` keyword is preserved via the alias.
    """

    spec: Optional[str] = Field(None, alias="content")
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

class SpecExportRequest(BaseModel):
    """Input for building a specification FROM mocks.

    The reverse of :class:`GeneratorRequest`: this one describes mocks with a
    document instead of describing mocks by one.
    """

    format: str
    namespace: Optional[str] = None
    folder_id: Optional[str] = Field(None, alias="folderId")
    tags: Optional[list[str]] = None
    mock_ids: Optional[list[str]] = Field(None, alias="mockIds")
    title: Optional[str] = None
    version: Optional[str] = None
    server_url: Optional[str] = Field(None, alias="serverUrl")

    model_config = {"populate_by_name": True}


class SpecExportWarning(BaseModel):
    """A mock the document could not fully express.

    Read these before trusting a document: a mock whose response is built by a
    script, rotates through oneOf variants, proxies a real upstream or reads a
    template file has no place in a specification, and the operation it belongs
    to stays in the document with a default response.
    """

    mock_id: str = Field("", alias="mockId")
    route: Optional[str] = None
    reason: str = ""

    model_config = {"populate_by_name": True}


class SpecExportStats(BaseModel):
    """Accounting for every mock considered, so a small document can be told
    apart from a filter that matched nothing."""

    considered: int = 0
    exported: int = 0
    skipped: int = 0
    paths: int = 0
    operations: int = 0
    channels: int = 0


class SpecExportResponse(BaseModel):
    """A built specification plus what it could not carry."""

    spec: dict[str, Any] = {}
    format: str = ""
    warnings: list[SpecExportWarning] = []
    stats: SpecExportStats = SpecExportStats()
