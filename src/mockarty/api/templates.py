# Copyright (c) 2026 Mockarty. All rights reserved.

"""Template API resource for managing payload templates."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.templates import TemplateFile


class TemplateAPI(SyncAPIBase):
    """Synchronous Template API resource."""

    def list(self) -> list[TemplateFile]:
        """List all available payload templates."""
        resp = self._request("GET", "/api/v1/templates")
        data = resp.json()
        if isinstance(data, list):
            return [TemplateFile.model_validate(t) for t in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("templates") or []
            return [TemplateFile.model_validate(t) for t in items]
        return []

    def get(self, name: str) -> str:
        """Get the content of a template file by name."""
        resp = self._request("GET", f"/api/v1/templates/{name}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("content") or ""
        return resp.text

    def create(self, name: str, content: str) -> TemplateFile:
        """Create or update a payload template."""
        resp = self._request(
            "POST", "/api/v1/templates", json={"name": name, "content": content}
        )
        return TemplateFile.model_validate(resp.json())

    def delete(self, name: str) -> None:
        """Delete a template file."""
        self._request("DELETE", f"/api/v1/templates/{name}")


class AsyncTemplateAPI(AsyncAPIBase):
    """Asynchronous Template API resource."""

    async def list(self) -> list[TemplateFile]:
        """List all available payload templates."""
        resp = await self._request("GET", "/api/v1/templates")
        data = resp.json()
        if isinstance(data, list):
            return [TemplateFile.model_validate(t) for t in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("templates") or []
            return [TemplateFile.model_validate(t) for t in items]
        return []

    async def get(self, name: str) -> str:
        """Get the content of a template file by name."""
        resp = await self._request("GET", f"/api/v1/templates/{name}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("content") or ""
        return resp.text

    async def create(self, name: str, content: str) -> TemplateFile:
        """Create or update a payload template."""
        resp = await self._request(
            "POST", "/api/v1/templates", json={"name": name, "content": content}
        )
        return TemplateFile.model_validate(resp.json())

    async def delete(self, name: str) -> None:
        """Delete a template file."""
        await self._request("DELETE", f"/api/v1/templates/{name}")
