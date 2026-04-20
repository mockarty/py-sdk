# Copyright (c) 2026 Mockarty. All rights reserved.

"""Prompts Storage API — managed AI prompts with FIFO-20 version history."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class PromptsAPI(SyncAPIBase):
    """Synchronous Prompts Storage API."""

    def list_prompts(self) -> list[dict[str, Any]]:
        resp = self._request(
            "GET", "/api/v1/stores/prompts", params={"namespace": self._namespace}
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def create_prompt(
        self,
        name: str,
        body: str,
        *,
        description: str | None = None,
        model: str | None = None,
        tags: list[str] | None = None,
        variables: dict[str, str] | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "body": body,
            "namespace": namespace or self._namespace,
        }
        if description is not None:
            payload["description"] = description
        if model is not None:
            payload["model"] = model
        if tags is not None:
            payload["tags"] = tags
        if variables is not None:
            payload["variables"] = variables
        resp = self._request("POST", "/api/v1/stores/prompts", json=payload)
        return resp.json()

    def get_prompt(self, prompt_id: str) -> dict[str, Any]:
        resp = self._request("GET", f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}")
        return resp.json()

    def update_prompt(self, prompt_id: str, **fields: Any) -> dict[str, Any]:
        """Updating ``body`` creates a new version (history FIFO-capped at 20)."""
        resp = self._request(
            "PUT",
            f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}",
            json=fields,
        )
        return resp.json()

    def delete_prompt(self, prompt_id: str) -> None:
        self._request("DELETE", f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}")

    def list_versions(self, prompt_id: str) -> list[dict[str, Any]]:
        resp = self._request(
            "GET", f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}/versions"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_version(self, prompt_id: str, version: int) -> dict[str, Any]:
        resp = self._request(
            "GET",
            f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}/versions/{int(version)}",
        )
        return resp.json()

    def rollback(self, prompt_id: str, to_version: int) -> dict[str, Any]:
        """Restore the prompt body from ``to_version``; current body is pushed to history."""
        resp = self._request(
            "POST",
            f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}/rollback",
            params={"to": int(to_version)},
        )
        return resp.json()


class AsyncPromptsAPI(AsyncAPIBase):
    """Asynchronous Prompts Storage API."""

    async def list_prompts(self) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET", "/api/v1/stores/prompts", params={"namespace": self._namespace}
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def create_prompt(
        self,
        name: str,
        body: str,
        *,
        description: str | None = None,
        model: str | None = None,
        tags: list[str] | None = None,
        variables: dict[str, str] | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "body": body,
            "namespace": namespace or self._namespace,
        }
        if description is not None:
            payload["description"] = description
        if model is not None:
            payload["model"] = model
        if tags is not None:
            payload["tags"] = tags
        if variables is not None:
            payload["variables"] = variables
        resp = await self._request("POST", "/api/v1/stores/prompts", json=payload)
        return resp.json()

    async def get_prompt(self, prompt_id: str) -> dict[str, Any]:
        resp = await self._request(
            "GET", f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}"
        )
        return resp.json()

    async def update_prompt(self, prompt_id: str, **fields: Any) -> dict[str, Any]:
        resp = await self._request(
            "PUT",
            f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}",
            json=fields,
        )
        return resp.json()

    async def delete_prompt(self, prompt_id: str) -> None:
        await self._request(
            "DELETE", f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}"
        )

    async def list_versions(self, prompt_id: str) -> list[dict[str, Any]]:
        resp = await self._request(
            "GET", f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}/versions"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_version(self, prompt_id: str, version: int) -> dict[str, Any]:
        resp = await self._request(
            "GET",
            f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}/versions/{int(version)}",
        )
        return resp.json()

    async def rollback(self, prompt_id: str, to_version: int) -> dict[str, Any]:
        resp = await self._request(
            "POST",
            f"/api/v1/stores/prompts/{quote(prompt_id, safe='')}/rollback",
            params={"to": int(to_version)},
        )
        return resp.json()
