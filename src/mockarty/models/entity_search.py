# Copyright (c) 2026 Mockarty. All rights reserved.

"""Entity-search models.

Wire format mirrors ``internal/webui/entity_search_handlers.go``: the server
returns camelCase keys (``createdAt``, ``numericId``) so we use Pydantic
field aliases. Population is allowed by either alias or attribute name to
keep callers ergonomic from both directions.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Constants — kept in sync with internal/webui/entity_search_handlers.go.
# Use these instead of bare strings so a typo at the call site is caught at
# import time rather than as an empty server response.
# ---------------------------------------------------------------------------

ENTITY_TYPE_MOCK = "mock"
ENTITY_TYPE_TEST_PLAN = "test_plan"
ENTITY_TYPE_PERF_CONFIG = "perf_config"
ENTITY_TYPE_FUZZ_CONFIG = "fuzz_config"
ENTITY_TYPE_CHAOS_EXPERIMENT = "chaos_experiment"
ENTITY_TYPE_CONTRACT_PACT = "contract_pact"

ENTITY_SEARCH_DEFAULT_LIMIT = 50
ENTITY_SEARCH_MAX_LIMIT = 200


class EntitySearchResult(BaseModel):
    """A single picker row.

    ``numeric_id`` is optional — only entity types with a human-friendly
    numeric identifier (e.g. Test Plans) populate it. The rest leave it as
    ``None``.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    name: str
    namespace: str
    created_at: str = Field(alias="createdAt")
    numeric_id: Optional[int] = Field(default=None, alias="numericId")


class EntitySearchResponse(BaseModel):
    """Picker response envelope.

    ``total`` is the count BEFORE pagination, suitable for rendering
    "showing N of M" hints in custom pickers.
    """

    items: List[EntitySearchResult] = Field(default_factory=list)
    total: int = 0
