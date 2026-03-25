# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Contract testing API resource for API contract validation."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.contract import (
    ContractConfig,
    ContractResult,
    ContractValidationRequest,
    ContractValidationResult,
)
from mockarty.models.mock import Mock


class ContractAPI(SyncAPIBase):
    """Synchronous Contract API resource."""

    # ── Validation endpoints ───────────────────────────────────────────

    def validate_mocks(
        self, request: ContractValidationRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Validate mocks against an API specification."""
        resp = self._request(
            "POST", "/api/v1/contract/validate-mocks", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    def verify_provider(self, request: dict[str, Any]) -> ContractValidationResult:
        """Verify a provider against a contract."""
        resp = self._request(
            "POST", "/api/v1/contract/verify-provider", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    def check_compatibility(self, request: dict[str, Any]) -> ContractValidationResult:
        """Check compatibility between specs."""
        resp = self._request(
            "POST", "/api/v1/contract/check-compatibility", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    def validate_payload(self, request: dict[str, Any]) -> ContractValidationResult:
        """Validate a payload against a specification."""
        resp = self._request(
            "POST", "/api/v1/contract/validate-payload", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    # ── Config endpoints ───────────────────────────────────────────────

    def list_configs(self) -> list[ContractConfig]:
        """List all contract testing configurations."""
        resp = self._request("GET", "/api/v1/contract/configs")
        data = resp.json()
        if isinstance(data, list):
            return [ContractConfig.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("configs") or []
            return [ContractConfig.model_validate(c) for c in items]
        return []

    def save_config(
        self, config: ContractConfig | dict[str, Any]
    ) -> ContractConfig:
        """Save a contract testing configuration."""
        resp = self._request("POST", "/api/v1/contract/configs", json=config)
        return ContractConfig.model_validate(resp.json())

    def delete_config(self, config_id: str) -> None:
        """Delete a contract testing configuration."""
        self._request("DELETE", f"/api/v1/contract/configs/{config_id}")

    # ── Result endpoints ───────────────────────────────────────────────

    def list_results(self) -> list[ContractResult]:
        """List all contract testing results."""
        resp = self._request("GET", "/api/v1/contract/results")
        data = resp.json()
        if isinstance(data, list):
            return [ContractResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [ContractResult.model_validate(r) for r in items]
        return []

    def get_result(self, result_id: str) -> ContractResult:
        """Get a specific contract testing result."""
        resp = self._request("GET", f"/api/v1/contract/results/{result_id}")
        return ContractResult.model_validate(resp.json())

    # ── Pact endpoints ─────────────────────────────────────────────────

    def list_pacts(self) -> list[dict[str, Any]]:
        """List all pact contracts."""
        resp = self._request("GET", "/api/v1/contract/pacts")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("pacts") or []
        return []

    def get_pact(self, pact_id: str) -> dict[str, Any]:
        """Get a pact contract by ID."""
        resp = self._request("GET", f"/api/v1/contract/pacts/{pact_id}")
        return resp.json()

    def publish_pact(self, pact: dict[str, Any]) -> dict[str, Any]:
        """Publish a pact contract."""
        resp = self._request("POST", "/api/v1/contract/pacts", json=pact)
        return resp.json()

    def verify_pact(self, request: dict[str, Any]) -> dict[str, Any]:
        """Verify a pact contract against a provider."""
        resp = self._request(
            "POST", "/api/v1/contract/pacts/verify", json=request
        )
        return resp.json()

    def can_i_deploy(self, request: dict[str, Any]) -> dict[str, Any]:
        """Check if a service version can be deployed."""
        resp = self._request(
            "POST", "/api/v1/contract/pacts/can-i-deploy", json=request
        )
        return resp.json()

    def delete_pact(self, pact_id: str) -> None:
        """Delete a pact contract."""
        self._request("DELETE", f"/api/v1/contract/pacts/{pact_id}")

    def generate_mocks_from_pact(self, pact_id: str) -> list[Mock]:
        """Generate mocks from a pact contract."""
        resp = self._request(
            "POST", f"/api/v1/contract/pacts/{pact_id}/mocks"
        )
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        if isinstance(data, dict):
            items = data.get("mocks") or data.get("items") or []
            return [Mock.model_validate(m) for m in items]
        return []

    def list_verifications(self) -> list[dict[str, Any]]:
        """List all pact verification results."""
        resp = self._request("GET", "/api/v1/contract/pacts/verifications")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("verifications") or []
        return []

    def detect_drift(self, request: dict[str, Any]) -> dict[str, Any]:
        """Detect API drift between spec and implementation."""
        resp = self._request(
            "POST", "/api/v1/contract/detect-drift", json=request
        )
        return resp.json()


class AsyncContractAPI(AsyncAPIBase):
    """Asynchronous Contract API resource."""

    # ── Validation endpoints ───────────────────────────────────────────

    async def validate_mocks(
        self, request: ContractValidationRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Validate mocks against an API specification."""
        resp = await self._request(
            "POST", "/api/v1/contract/validate-mocks", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    async def verify_provider(
        self, request: dict[str, Any]
    ) -> ContractValidationResult:
        """Verify a provider against a contract."""
        resp = await self._request(
            "POST", "/api/v1/contract/verify-provider", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    async def check_compatibility(
        self, request: dict[str, Any]
    ) -> ContractValidationResult:
        """Check compatibility between specs."""
        resp = await self._request(
            "POST", "/api/v1/contract/check-compatibility", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    async def validate_payload(
        self, request: dict[str, Any]
    ) -> ContractValidationResult:
        """Validate a payload against a specification."""
        resp = await self._request(
            "POST", "/api/v1/contract/validate-payload", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    # ── Config endpoints ───────────────────────────────────────────────

    async def list_configs(self) -> list[ContractConfig]:
        """List all contract testing configurations."""
        resp = await self._request("GET", "/api/v1/contract/configs")
        data = resp.json()
        if isinstance(data, list):
            return [ContractConfig.model_validate(c) for c in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("configs") or []
            return [ContractConfig.model_validate(c) for c in items]
        return []

    async def save_config(
        self, config: ContractConfig | dict[str, Any]
    ) -> ContractConfig:
        """Save a contract testing configuration."""
        resp = await self._request(
            "POST", "/api/v1/contract/configs", json=config
        )
        return ContractConfig.model_validate(resp.json())

    async def delete_config(self, config_id: str) -> None:
        """Delete a contract testing configuration."""
        await self._request("DELETE", f"/api/v1/contract/configs/{config_id}")

    # ── Result endpoints ───────────────────────────────────────────────

    async def list_results(self) -> list[ContractResult]:
        """List all contract testing results."""
        resp = await self._request("GET", "/api/v1/contract/results")
        data = resp.json()
        if isinstance(data, list):
            return [ContractResult.model_validate(r) for r in data]
        if isinstance(data, dict):
            items = data.get("items") or data.get("results") or []
            return [ContractResult.model_validate(r) for r in items]
        return []

    async def get_result(self, result_id: str) -> ContractResult:
        """Get a specific contract testing result."""
        resp = await self._request(
            "GET", f"/api/v1/contract/results/{result_id}"
        )
        return ContractResult.model_validate(resp.json())

    # ── Pact endpoints ─────────────────────────────────────────────────

    async def list_pacts(self) -> list[dict[str, Any]]:
        """List all pact contracts."""
        resp = await self._request("GET", "/api/v1/contract/pacts")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("pacts") or []
        return []

    async def get_pact(self, pact_id: str) -> dict[str, Any]:
        """Get a pact contract by ID."""
        resp = await self._request(
            "GET", f"/api/v1/contract/pacts/{pact_id}"
        )
        return resp.json()

    async def publish_pact(self, pact: dict[str, Any]) -> dict[str, Any]:
        """Publish a pact contract."""
        resp = await self._request(
            "POST", "/api/v1/contract/pacts", json=pact
        )
        return resp.json()

    async def verify_pact(self, request: dict[str, Any]) -> dict[str, Any]:
        """Verify a pact contract against a provider."""
        resp = await self._request(
            "POST", "/api/v1/contract/pacts/verify", json=request
        )
        return resp.json()

    async def can_i_deploy(self, request: dict[str, Any]) -> dict[str, Any]:
        """Check if a service version can be deployed."""
        resp = await self._request(
            "POST", "/api/v1/contract/pacts/can-i-deploy", json=request
        )
        return resp.json()

    async def delete_pact(self, pact_id: str) -> None:
        """Delete a pact contract."""
        await self._request("DELETE", f"/api/v1/contract/pacts/{pact_id}")

    async def generate_mocks_from_pact(self, pact_id: str) -> list[Mock]:
        """Generate mocks from a pact contract."""
        resp = await self._request(
            "POST", f"/api/v1/contract/pacts/{pact_id}/mocks"
        )
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        if isinstance(data, dict):
            items = data.get("mocks") or data.get("items") or []
            return [Mock.model_validate(m) for m in items]
        return []

    async def list_verifications(self) -> list[dict[str, Any]]:
        """List all pact verification results."""
        resp = await self._request(
            "GET", "/api/v1/contract/pacts/verifications"
        )
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("verifications") or []
        return []

    async def detect_drift(self, request: dict[str, Any]) -> dict[str, Any]:
        """Detect API drift between spec and implementation."""
        resp = await self._request(
            "POST", "/api/v1/contract/detect-drift", json=request
        )
        return resp.json()
