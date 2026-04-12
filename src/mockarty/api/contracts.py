# Copyright (c) 2026 Mockarty. All rights reserved.

"""Contract testing API resource for API contract validation."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.contract import (
    CheckCompatibilityRequest,
    ContractConfig,
    ContractResult,
    ContractValidationRequest,
    ContractValidationResult,
    DriftDetectionRequest,
    PactVerifyRequest,
    ValidatePayloadRequest,
)
from mockarty.models.mock import Mock


class ContractAPI(SyncAPIBase):
    """Synchronous Contract API resource."""

    # ── Validation endpoints ───────────────────────────────────────────

    def validate_mocks(
        self, request: ContractValidationRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Validate mocks against an API specification."""
        resp = self._request("POST", "/api/v1/contract/validate-mocks", json=request)
        return ContractValidationResult.model_validate(resp.json())

    def verify_provider(
        self, request: ContractValidationRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Verify a provider against a contract."""
        resp = self._request("POST", "/api/v1/contract/verify-provider", json=request)
        return ContractValidationResult.model_validate(resp.json())

    def check_compatibility(
        self, request: CheckCompatibilityRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Check backward compatibility between two spec versions."""
        resp = self._request(
            "POST", "/api/v1/contract/check-compatibility", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    def validate_payload(
        self, request: ValidatePayloadRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Validate a single JSON payload against a spec schema."""
        resp = self._request("POST", "/api/v1/contract/validate-payload", json=request)
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

    def save_config(self, config: ContractConfig | dict[str, Any]) -> ContractConfig:
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

    def verify_pact(
        self, request: PactVerifyRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Verify a pact contract against a provider."""
        resp = self._request("POST", "/api/v1/contract/pacts/verify", json=request)
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
        resp = self._request("POST", f"/api/v1/contract/pacts/{pact_id}/mocks")
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

    def detect_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect API drift between mocks and live service."""
        resp = self._request("POST", "/api/v1/contract/detect-drift", json=request)
        return resp.json()

    def detect_graphql_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect GraphQL schema drift via introspection."""
        resp = self._request(
            "POST", "/api/v1/contract/detect-drift/graphql", json=request
        )
        return resp.json()

    def detect_grpc_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect gRPC service drift via reflection."""
        resp = self._request("POST", "/api/v1/contract/detect-drift/grpc", json=request)
        return resp.json()

    def detect_wsdl_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect SOAP/WSDL service drift."""
        resp = self._request("POST", "/api/v1/contract/detect-drift/wsdl", json=request)
        return resp.json()

    def detect_mcp_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect MCP server drift."""
        resp = self._request("POST", "/api/v1/contract/detect-drift/mcp", json=request)
        return resp.json()

    # ── API Registry ────────────────────────────────────────────────

    def list_registry(
        self, query: str = "", spec_type: str = ""
    ) -> list[dict[str, Any]]:
        """List published APIs in the registry."""
        params: dict[str, str] = {}
        if query:
            params["q"] = query
        if spec_type:
            params["specType"] = spec_type
        resp = self._request("GET", "/api/v1/contract/registry", params=params)
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_registry_entry(self, entry_id: str) -> dict[str, Any]:
        """Get a single registry entry by ID."""
        resp = self._request("GET", f"/api/v1/contract/registry/{entry_id}")
        return resp.json()

    def publish_to_registry(
        self,
        service_name: str,
        spec_type: str = "openapi",
        version: str = "",
        description: str = "",
        visibility: str = "public",
        spec_content: str | None = None,
        spec_url: str | None = None,
    ) -> dict[str, Any]:
        """Publish an API specification to the internal registry."""
        body: dict[str, Any] = {
            "serviceName": service_name,
            "specType": spec_type,
            "visibility": visibility,
        }
        if version:
            body["version"] = version
        if description:
            body["description"] = description
        if spec_content:
            body["specContent"] = spec_content
        if spec_url:
            body["specUrl"] = spec_url
        resp = self._request("POST", "/api/v1/contract/registry", json=body)
        return resp.json()

    def update_registry_entry(
        self, entry_id: str, update: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing registry entry."""
        resp = self._request(
            "PUT", f"/api/v1/contract/registry/{entry_id}", json=update
        )
        return resp.json()

    def delete_registry_entry(self, entry_id: str) -> None:
        """Delete a registry entry."""
        self._request("DELETE", f"/api/v1/contract/registry/{entry_id}")

    def generate_mocks_from_registry(self, entry_id: str) -> dict[str, Any]:
        """Generate Mockarty mocks from a registry entry's specification."""
        resp = self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/generate-mocks"
        )
        return resp.json()

    def check_impact(self, entry_id: str, new_spec_content: str) -> dict[str, Any]:
        """Check which subscribers would be affected by a spec change."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/check-impact",
            json={"newSpecContent": new_spec_content},
        )
        return resp.json()

    # ── Subscriptions ───────────────────────────────────────────────

    def list_subscriptions(self) -> list[dict[str, Any]]:
        """List current namespace's subscriptions to APIs."""
        resp = self._request("GET", "/api/v1/contract/subscriptions")
        data = resp.json()
        return data if isinstance(data, list) else []

    def subscribe(
        self,
        registry_entry_id: str,
        service_name: str,
        watch_endpoints: list[str] | None = None,
        notify_on_breaking: bool = True,
        auto_block: bool = False,
    ) -> dict[str, Any]:
        """Subscribe to an API from the registry."""
        body: dict[str, Any] = {
            "serviceName": service_name,
            "notifyOnBreaking": notify_on_breaking,
            "autoBlock": auto_block,
        }
        if watch_endpoints:
            body["watchEndpoints"] = watch_endpoints
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{registry_entry_id}/subscribe",
            json=body,
        )
        return resp.json()

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""
        self._request("DELETE", f"/api/v1/contract/subscriptions/{subscription_id}")

    def list_subscribers(self, registry_entry_id: str) -> list[dict[str, Any]]:
        """List who subscribes to a specific API."""
        resp = self._request(
            "GET", f"/api/v1/contract/registry/{registry_entry_id}/subscribers"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    # ── Change Requests ─────────────────────────────────────────────

    def create_change_request(
        self, registry_entry_id: str, new_spec_content: str, new_version: str = ""
    ) -> dict[str, Any]:
        """Submit a spec change for review by affected subscribers."""
        body: dict[str, Any] = {"newSpecContent": new_spec_content}
        if new_version:
            body["newVersion"] = new_version
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{registry_entry_id}/change-requests",
            json=body,
        )
        return resp.json()

    def list_change_requests(self, registry_entry_id: str) -> list[dict[str, Any]]:
        """List change requests for a registry entry."""
        resp = self._request(
            "GET", f"/api/v1/contract/registry/{registry_entry_id}/change-requests"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def approve_change_request(self, cr_id: str, comment: str = "") -> dict[str, Any]:
        """Approve a change request."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/change-requests/{cr_id}/approve",
            json={"comment": comment},
        )
        return resp.json()

    def reject_change_request(self, cr_id: str, comment: str = "") -> dict[str, Any]:
        """Reject a change request."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/change-requests/{cr_id}/reject",
            json={"comment": comment},
        )
        return resp.json()

    def pending_change_requests(self) -> list[dict[str, Any]]:
        """List change requests awaiting my team's approval."""
        resp = self._request("GET", "/api/v1/contract/change-requests/pending")
        data = resp.json()
        return data if isinstance(data, list) else []

    # ── Trends, Participants, Reviews ───────────────────────────────

    def get_trends(self, days: int = 60) -> list[dict[str, Any]]:
        """Get validation trend data for the past N days."""
        resp = self._request("GET", f"/api/v1/contract/trends?days={days}")
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_participants(self) -> list[str]:
        """Get unique consumer/provider names from pacts for autocomplete."""
        resp = self._request("GET", "/api/v1/contract/pacts/participants")
        data = resp.json()
        return data if isinstance(data, list) else []

    def validate_from_registry(self, entry_id: str) -> dict[str, Any]:
        """Validate mocks against a registry entry specification."""
        resp = self._request("POST", f"/api/v1/contract/registry/{entry_id}/validate")
        return resp.json()

    def submit_for_review(self, entry_id: str, reviewer_id: str = "") -> dict[str, Any]:
        """Submit a registry entry for review."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/submit-review",
            json={"reviewerId": reviewer_id},
        )
        return resp.json()

    def approve_review(self, entry_id: str, comment: str = "") -> dict[str, Any]:
        """Approve a registry entry review."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/approve-review",
            json={"comment": comment},
        )
        return resp.json()

    def reject_review(self, entry_id: str, comment: str = "") -> dict[str, Any]:
        """Reject a registry entry review."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/reject-review",
            json={"comment": comment},
        )
        return resp.json()

    def assign_reviewer(self, entry_id: str, reviewer_id: str) -> dict[str, Any]:
        """Assign a reviewer to a registry entry."""
        resp = self._request(
            "PUT",
            f"/api/v1/contract/registry/{entry_id}/reviewer",
            json={"reviewerId": reviewer_id},
        )
        return resp.json()

    def get_registry_version(self, entry_id: str, version: int) -> dict[str, Any]:
        """Get a specific version of a registry entry."""
        resp = self._request(
            "GET", f"/api/v1/contract/registry/{entry_id}/versions/{version}"
        )
        return resp.json()

    def get_consumer_contract_version(
        self, contract_id: str, version: int
    ) -> dict[str, Any]:
        """Get a specific version of a consumer contract."""
        resp = self._request(
            "GET",
            f"/api/v1/contract/consumer-contracts/{contract_id}/versions/{version}",
        )
        return resp.json()

    # ── Consumer Contracts (Dependency Bundles) ───────────────────────

    def list_consumer_contracts(self) -> list[dict[str, Any]]:
        """List all consumer contracts in the current namespace."""
        resp = self._request("GET", "/api/v1/contract/consumer-contracts")
        data = resp.json()
        return data if isinstance(data, list) else []

    def get_consumer_contract(self, contract_id: str) -> dict[str, Any]:
        """Get a consumer contract by ID."""
        resp = self._request(
            "GET", f"/api/v1/contract/consumer-contracts/{contract_id}"
        )
        return resp.json()

    def create_consumer_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Create or update a consumer contract."""
        resp = self._request(
            "POST", "/api/v1/contract/consumer-contracts", json=contract
        )
        return resp.json()

    def delete_consumer_contract(self, contract_id: str) -> dict[str, Any]:
        """Delete a consumer contract."""
        resp = self._request(
            "DELETE", f"/api/v1/contract/consumer-contracts/{contract_id}"
        )
        return resp.json()

    def can_i_deploy_v2(self, request: dict[str, Any]) -> dict[str, Any]:
        """Bidirectional deployment readiness check."""
        resp = self._request("POST", "/api/v1/contract/can-i-deploy", json=request)
        return resp.json()

    def parse_endpoints(self, entry_id: str) -> dict[str, Any]:
        """Parse endpoints from a registry entry specification."""
        resp = self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/parse-endpoints", json={}
        )
        return resp.json()

    def parse_fields(
        self, entry_id: str, route: str, status_code: int = 200
    ) -> dict[str, Any]:
        """Parse response fields for a specific endpoint."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/parse-fields",
            json={"route": route, "statusCode": status_code},
        )
        return resp.json()

    def list_registry_versions(self, entry_id: str) -> list[dict[str, Any]]:
        """List version history for a registry entry."""
        resp = self._request("GET", f"/api/v1/contract/registry/{entry_id}/versions")
        data = resp.json()
        return data if isinstance(data, list) else []

    def rollback_registry_version(self, entry_id: str, version: int) -> dict[str, Any]:
        """Rollback a registry entry to a previous version."""
        resp = self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/versions/{version}/rollback"
        )
        return resp.json()

    def diff_registry_versions(self, entry_id: str, v1: int, v2: int) -> dict[str, Any]:
        """Compute diff between two registry versions."""
        resp = self._request(
            "GET", f"/api/v1/contract/registry/{entry_id}/versions/{v1}/diff/{v2}"
        )
        return resp.json()

    def list_consumer_contract_versions(self, contract_id: str) -> list[dict[str, Any]]:
        """List version history for a consumer contract."""
        resp = self._request(
            "GET", f"/api/v1/contract/consumer-contracts/{contract_id}/versions"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    def rollback_consumer_contract_version(
        self, contract_id: str, version: int
    ) -> dict[str, Any]:
        """Rollback a consumer contract to a previous version."""
        resp = self._request(
            "POST",
            f"/api/v1/contract/consumer-contracts/{contract_id}/versions/{version}/rollback",
        )
        return resp.json()

    def health(self) -> dict[str, Any]:
        """Get contract health status for the current namespace."""
        resp = self._request("GET", "/api/v1/contract/health")
        return resp.json()

    # ── Missing endpoints added for full API parity ───────────────────

    def bdct_verify(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run bidirectional contract testing (Pact vs provider spec)."""
        return self._request(
            "POST", "/api/v1/contract/bdct/verify", json=request
        ).json()

    def parse_json_fields(self, request: dict[str, Any]) -> dict[str, Any]:
        """Parse field trees from inline spec content."""
        return self._request(
            "POST", "/api/v1/contract/parse-json-fields", json=request
        ).json()

    def diff_consumer_contract(
        self, contract_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare a consumer contract against another."""
        return self._request(
            "POST",
            f"/api/v1/contract/consumer-contracts/{contract_id}/diff",
            json=request,
        ).json()

    def diff_consumer_contract_versions(
        self, contract_id: str, v1: int, v2: int
    ) -> dict[str, Any]:
        """Diff two versions of a consumer contract."""
        return self._request(
            "GET",
            f"/api/v1/contract/consumer-contracts/{contract_id}/versions/{v1}/diff/{v2}",
        ).json()

    def list_registry_namespaces(self) -> list[str]:
        """List namespaces that have registry entries."""
        return self._request("GET", "/api/v1/contract/registry/namespaces").json()

    def analyze_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """AI-assisted analysis of contract findings."""
        return self._request(
            "POST", "/api/v1/contract/findings/analyze", json=request
        ).json()

    def auto_triage_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """Auto-triage contract findings by severity."""
        return self._request(
            "POST", "/api/v1/contract/findings/auto-triage", json=request
        ).json()

    def export_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """Export contract findings."""
        return self._request(
            "POST", "/api/v1/contract/findings/export", json=request
        ).json()

    def run_config(self, config_id: str) -> dict[str, Any]:
        """Trigger immediate execution of a contract schedule."""
        return self._request("POST", f"/api/v1/contract/configs/{config_id}/run").json()


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
        self, request: ContractValidationRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Verify a provider against a contract."""
        resp = await self._request(
            "POST", "/api/v1/contract/verify-provider", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    async def check_compatibility(
        self, request: CheckCompatibilityRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Check backward compatibility between two spec versions."""
        resp = await self._request(
            "POST", "/api/v1/contract/check-compatibility", json=request
        )
        return ContractValidationResult.model_validate(resp.json())

    async def validate_payload(
        self, request: ValidatePayloadRequest | dict[str, Any]
    ) -> ContractValidationResult:
        """Validate a single JSON payload against a spec schema."""
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
        resp = await self._request("POST", "/api/v1/contract/configs", json=config)
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
        resp = await self._request("GET", f"/api/v1/contract/results/{result_id}")
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
        resp = await self._request("GET", f"/api/v1/contract/pacts/{pact_id}")
        return resp.json()

    async def publish_pact(self, pact: dict[str, Any]) -> dict[str, Any]:
        """Publish a pact contract."""
        resp = await self._request("POST", "/api/v1/contract/pacts", json=pact)
        return resp.json()

    async def verify_pact(
        self, request: PactVerifyRequest | dict[str, Any]
    ) -> dict[str, Any]:
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
        resp = await self._request("POST", f"/api/v1/contract/pacts/{pact_id}/mocks")
        data = resp.json()
        if isinstance(data, list):
            return [Mock.model_validate(m) for m in data]
        if isinstance(data, dict):
            items = data.get("mocks") or data.get("items") or []
            return [Mock.model_validate(m) for m in items]
        return []

    async def list_verifications(self) -> list[dict[str, Any]]:
        """List all pact verification results."""
        resp = await self._request("GET", "/api/v1/contract/pacts/verifications")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("items") or data.get("verifications") or []
        return []

    async def detect_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect API drift between mocks and live service."""
        resp = await self._request(
            "POST", "/api/v1/contract/detect-drift", json=request
        )
        return resp.json()

    async def detect_graphql_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect GraphQL schema drift via introspection."""
        resp = await self._request(
            "POST", "/api/v1/contract/detect-drift/graphql", json=request
        )
        return resp.json()

    async def detect_grpc_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect gRPC service drift via reflection."""
        resp = await self._request(
            "POST", "/api/v1/contract/detect-drift/grpc", json=request
        )
        return resp.json()

    async def detect_wsdl_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect SOAP/WSDL service drift."""
        resp = await self._request(
            "POST", "/api/v1/contract/detect-drift/wsdl", json=request
        )
        return resp.json()

    async def detect_mcp_drift(
        self, request: DriftDetectionRequest | dict[str, Any]
    ) -> dict[str, Any]:
        """Detect MCP server drift."""
        resp = await self._request(
            "POST", "/api/v1/contract/detect-drift/mcp", json=request
        )
        return resp.json()

    # ─── API Registry ────────────────────────────────────────────────

    async def list_registry(
        self, query: str = "", spec_type: str = ""
    ) -> list[dict[str, Any]]:
        """List published APIs in the registry.

        Args:
            query: Search text (filters by service name, description, namespace).
            spec_type: Filter by spec type (openapi, grpc, graphql, mcp, asyncapi).

        Returns:
            List of registry entries.
        """
        params = {}
        if query:
            params["q"] = query
        if spec_type:
            params["specType"] = spec_type
        resp = await self._request("GET", "/api/v1/contract/registry", params=params)
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_registry_entry(self, entry_id: str) -> dict[str, Any]:
        """Get a single registry entry by ID."""
        resp = await self._request("GET", f"/api/v1/contract/registry/{entry_id}")
        return resp.json()

    async def publish_to_registry(
        self,
        service_name: str,
        spec_type: str = "openapi",
        version: str = "",
        description: str = "",
        visibility: str = "public",
        spec_content: str | None = None,
        spec_url: str | None = None,
    ) -> dict[str, Any]:
        """Publish an API specification to the internal registry.

        Args:
            service_name: Name of the service (e.g., "UserService").
            spec_type: One of: openapi, grpc, graphql, mcp, asyncapi.
            version: Semantic version (e.g., "1.0.0").
            description: Human-readable description.
            visibility: One of: public, internal, restricted.
            spec_content: Inline specification content.
            spec_url: URL to fetch specification from.

        Returns:
            The created registry entry.
        """
        body: dict[str, Any] = {
            "serviceName": service_name,
            "specType": spec_type,
            "visibility": visibility,
        }
        if version:
            body["version"] = version
        if description:
            body["description"] = description
        if spec_content:
            body["specContent"] = spec_content
        if spec_url:
            body["specUrl"] = spec_url
        resp = await self._request("POST", "/api/v1/contract/registry", json=body)
        return resp.json()

    async def update_registry_entry(
        self, entry_id: str, update: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing registry entry."""
        resp = await self._request(
            "PUT", f"/api/v1/contract/registry/{entry_id}", json=update
        )
        return resp.json()

    async def delete_registry_entry(self, entry_id: str) -> None:
        """Delete a registry entry."""
        await self._request("DELETE", f"/api/v1/contract/registry/{entry_id}")

    async def generate_mocks_from_registry(self, entry_id: str) -> dict[str, Any]:
        """Generate Mockarty mocks from a registry entry's specification.

        Returns:
            Dict with 'generated' count and service metadata.
        """
        resp = await self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/generate-mocks"
        )
        return resp.json()

    async def check_impact(
        self, entry_id: str, new_spec_content: str
    ) -> dict[str, Any]:
        """Check which subscribers would be affected by a spec change.

        Returns:
            Dict with isCompatible, breakingChanges, affectedTeams, blocked.
        """
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/check-impact",
            json={"newSpecContent": new_spec_content},
        )
        return resp.json()

    # ─── Subscriptions ───────────────────────────────────────────────

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        """List current namespace's subscriptions to APIs."""
        resp = await self._request("GET", "/api/v1/contract/subscriptions")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def subscribe(
        self,
        registry_entry_id: str,
        service_name: str,
        watch_endpoints: list[str] | None = None,
        notify_on_breaking: bool = True,
        auto_block: bool = False,
    ) -> dict[str, Any]:
        """Subscribe to an API from the registry.

        Args:
            registry_entry_id: ID of the registry entry to subscribe to.
            service_name: Your service name (consumer).
            watch_endpoints: Specific endpoints to monitor (empty = all).
            notify_on_breaking: Send alerts on breaking changes.
            auto_block: Block spec updates until you approve.

        Returns:
            The created subscription.
        """
        body: dict[str, Any] = {
            "serviceName": service_name,
            "notifyOnBreaking": notify_on_breaking,
            "autoBlock": auto_block,
        }
        if watch_endpoints:
            body["watchEndpoints"] = watch_endpoints
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{registry_entry_id}/subscribe",
            json=body,
        )
        return resp.json()

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""
        await self._request(
            "DELETE", f"/api/v1/contract/subscriptions/{subscription_id}"
        )

    async def list_subscribers(self, registry_entry_id: str) -> list[dict[str, Any]]:
        """List who subscribes to a specific API."""
        resp = await self._request(
            "GET", f"/api/v1/contract/registry/{registry_entry_id}/subscribers"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    # ─── Change Requests ─────────────────────────────────────────

    async def create_change_request(
        self, registry_entry_id: str, new_spec_content: str, new_version: str = ""
    ) -> dict[str, Any]:
        """Submit a spec change for review by affected subscribers."""
        body: dict[str, Any] = {"newSpecContent": new_spec_content}
        if new_version:
            body["newVersion"] = new_version
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{registry_entry_id}/change-requests",
            json=body,
        )
        return resp.json()

    async def list_change_requests(
        self, registry_entry_id: str
    ) -> list[dict[str, Any]]:
        """List change requests for a registry entry."""
        resp = await self._request(
            "GET", f"/api/v1/contract/registry/{registry_entry_id}/change-requests"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def approve_change_request(
        self, cr_id: str, comment: str = ""
    ) -> dict[str, Any]:
        """Approve a change request."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/change-requests/{cr_id}/approve",
            json={"comment": comment},
        )
        return resp.json()

    async def reject_change_request(
        self, cr_id: str, comment: str = ""
    ) -> dict[str, Any]:
        """Reject a change request."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/change-requests/{cr_id}/reject",
            json={"comment": comment},
        )
        return resp.json()

    async def pending_change_requests(self) -> list[dict[str, Any]]:
        """List change requests awaiting my team's approval."""
        resp = await self._request("GET", "/api/v1/contract/change-requests/pending")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_trends(self, days: int = 60) -> list[dict[str, Any]]:
        """Get validation trend data for the past N days."""
        resp = await self._request("GET", f"/api/v1/contract/trends?days={days}")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_participants(self) -> list[str]:
        """Get unique consumer/provider names from pacts for autocomplete."""
        resp = await self._request("GET", "/api/v1/contract/pacts/participants")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def validate_from_registry(self, entry_id: str) -> dict[str, Any]:
        """Validate mocks against a registry entry specification."""
        resp = await self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/validate"
        )
        return resp.json()

    async def submit_for_review(
        self, entry_id: str, reviewer_id: str = ""
    ) -> dict[str, Any]:
        """Submit a registry entry for review."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/submit-review",
            json={"reviewerId": reviewer_id},
        )
        return resp.json()

    async def approve_review(self, entry_id: str, comment: str = "") -> dict[str, Any]:
        """Approve a registry entry review."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/approve-review",
            json={"comment": comment},
        )
        return resp.json()

    async def reject_review(self, entry_id: str, comment: str = "") -> dict[str, Any]:
        """Reject a registry entry review."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/reject-review",
            json={"comment": comment},
        )
        return resp.json()

    async def assign_reviewer(self, entry_id: str, reviewer_id: str) -> dict[str, Any]:
        """Assign a reviewer to a registry entry."""
        resp = await self._request(
            "PUT",
            f"/api/v1/contract/registry/{entry_id}/reviewer",
            json={"reviewerId": reviewer_id},
        )
        return resp.json()

    # ── Consumer Contracts (Dependency Bundles) ───────────────────────

    async def list_consumer_contracts(self) -> list[dict[str, Any]]:
        """List all consumer contracts in the current namespace."""
        resp = await self._request("GET", "/api/v1/contract/consumer-contracts")
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_consumer_contract(self, contract_id: str) -> dict[str, Any]:
        """Get a consumer contract by ID."""
        resp = await self._request(
            "GET", f"/api/v1/contract/consumer-contracts/{contract_id}"
        )
        return resp.json()

    async def create_consumer_contract(
        self, contract: dict[str, Any]
    ) -> dict[str, Any]:
        """Create or update a consumer contract."""
        resp = await self._request(
            "POST", "/api/v1/contract/consumer-contracts", json=contract
        )
        return resp.json()

    async def delete_consumer_contract(self, contract_id: str) -> dict[str, Any]:
        """Delete a consumer contract."""
        resp = await self._request(
            "DELETE", f"/api/v1/contract/consumer-contracts/{contract_id}"
        )
        return resp.json()

    # ── Can I Deploy V2 (Bidirectional) ──────────────────────────────

    async def can_i_deploy_v2(self, request: dict[str, Any]) -> dict[str, Any]:
        """Bidirectional deployment readiness check.

        Args:
            request: Dict with 'role' ('consumer' or 'provider'),
                     'contractId' for consumer, 'registryEntryId' + optional 'newSpec' for provider.
        """
        resp = await self._request(
            "POST", "/api/v1/contract/can-i-deploy", json=request
        )
        return resp.json()

    # ── Spec Parsing (Wizard Support) ────────────────────────────────

    async def parse_endpoints(self, entry_id: str) -> dict[str, Any]:
        """Parse endpoints from a registry entry specification."""
        resp = await self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/parse-endpoints", json={}
        )
        return resp.json()

    async def parse_fields(
        self, entry_id: str, route: str, status_code: int = 200
    ) -> dict[str, Any]:
        """Parse response fields for a specific endpoint."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/registry/{entry_id}/parse-fields",
            json={"route": route, "statusCode": status_code},
        )
        return resp.json()

    # ── Versioning ───────────────────────────────────────────────────

    async def list_registry_versions(self, entry_id: str) -> list[dict[str, Any]]:
        """List version history for a registry entry."""
        resp = await self._request(
            "GET", f"/api/v1/contract/registry/{entry_id}/versions"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_registry_version(self, entry_id: str, version: int) -> dict[str, Any]:
        """Get a specific version of a registry entry."""
        resp = await self._request(
            "GET", f"/api/v1/contract/registry/{entry_id}/versions/{version}"
        )
        return resp.json()

    async def rollback_registry_version(
        self, entry_id: str, version: int
    ) -> dict[str, Any]:
        """Rollback a registry entry to a previous version."""
        resp = await self._request(
            "POST", f"/api/v1/contract/registry/{entry_id}/versions/{version}/rollback"
        )
        return resp.json()

    async def diff_registry_versions(
        self, entry_id: str, v1: int, v2: int
    ) -> dict[str, Any]:
        """Compute diff between two versions of a registry entry."""
        resp = await self._request(
            "GET", f"/api/v1/contract/registry/{entry_id}/versions/{v1}/diff/{v2}"
        )
        return resp.json()

    async def list_consumer_contract_versions(
        self, contract_id: str
    ) -> list[dict[str, Any]]:
        """List version history for a consumer contract."""
        resp = await self._request(
            "GET", f"/api/v1/contract/consumer-contracts/{contract_id}/versions"
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    async def get_consumer_contract_version(
        self, contract_id: str, version: int
    ) -> dict[str, Any]:
        """Get a specific version of a consumer contract."""
        resp = await self._request(
            "GET",
            f"/api/v1/contract/consumer-contracts/{contract_id}/versions/{version}",
        )
        return resp.json()

    async def rollback_consumer_contract_version(
        self, contract_id: str, version: int
    ) -> dict[str, Any]:
        """Rollback a consumer contract to a previous version."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/consumer-contracts/{contract_id}/versions/{version}/rollback",
        )
        return resp.json()

    # ── Health ───────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Get contract health status for the current namespace."""
        resp = await self._request("GET", "/api/v1/contract/health")
        return resp.json()

    # ── Missing endpoints added for full API parity ───────────────────

    async def bdct_verify(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run bidirectional contract testing (Pact vs provider spec)."""
        resp = await self._request("POST", "/api/v1/contract/bdct/verify", json=request)
        return resp.json()

    async def parse_json_fields(self, request: dict[str, Any]) -> dict[str, Any]:
        """Parse field trees from inline spec content."""
        resp = await self._request(
            "POST", "/api/v1/contract/parse-json-fields", json=request
        )
        return resp.json()

    async def diff_consumer_contract(
        self, contract_id: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare a consumer contract against another."""
        resp = await self._request(
            "POST",
            f"/api/v1/contract/consumer-contracts/{contract_id}/diff",
            json=request,
        )
        return resp.json()

    async def diff_consumer_contract_versions(
        self, contract_id: str, v1: int, v2: int
    ) -> dict[str, Any]:
        """Diff two versions of a consumer contract."""
        resp = await self._request(
            "GET",
            f"/api/v1/contract/consumer-contracts/{contract_id}/versions/{v1}/diff/{v2}",
        )
        return resp.json()

    async def list_registry_namespaces(self) -> list[str]:
        """List namespaces that have registry entries."""
        resp = await self._request("GET", "/api/v1/contract/registry/namespaces")
        return resp.json()

    async def analyze_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """AI-assisted analysis of contract findings."""
        resp = await self._request(
            "POST", "/api/v1/contract/findings/analyze", json=request
        )
        return resp.json()

    async def auto_triage_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """Auto-triage contract findings by severity."""
        resp = await self._request(
            "POST", "/api/v1/contract/findings/auto-triage", json=request
        )
        return resp.json()

    async def export_findings(self, request: dict[str, Any]) -> dict[str, Any]:
        """Export contract findings."""
        resp = await self._request(
            "POST", "/api/v1/contract/findings/export", json=request
        )
        return resp.json()

    async def run_config(self, config_id: str) -> dict[str, Any]:
        """Trigger immediate execution of a contract schedule."""
        resp = await self._request("POST", f"/api/v1/contract/configs/{config_id}/run")
        return resp.json()
