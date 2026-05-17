# Copyright (c) 2026 Mockarty. All rights reserved.

"""Synchronous Mockarty client."""

from __future__ import annotations

import httpx

from mockarty._base_client import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_NAMESPACE,
    DEFAULT_TIMEOUT,
    build_headers,
    build_transport,
    resolve_api_key,
    resolve_base_url,
)
from mockarty.api.agent_tasks import AgentTaskAPI
from mockarty.api.chaos import ChaosAPI
from mockarty.api.collections import CollectionAPI
from mockarty.api.contracts import ContractAPI
from mockarty.api.entity_search import EntitySearchAPI
from mockarty.api.external_runs import ExternalRunsAPI
from mockarty.api.environments import EnvironmentAPI
from mockarty.api.folders import FolderAPI
from mockarty.api.fuzzing import FuzzingAPI
from mockarty.api.generator import GeneratorAPI
from mockarty.api.health import HealthAPI
from mockarty.api.imports import ImportAPI
from mockarty.api.me import MeAPI
from mockarty.api.mocks import MockAPI
from mockarty.api.namespace_settings import NamespaceSettingsAPI
from mockarty.api.namespaces import NamespaceAPI
from mockarty.api.perf import PerfAPI
from mockarty.api.prompts import PromptsAPI
from mockarty.api.proxy import ProxyAPI
from mockarty.api.secrets import SecretsAPI
from mockarty.api.recorder import RecorderAPI
from mockarty.api.stats import StatsAPI
from mockarty.api.stores import StoreAPI
from mockarty.api.tags import TagAPI
from mockarty.api.templates import TemplateAPI
from mockarty.api.testplans import TestPlansAPI
from mockarty.api.testruns import TestRunAPI
from mockarty.api.undefined import UndefinedAPI


