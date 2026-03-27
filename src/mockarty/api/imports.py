# Copyright (c) 2026 Mockarty. All rights reserved.

"""Import API resource for importing collections from external tools."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.imports import ImportResult


class ImportAPI(SyncAPIBase):
    """Synchronous Import API resource."""

    def postman(self, collection: dict[str, Any]) -> ImportResult:
        """Import a Postman collection."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/postman", json=collection
        )
        return ImportResult.model_validate(resp.json())

    def insomnia(self, collection: dict[str, Any]) -> ImportResult:
        """Import an Insomnia collection."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/insomnia", json=collection
        )
        return ImportResult.model_validate(resp.json())

    def har(self, data: dict[str, Any]) -> ImportResult:
        """Import a HAR (HTTP Archive) file."""
        resp = self._request("POST", "/api/v1/api-tester/import/har", json=data)
        return ImportResult.model_validate(resp.json())

    def curl(self, commands: list[str]) -> ImportResult:
        """Import from cURL commands."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/curl", json={"commands": commands}
        )
        return ImportResult.model_validate(resp.json())


class AsyncImportAPI(AsyncAPIBase):
    """Asynchronous Import API resource."""

    async def postman(self, collection: dict[str, Any]) -> ImportResult:
        """Import a Postman collection."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/import/postman", json=collection
        )
        return ImportResult.model_validate(resp.json())

    async def insomnia(self, collection: dict[str, Any]) -> ImportResult:
        """Import an Insomnia collection."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/import/insomnia", json=collection
        )
        return ImportResult.model_validate(resp.json())

    async def har(self, data: dict[str, Any]) -> ImportResult:
        """Import a HAR (HTTP Archive) file."""
        resp = await self._request("POST", "/api/v1/api-tester/import/har", json=data)
        return ImportResult.model_validate(resp.json())

    async def curl(self, commands: list[str]) -> ImportResult:
        """Import from cURL commands."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/import/curl", json={"commands": commands}
        )
        return ImportResult.model_validate(resp.json())
