# Copyright (c) 2026 Mockarty. All rights reserved.

"""Per-caller endpoints (``/api/v1/me/*``).

Currently exposes ``awaiting_manual()`` — the topbar bell-counter back-end
that lists every TCM case-run step waiting on the calling identity for a
manual verdict. Useful as a CI guard:

.. code-block:: python

    pending = client.me.awaiting_manual()
    if pending["count"] > 0:
        raise SystemExit(f"{pending['count']} steps still waiting on QA")
"""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class MeAPI(SyncAPIBase):
    """Synchronous /api/v1/me/* endpoints."""

    def awaiting_manual(self) -> dict[str, Any]:
        """Return ``{"count": int, "items": [...]}``.

        Each item carries the deep-link URL the topbar dropdown opens; CI
        scripts can surface the same URL in alerts so the on-call QA jumps
        straight to the resolve-drawer.
        """
        resp = self._request("GET", "/api/v1/me/awaiting-manual")
        return resp.json()


class AsyncMeAPI(AsyncAPIBase):
    """Asynchronous /api/v1/me/* endpoints."""

    async def awaiting_manual(self) -> dict[str, Any]:
        resp = await self._request("GET", "/api/v1/me/awaiting-manual")
        return resp.json()
