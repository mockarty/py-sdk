# Copyright (c) 2026 Mockarty. All rights reserved.

"""Performance testing API resource."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.common import PerfComparison, PerfConfig, PerfResult, PerfTask


class PerfAPI(SyncAPIBase):
    """Synchronous Performance testing API resource."""

    def run(self, config: PerfConfig | dict[str, Any]) -> PerfTask:
        """Start a new performance test run."""
        resp = self._request("POST", "/api/v1/perf/run", json=config)
        return PerfTask.model_validate(resp.json())

    def stop(self, task_id: str) -> None:
        """Stop a running performance test."""
        self._request("POST", f"/api/v1/perf/stop/{task_id}")

    def results(self) -> list[PerfResult]:
        """List all performance test results."""
        resp = self._request("GET", "/api/v1/perf-results")
        data = resp.json()
        if isinstance(data, list):
            return [PerfResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [PerfResult.model_validate(r) for r in items]
        return []

    def get_result(self, result_id: str) -> PerfResult:
        """Get a specific performance test result."""
        resp = self._request("GET", f"/api/v1/perf-results/{result_id}")
        return PerfResult.model_validate(resp.json())

    def compare(self, ids: list[str]) -> PerfComparison:
        """Compare multiple performance test results."""
        resp = self._request(
            "GET", "/api/v1/perf-results/compare", params={"ids": ",".join(ids)}
        )
        return PerfComparison.model_validate(resp.json())

    # ── Configs ────────────────────────────────────────────────────────

    def list_configs(self) -> list[PerfConfig]:
        """List all performance test configurations."""
        resp = self._request("GET", "/api/v1/perf-configs")
        data = resp.json()
        if isinstance(data, list):
            return [PerfConfig.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("configs") or []
            return [PerfConfig.model_validate(c) for c in items]
        return []

    def get_config(self, config_id: str) -> PerfConfig:
        """Get a performance test configuration by ID."""
        resp = self._request("GET", f"/api/v1/perf-configs/{config_id}")
        return PerfConfig.model_validate(resp.json())

    def create_config(self, config: PerfConfig | dict[str, Any]) -> PerfConfig:
        """Create a performance test configuration."""
        resp = self._request("POST", "/api/v1/perf-configs", json=config)
        return PerfConfig.model_validate(resp.json())

    def update_config(
        self, config_id: str, config: PerfConfig | dict[str, Any]
    ) -> PerfConfig:
        """Update a performance test configuration."""
        resp = self._request("PUT", f"/api/v1/perf-configs/{config_id}", json=config)
        return PerfConfig.model_validate(resp.json())

    def delete_config(self, config_id: str) -> None:
        """Delete a performance test configuration."""
        self._request("DELETE", f"/api/v1/perf-configs/{config_id}")

    # ── Schedules ──────────────────────────────────────────────────────

    def list_schedules(self) -> list[dict[str, Any]]:
        """List all performance test schedules."""
        resp = self._request("GET", "/api/v1/perf-schedules")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("schedules") or []
        return []

    def create_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Create a performance test schedule."""
        resp = self._request("POST", "/api/v1/perf-schedules", json=schedule)
        return resp.json()

    def update_schedule(
        self, schedule_id: str, schedule: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a performance test schedule."""
        resp = self._request(
            "PUT", f"/api/v1/perf-schedules/{schedule_id}", json=schedule
        )
        return resp.json()

    def delete_schedule(self, schedule_id: str) -> None:
        """Delete a performance test schedule."""
        self._request("DELETE", f"/api/v1/perf-schedules/{schedule_id}")

    # ── Result history / trend ─────────────────────────────────────────

    def get_result_history(self, config_id: str) -> list[PerfResult]:
        """Get result history for a performance test config."""
        resp = self._request("GET", f"/api/v1/perf-results/history/{config_id}")
        data = resp.json()
        if isinstance(data, list):
            return [PerfResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [PerfResult.model_validate(r) for r in items]
        return []

    def get_result_trend(self, config_id: str) -> dict[str, Any]:
        """Get result trend data for a performance test config."""
        resp = self._request("GET", f"/api/v1/perf-results/trend/{config_id}")
        return resp.json()

    def delete_result(self, result_id: str) -> None:
        """Delete a performance test result."""
        self._request("DELETE", f"/api/v1/perf-results/{result_id}")

    def run_collection(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a performance test from a collection."""
        resp = self._request("POST", "/api/v1/perf/run-collection", json=request)
        return resp.json()


class AsyncPerfAPI(AsyncAPIBase):
    """Asynchronous Performance testing API resource."""

    async def run(self, config: PerfConfig | dict[str, Any]) -> PerfTask:
        """Start a new performance test run."""
        resp = await self._request("POST", "/api/v1/perf/run", json=config)
        return PerfTask.model_validate(resp.json())

    async def stop(self, task_id: str) -> None:
        """Stop a running performance test."""
        await self._request("POST", f"/api/v1/perf/stop/{task_id}")

    async def results(self) -> list[PerfResult]:
        """List all performance test results."""
        resp = await self._request("GET", "/api/v1/perf-results")
        data = resp.json()
        if isinstance(data, list):
            return [PerfResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [PerfResult.model_validate(r) for r in items]
        return []

    async def get_result(self, result_id: str) -> PerfResult:
        """Get a specific performance test result."""
        resp = await self._request("GET", f"/api/v1/perf-results/{result_id}")
        return PerfResult.model_validate(resp.json())

    async def compare(self, ids: list[str]) -> PerfComparison:
        """Compare multiple performance test results."""
        resp = await self._request(
            "GET", "/api/v1/perf-results/compare", params={"ids": ",".join(ids)}
        )
        return PerfComparison.model_validate(resp.json())

    # ── Configs ────────────────────────────────────────────────────────

    async def list_configs(self) -> list[PerfConfig]:
        """List all performance test configurations."""
        resp = await self._request("GET", "/api/v1/perf-configs")
        data = resp.json()
        if isinstance(data, list):
            return [PerfConfig.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("configs") or []
            return [PerfConfig.model_validate(c) for c in items]
        return []

    async def get_config(self, config_id: str) -> PerfConfig:
        """Get a performance test configuration by ID."""
        resp = await self._request("GET", f"/api/v1/perf-configs/{config_id}")
        return PerfConfig.model_validate(resp.json())

    async def create_config(self, config: PerfConfig | dict[str, Any]) -> PerfConfig:
        """Create a performance test configuration."""
        resp = await self._request("POST", "/api/v1/perf-configs", json=config)
        return PerfConfig.model_validate(resp.json())

    async def update_config(
        self, config_id: str, config: PerfConfig | dict[str, Any]
    ) -> PerfConfig:
        """Update a performance test configuration."""
        resp = await self._request(
            "PUT", f"/api/v1/perf-configs/{config_id}", json=config
        )
        return PerfConfig.model_validate(resp.json())

    async def delete_config(self, config_id: str) -> None:
        """Delete a performance test configuration."""
        await self._request("DELETE", f"/api/v1/perf-configs/{config_id}")

    # ── Schedules ──────────────────────────────────────────────────────

    async def list_schedules(self) -> list[dict[str, Any]]:
        """List all performance test schedules."""
        resp = await self._request("GET", "/api/v1/perf-schedules")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("schedules") or []
        return []

    async def create_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Create a performance test schedule."""
        resp = await self._request("POST", "/api/v1/perf-schedules", json=schedule)
        return resp.json()

    async def update_schedule(
        self, schedule_id: str, schedule: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a performance test schedule."""
        resp = await self._request(
            "PUT", f"/api/v1/perf-schedules/{schedule_id}", json=schedule
        )
        return resp.json()

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a performance test schedule."""
        await self._request("DELETE", f"/api/v1/perf-schedules/{schedule_id}")

    # ── Result history / trend ─────────────────────────────────────────

    async def get_result_history(self, config_id: str) -> list[PerfResult]:
        """Get result history for a performance test config."""
        resp = await self._request("GET", f"/api/v1/perf-results/history/{config_id}")
        data = resp.json()
        if isinstance(data, list):
            return [PerfResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [PerfResult.model_validate(r) for r in items]
        return []

    async def get_result_trend(self, config_id: str) -> dict[str, Any]:
        """Get result trend data for a performance test config."""
        resp = await self._request("GET", f"/api/v1/perf-results/trend/{config_id}")
        return resp.json()

    async def delete_result(self, result_id: str) -> None:
        """Delete a performance test result."""
        await self._request("DELETE", f"/api/v1/perf-results/{result_id}")

    async def run_collection(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a performance test from a collection."""
        resp = await self._request("POST", "/api/v1/perf/run-collection", json=request)
        return resp.json()
