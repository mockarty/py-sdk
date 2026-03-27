# Copyright (c) 2026 Mockarty. All rights reserved.

"""API resource classes for Mockarty client."""

from mockarty.api.agent_tasks import AgentTaskAPI, AsyncAgentTaskAPI
from mockarty.api.chaos import AsyncChaosAPI, ChaosAPI
from mockarty.api.collections import AsyncCollectionAPI, CollectionAPI
from mockarty.api.contracts import AsyncContractAPI, ContractAPI
from mockarty.api.environments import AsyncEnvironmentAPI, EnvironmentAPI
from mockarty.api.folders import AsyncFolderAPI, FolderAPI
from mockarty.api.fuzzing import AsyncFuzzingAPI, FuzzingAPI
from mockarty.api.generator import AsyncGeneratorAPI, GeneratorAPI
from mockarty.api.health import AsyncHealthAPI, HealthAPI
from mockarty.api.imports import AsyncImportAPI, ImportAPI
from mockarty.api.mocks import AsyncMockAPI, MockAPI
from mockarty.api.namespace_settings import (
    AsyncNamespaceSettingsAPI,
    NamespaceSettingsAPI,
)
from mockarty.api.namespaces import AsyncNamespaceAPI, NamespaceAPI
from mockarty.api.perf import AsyncPerfAPI, PerfAPI
from mockarty.api.proxy import AsyncProxyAPI, ProxyAPI
from mockarty.api.recorder import AsyncRecorderAPI, RecorderAPI
from mockarty.api.stats import AsyncStatsAPI, StatsAPI
from mockarty.api.stores import AsyncStoreAPI, StoreAPI
from mockarty.api.tags import AsyncTagAPI, TagAPI
from mockarty.api.templates import AsyncTemplateAPI, TemplateAPI
from mockarty.api.testruns import AsyncTestRunAPI, TestRunAPI
from mockarty.api.undefined import AsyncUndefinedAPI, UndefinedAPI

__all__ = [
    "AgentTaskAPI",
    "AsyncAgentTaskAPI",
    "AsyncChaosAPI",
    "AsyncCollectionAPI",
    "AsyncContractAPI",
    "AsyncEnvironmentAPI",
    "AsyncFolderAPI",
    "AsyncFuzzingAPI",
    "AsyncGeneratorAPI",
    "AsyncHealthAPI",
    "AsyncImportAPI",
    "AsyncMockAPI",
    "AsyncNamespaceAPI",
    "AsyncNamespaceSettingsAPI",
    "AsyncPerfAPI",
    "AsyncProxyAPI",
    "AsyncRecorderAPI",
    "AsyncStatsAPI",
    "AsyncStoreAPI",
    "AsyncTagAPI",
    "AsyncTemplateAPI",
    "AsyncTestRunAPI",
    "AsyncUndefinedAPI",
    "ChaosAPI",
    "CollectionAPI",
    "ContractAPI",
    "EnvironmentAPI",
    "FolderAPI",
    "FuzzingAPI",
    "GeneratorAPI",
    "HealthAPI",
    "ImportAPI",
    "MockAPI",
    "NamespaceAPI",
    "NamespaceSettingsAPI",
    "PerfAPI",
    "ProxyAPI",
    "RecorderAPI",
    "StatsAPI",
    "StoreAPI",
    "TagAPI",
    "TemplateAPI",
    "TestRunAPI",
    "UndefinedAPI",
]
