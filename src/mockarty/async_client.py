# Copyright (c) 2026 Mockarty. All rights reserved.

"""Asynchronous Mockarty client."""

from __future__ import annotations

import httpx

from mockarty._base_client import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_NAMESPACE,
    DEFAULT_TIMEOUT,
    build_async_transport,
    build_headers,
    resolve_api_key,
    resolve_base_url,
)
from mockarty.api.agent_tasks import AsyncAgentTaskAPI
from mockarty.api.autonomous_missions import AsyncAutonomousMissionsAPI
from mockarty.api.chaos import AsyncChaosAPI
from mockarty.api.cloud_webhooks import AsyncCloudWebhooksAPI
from mockarty.api.cloud_instances import AsyncCloudInstancesAPI
from mockarty.api.cloud_connectors import AsyncCloudConnectorsAPI
from mockarty.api.cloud_oauth_providers import AsyncCloudOAuthProvidersAPI
from mockarty.api.cloud_risk import AsyncCloudRiskAPI
from mockarty.api.cloud_refunds import AsyncCloudRefundsAPI
from mockarty.api.cloud_identity import AsyncCloudIdentityAPI
from mockarty.api.cloud_spaces import AsyncCloudSpacesAPI
from mockarty.api.cloud_entitlements import AsyncCloudEntitlementsAPI
from mockarty.api.cloud_shared_projects import AsyncCloudSharedProjectsAPI
from mockarty.api.cloud_customer_operations import AsyncCloudCustomerAPI, AsyncCloudOperationsAPI
from mockarty.api.coder_delivery import AsyncCoderDeliveryAPI
from mockarty.api.ci_triggers import AsyncCITriggerAPI
from mockarty.api.collections import AsyncCollectionAPI
from mockarty.api.contracts import AsyncContractAPI
from mockarty.api.discovery import AsyncDiscoveryAPI
from mockarty.api.delivery_policy import AsyncDeliveryPolicyAPI
from mockarty.api.media_delivery import AsyncMediaDeliveryAPI
from mockarty.api.effect_reconciliation import AsyncEffectReconciliationAPI
from mockarty.api.economics import AsyncEconomicsAPI
from mockarty.api.entity_search import AsyncEntitySearchAPI
from mockarty.api.environments import AsyncEnvironmentAPI
from mockarty.api.experience import AsyncExperienceAPI
from mockarty.api.llm_security import AsyncLLMSecurityAPI
from mockarty.api.external_runs import AsyncExternalRunsAPI
from mockarty.api.folders import AsyncFolderAPI
from mockarty.api.fuzzing import AsyncFuzzingAPI
from mockarty.api.generator import AsyncGeneratorAPI
from mockarty.api.gitsync import AsyncGitSyncAPI
from mockarty.api.health import AsyncHealthAPI
from mockarty.api.imports import AsyncImportAPI
from mockarty.api.issuetracker import AsyncIssueTrackerAPI
from mockarty.api.mcp import AsyncMCPClient
from mockarty.api.me import AsyncMeAPI
from mockarty.api.mocks import AsyncMockAPI
from mockarty.api.namespace_settings import AsyncNamespaceSettingsAPI
from mockarty.api.namespaces import AsyncNamespaceAPI
from mockarty.api.perf import AsyncPerfAPI
from mockarty.api.page_analyzer import AsyncPageAnalyzerAPI
from mockarty.api.prompts import AsyncPromptsAPI
from mockarty.api.proxy import AsyncProxyAPI
from mockarty.api.recorder import AsyncRecorderAPI
from mockarty.api.secrets import AsyncSecretsAPI
from mockarty.api.stats import AsyncStatsAPI
from mockarty.api.stores import AsyncStoreAPI
from mockarty.api.tags import AsyncTagAPI
from mockarty.api.tcm import AsyncTCMAPI
from mockarty.api.templates import AsyncTemplateAPI
from mockarty.api.testplans import AsyncTestPlansAPI
from mockarty.api.testruns import AsyncTestRunAPI
from mockarty.api.uitests import AsyncUITestAPI
from mockarty.api.undefined import AsyncUndefinedAPI
from mockarty.api.workflow_definitions import AsyncWorkflowDefinitionsAPI


