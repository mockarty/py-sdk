# Copyright (c) 2026 Mockarty. All rights reserved.

"""Namespace management API resource."""

from __future__ import annotations

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class NamespaceAPI(SyncAPIBase):
    """Synchronous Namespace API resource."""

    def create(self, name: str) -> None:
        """Create a new namespace."""
        self._request("POST", "/api/v1/namespaces", json={"name": name})

    def list(self) -> list[str]:
        """List all available namespaces."""
        resp = self._request("GET", "/api/v1/namespaces")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("namespaces") or data.get("items") or []
        return []

    def copy_mocks(
        self,
        source_namespace: str,
        target_namespace: str,
        mock_ids: list[str] | None = None,
    ) -> None:
        """Copy mocks from one namespace to another.

        Args:
            source_namespace: Source namespace name.
            target_namespace: Target namespace name.
            mock_ids: Optional list of specific mock IDs to copy.
                      If omitted, all mocks are copied.
        """
        body = {
            "sourceNamespace": source_namespace,
            "targetNamespace": target_namespace,
        }
        if mock_ids is not None:
            body["mockIds"] = mock_ids  # type: ignore[assignment]
        self._request("POST", "/api/v1/namespaces/copy-mocks", json=body)


class AsyncNamespaceAPI(AsyncAPIBase):
    """Asynchronous Namespace API resource."""

    async def create(self, name: str) -> None:
        """Create a new namespace."""
        await self._request("POST", "/api/v1/namespaces", json={"name": name})

    async def list(self) -> list[str]:
        """List all available namespaces."""
        resp = await self._request("GET", "/api/v1/namespaces")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("namespaces") or data.get("items") or []
        return []

    async def copy_mocks(
        self,
        source_namespace: str,
        target_namespace: str,
        mock_ids: list[str] | None = None,
    ) -> None:
        """Copy mocks from one namespace to another."""
        body = {
            "sourceNamespace": source_namespace,
            "targetNamespace": target_namespace,
        }
        if mock_ids is not None:
            body["mockIds"] = mock_ids  # type: ignore[assignment]
        await self._request("POST", "/api/v1/namespaces/copy-mocks", json=body)
