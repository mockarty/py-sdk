# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Fuzzing API resource for security and reliability testing."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.fuzzing import FuzzingConfig, FuzzingResult, FuzzingRun


class FuzzingAPI(SyncAPIBase):
    """Synchronous Fuzzing API resource."""

    def create_config(self, config: FuzzingConfig | dict[str, Any]) -> FuzzingConfig:
        """Create a new fuzzing configuration."""
        resp = self._request("POST", "/api/v1/fuzzing/configs", json=config)
        return FuzzingConfig.model_validate(resp.json())

    def list_configs(self) -> list[FuzzingConfig]:
        """List all fuzzing configurations."""
        resp = self._request("GET", "/api/v1/fuzzing/configs")
        data = resp.json()
        if isinstance(data, list):
            return [FuzzingConfig.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("configs") or []
            return [FuzzingConfig.model_validate(c) for c in items]
        return []

    def get_config(self, config_id: str) -> FuzzingConfig:
        """Get a fuzzing configuration by ID."""
        resp = self._request("GET", f"/api/v1/fuzzing/configs/{config_id}")
        return FuzzingConfig.model_validate(resp.json())

    def delete_config(self, config_id: str) -> None:
        """Delete a fuzzing configuration."""
        self._request("DELETE", f"/api/v1/fuzzing/configs/{config_id}")

    def start(self, config: FuzzingConfig | dict[str, Any]) -> FuzzingRun:
        """Start a fuzzing test run."""
        resp = self._request("POST", "/api/v1/fuzzing/run", json=config)
        return FuzzingRun.model_validate(resp.json())

    def stop(self, run_id: str) -> None:
        """Stop a running fuzzing test."""
        self._request("POST", f"/api/v1/fuzzing/run/{run_id}/stop")

    def list_results(self) -> list[FuzzingResult]:
        """List all fuzzing test results."""
        resp = self._request("GET", "/api/v1/fuzzing/results")
        data = resp.json()
        if isinstance(data, list):
            return [FuzzingResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [FuzzingResult.model_validate(r) for r in items]
        return []

    def get_result(self, result_id: str) -> FuzzingResult:
        """Get a specific fuzzing test result."""
        resp = self._request("GET", f"/api/v1/fuzzing/results/{result_id}")
        return FuzzingResult.model_validate(resp.json())

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all fuzzing activity."""
        resp = self._request("GET", "/api/v1/fuzzing/summary")
        return resp.json()

    def quick_fuzz(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a quick fuzz test."""
        resp = self._request("POST", "/api/v1/fuzzing/quick-fuzz", json=request)
        return resp.json()

    # ── Findings ───────────────────────────────────────────────────────

    def list_findings(self) -> list[dict[str, Any]]:
        """List all fuzzing findings."""
        resp = self._request("GET", "/api/v1/fuzzing/findings")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("findings") or []
        return []

    def get_finding(self, finding_id: str) -> dict[str, Any]:
        """Get a specific fuzzing finding."""
        resp = self._request("GET", f"/api/v1/fuzzing/findings/{finding_id}")
        return resp.json()

    def triage_finding(
        self, finding_id: str, status: str, notes: str | None = None
    ) -> dict[str, Any]:
        """Triage a fuzzing finding by setting its status."""
        body: dict[str, Any] = {"status": status}
        if notes is not None:
            body["notes"] = notes
        resp = self._request(
            "PUT", f"/api/v1/fuzzing/findings/{finding_id}/triage", json=body
        )
        return resp.json()

    def replay_finding(self, finding_id: str) -> dict[str, Any]:
        """Replay a fuzzing finding."""
        resp = self._request("POST", f"/api/v1/fuzzing/findings/{finding_id}/replay")
        return resp.json()

    def analyze_finding(self, finding_id: str) -> dict[str, Any]:
        """Analyze a fuzzing finding with AI."""
        resp = self._request("POST", f"/api/v1/fuzzing/findings/{finding_id}/analyze")
        return resp.json()

    def batch_analyze(self, ids: list[str]) -> dict[str, Any]:
        """Batch analyze multiple fuzzing findings."""
        resp = self._request(
            "POST", "/api/v1/fuzzing/findings/batch-analyze", json={"ids": ids}
        )
        return resp.json()

    def batch_triage(self, ids: list[str], status: str) -> dict[str, Any]:
        """Batch triage multiple fuzzing findings."""
        resp = self._request(
            "POST",
            "/api/v1/fuzzing/findings/batch-triage",
            json={"ids": ids, "status": status},
        )
        return resp.json()

    def export_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """Export fuzzing findings."""
        resp = self._request("POST", "/api/v1/fuzzing/findings/export", json=request)
        return resp.json()

    # ── Imports ────────────────────────────────────────────────────────

    def import_from_curl(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing target from a cURL command."""
        resp = self._request("POST", "/api/v1/fuzzing/import/curl", json=data)
        return resp.json()

    def import_from_openapi(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from an OpenAPI spec."""
        resp = self._request("POST", "/api/v1/fuzzing/import/openapi", json=data)
        return resp.json()

    def import_from_collection(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from a collection."""
        resp = self._request("POST", "/api/v1/fuzzing/import/collection", json=data)
        return resp.json()

    def import_from_recorder(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from a recorder session."""
        resp = self._request("POST", "/api/v1/fuzzing/import/recorder", json=data)
        return resp.json()

    def import_from_mock(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from a mock."""
        resp = self._request("POST", "/api/v1/fuzzing/import/mock", json=data)
        return resp.json()

    # ── Schedules ──────────────────────────────────────────────────────

    def list_schedules(self) -> list[dict[str, Any]]:
        """List all fuzzing schedules."""
        resp = self._request("GET", "/api/v1/fuzzing/schedules")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("schedules") or []
        return []

    def create_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Create a fuzzing schedule."""
        resp = self._request("POST", "/api/v1/fuzzing/schedules", json=schedule)
        return resp.json()

    def update_schedule(
        self, schedule_id: str, schedule: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a fuzzing schedule."""
        resp = self._request(
            "PUT", f"/api/v1/fuzzing/schedules/{schedule_id}", json=schedule
        )
        return resp.json()

    def delete_schedule(self, schedule_id: str) -> None:
        """Delete a fuzzing schedule."""
        self._request("DELETE", f"/api/v1/fuzzing/schedules/{schedule_id}")


class AsyncFuzzingAPI(AsyncAPIBase):
    """Asynchronous Fuzzing API resource."""

    async def create_config(
        self, config: FuzzingConfig | dict[str, Any]
    ) -> FuzzingConfig:
        """Create a new fuzzing configuration."""
        resp = await self._request("POST", "/api/v1/fuzzing/configs", json=config)
        return FuzzingConfig.model_validate(resp.json())

    async def list_configs(self) -> list[FuzzingConfig]:
        """List all fuzzing configurations."""
        resp = await self._request("GET", "/api/v1/fuzzing/configs")
        data = resp.json()
        if isinstance(data, list):
            return [FuzzingConfig.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("configs") or []
            return [FuzzingConfig.model_validate(c) for c in items]
        return []

    async def get_config(self, config_id: str) -> FuzzingConfig:
        """Get a fuzzing configuration by ID."""
        resp = await self._request("GET", f"/api/v1/fuzzing/configs/{config_id}")
        return FuzzingConfig.model_validate(resp.json())

    async def delete_config(self, config_id: str) -> None:
        """Delete a fuzzing configuration."""
        await self._request("DELETE", f"/api/v1/fuzzing/configs/{config_id}")

    async def start(self, config: FuzzingConfig | dict[str, Any]) -> FuzzingRun:
        """Start a fuzzing test run."""
        resp = await self._request("POST", "/api/v1/fuzzing/run", json=config)
        return FuzzingRun.model_validate(resp.json())

    async def stop(self, run_id: str) -> None:
        """Stop a running fuzzing test."""
        await self._request("POST", f"/api/v1/fuzzing/run/{run_id}/stop")

    async def list_results(self) -> list[FuzzingResult]:
        """List all fuzzing test results."""
        resp = await self._request("GET", "/api/v1/fuzzing/results")
        data = resp.json()
        if isinstance(data, list):
            return [FuzzingResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [FuzzingResult.model_validate(r) for r in items]
        return []

    async def get_result(self, result_id: str) -> FuzzingResult:
        """Get a specific fuzzing test result."""
        resp = await self._request("GET", f"/api/v1/fuzzing/results/{result_id}")
        return FuzzingResult.model_validate(resp.json())

    # ── Summary ────────────────────────────────────────────────────────

    async def get_summary(self) -> dict[str, Any]:
        """Get a summary of all fuzzing activity."""
        resp = await self._request("GET", "/api/v1/fuzzing/summary")
        return resp.json()

    async def quick_fuzz(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run a quick fuzz test."""
        resp = await self._request("POST", "/api/v1/fuzzing/quick-fuzz", json=request)
        return resp.json()

    # ── Findings ───────────────────────────────────────────────────────

    async def list_findings(self) -> list[dict[str, Any]]:
        """List all fuzzing findings."""
        resp = await self._request("GET", "/api/v1/fuzzing/findings")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("findings") or []
        return []

    async def get_finding(self, finding_id: str) -> dict[str, Any]:
        """Get a specific fuzzing finding."""
        resp = await self._request("GET", f"/api/v1/fuzzing/findings/{finding_id}")
        return resp.json()

    async def triage_finding(
        self, finding_id: str, status: str, notes: str | None = None
    ) -> dict[str, Any]:
        """Triage a fuzzing finding by setting its status."""
        body: dict[str, Any] = {"status": status}
        if notes is not None:
            body["notes"] = notes
        resp = await self._request(
            "PUT", f"/api/v1/fuzzing/findings/{finding_id}/triage", json=body
        )
        return resp.json()

    async def replay_finding(self, finding_id: str) -> dict[str, Any]:
        """Replay a fuzzing finding."""
        resp = await self._request(
            "POST", f"/api/v1/fuzzing/findings/{finding_id}/replay"
        )
        return resp.json()

    async def analyze_finding(self, finding_id: str) -> dict[str, Any]:
        """Analyze a fuzzing finding with AI."""
        resp = await self._request(
            "POST", f"/api/v1/fuzzing/findings/{finding_id}/analyze"
        )
        return resp.json()

    async def batch_analyze(self, ids: list[str]) -> dict[str, Any]:
        """Batch analyze multiple fuzzing findings."""
        resp = await self._request(
            "POST",
            "/api/v1/fuzzing/findings/batch-analyze",
            json={"ids": ids},
        )
        return resp.json()

    async def batch_triage(self, ids: list[str], status: str) -> dict[str, Any]:
        """Batch triage multiple fuzzing findings."""
        resp = await self._request(
            "POST",
            "/api/v1/fuzzing/findings/batch-triage",
            json={"ids": ids, "status": status},
        )
        return resp.json()

    async def export_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """Export fuzzing findings."""
        resp = await self._request(
            "POST", "/api/v1/fuzzing/findings/export", json=request
        )
        return resp.json()

    # ── Imports ────────────────────────────────────────────────────────

    async def import_from_curl(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing target from a cURL command."""
        resp = await self._request("POST", "/api/v1/fuzzing/import/curl", json=data)
        return resp.json()

    async def import_from_openapi(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from an OpenAPI spec."""
        resp = await self._request("POST", "/api/v1/fuzzing/import/openapi", json=data)
        return resp.json()

    async def import_from_collection(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from a collection."""
        resp = await self._request(
            "POST", "/api/v1/fuzzing/import/collection", json=data
        )
        return resp.json()

    async def import_from_recorder(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from a recorder session."""
        resp = await self._request("POST", "/api/v1/fuzzing/import/recorder", json=data)
        return resp.json()

    async def import_from_mock(self, data: dict[str, Any]) -> dict[str, Any]:
        """Import fuzzing targets from a mock."""
        resp = await self._request("POST", "/api/v1/fuzzing/import/mock", json=data)
        return resp.json()

    # ── Schedules ──────────────────────────────────────────────────────

    async def list_schedules(self) -> list[dict[str, Any]]:
        """List all fuzzing schedules."""
        resp = await self._request("GET", "/api/v1/fuzzing/schedules")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("schedules") or []
        return []

    async def create_schedule(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Create a fuzzing schedule."""
        resp = await self._request("POST", "/api/v1/fuzzing/schedules", json=schedule)
        return resp.json()

    async def update_schedule(
        self, schedule_id: str, schedule: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a fuzzing schedule."""
        resp = await self._request(
            "PUT", f"/api/v1/fuzzing/schedules/{schedule_id}", json=schedule
        )
        return resp.json()

    async def delete_schedule(self, schedule_id: str) -> None:
        """Delete a fuzzing schedule."""
        await self._request("DELETE", f"/api/v1/fuzzing/schedules/{schedule_id}")
