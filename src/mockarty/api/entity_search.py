# Copyright (c) 2026 Mockarty. All rights reserved.

"""Entity-search API resource.

Wraps the unified picker endpoint
(``GET /api/v1/entity-search``) defined in
``internal/webui/entity_search_handlers.go``. Used by UI pickers and CI/CD
automation that needs to resolve a human-readable name into the canonical
UUID before issuing further API calls.

Example (sync)::

    with MockartyClient() as c:
        plans = c.entity_search.search(
            entity_type=ENTITY_TYPE_TEST_PLAN,
            query="smoke",
            limit=25,
        )
        for p in plans.items:
            print(p.id, p.name, p.numeric_id)

Tenant-scoped tokens cannot search a different namespace via the
``namespace`` parameter — the server silently ignores the override and uses
the token's bound namespace. Global admins may pass any namespace (or leave
it empty for cross-namespace search).
"""

from __future__ import annotations

from typing import Any, Optional

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.entity_search import EntitySearchResponse


_PATH = "/api/v1/entity-search"


def _build_params(
    *,
    entity_type: str,
    namespace: Optional[str],
    query: Optional[str],
    limit: Optional[int],
    offset: Optional[int],
) -> dict[str, Any]:
    t = (entity_type or "").strip()
    if not t:
        raise ValueError("entity_type is required")
    params: dict[str, Any] = {"type": t}
    if namespace:
        ns = namespace.strip()
        if ns:
            params["namespace"] = ns
    if query:
        q = query.strip()
        if q:
            params["q"] = q
    if limit is not None and limit > 0:
        params["limit"] = int(limit)
    if offset is not None and offset > 0:
        params["offset"] = int(offset)
    return params


class EntitySearchAPI(SyncAPIBase):
    """Synchronous entity-search API resource."""

    def search(
        self,
        *,
        entity_type: str,
        namespace: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> EntitySearchResponse:
        """GET /api/v1/entity-search.

        Args:
            entity_type: One of the ``ENTITY_TYPE_*`` constants.
            namespace: Optional namespace filter. Tenant tokens always
                resolve to their bound namespace regardless of this value.
            query: Optional case-insensitive substring match on name.
            limit: Server caps at ``ENTITY_SEARCH_MAX_LIMIT`` (200).
                Defaults to 50 server-side when omitted.
            offset: Pagination offset. ``0`` is treated identically to
                ``None`` and omitted from the request.
        """
        params = _build_params(
            entity_type=entity_type,
            namespace=namespace,
            query=query,
            limit=limit,
            offset=offset,
        )
        resp = self._request("GET", _PATH, params=params)
        return EntitySearchResponse.model_validate(resp.json())


class AsyncEntitySearchAPI(AsyncAPIBase):
    """Asynchronous entity-search API resource (mirrors EntitySearchAPI)."""

    async def search(
        self,
        *,
        entity_type: str,
        namespace: Optional[str] = None,
        query: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> EntitySearchResponse:
        params = _build_params(
            entity_type=entity_type,
            namespace=namespace,
            query=query,
            limit=limit,
            offset=offset,
        )
        resp = await self._request("GET", _PATH, params=params)
        return EntitySearchResponse.model_validate(resp.json())