class MockartyClient:
    """Synchronous client for the Mockarty REST API.

    Example::

        client = MockartyClient(base_url="http://localhost:5770", api_key="my-key")
        mock = client.mocks.get("my-mock-id")
        client.close()

    Or as a context manager::

        with MockartyClient() as client:
            mocks = client.mocks.list()

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

    # Names of every cached lazy-init API attribute. The single source of
    # truth for both ``__init__`` (zero-out the slots) and the
    # ``namespace`` setter (re-zero so the next property access rebuilds
    # with the new namespace). Adding a new API resource = one line
    # below — forget it and you get a clear AttributeError at first
    # access, never a stale cached client.
    _API_RESOURCE_ATTRS: tuple[str, ...] = (
        "_chaos",
        "_mocks",
        "_namespaces",
        "_stores",
        "_collections",
        "_perf",
        "_health",
        "_generator",
        "_fuzzing",
        "_contracts",
        "_recorder",
        "_templates",
        "_imports",
        "_test_runs",
        "_test_plans",
        "_tags",
        "_folders",
        "_undefined",
        "_stats",
        "_agent_tasks",
        "_namespace_settings",
        "_proxy",
        "_environments",
        "_entity_search",
        "_external_runs",
        "_secrets",
        "_prompts",
        "_me",
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

        self._http = httpx.Client(
            base_url=self._base_url,
            headers=build_headers(self._api_key, self._namespace),
            timeout=httpx.Timeout(timeout),
            transport=build_transport(max_retries),
        )

        # Lazily-initialised API resources — start all None; each
        # property below fills its own slot on first access.
        for attr in self._API_RESOURCE_ATTRS:
            setattr(self, attr, None)

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self) -> MockartyClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        self._http.close()

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
        """Update the default namespace and refresh the header.

        Resets every cached API instance so the next property access
        rebuilds it bound to the new namespace. Driven off the
        ``_API_RESOURCE_ATTRS`` table so adding a new resource only
        needs a one-line entry there, not a parallel reset block here.
        """
        self._namespace = value
        self._http.headers["X-Namespace"] = value
        for attr in self._API_RESOURCE_ATTRS:
            setattr(self, attr, None)

    # ── API resources ─────────────────────────────────────────────────

    @property
    def chaos(self) -> ChaosAPI:
        """Chaos engineering API."""
        if self._chaos is None:
            self._chaos = ChaosAPI(self._http, self._namespace)
        return self._chaos

    @property
    def mocks(self) -> MockAPI:
        """Mock CRUD API."""
        if self._mocks is None:
            self._mocks = MockAPI(self._http, self._namespace)
        return self._mocks

    @property
    def namespaces(self) -> NamespaceAPI:
        """Namespace management API."""
        if self._namespaces is None:
            self._namespaces = NamespaceAPI(self._http, self._namespace)
        return self._namespaces

    @property
    def stores(self) -> StoreAPI:
        """Store management API (Global and Chain stores)."""
        if self._stores is None:
            self._stores = StoreAPI(self._http, self._namespace)
        return self._stores

    @property
    def secrets(self) -> SecretsAPI:
        """Secrets Storage API (encrypted key/value stores, optional Vault backend)."""
        if self._secrets is None:
            self._secrets = SecretsAPI(self._http, self._namespace)
        return self._secrets

    @property
    def prompts(self) -> PromptsAPI:
        """Prompts Storage API (managed AI prompts with FIFO-20 versioning)."""
        if self._prompts is None:
            self._prompts = PromptsAPI(self._http, self._namespace)
        return self._prompts

    @property
    def collections(self) -> CollectionAPI:
        """API Tester collections API."""
        if self._collections is None:
            self._collections = CollectionAPI(self._http, self._namespace)
        return self._collections

    @property
    def perf(self) -> PerfAPI:
        """Performance testing API."""
        if self._perf is None:
            self._perf = PerfAPI(self._http, self._namespace)
        return self._perf

    @property
    def health(self) -> HealthAPI:
        """Health check API."""
        if self._health is None:
            self._health = HealthAPI(self._http, self._namespace)
        return self._health

    @property
    def generator(self) -> GeneratorAPI:
        """Mock generator API (OpenAPI, GraphQL, gRPC, SOAP)."""
        if self._generator is None:
            self._generator = GeneratorAPI(self._http, self._namespace)
        return self._generator

    @property
    def fuzzing(self) -> FuzzingAPI:
        """Fuzzing testing API."""
        if self._fuzzing is None:
            self._fuzzing = FuzzingAPI(self._http, self._namespace)
        return self._fuzzing

    @property
    def contracts(self) -> ContractAPI:
        """Contract testing API."""
        if self._contracts is None:
            self._contracts = ContractAPI(self._http, self._namespace)
        return self._contracts

    @property
    def recorder(self) -> RecorderAPI:
        """Traffic recorder API."""
        if self._recorder is None:
            self._recorder = RecorderAPI(self._http, self._namespace)
        return self._recorder

    @property
    def templates(self) -> TemplateAPI:
        """Payload template management API."""
        if self._templates is None:
            self._templates = TemplateAPI(self._http, self._namespace)
        return self._templates

    @property
    def imports(self) -> ImportAPI:
        """Collection import API (Postman, Insomnia, HAR, cURL)."""
        if self._imports is None:
            self._imports = ImportAPI(self._http, self._namespace)
        return self._imports

    @property
    def test_runs(self) -> TestRunAPI:
        """Test run history API."""
        if self._test_runs is None:
            self._test_runs = TestRunAPI(self._http, self._namespace)
        return self._test_runs

    @property
    def test_plans(self) -> TestPlansAPI:
        """Test Plans API — master orchestrator for heterogeneous runs."""
        if self._test_plans is None:
            self._test_plans = TestPlansAPI(self._http, self._namespace)
        return self._test_plans

    @property
    def me(self) -> MeAPI:
        """Per-caller endpoints (``/api/v1/me/*``).

        Currently exposes ``awaiting_manual()`` for the topbar bell-counter
        / CI guard. Future per-caller routes (preferences, API key listing)
        will live here too.
        """
        if self._me is None:
            self._me = MeAPI(self._http, self._namespace)
        return self._me

    @property
    def tags(self) -> TagAPI:
        """Tag management API."""
        if self._tags is None:
            self._tags = TagAPI(self._http, self._namespace)
        return self._tags

    @property
    def folders(self) -> FolderAPI:
        """Mock folder management API."""
        if self._folders is None:
            self._folders = FolderAPI(self._http, self._namespace)
        return self._folders

    @property
    def undefined(self) -> UndefinedAPI:
        """Undefined (unmatched) requests API."""
        if self._undefined is None:
            self._undefined = UndefinedAPI(self._http, self._namespace)
        return self._undefined

    @property
    def stats(self) -> StatsAPI:
        """System statistics and status API."""
        if self._stats is None:
            self._stats = StatsAPI(self._http, self._namespace)
        return self._stats

    @property
    def agent_tasks(self) -> AgentTaskAPI:
        """AI agent task API."""
        if self._agent_tasks is None:
            self._agent_tasks = AgentTaskAPI(self._http, self._namespace)
        return self._agent_tasks

    @property
    def namespace_settings(self) -> NamespaceSettingsAPI:
        """Per-namespace settings API (users, cleanup, webhooks)."""
        if self._namespace_settings is None:
            self._namespace_settings = NamespaceSettingsAPI(self._http, self._namespace)
        return self._namespace_settings

    @property
    def proxy(self) -> ProxyAPI:
        """Proxy API for forwarding requests."""
        if self._proxy is None:
            self._proxy = ProxyAPI(self._http, self._namespace)
        return self._proxy

    @property
    def environments(self) -> EnvironmentAPI:
        """API Tester environments API."""
        if self._environments is None:
            self._environments = EnvironmentAPI(self._http, self._namespace)
        return self._environments

    @property
    def entity_search(self) -> EntitySearchAPI:
        """Unified entity-search API (resolve names → IDs across all types)."""
        if self._entity_search is None:
            self._entity_search = EntitySearchAPI(self._http, self._namespace)
        return self._entity_search

    @property
    def external_runs(self) -> ExternalRunsAPI:
        """External-framework upload API (POST /tcm/external-runs)."""
        if self._external_runs is None:
            self._external_runs = ExternalRunsAPI(self._http, self._namespace)
        return self._external_runs

