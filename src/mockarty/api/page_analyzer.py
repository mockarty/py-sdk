"""HTTP-level Page Analyzer lifecycle."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


_BASE = "/api/v1/page-analyzer"


def _id(value: str, kind: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"page analyzer {kind} id is required")
    return quote(value, safe="")


class PageAnalyzerAPI(SyncAPIBase):
    def list_configs(self) -> dict[str, Any]:
        return self._request("GET", f"{_BASE}/configs", params={"namespace": self._namespace}).json()

    def save_config(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{_BASE}/configs", params={"namespace": self._namespace}, json=body).json()

    def update_config(self, config_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"{_BASE}/configs/{_id(config_id, 'config')}", params={"namespace": self._namespace}, json=body).json()

    def delete_config(self, config_id: str) -> None:
        self._request("DELETE", f"{_BASE}/configs/{_id(config_id, 'config')}", params={"namespace": self._namespace})

    def run(self, body: dict[str, Any]) -> dict[str, Any]:
        if not body.get("targetUrl") and not body.get("configId"):
            raise ValueError("page analyzer targetUrl or configId is required")
        return self._request("POST", f"{_BASE}/run", params={"namespace": self._namespace}, json=body).json()

    def list_results(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return self._request("GET", f"{_BASE}/results", params={"namespace": self._namespace, "limit": limit, "offset": offset}).json()

    def get_result(self, result_id: str) -> dict[str, Any]:
        return self._request("GET", f"{_BASE}/results/{_id(result_id, 'result')}", params={"namespace": self._namespace}).json()

    def delete_result(self, result_id: str) -> None:
        self._request("DELETE", f"{_BASE}/results/{_id(result_id, 'result')}", params={"namespace": self._namespace})

    def analyze_with_ai(self, result_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", f"{_BASE}/results/{_id(result_id, 'result')}/ai-analyze", params={"namespace": self._namespace}, json=body or {}).json()


class AsyncPageAnalyzerAPI(AsyncAPIBase):
    async def list_configs(self) -> dict[str, Any]:
        return (await self._request("GET", f"{_BASE}/configs", params={"namespace": self._namespace})).json()

    async def save_config(self, body: dict[str, Any]) -> dict[str, Any]:
        return (await self._request("POST", f"{_BASE}/configs", params={"namespace": self._namespace}, json=body)).json()

    async def update_config(self, config_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return (await self._request("PUT", f"{_BASE}/configs/{_id(config_id, 'config')}", params={"namespace": self._namespace}, json=body)).json()

    async def delete_config(self, config_id: str) -> None:
        await self._request("DELETE", f"{_BASE}/configs/{_id(config_id, 'config')}", params={"namespace": self._namespace})

    async def run(self, body: dict[str, Any]) -> dict[str, Any]:
        if not body.get("targetUrl") and not body.get("configId"):
            raise ValueError("page analyzer targetUrl or configId is required")
        return (await self._request("POST", f"{_BASE}/run", params={"namespace": self._namespace}, json=body)).json()

    async def list_results(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        return (await self._request("GET", f"{_BASE}/results", params={"namespace": self._namespace, "limit": limit, "offset": offset})).json()

    async def get_result(self, result_id: str) -> dict[str, Any]:
        return (await self._request("GET", f"{_BASE}/results/{_id(result_id, 'result')}", params={"namespace": self._namespace})).json()

    async def delete_result(self, result_id: str) -> None:
        await self._request("DELETE", f"{_BASE}/results/{_id(result_id, 'result')}", params={"namespace": self._namespace})

    async def analyze_with_ai(self, result_id: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return (await self._request("POST", f"{_BASE}/results/{_id(result_id, 'result')}/ai-analyze", params={"namespace": self._namespace}, json=body or {})).json()