class AsyncMockartyClient:
    """Asynchronous client for the Mockarty REST API.

    Example::

        async with AsyncMockartyClient() as client:
            mock = await client.mocks.get("my-mock-id")

    Configuration can also come from environment variables:

    - ``MOCKARTY_BASE_URL`` -- server URL (default: ``http://localhost:5770``)
    - ``MOCKARTY_API_KEY`` -- API authentication key

    Args:
        base_url: Mockarty server URL. Falls back to ``MOCKARTY_BASE_URL`` env var.
        api_key: API authentication key. Falls back to ``MOCKARTY_API_KEY`` env var.
        namespace: Default namespace for API requests.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of automatic retries on transient failures.
    """

    # Single source of truth for cached namespace-bound API resources. Both
    # construction and namespace changes reset this exact set, so a newly
    # added API cannot retain the previous tenant by omission.
    _API_RESOURCE_ATTRS: tuple[str, ...] = (
        "_chaos", "_cloud_webhooks", "_cloud_instances", "_cloud_connectors", "_cloud_oauth_providers", "_cloud_risk", "_cloud_refunds", "_cloud_identity", "_cloud_spaces", "_cloud_entitlements", "_cloud_shared_projects", "_cloud_customer", "_cloud_operations", "_delivery_policy", "_media_delivery", "_effect_reconciliation", "_page_analyzer", "_ci_triggers", "_mocks", "_namespaces",
        "_stores", "_collections", "_perf", "_health", "_generator", "_fuzzing",
        "_contracts", "_recorder", "_templates", "_imports", "_test_runs",
        "_test_plans", "_tags", "_ui_tests", "_git_sync", "_folders", "_undefined",
        "_stats", "_agent_tasks", "_autonomous_missions", "_coder_delivery", "_mcp", "_issue_tracker", "_tcm",
        "_namespace_settings", "_proxy", "_environments", "_entity_search",
        "_experience", "_economics", "_llm_security", "_external_runs", "_discovery",
        "_workflow_definitions", "_secrets", "_prompts", "_me",
    )

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        namespace: str = DEFAULT_NAMESPACE,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._base_url = resolve_base_url(base_url)
        self._api_key = resolve_api_key(api_key)
        self._namespace = namespace
        self._timeout = timeout

        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers=build_headers(self._api_key, self._namespace),
            timeout=httpx.Timeout(timeout),
            transport=build_async_transport(max_retries),
        )

        for attr in self._API_RESOURCE_ATTRS:
            setattr(self, attr, None)

    # ── Context manager ───────────────────────────────────────────────

    async def __aenter__(self) -> AsyncMockartyClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._http.aclose()

    # ── Configuration ─────────────────────────────────────────────────

    @property
    def base_url(self) -> str:
        """The base URL of the Mockarty server."""
        return self._base_url

    @property
    def namespace(self) -> str:
        """The default namespace used for API requests."""
        return self._namespace

    @namespace.setter
    def namespace(self, value: str) -> None:
        """Update the default namespace and refresh the header."""
        self._namespace = value
        self._http.headers["X-Namespace"] = value
        for attr in self._API_RESOURCE_ATTRS:
            setattr(self, attr, None)

    # ── API resources ─────────────────────────────────────────────────

    @property
    def ci_triggers(self) -> AsyncCITriggerAPI:
        """CI Triggers API (generic webhooks)."""
        if self._ci_triggers is None:
            self._ci_triggers = AsyncCITriggerAPI(self._http, self._namespace)
        return self._ci_triggers

    @property
    def chaos(self) -> AsyncChaosAPI:
        """Chaos engineering API."""
        if self._chaos is None:
            self._chaos = AsyncChaosAPI(self._http, self._namespace)
        return self._chaos

    @property
    def cloud_webhooks(self) -> AsyncCloudWebhooksAPI:
        """Cloud webhook lifecycle API."""
        if self._cloud_webhooks is None:
            self._cloud_webhooks = AsyncCloudWebhooksAPI(self._http, self._namespace)
        return self._cloud_webhooks

    @property
    def cloud_instances(self) -> AsyncCloudInstancesAPI:
        """Dedicated Mockarty Cloud instance lifecycle API."""
        if self._cloud_instances is None:
            self._cloud_instances = AsyncCloudInstancesAPI(self._http, self._namespace)
        return self._cloud_instances

    @property
    def cloud_connectors(self) -> AsyncCloudConnectorsAPI:
        """Operator-only Cloud platform connector lifecycle."""
        if self._cloud_connectors is None:
            self._cloud_connectors = AsyncCloudConnectorsAPI(self._http, self._namespace)
        return self._cloud_connectors

    @property
    def cloud_oauth_providers(self) -> AsyncCloudOAuthProvidersAPI:
        """Operator-only Cloud cabinet sign-in provider registry."""
        if self._cloud_oauth_providers is None:
            self._cloud_oauth_providers = AsyncCloudOAuthProvidersAPI(self._http, self._namespace)
        return self._cloud_oauth_providers

    @property
    def cloud_risk(self) -> AsyncCloudRiskAPI:
        """Operator-only Cloud risk case and enforcement API."""
        if self._cloud_risk is None:
            self._cloud_risk = AsyncCloudRiskAPI(self._http, self._namespace)
        return self._cloud_risk

    @property
    def cloud_refunds(self) -> AsyncCloudRefundsAPI:
        """Operator-only durable Cloud refund recovery API."""
        if self._cloud_refunds is None:
            self._cloud_refunds = AsyncCloudRefundsAPI(self._http, self._namespace)
        return self._cloud_refunds

    @property
    def cloud_identity(self) -> AsyncCloudIdentityAPI:
        """Current Cloud account sign-in methods and step-up verification."""
        if self._cloud_identity is None:
            self._cloud_identity = AsyncCloudIdentityAPI(self._http, self._namespace)
        return self._cloud_identity

    @property
    def cloud_spaces(self) -> AsyncCloudSpacesAPI:
        """Canonical explicit-Space collaboration API."""
        if self._cloud_spaces is None:
            self._cloud_spaces = AsyncCloudSpacesAPI(self._http, self._namespace)
        return self._cloud_spaces

    @property
    def cloud_customer(self) -> AsyncCloudCustomerAPI:
        """Customer-authorized loyalty, support and security-appeal APIs."""
        if self._cloud_customer is None:
            self._cloud_customer = AsyncCloudCustomerAPI(self._http, self._namespace)
        return self._cloud_customer

    @property
    def cloud_operations(self) -> AsyncCloudOperationsAPI:
        """Least-privilege operator support and product analytics APIs."""
        if self._cloud_operations is None:
            self._cloud_operations = AsyncCloudOperationsAPI(self._http, self._namespace)
        return self._cloud_operations

    @property
    def cloud_entitlements(self) -> AsyncCloudEntitlementsAPI:
        """Committed unsigned Cloud entitlement projection API."""
        if self._cloud_entitlements is None:
            self._cloud_entitlements = AsyncCloudEntitlementsAPI(self._http, self._namespace)
        return self._cloud_entitlements

    @property
    def cloud_shared_projects(self) -> AsyncCloudSharedProjectsAPI:
        """Public Shared SaaS project CRUD API."""
        if self._cloud_shared_projects is None:
            self._cloud_shared_projects = AsyncCloudSharedProjectsAPI(self._http, self._namespace)
        return self._cloud_shared_projects

    @property
    def delivery_policy(self) -> AsyncDeliveryPolicyAPI:
        """Administrator delivery-policy environment management."""
        if self._delivery_policy is None:
            self._delivery_policy = AsyncDeliveryPolicyAPI(self._http, self._namespace)
        return self._delivery_policy

    @property
    def media_delivery(self) -> AsyncMediaDeliveryAPI:
        """Inspect and reconcile media jobs held after ambiguous push delivery."""
        if self._media_delivery is None:
            self._media_delivery = AsyncMediaDeliveryAPI(self._http, self._namespace)
        return self._media_delivery

    @property
    def effect_reconciliation(self) -> AsyncEffectReconciliationAPI:
        """Admin queue for unresolved external effects."""
        if self._effect_reconciliation is None:
            self._effect_reconciliation = AsyncEffectReconciliationAPI(self._http, self._namespace)
        return self._effect_reconciliation

    @property
    def page_analyzer(self) -> AsyncPageAnalyzerAPI:
        """HTTP-level page analysis API."""
        if self._page_analyzer is None:
            self._page_analyzer = AsyncPageAnalyzerAPI(self._http, self._namespace)
        return self._page_analyzer

    @property
    def mocks(self) -> AsyncMockAPI:
        """Mock CRUD API."""
        if self._mocks is None:
            self._mocks = AsyncMockAPI(self._http, self._namespace)
        return self._mocks

    @property
    def namespaces(self) -> AsyncNamespaceAPI:
        """Namespace management API."""
        if self._namespaces is None:
            self._namespaces = AsyncNamespaceAPI(self._http, self._namespace)
        return self._namespaces

    @property
    def stores(self) -> AsyncStoreAPI:
        """Store management API (Global and Chain stores)."""
        if self._stores is None:
            self._stores = AsyncStoreAPI(self._http, self._namespace)
        return self._stores

    @property
    def secrets(self) -> AsyncSecretsAPI:
        """Secrets Storage API (async)."""
        if self._secrets is None:
            self._secrets = AsyncSecretsAPI(self._http, self._namespace)
        return self._secrets

    @property
    def prompts(self) -> AsyncPromptsAPI:
        """Prompts Storage API (async)."""
        if self._prompts is None:
            self._prompts = AsyncPromptsAPI(self._http, self._namespace)
        return self._prompts

    @property
    def collections(self) -> AsyncCollectionAPI:
        """API Tester collections API."""
        if self._collections is None:
            self._collections = AsyncCollectionAPI(self._http, self._namespace)
        return self._collections

    @property
    def perf(self) -> AsyncPerfAPI:
        """Performance testing API."""
        if self._perf is None:
            self._perf = AsyncPerfAPI(self._http, self._namespace)
        return self._perf

    @property
    def health(self) -> AsyncHealthAPI:
        """Health check API."""
        if self._health is None:
            self._health = AsyncHealthAPI(self._http, self._namespace)
        return self._health

    @property
    def generator(self) -> AsyncGeneratorAPI:
        """Mock generator API (OpenAPI, GraphQL, gRPC, SOAP)."""
        if self._generator is None:
            self._generator = AsyncGeneratorAPI(self._http, self._namespace)
        return self._generator

    @property
    def fuzzing(self) -> AsyncFuzzingAPI:
        """Fuzzing testing API."""
        if self._fuzzing is None:
            self._fuzzing = AsyncFuzzingAPI(self._http, self._namespace)
        return self._fuzzing

    @property
    def contracts(self) -> AsyncContractAPI:
        """Contract testing API."""
        if self._contracts is None:
            self._contracts = AsyncContractAPI(self._http, self._namespace)
        return self._contracts

    @property
    def recorder(self) -> AsyncRecorderAPI:
        """Traffic recorder API."""
        if self._recorder is None:
            self._recorder = AsyncRecorderAPI(self._http, self._namespace)
        return self._recorder

    @property
    def templates(self) -> AsyncTemplateAPI:
        """Payload template management API."""
        if self._templates is None:
            self._templates = AsyncTemplateAPI(self._http, self._namespace)
        return self._templates

    @property
    def imports(self) -> AsyncImportAPI:
        """Collection import API (Postman, Insomnia, HAR, cURL)."""
        if self._imports is None:
            self._imports = AsyncImportAPI(self._http, self._namespace)
        return self._imports

    @property
    def test_runs(self) -> AsyncTestRunAPI:
        """Test run history API."""
        if self._test_runs is None:
            self._test_runs = AsyncTestRunAPI(self._http, self._namespace)
        return self._test_runs

    @property
    def test_plans(self) -> AsyncTestPlansAPI:
        """Test Plans API — master orchestrator for heterogeneous runs."""
        if self._test_plans is None:
            self._test_plans = AsyncTestPlansAPI(self._http, self._namespace)
        return self._test_plans

    @property
    def me(self) -> AsyncMeAPI:
        """Per-caller endpoints (``/api/v1/me/*``)."""
        if self._me is None:
            self._me = AsyncMeAPI(self._http, self._namespace)
        return self._me

    @property
    def tags(self) -> AsyncTagAPI:
        """Tag management API."""
        if self._tags is None:
            self._tags = AsyncTagAPI(self._http, self._namespace)
        return self._tags

    @property
    def ui_tests(self) -> AsyncUITestAPI:
        """Recorded-UI-test API (save / run / poll / export)."""
        if self._ui_tests is None:
            self._ui_tests = AsyncUITestAPI(self._http, self._namespace)
        return self._ui_tests

    @property
    def git_sync(self) -> AsyncGitSyncAPI:
        """Git-sync API — bind a repo, pull/push autotest collections."""
        if self._git_sync is None:
            self._git_sync = AsyncGitSyncAPI(self._http, self._namespace)
        return self._git_sync

    @property
    def folders(self) -> AsyncFolderAPI:
        """Mock folder management API."""
        if self._folders is None:
            self._folders = AsyncFolderAPI(self._http, self._namespace)
        return self._folders

    @property
    def undefined(self) -> AsyncUndefinedAPI:
        """Undefined (unmatched) requests API."""
        if self._undefined is None:
            self._undefined = AsyncUndefinedAPI(self._http, self._namespace)
        return self._undefined

    @property
    def stats(self) -> AsyncStatsAPI:
        """System statistics and status API."""
        if self._stats is None:
            self._stats = AsyncStatsAPI(self._http, self._namespace)
        return self._stats

    @property
    def agent_tasks(self) -> AsyncAgentTaskAPI:
        """AI agent task API."""
        if self._agent_tasks is None:
            self._agent_tasks = AsyncAgentTaskAPI(self._http, self._namespace)
        return self._agent_tasks

    @property
    def mcp(self) -> AsyncMCPClient:
        """Model Context Protocol client — list_tools/call_tool against /mcp."""
        if self._mcp is None:
            self._mcp = AsyncMCPClient(self._http, self._namespace)
        return self._mcp

    @property
    def issue_tracker(self) -> AsyncIssueTrackerAPI:
        """Issue-tracker task automation (issues/comments/projects/sprints)."""
        if self._issue_tracker is None:
            self._issue_tracker = AsyncIssueTrackerAPI(self._http, self._namespace)
        return self._issue_tracker

    @property
    def tcm(self) -> AsyncTCMAPI:
        """Test Case Management automation (cases/case-runs/defects)."""
        if self._tcm is None:
            self._tcm = AsyncTCMAPI(self._http, self._namespace)
        return self._tcm

    @property
    def namespace_settings(self) -> AsyncNamespaceSettingsAPI:
        """Per-namespace settings API (users, cleanup, webhooks)."""
        if self._namespace_settings is None:
            self._namespace_settings = AsyncNamespaceSettingsAPI(
                self._http, self._namespace
            )
        return self._namespace_settings

    @property
    def proxy(self) -> AsyncProxyAPI:
        """Proxy API for forwarding requests."""
        if self._proxy is None:
            self._proxy = AsyncProxyAPI(self._http, self._namespace)
        return self._proxy

    @property
    def environments(self) -> AsyncEnvironmentAPI:
        """API Tester environments API."""
        if self._environments is None:
            self._environments = AsyncEnvironmentAPI(self._http, self._namespace)
        return self._environments

    @property
    def entity_search(self) -> AsyncEntitySearchAPI:
        """Unified entity-search API (resolve names → IDs across all types)."""
        if self._entity_search is None:
            self._entity_search = AsyncEntitySearchAPI(self._http, self._namespace)
        return self._entity_search

    @property
    def experience(self) -> AsyncExperienceAPI:
        """Reusable AutoTester run experience API."""
        if self._experience is None:
            self._experience = AsyncExperienceAPI(self._http, self._namespace)
        return self._experience

    @property
    def autonomous_missions(self) -> AsyncAutonomousMissionsAPI:
        """Autonomous mission intake and supervision API."""
        if self._autonomous_missions is None:
            self._autonomous_missions = AsyncAutonomousMissionsAPI(self._http, self._namespace)
        return self._autonomous_missions

    @property
    def coder_delivery(self) -> AsyncCoderDeliveryAPI:
        """Admitted repositories, delivery configuration, and deploy missions."""
        if self._coder_delivery is None:
            self._coder_delivery = AsyncCoderDeliveryAPI(self._http, self._namespace)
        return self._coder_delivery

    @property
    def economics(self) -> AsyncEconomicsAPI:
        """Administrator LLM usage and immutable price-book API."""
        if self._economics is None:
            self._economics = AsyncEconomicsAPI(self._http, self._namespace)
        return self._economics

    @property
    def llm_security(self) -> AsyncLLMSecurityAPI:
        """Layered prompt-security management API."""
        if self._llm_security is None:
            self._llm_security = AsyncLLMSecurityAPI(self._http, self._namespace)
        return self._llm_security

    @property
    def external_runs(self) -> AsyncExternalRunsAPI:
        """External-framework upload API (POST /tcm/external-runs)."""
        if self._external_runs is None:
            self._external_runs = AsyncExternalRunsAPI(self._http, self._namespace)
        return self._external_runs

    @property
    def discovery(self) -> AsyncDiscoveryAPI:
        """Test-discovery sync API (POST /tcm/discovery)."""
        if self._discovery is None:
            self._discovery = AsyncDiscoveryAPI(self._http, self._namespace)
        return self._discovery

    @property
    def workflow_definitions(self) -> AsyncWorkflowDefinitionsAPI:
        """Versioned workflow draft, dry-run and publish API."""
        if self._workflow_definitions is None:
            self._workflow_definitions = AsyncWorkflowDefinitionsAPI(
                self._http, self._namespace
            )
        return self._workflow_definitions
