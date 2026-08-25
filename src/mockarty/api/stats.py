# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Stats API resource for system statistics and status."""

from __future__ import annotations

from typing import Any, TypedDict, cast

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class CapabilitySchemas(TypedDict, total=False):
    input: dict[str, Any]
    output: dict[str, Any]
    settings: dict[str, Any]
    result: dict[str, Any]
    evidence: dict[str, Any]
    admission: dict[str, Any]


class CapabilityDataBoundary(TypedDict, total=False):
    classes: list[str]
    residencies: list[str]
    allowedHosts: list[str]
    networkScope: str


class CapabilityPolicy(TypedDict, total=False):
    requiredRoles: list[str]
    requiredPermissions: list[str]
    dataBoundary: CapabilityDataBoundary
    sideEffect: str
    idempotency: str
    timeoutMillis: int
    maxRetries: int


class CapabilityResource(TypedDict, total=False):
    memoryBytes: int
    scratchBytes: int
    costUpperBoundMicros: int
    cpuUnits: int
    maxConcurrency: int


class CapabilityProvenance(TypedDict, total=False):
    sourceKind: str
    sourceRef: str
    digest: str
    publisher: str


class CapabilityTrust(TypedDict, total=False):
    level: str
    isolation: str
    signatureKeyId: str
    verified: bool


class CapabilityExecutor(TypedDict, total=False):
    kind: str
    binding: str


class CapabilityHealth(TypedDict, total=False):
    kind: str
    probe: str
    timeoutMillis: int


class CapabilityCompatibility(TypedDict, total=False):
    minHostVersion: str
    maxHostVersion: str


class CapabilityAvailability(TypedDict, total=False):
    available: bool
    reason: str


class CapabilityDescriptor(TypedDict, total=False):
    contractVersion: str
    key: str
    version: str
    provider: str
    kind: str
    title: str
    description: str
    featureKey: str
    hosts: list[str]
    schemas: CapabilitySchemas
    policy: CapabilityPolicy
    resource: CapabilityResource
    provenance: CapabilityProvenance
    trust: CapabilityTrust
    executor: CapabilityExecutor
    health: CapabilityHealth
    compatibility: CapabilityCompatibility
    availability: CapabilityAvailability
    builtin: bool


class CapabilityCatalog(TypedDict):
    capabilities: list[CapabilityDescriptor]
    count: int
    skipped: int


class StatsAPI(SyncAPIBase):
    """Synchronous Stats API resource."""

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        resp = self._request("GET", "/api/v1/stats")
        return resp.json()

    def get_counts(self) -> dict[str, Any]:
        """Get resource counts (mocks, namespaces, etc.)."""
        resp = self._request("GET", "/api/v1/counts")
        return resp.json()

    def get_status(self) -> dict[str, Any]:
        """Get system status information."""
        resp = self._request("GET", "/api/v1/status")
        return resp.json()

    def get_features(self) -> dict[str, Any]:
        """Get available feature flags."""
        resp = self._request("GET", "/api/v1/features")
        return resp.json()

    def list_capabilities(self) -> CapabilityCatalog:
        """List canonical capability descriptors available to this namespace."""
        resp = self._request("GET", "/api/v1/capabilities", params={"namespace": self._namespace})
        return cast(CapabilityCatalog, resp.json())


class AsyncStatsAPI(AsyncAPIBase):
    """Asynchronous Stats API resource."""

    async def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        resp = await self._request("GET", "/api/v1/stats")
        return resp.json()

    async def get_counts(self) -> dict[str, Any]:
        """Get resource counts (mocks, namespaces, etc.)."""
        resp = await self._request("GET", "/api/v1/counts")
        return resp.json()

    async def get_status(self) -> dict[str, Any]:
        """Get system status information."""
        resp = await self._request("GET", "/api/v1/status")
        return resp.json()

    async def get_features(self) -> dict[str, Any]:
        """Get available feature flags."""
        resp = await self._request("GET", "/api/v1/features")
        return resp.json()

    async def list_capabilities(self) -> CapabilityCatalog:
        """List canonical capability descriptors available to this namespace."""
        resp = await self._request("GET", "/api/v1/capabilities", params={"namespace": self._namespace})
        return cast(CapabilityCatalog, resp.json())
