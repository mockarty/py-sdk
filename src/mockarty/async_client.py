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
from mockarty.api.chaos import AsyncChaosAPI
from mockarty.api.collections import AsyncCollectionAPI
from mockarty.api.contracts import AsyncContractAPI
from mockarty.api.entity_search import AsyncEntitySearchAPI
from mockarty.api.environments import AsyncEnvironmentAPI
from mockarty.api.folders import AsyncFolderAPI
from mockarty.api.fuzzing import AsyncFuzzingAPI
from mockarty.api.generator import AsyncGeneratorAPI
from mockarty.api.health import AsyncHealthAPI
from mockarty.api.imports import AsyncImportAPI
from mockarty.api.mocks import AsyncMockAPI
from mockarty.api.namespace_settings import AsyncNamespaceSettingsAPI
from mockarty.api.namespaces import AsyncNamespaceAPI
from mockarty.api.perf import AsyncPerfAPI
from mockarty.api.prompts import AsyncPromptsAPI
from mockarty.api.proxy import AsyncProxyAPI
from mockarty.api.secrets import AsyncSecretsAPI
from mockarty.api.recorder import AsyncRecorderAPI
from mockarty.api.stats import AsyncStatsAPI
from mockarty.api.stores import AsyncStoreAPI
from mockarty.api.tags import AsyncTagAPI
from mockarty.api.templates import AsyncTemplateAPI
from mockarty.api.testplans import AsyncTestPlansAPI
from mockarty.api.testruns import AsyncTestRunAPI
from mockarty.api.trash import AsyncTrashAPI
from mockarty.api.undefined import AsyncUndefinedAPI


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

        # Lazily-initialised API resources
        self._chaos: AsyncChaosAPI | None = None
        self._mocks: AsyncMockAPI | None = None
        self._namespaces: AsyncNamespaceAPI | None = None
        self._stores: AsyncStoreAPI | None = None
        self._collections: AsyncCollectionAPI | None = None
        self._perf: AsyncPerfAPI | None = None
        self._health: AsyncHealthAPI | None = None
        self._generator: AsyncGeneratorAPI | None = None
        self._fuzzing: AsyncFuzzingAPI | None = None
        self._contracts: AsyncContractAPI | None = None
        self._recorder: AsyncRecorderAPI | None = None
        self._templates: AsyncTemplateAPI | None = None
        self._imports: AsyncImportAPI | None = None
        self._test_runs: AsyncTestRunAPI | None = None
        self._test_plans: AsyncTestPlansAPI | None = None
        self._tags: AsyncTagAPI | None = None
        self._folders: AsyncFolderAPI | None = None
        self._undefined: AsyncUndefinedAPI | None = None
        self._stats: AsyncStatsAPI | None = None
        self._agent_tasks: AsyncAgentTaskAPI | None = None
        self._namespace_settings: AsyncNamespaceSettingsAPI | None = None
        self._proxy: AsyncProxyAPI | None = None
        self._environments: AsyncEnvironmentAPI | None = None
        self._entity_search: AsyncEntitySearchAPI | None = None
        self._trash: AsyncTrashAPI | None = None
        self._secrets: AsyncSecretsAPI | None = None
        self._prompts: AsyncPromptsAPI | None = None

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
        # Reset cached API instances so they pick up the new namespace
        self._chaos = None
        self._mocks = None
        self._namespaces = None
        self._stores = None
        self._collections = None
        self._perf = None
        self._health = None
        self._generator = None
        self._fuzzing = None
        self._contracts = None
        self._recorder = None
        self._templates = None
        self._imports = None
        self._test_runs = None
        self._test_plans = None
        self._tags = None
        self._folders = None
        self._undefined = None
        self._stats = None
        self._agent_tasks = None
        self._namespace_settings = None
        self._proxy = None
        self._environments = None
        self._entity_search = None
        self._trash = None
        self._secrets = None
        self._prompts = None

    # ── API resources ─────────────────────────────────────────────────

    @property
    def chaos(self) -> AsyncChaosAPI:
        """Chaos engineering API."""
        if self._chaos is None:
            self._chaos = AsyncChaosAPI(self._http, self._namespace)
        return self._chaos

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
    def tags(self) -> AsyncTagAPI:
        """Tag management API."""
        if self._tags is None:
            self._tags = AsyncTagAPI(self._http, self._namespace)
        return self._tags

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
    def trash(self) -> AsyncTrashAPI:
        """Recycle Bin / Soft-Delete API (list, restore, purge)."""
        if self._trash is None:
            self._trash = AsyncTrashAPI(self._http, self._namespace)
        return self._trash
