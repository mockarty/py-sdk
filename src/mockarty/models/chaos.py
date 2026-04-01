# Copyright (c) 2026 Mockarty. All rights reserved.

"""Chaos engineering models for resilience and fault injection testing.

All model fields use camelCase JSON aliases that exactly match the server-side
Go struct tags (see internal/chaos/models.go and sdk/go-sdk/model_chaos.go).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fault Configuration
# ---------------------------------------------------------------------------


class FaultConfig(BaseModel):
    """A single fault injection action within an experiment.

    Matches Go ``FaultConfig`` in ``internal/chaos/models.go``.
    """

    type: Optional[str] = None
    parameters: Optional[dict[str, Any]] = None

    # General fields used by specific fault types
    grace_period_sec: Optional[int] = Field(None, alias="gracePeriodSec")
    replicas: Optional[int] = None
    duration: Optional[str] = None
    interval_sec: Optional[int] = Field(None, alias="intervalSec")

    # Network-specific
    latency_ms: Optional[int] = Field(None, alias="latencyMs")
    loss_percent: Optional[int] = Field(None, alias="lossPercent")
    jitter_ms: Optional[int] = Field(None, alias="jitterMs")
    corrupt_percent: Optional[int] = Field(None, alias="corruptPercent")

    # Resource stress-specific
    cpu_cores: Optional[int] = Field(None, alias="cpuCores")
    memory_mb: Optional[int] = Field(None, alias="memoryMB")
    stress_type: Optional[str] = Field(None, alias="stressType")

    # DNS-specific
    target_domain: Optional[str] = Field(None, alias="targetDomain")
    spoof_ip: Optional[str] = Field(None, alias="spoofIP")

    # IO chaos-specific
    io_latency_ms: Optional[int] = Field(None, alias="ioLatencyMs")
    io_err_percent: Optional[int] = Field(None, alias="ioErrPercent")
    io_path: Optional[str] = Field(None, alias="ioPath")

    # Time chaos-specific
    time_offset_sec: Optional[int] = Field(None, alias="timeOffsetSec")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Target Configuration
# ---------------------------------------------------------------------------


class TargetConfig(BaseModel):
    """Specifies which resources are targeted by the experiment.

    Matches Go ``TargetConfig`` in ``internal/chaos/models.go``.
    """

    mode: Optional[str] = None
    selector: Optional[dict[str, str]] = None
    deployment: Optional[str] = None
    namespace: Optional[str] = None
    pod_names: Optional[list[str]] = Field(None, alias="podNames")
    node_name: Optional[str] = Field(None, alias="nodeName")
    percentage: Optional[int] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Steady State
# ---------------------------------------------------------------------------


class SteadyStateCheck(BaseModel):
    """A single verification of a steady-state hypothesis.

    Matches Go ``SteadyStateCheck`` in ``internal/chaos/models.go``.
    """

    name: Optional[str] = None
    type: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    expected: Optional[Any] = None
    tolerance: Optional[float] = None
    timeout_sec: Optional[int] = Field(None, alias="timeoutSec")
    interval_sec: Optional[int] = Field(None, alias="intervalSec")
    query: Optional[str] = None
    headers: Optional[dict[str, str]] = None

    model_config = {"populate_by_name": True}


class SteadyState(BaseModel):
    """Defines expected baseline conditions and checks to verify them."""

    checks: Optional[list[SteadyStateCheck]] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Schedule Configuration
# ---------------------------------------------------------------------------


class ScheduleConfig(BaseModel):
    """Controls the scheduling behavior of the experiment.

    Matches Go ``ScheduleConfig`` in ``internal/chaos/models.go``.
    """

    cron_expr: Optional[str] = Field(None, alias="cronExpr")
    repeat_count: Optional[int] = Field(None, alias="repeatCount")
    jitter: Optional[int] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Safety Configuration
# ---------------------------------------------------------------------------


class SafetyConfig(BaseModel):
    """Guardrails to prevent chaos from causing unacceptable damage.

    Matches Go ``SafetyConfig`` in ``internal/chaos/models.go``.
    """

    deny_namespaces: Optional[list[str]] = Field(None, alias="denyNamespaces")
    allow_namespaces: Optional[list[str]] = Field(None, alias="allowNamespaces")
    max_concurrent: Optional[int] = Field(None, alias="maxConcurrent")
    max_pods_affected: Optional[int] = Field(None, alias="maxPodsAffected")
    min_replicas_alive: Optional[int] = Field(None, alias="minReplicasAlive")
    auto_rollback: Optional[bool] = Field(None, alias="autoRollback")
    halt_on_steady_fail: Optional[bool] = Field(None, alias="haltOnSteadyFail")
    require_approval: Optional[bool] = Field(None, alias="requireApproval")
    blast_radius_percent: Optional[int] = Field(None, alias="blastRadiusPercent")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class MinMaxAvg(BaseModel):
    """Min/max/avg statistics for a numeric metric."""

    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None

    model_config = {"populate_by_name": True}


class PhaseMetrics(BaseModel):
    """Metrics collected during a specific phase of the experiment.

    Matches Go ``PhaseMetrics`` in ``internal/chaos/models.go``.
    """

    phase: Optional[str] = None
    start_time: Optional[str] = Field(None, alias="startTime")
    end_time: Optional[str] = Field(None, alias="endTime")
    latency: Optional[MinMaxAvg] = None
    error_rate: Optional[float] = Field(None, alias="errorRate")
    throughput: Optional[float] = None
    pod_restarts: Optional[int] = Field(None, alias="podRestarts")

    model_config = {"populate_by_name": True}


class TimelineEvent(BaseModel):
    """A discrete event that occurred during the experiment.

    Matches Go ``TimelineEvent`` in ``internal/chaos/models.go``.
    """

    timestamp: Optional[str] = None
    type: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Any] = None
    severity: Optional[str] = None

    model_config = {"populate_by_name": True}


class AffectedResource(BaseModel):
    """A resource that was impacted by the experiment.

    Matches Go ``AffectedResource`` in ``internal/chaos/models.go``.
    """

    kind: Optional[str] = None
    name: Optional[str] = None
    namespace: Optional[str] = None
    action: Optional[str] = None
    recovered: Optional[bool] = None

    model_config = {"populate_by_name": True}


class ChaosResults(BaseModel):
    """Aggregated results from a completed experiment.

    Matches Go ``ChaosResults`` in ``internal/chaos/models.go``.
    """

    steady_state_before: Optional[bool] = Field(None, alias="steadyStateBefore")
    steady_state_after: Optional[bool] = Field(None, alias="steadyStateAfter")
    steady_state_during: Optional[bool] = Field(None, alias="steadyStateDuring")
    phases: Optional[list[PhaseMetrics]] = None
    timeline: Optional[list[TimelineEvent]] = None
    affected_resources: Optional[list[AffectedResource]] = Field(
        None, alias="affectedResources"
    )
    total_duration_ms: Optional[int] = Field(None, alias="totalDurationMs")
    error_count: Optional[int] = Field(None, alias="errorCount")
    recovery_time_ms: Optional[int] = Field(None, alias="recoveryTimeMs")
    resilience_score: Optional[int] = Field(None, alias="resilienceScore")
    summary: Optional[str] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Core Experiment Model
# ---------------------------------------------------------------------------


class ChaosExperiment(BaseModel):
    """A chaos engineering experiment definition.

    Matches Go ``ChaosExperiment`` in ``internal/chaos/models.go``.
    """

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    namespace: Optional[str] = None
    status: Optional[str] = None
    preset_name: Optional[str] = Field(None, alias="presetName")
    faults: Optional[list[FaultConfig]] = None
    target: Optional[TargetConfig] = None
    steady_state: Optional[SteadyState] = Field(None, alias="steadyState")
    schedule: Optional[ScheduleConfig] = None
    safety: Optional[SafetyConfig] = None
    results: Optional[ChaosResults] = None
    duration_sec: Optional[int] = Field(None, alias="durationSec")
    warmup_sec: Optional[int] = Field(None, alias="warmupSec")
    cooldown_sec: Optional[int] = Field(None, alias="cooldownSec")
    created_by: Optional[str] = Field(None, alias="createdBy")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
    started_at: Optional[str] = Field(None, alias="startedAt")
    ended_at: Optional[str] = Field(None, alias="endedAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Profiles (Cluster Connections) -- maps to InfraProfile on the server
# ---------------------------------------------------------------------------


class InfraProfile(BaseModel):
    """A Kubernetes cluster connection profile for chaos experiments.

    Matches Go ``InfraProfile`` in ``internal/chaos/models.go`` and
    ``ChaosProfile`` in ``sdk/go-sdk/model_chaos.go``.
    """

    id: Optional[str] = None
    namespace_id: Optional[str] = Field(None, alias="namespaceId")
    name: Optional[str] = None
    kubeconfig_path: Optional[str] = Field(None, alias="kubeconfigPath")
    kubeconfig_data: Optional[str] = Field(None, alias="kubeconfigData")
    context: Optional[str] = None
    in_cluster: Optional[bool] = Field(None, alias="inCluster")
    default_namespace: Optional[str] = Field(None, alias="defaultNamespace")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


# Alias for backward compatibility
ChaosProfile = InfraProfile


# ---------------------------------------------------------------------------
# Connection Result
# ---------------------------------------------------------------------------


class ChaosConnectionResult(BaseModel):
    """Result of a cluster connectivity test.

    Matches Go ``ChaosConnectionResult`` in ``sdk/go-sdk/model_chaos.go``.
    """

    connected: Optional[bool] = None
    error: Optional[str] = None
    profile_id: Optional[str] = Field(None, alias="profileId")
    profile_name: Optional[str] = Field(None, alias="profileName")
    capabilities: Optional[Any] = None
    warning: Optional[str] = None
    message: Optional[str] = None

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


class ChaosPreset(BaseModel):
    """A predefined chaos experiment template.

    Matches Go ``PresetInfo`` in ``internal/chaos/presets.go`` and
    ``ChaosPreset`` in ``sdk/go-sdk/model_chaos.go``.
    """

    name: Optional[str] = None
    display_name: Optional[str] = Field(None, alias="displayName")
    description: Optional[str] = None
    fault_types: Optional[list[str]] = Field(None, alias="faultTypes")
    risk_level: Optional[str] = Field(None, alias="riskLevel")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class ChaosOperatorStatus(BaseModel):
    """Status of the chaos operator in a cluster.

    Matches Go ``ChaosOperatorStatus`` in ``sdk/go-sdk/model_chaos.go``.
    """

    installed: Optional[bool] = None
    healthy: Optional[bool] = None
    replicas: Optional[int] = None
    ready_replicas: Optional[int] = Field(None, alias="readyReplicas")
    namespace: Optional[str] = None
    message: Optional[str] = None
    setup_steps: Optional[list[str]] = Field(None, alias="setupSteps")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Metrics & Events
# ---------------------------------------------------------------------------


class MetricsSnapshot(BaseModel):
    """A point-in-time snapshot of cluster/service metrics.

    Matches Go ``MetricsSnapshot`` in ``internal/chaos/models.go``.
    """

    timestamp: Optional[str] = None
    pod_count: Optional[int] = Field(None, alias="podCount")
    ready_pod_count: Optional[int] = Field(None, alias="readyPodCount")
    restart_count: Optional[int] = Field(None, alias="restartCount")
    latency_p50_ms: Optional[float] = Field(None, alias="latencyP50Ms")
    latency_p95_ms: Optional[float] = Field(None, alias="latencyP95Ms")
    latency_p99_ms: Optional[float] = Field(None, alias="latencyP99Ms")
    error_rate: Optional[float] = Field(None, alias="errorRate")
    custom_metrics: Optional[dict[str, float]] = Field(None, alias="customMetrics")

    model_config = {"populate_by_name": True}


class HealthCheckResult(BaseModel):
    """The outcome of a single health check execution.

    Matches Go ``HealthCheckResult`` in ``internal/chaos/models.go``.
    """

    check_name: Optional[str] = Field(None, alias="checkName")
    passed: Optional[bool] = None
    actual_value: Optional[Any] = Field(None, alias="actualValue")
    expected_value: Optional[Any] = Field(None, alias="expectedValue")
    message: Optional[str] = None
    timestamp: Optional[str] = None
    duration_ms: Optional[int] = Field(None, alias="durationMs")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Convenience Envelope Models
# ---------------------------------------------------------------------------


class ChaosMetrics(BaseModel):
    """Metrics envelope returned by GET /api/v1/chaos/experiments/:id/metrics."""

    experiment_id: Optional[str] = Field(None, alias="experimentId")
    snapshots: Optional[list[MetricsSnapshot]] = None
    count: Optional[int] = None

    model_config = {"populate_by_name": True}


class ChaosEvent(BaseModel):
    """An event recorded during a chaos experiment (timeline envelope)."""

    experiment_id: Optional[str] = Field(None, alias="experimentId")
    events: Optional[list[TimelineEvent]] = None
    count: Optional[int] = None

    model_config = {"populate_by_name": True}


class ChaosReport(BaseModel):
    """A summary report for a chaos experiment."""

    experiment: Optional[ChaosExperiment] = None
    events: Optional[list[dict[str, Any]]] = None
    metrics: Optional[list[dict[str, Any]]] = None
    results: Optional[ChaosResults] = None
    steady_state_before: Optional[bool] = Field(None, alias="steadyStateBefore")
    steady_state_after: Optional[bool] = Field(None, alias="steadyStateAfter")
    steady_state_during: Optional[bool] = Field(None, alias="steadyStateDuring")
    recovery_time_ms: Optional[int] = Field(None, alias="recoveryTimeMs")
    error_count: Optional[int] = Field(None, alias="errorCount")
    summary: Optional[str] = None
    affected_resources: Optional[list[AffectedResource]] = Field(
        None, alias="affectedResources"
    )

    model_config = {"populate_by_name": True}


class ChaosSnapshot(BaseModel):
    """A point-in-time snapshot of system state during a chaos experiment."""

    experiment_id: Optional[str] = Field(None, alias="experimentId")
    timestamp: Optional[str] = None
    pods: Optional[list[dict[str, Any]]] = None
    services: Optional[list[dict[str, Any]]] = None
    deployments: Optional[list[dict[str, Any]]] = None
    state: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}
