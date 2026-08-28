# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""API resource classes for Mockarty client."""

from mockarty.api.agent_tasks import AgentTaskAPI, AsyncAgentTaskAPI
from mockarty.api.autonomous_missions import AsyncAutonomousMissionsAPI, AutonomousMissionsAPI
from mockarty.api.coder_delivery import AsyncCoderDeliveryAPI, CoderDeliveryAPI
from mockarty.api.chaos import AsyncChaosAPI, ChaosAPI
from mockarty.api.cloud_entitlements import AsyncCloudEntitlementsAPI, CloudEntitlementsAPI
from mockarty.api.ci_triggers import AsyncCITriggerAPI, CITriggerAPI
from mockarty.api.collections import AsyncCollectionAPI, CollectionAPI
from mockarty.api.contracts import AsyncContractAPI, ContractAPI
from mockarty.api.economics import AsyncEconomicsAPI, EconomicsAPI
from mockarty.api.delivery_policy import AsyncDeliveryPolicyAPI, DeliveryPolicyAPI
from mockarty.api.entity_search import AsyncEntitySearchAPI, EntitySearchAPI
from mockarty.api.environments import AsyncEnvironmentAPI, EnvironmentAPI
from mockarty.api.experience import AsyncExperienceAPI, ExperienceAPI
from mockarty.api.folders import AsyncFolderAPI, FolderAPI
from mockarty.api.fuzzing import AsyncFuzzingAPI, FuzzingAPI
from mockarty.api.generator import AsyncGeneratorAPI, GeneratorAPI
from mockarty.api.health import AsyncHealthAPI, HealthAPI
from mockarty.api.imports import AsyncImportAPI, ImportAPI
from mockarty.api.llm_security import AsyncLLMSecurityAPI, LLMSecurityAPI
from mockarty.api.mocks import AsyncMockAPI, MockAPI
from mockarty.api.namespace_settings import (
    AsyncNamespaceSettingsAPI,
    NamespaceSettingsAPI,
)
from mockarty.api.namespaces import AsyncNamespaceAPI, NamespaceAPI
from mockarty.api.perf import AsyncPerfAPI, PerfAPI
from mockarty.api.prompts import AsyncPromptsAPI, PromptsAPI
from mockarty.api.proxy import AsyncProxyAPI, ProxyAPI
from mockarty.api.recorder import AsyncRecorderAPI, RecorderAPI
from mockarty.api.secrets import AsyncSecretsAPI, SecretsAPI
from mockarty.api.stats import AsyncStatsAPI, StatsAPI
from mockarty.api.stores import AsyncStoreAPI, StoreAPI
from mockarty.api.tags import AsyncTagAPI, TagAPI
from mockarty.api.templates import AsyncTemplateAPI, TemplateAPI
from mockarty.api.testruns import AsyncTestRunAPI, TestRunAPI
from mockarty.api.undefined import AsyncUndefinedAPI, UndefinedAPI

__all__ = [
    "AgentTaskAPI",
    "AsyncAgentTaskAPI",
    "AsyncAutonomousMissionsAPI",
    "AsyncCoderDeliveryAPI",
    "AutonomousMissionsAPI",
    "CoderDeliveryAPI",
    "AsyncCITriggerAPI",
    "AsyncChaosAPI",
    "AsyncCloudEntitlementsAPI",
    "AsyncCollectionAPI",
    "AsyncContractAPI",
    "AsyncEntitySearchAPI",
    "AsyncExperienceAPI",
    "AsyncEconomicsAPI",
    "AsyncDeliveryPolicyAPI",
    "AsyncEnvironmentAPI",
    "AsyncFolderAPI",
    "AsyncFuzzingAPI",
    "AsyncGeneratorAPI",
    "AsyncHealthAPI",
    "AsyncImportAPI",
    "AsyncLLMSecurityAPI",
    "AsyncMockAPI",
    "AsyncNamespaceAPI",
    "AsyncNamespaceSettingsAPI",
    "AsyncPerfAPI",
    "AsyncPromptsAPI",
    "AsyncProxyAPI",
    "AsyncSecretsAPI",
    "AsyncRecorderAPI",
    "AsyncStatsAPI",
    "AsyncStoreAPI",
    "AsyncTagAPI",
    "AsyncTemplateAPI",
    "AsyncTestRunAPI",
    "AsyncUndefinedAPI",
    "CITriggerAPI",
    "ChaosAPI",
    "CloudEntitlementsAPI",
    "CollectionAPI",
    "ContractAPI",
    "EntitySearchAPI",
    "ExperienceAPI",
    "EconomicsAPI",
    "DeliveryPolicyAPI",
    "EnvironmentAPI",
    "FolderAPI",
    "FuzzingAPI",
    "GeneratorAPI",
    "HealthAPI",
    "ImportAPI",
    "LLMSecurityAPI",
    "MockAPI",
    "NamespaceAPI",
    "NamespaceSettingsAPI",
    "PerfAPI",
    "PromptsAPI",
    "ProxyAPI",
    "SecretsAPI",
    "RecorderAPI",
    "StatsAPI",
    "StoreAPI",
    "TagAPI",
    "TemplateAPI",
    "TestRunAPI",
    "UndefinedAPI",
]
