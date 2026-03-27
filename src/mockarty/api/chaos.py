# Copyright (c) 2026 Mockarty. All rights reserved.

"""Chaos engineering API resource for resilience and fault injection testing.

All API paths and request/response shapes match the server routes registered in
``internal/chaos/api.go`` ``RegisterChaosRoutes`` and the corrected Go SDK in
``sdk/go-sdk/api_chaos.go``.
"""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


class ChaosAPI(SyncAPIBase):
    """Synchronous Chaos Engineering API resource."""

    # ── Profiles (Kubernetes cluster connections) ──────────────────────

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all Kubernetes cluster connection profiles.

        GET /api/v1/chaos/profiles
        """
        resp = self._request("GET", "/api/v1/chaos/profiles")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("profiles") or []
        return []

    def create_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new cluster connection profile.

        POST /api/v1/chaos/profiles
        """
        resp = self._request("POST", "/api/v1/chaos/profiles", json=profile)
        return resp.json()

    def update_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing cluster connection profile.

        PUT /api/v1/chaos/profiles/:id
        """
        resp = self._request(
            "PUT", f"/api/v1/chaos/profiles/{profile_id}", json=profile
        )
        return resp.json()

    def delete_profile(self, profile_id: str) -> None:
        """Delete a cluster connection profile.

        DELETE /api/v1/chaos/profiles/:id
        """
        self._request("DELETE", f"/api/v1/chaos/profiles/{profile_id}")

    def test_profile(self, profile_id: str) -> dict[str, Any]:
        """Test connectivity of an existing cluster connection profile.

        POST /api/v1/chaos/profiles/:id/test
        """
        resp = self._request("POST", f"/api/v1/chaos/profiles/{profile_id}/test")
        return resp.json()

    def connect_profile(self, profile_id: str) -> dict[str, Any]:
        """Connect to a cluster using the given profile.

        POST /api/v1/chaos/profiles/:id/connect
        """
        resp = self._request("POST", f"/api/v1/chaos/profiles/{profile_id}/connect")
        return resp.json()

    def test_inline_kubeconfig(
        self, kubeconfig: str, context: str | None = None
    ) -> dict[str, Any]:
        """Test K8s connectivity using inline kubeconfig data (not a saved profile).

        POST /api/v1/chaos/profiles-test

        Args:
            kubeconfig: The kubeconfig content as a string.
            context: Optional kubectl context name.
        """
        body: dict[str, Any] = {"kubeconfig": kubeconfig}
        if context is not None:
            body["context"] = context
        resp = self._request("POST", "/api/v1/chaos/profiles-test", json=body)
        return resp.json()

    # ── Presets ────────────────────────────────────────────────────────

    def list_presets(self) -> list[dict[str, Any]]:
        """List all available chaos experiment presets.

        GET /api/v1/chaos/presets
        """
        resp = self._request("GET", "/api/v1/chaos/presets")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("presets") or []
        return []

    # ── Experiments (CRUD) ────────────────────────────────────────────

    def list(
        self,
        namespace: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List chaos experiments with optional filtering.

        GET /api/v1/chaos/experiments

        Returns:
            A tuple of (experiments list, total count).
        """
        params: dict[str, Any] = {}
        if namespace is not None:
            params["namespace"] = namespace
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        resp = self._request("GET", "/api/v1/chaos/experiments", params=params or None)
        data = resp.json()
        if isinstance(data, dict):
            experiments = data.get("experiments") or []
            total = data.get("total", len(experiments))
            return experiments, total
        return [], 0

    def get(self, experiment_id: str) -> dict[str, Any]:
        """Get a chaos experiment by ID.

        GET /api/v1/chaos/experiments/:id
        """
        resp = self._request("GET", f"/api/v1/chaos/experiments/{experiment_id}")
        return resp.json()

    def create(self, experiment: dict[str, Any]) -> dict[str, Any]:
        """Create a new chaos experiment.

        POST /api/v1/chaos/experiments
        """
        resp = self._request("POST", "/api/v1/chaos/experiments", json=experiment)
        return resp.json()

    def update(
        self, experiment_id: str, experiment: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing chaos experiment.

        PUT /api/v1/chaos/experiments/:id
        """
        resp = self._request(
            "PUT", f"/api/v1/chaos/experiments/{experiment_id}", json=experiment
        )
        return resp.json()

    def delete(self, experiment_id: str) -> None:
        """Delete a chaos experiment.

        DELETE /api/v1/chaos/experiments/:id
        """
        self._request("DELETE", f"/api/v1/chaos/experiments/{experiment_id}")

    # ── Experiment Execution ──────────────────────────────────────────

    def run(self, experiment_id: str) -> None:
        """Start execution of a chaos experiment.

        POST /api/v1/chaos/experiments/:id/run
        """
        self._request("POST", f"/api/v1/chaos/experiments/{experiment_id}/run")

    def abort(self, experiment_id: str) -> None:
        """Abort a running chaos experiment.

        POST /api/v1/chaos/experiments/:id/abort
        """
        self._request("POST", f"/api/v1/chaos/experiments/{experiment_id}/abort")

    # ── Experiment Results & Metrics ──────────────────────────────────

    def get_metrics(self, experiment_id: str) -> list[dict[str, Any]]:
        """Get metric snapshots collected during an experiment.

        GET /api/v1/chaos/experiments/:id/metrics

        Returns:
            List of metric snapshots (unwrapped from envelope).
        """
        resp = self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/metrics"
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("snapshots") or []
        return []

    def get_events(self, experiment_id: str) -> list[dict[str, Any]]:
        """Get timeline events for an experiment.

        GET /api/v1/chaos/experiments/:id/events

        Returns:
            List of timeline events (unwrapped from envelope).
        """
        resp = self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/events"
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("events") or []
        return []

    def get_report(self, experiment_id: str) -> dict[str, Any]:
        """Get a full experiment report with analytics.

        GET /api/v1/chaos/experiments/:id/report
        """
        resp = self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/report"
        )
        return resp.json()

    def download_report(
        self, experiment_id: str, format: str = "html"
    ) -> bytes:
        """Download an experiment report in the specified format.

        GET /api/v1/chaos/experiments/:id/report/download?format=...

        Args:
            experiment_id: The experiment ID.
            format: Report format (``"html"``, ``"json"``, ``"junit"``, ``"allure"``).
                Defaults to ``"html"``.

        Returns:
            Raw report bytes.
        """
        resp = self._request(
            "GET",
            f"/api/v1/chaos/experiments/{experiment_id}/report/download",
            params={"format": format},
        )
        return resp.content

    def get_snapshot(self, experiment_id: str) -> dict[str, Any]:
        """Get a point-in-time resource snapshot for an experiment.

        GET /api/v1/chaos/experiments/:id/snapshot
        """
        resp = self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/snapshot"
        )
        return resp.json()

    # ── Queue ──────────────────────────────────────────────────────────

    def get_queue_status(self, cluster_id: str) -> dict[str, Any]:
        """Get the experiment queue status for a cluster.

        GET /api/v1/chaos/queue/:clusterId
        """
        resp = self._request("GET", f"/api/v1/chaos/queue/{cluster_id}")
        return resp.json()

    # ── Cluster Operations (ad-hoc) ───────────────────────────────────

    def get_topology(
        self, profile_id: str, namespace: str | None = None
    ) -> dict[str, Any]:
        """Get the cluster topology for a profile and optional namespace.

        GET /api/v1/chaos/clusters/:id/topology?namespace=...

        Args:
            profile_id: The cluster/profile ID.
            namespace: Optional Kubernetes namespace to scope the topology.
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = self._request(
            "GET", f"/api/v1/chaos/clusters/{profile_id}/topology", params=params
        )
        return resp.json()

    def kill_pod(
        self,
        namespace: str,
        name: str,
        grace_period: int | None = None,
    ) -> None:
        """Kill a pod in the given namespace.

        DELETE /api/v1/chaos/pods/:namespace/:name?gracePeriod=...

        Args:
            namespace: The Kubernetes namespace.
            name: The pod name.
            grace_period: Optional grace period in seconds (0 = immediate).
        """
        params: dict[str, Any] | None = None
        if grace_period is not None and grace_period > 0:
            params = {"gracePeriod": str(grace_period)}
        self._request(
            "DELETE", f"/api/v1/chaos/pods/{namespace}/{name}", params=params
        )

    def get_pod_detail(self, namespace: str, name: str) -> dict[str, Any]:
        """Get detailed information about a specific pod.

        GET /api/v1/chaos/pods/:namespace/:name
        """
        resp = self._request("GET", f"/api/v1/chaos/pods/{namespace}/{name}")
        return resp.json()

    def get_pod_logs(
        self,
        namespace: str,
        name: str,
        container: str | None = None,
        tail_lines: int | None = None,
    ) -> str:
        """Get logs from a specific pod container.

        GET /api/v1/chaos/pods/:namespace/:name/logs?container=...&tailLines=...

        Args:
            namespace: The Kubernetes namespace.
            name: The pod name.
            container: Optional container name within the pod.
            tail_lines: Optional number of lines from the end of the log.

        Returns:
            Pod log output as a string.
        """
        params: dict[str, Any] = {}
        if container is not None:
            params["container"] = container
        if tail_lines is not None:
            params["tailLines"] = tail_lines
        resp = self._request(
            "GET",
            f"/api/v1/chaos/pods/{namespace}/{name}/logs",
            params=params or None,
        )
        return resp.text

    def get_deployment_detail(self, namespace: str, name: str) -> dict[str, Any]:
        """Get detailed information about a specific deployment.

        GET /api/v1/chaos/deployments/:namespace/:name
        """
        resp = self._request(
            "GET", f"/api/v1/chaos/deployments/{namespace}/{name}"
        )
        return resp.json()

    def scale_deployment(
        self, namespace: str, name: str, replicas: int
    ) -> dict[str, Any]:
        """Scale a deployment to the specified number of replicas.

        POST /api/v1/chaos/deployments/:namespace/:name/scale

        Args:
            namespace: The Kubernetes namespace.
            name: The deployment name.
            replicas: Desired replica count.
        """
        resp = self._request(
            "POST",
            f"/api/v1/chaos/deployments/{namespace}/{name}/scale",
            json={"replicas": replicas},
        )
        return resp.json()

    def restart_deployment(self, namespace: str, name: str) -> None:
        """Perform a rolling restart of a deployment.

        POST /api/v1/chaos/deployments/:namespace/:name/restart
        """
        self._request(
            "POST", f"/api/v1/chaos/deployments/{namespace}/{name}/restart"
        )

    # ── ConfigMaps ────────────────────────────────────────────────────

    def list_configmaps(self, namespace: str) -> list[dict[str, Any]]:
        """List all ConfigMaps in the given namespace.

        GET /api/v1/chaos/configmaps/:namespace

        Returns:
            List of ConfigMap objects (unwrapped from envelope).
        """
        resp = self._request("GET", f"/api/v1/chaos/configmaps/{namespace}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("configmaps") or []
        return []

    def get_configmap(self, namespace: str, name: str) -> dict[str, Any]:
        """Get details of a specific ConfigMap.

        GET /api/v1/chaos/configmaps/:namespace/:name
        """
        resp = self._request(
            "GET", f"/api/v1/chaos/configmaps/{namespace}/{name}"
        )
        return resp.json()

    def update_configmap(
        self, namespace: str, name: str, data: dict[str, str]
    ) -> None:
        """Replace the data section of an existing ConfigMap.

        PUT /api/v1/chaos/configmaps/:namespace/:name

        Args:
            namespace: The Kubernetes namespace.
            name: The ConfigMap name.
            data: Key-value pairs to set in the ConfigMap.
        """
        self._request(
            "PUT",
            f"/api/v1/chaos/configmaps/{namespace}/{name}",
            json={"data": data},
        )

    # ── Services ──────────────────────────────────────────────────────

    def list_services(self, namespace: str) -> list[dict[str, Any]]:
        """List all services in the given namespace.

        GET /api/v1/chaos/services/:namespace

        Returns:
            List of Service objects (unwrapped from envelope).
        """
        resp = self._request("GET", f"/api/v1/chaos/services/{namespace}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("services") or []
        return []

    # ── CRDs (Custom Resource Definitions) ────────────────────────────

    def list_crds(self) -> list[dict[str, Any]]:
        """List all Custom Resource Definitions in the cluster.

        GET /api/v1/chaos/crds

        Returns:
            List of CRD objects (unwrapped from envelope).
        """
        resp = self._request("GET", "/api/v1/chaos/crds")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("crds") or []
        return []

    def list_crd_resources(
        self,
        group: str,
        version: str,
        resource: str,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """List instances of a specific custom resource.

        GET /api/v1/chaos/crds/:group/:version/:resource?namespace=...

        Args:
            group: CRD API group.
            version: CRD API version.
            resource: CRD resource name (plural).
            namespace: Optional namespace to scope the query.

        Returns:
            List of custom resource objects (unwrapped from envelope).
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = self._request(
            "GET",
            f"/api/v1/chaos/crds/{group}/{version}/{resource}",
            params=params,
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("resources") or []
        return []

    # ── Kubernetes Events ─────────────────────────────────────────────

    def list_k8s_events(
        self, namespace: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """List recent Kubernetes events in the given namespace.

        GET /api/v1/chaos/events/:namespace?limit=...

        Args:
            namespace: The Kubernetes namespace.
            limit: Maximum number of events to return.

        Returns:
            List of event objects (unwrapped from envelope).
        """
        params: dict[str, Any] | None = None
        if limit is not None:
            params = {"limit": limit}
        resp = self._request(
            "GET", f"/api/v1/chaos/events/{namespace}", params=params
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("events") or []
        return []

    # ── Operator ──────────────────────────────────────────────────────

    def get_operator_status(self, namespace: str | None = None) -> dict[str, Any]:
        """Get the chaos operator installation status.

        GET /api/v1/chaos/operator/status?namespace=...

        Args:
            namespace: Optional Kubernetes namespace where the operator is deployed.
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = self._request("GET", "/api/v1/chaos/operator/status", params=params)
        return resp.json()

    def install_operator(self, namespace: str | None = None) -> dict[str, Any]:
        """Generate the operator manifest for manual application.

        POST /api/v1/chaos/operator/install?namespace=...

        Args:
            namespace: Optional K8s namespace for the operator.
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = self._request("POST", "/api/v1/chaos/operator/install", params=params)
        return resp.json()

    def generate_operator_manifest(
        self, admin_url: str | None = None, image: str | None = None
    ) -> str:
        """Generate a YAML manifest for installing the chaos operator.

        POST /api/v1/chaos/operator/manifest

        Args:
            admin_url: Optional Mockarty admin node URL to embed in the manifest.
            image: Optional custom operator image.

        Returns:
            YAML manifest as a string.
        """
        body: dict[str, Any] = {}
        if admin_url is not None:
            body["adminUrl"] = admin_url
        if image is not None:
            body["image"] = image
        resp = self._request(
            "POST", "/api/v1/chaos/operator/manifest", json=body or None
        )
        return resp.text


# ---------------------------------------------------------------------------
# Async variant
# ---------------------------------------------------------------------------


class AsyncChaosAPI(AsyncAPIBase):
    """Asynchronous Chaos Engineering API resource."""

    # ── Profiles (Kubernetes cluster connections) ──────────────────────

    async def list_profiles(self) -> list[dict[str, Any]]:
        """List all Kubernetes cluster connection profiles.

        GET /api/v1/chaos/profiles
        """
        resp = await self._request("GET", "/api/v1/chaos/profiles")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("profiles") or []
        return []

    async def create_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Create a new cluster connection profile.

        POST /api/v1/chaos/profiles
        """
        resp = await self._request("POST", "/api/v1/chaos/profiles", json=profile)
        return resp.json()

    async def update_profile(
        self, profile_id: str, profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing cluster connection profile.

        PUT /api/v1/chaos/profiles/:id
        """
        resp = await self._request(
            "PUT", f"/api/v1/chaos/profiles/{profile_id}", json=profile
        )
        return resp.json()

    async def delete_profile(self, profile_id: str) -> None:
        """Delete a cluster connection profile.

        DELETE /api/v1/chaos/profiles/:id
        """
        await self._request("DELETE", f"/api/v1/chaos/profiles/{profile_id}")

    async def test_profile(self, profile_id: str) -> dict[str, Any]:
        """Test connectivity of an existing cluster connection profile.

        POST /api/v1/chaos/profiles/:id/test
        """
        resp = await self._request(
            "POST", f"/api/v1/chaos/profiles/{profile_id}/test"
        )
        return resp.json()

    async def connect_profile(self, profile_id: str) -> dict[str, Any]:
        """Connect to a cluster using the given profile.

        POST /api/v1/chaos/profiles/:id/connect
        """
        resp = await self._request(
            "POST", f"/api/v1/chaos/profiles/{profile_id}/connect"
        )
        return resp.json()

    async def test_inline_kubeconfig(
        self, kubeconfig: str, context: str | None = None
    ) -> dict[str, Any]:
        """Test K8s connectivity using inline kubeconfig data (not a saved profile).

        POST /api/v1/chaos/profiles-test

        Args:
            kubeconfig: The kubeconfig content as a string.
            context: Optional kubectl context name.
        """
        body: dict[str, Any] = {"kubeconfig": kubeconfig}
        if context is not None:
            body["context"] = context
        resp = await self._request("POST", "/api/v1/chaos/profiles-test", json=body)
        return resp.json()

    # ── Presets ────────────────────────────────────────────────────────

    async def list_presets(self) -> list[dict[str, Any]]:
        """List all available chaos experiment presets.

        GET /api/v1/chaos/presets
        """
        resp = await self._request("GET", "/api/v1/chaos/presets")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("presets") or []
        return []

    # ── Experiments (CRUD) ────────────────────────────────────────────

    async def list(
        self,
        namespace: str | None = None,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List chaos experiments with optional filtering.

        GET /api/v1/chaos/experiments

        Returns:
            A tuple of (experiments list, total count).
        """
        params: dict[str, Any] = {}
        if namespace is not None:
            params["namespace"] = namespace
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        resp = await self._request(
            "GET", "/api/v1/chaos/experiments", params=params or None
        )
        data = resp.json()
        if isinstance(data, dict):
            experiments = data.get("experiments") or []
            total = data.get("total", len(experiments))
            return experiments, total
        return [], 0

    async def get(self, experiment_id: str) -> dict[str, Any]:
        """Get a chaos experiment by ID.

        GET /api/v1/chaos/experiments/:id
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}"
        )
        return resp.json()

    async def create(self, experiment: dict[str, Any]) -> dict[str, Any]:
        """Create a new chaos experiment.

        POST /api/v1/chaos/experiments
        """
        resp = await self._request(
            "POST", "/api/v1/chaos/experiments", json=experiment
        )
        return resp.json()

    async def update(
        self, experiment_id: str, experiment: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing chaos experiment.

        PUT /api/v1/chaos/experiments/:id
        """
        resp = await self._request(
            "PUT", f"/api/v1/chaos/experiments/{experiment_id}", json=experiment
        )
        return resp.json()

    async def delete(self, experiment_id: str) -> None:
        """Delete a chaos experiment.

        DELETE /api/v1/chaos/experiments/:id
        """
        await self._request("DELETE", f"/api/v1/chaos/experiments/{experiment_id}")

    # ── Experiment Execution ──────────────────────────────────────────

    async def run(self, experiment_id: str) -> None:
        """Start execution of a chaos experiment.

        POST /api/v1/chaos/experiments/:id/run
        """
        await self._request(
            "POST", f"/api/v1/chaos/experiments/{experiment_id}/run"
        )

    async def abort(self, experiment_id: str) -> None:
        """Abort a running chaos experiment.

        POST /api/v1/chaos/experiments/:id/abort
        """
        await self._request(
            "POST", f"/api/v1/chaos/experiments/{experiment_id}/abort"
        )

    # ── Experiment Results & Metrics ──────────────────────────────────

    async def get_metrics(self, experiment_id: str) -> list[dict[str, Any]]:
        """Get metric snapshots collected during an experiment.

        GET /api/v1/chaos/experiments/:id/metrics

        Returns:
            List of metric snapshots (unwrapped from envelope).
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/metrics"
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("snapshots") or []
        return []

    async def get_events(self, experiment_id: str) -> list[dict[str, Any]]:
        """Get timeline events for an experiment.

        GET /api/v1/chaos/experiments/:id/events

        Returns:
            List of timeline events (unwrapped from envelope).
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/events"
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("events") or []
        return []

    async def get_report(self, experiment_id: str) -> dict[str, Any]:
        """Get a full experiment report with analytics.

        GET /api/v1/chaos/experiments/:id/report
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/report"
        )
        return resp.json()

    async def download_report(
        self, experiment_id: str, format: str = "html"
    ) -> bytes:
        """Download an experiment report in the specified format.

        GET /api/v1/chaos/experiments/:id/report/download?format=...

        Args:
            experiment_id: The experiment ID.
            format: Report format (``"html"``, ``"json"``, ``"junit"``, ``"allure"``).
                Defaults to ``"html"``.

        Returns:
            Raw report bytes.
        """
        resp = await self._request(
            "GET",
            f"/api/v1/chaos/experiments/{experiment_id}/report/download",
            params={"format": format},
        )
        return resp.content

    async def get_snapshot(self, experiment_id: str) -> dict[str, Any]:
        """Get a point-in-time resource snapshot for an experiment.

        GET /api/v1/chaos/experiments/:id/snapshot
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/experiments/{experiment_id}/snapshot"
        )
        return resp.json()

    # ── Queue ──────────────────────────────────────────────────────────

    async def get_queue_status(self, cluster_id: str) -> dict[str, Any]:
        """Get the experiment queue status for a cluster.

        GET /api/v1/chaos/queue/:clusterId
        """
        resp = await self._request("GET", f"/api/v1/chaos/queue/{cluster_id}")
        return resp.json()

    # ── Cluster Operations (ad-hoc) ───────────────────────────────────

    async def get_topology(
        self, profile_id: str, namespace: str | None = None
    ) -> dict[str, Any]:
        """Get the cluster topology for a profile and optional namespace.

        GET /api/v1/chaos/clusters/:id/topology?namespace=...

        Args:
            profile_id: The cluster/profile ID.
            namespace: Optional Kubernetes namespace to scope the topology.
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = await self._request(
            "GET", f"/api/v1/chaos/clusters/{profile_id}/topology", params=params
        )
        return resp.json()

    async def kill_pod(
        self,
        namespace: str,
        name: str,
        grace_period: int | None = None,
    ) -> None:
        """Kill a pod in the given namespace.

        DELETE /api/v1/chaos/pods/:namespace/:name?gracePeriod=...

        Args:
            namespace: The Kubernetes namespace.
            name: The pod name.
            grace_period: Optional grace period in seconds (0 = immediate).
        """
        params: dict[str, Any] | None = None
        if grace_period is not None and grace_period > 0:
            params = {"gracePeriod": str(grace_period)}
        await self._request(
            "DELETE", f"/api/v1/chaos/pods/{namespace}/{name}", params=params
        )

    async def get_pod_detail(self, namespace: str, name: str) -> dict[str, Any]:
        """Get detailed information about a specific pod.

        GET /api/v1/chaos/pods/:namespace/:name
        """
        resp = await self._request("GET", f"/api/v1/chaos/pods/{namespace}/{name}")
        return resp.json()

    async def get_pod_logs(
        self,
        namespace: str,
        name: str,
        container: str | None = None,
        tail_lines: int | None = None,
    ) -> str:
        """Get logs from a specific pod container.

        GET /api/v1/chaos/pods/:namespace/:name/logs?container=...&tailLines=...

        Args:
            namespace: The Kubernetes namespace.
            name: The pod name.
            container: Optional container name within the pod.
            tail_lines: Optional number of lines from the end of the log.

        Returns:
            Pod log output as a string.
        """
        params: dict[str, Any] = {}
        if container is not None:
            params["container"] = container
        if tail_lines is not None:
            params["tailLines"] = tail_lines
        resp = await self._request(
            "GET",
            f"/api/v1/chaos/pods/{namespace}/{name}/logs",
            params=params or None,
        )
        return resp.text

    async def get_deployment_detail(
        self, namespace: str, name: str
    ) -> dict[str, Any]:
        """Get detailed information about a specific deployment.

        GET /api/v1/chaos/deployments/:namespace/:name
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/deployments/{namespace}/{name}"
        )
        return resp.json()

    async def scale_deployment(
        self, namespace: str, name: str, replicas: int
    ) -> dict[str, Any]:
        """Scale a deployment to the specified number of replicas.

        POST /api/v1/chaos/deployments/:namespace/:name/scale

        Args:
            namespace: The Kubernetes namespace.
            name: The deployment name.
            replicas: Desired replica count.
        """
        resp = await self._request(
            "POST",
            f"/api/v1/chaos/deployments/{namespace}/{name}/scale",
            json={"replicas": replicas},
        )
        return resp.json()

    async def restart_deployment(self, namespace: str, name: str) -> None:
        """Perform a rolling restart of a deployment.

        POST /api/v1/chaos/deployments/:namespace/:name/restart
        """
        await self._request(
            "POST", f"/api/v1/chaos/deployments/{namespace}/{name}/restart"
        )

    # ── ConfigMaps ────────────────────────────────────────────────────

    async def list_configmaps(self, namespace: str) -> list[dict[str, Any]]:
        """List all ConfigMaps in the given namespace.

        GET /api/v1/chaos/configmaps/:namespace

        Returns:
            List of ConfigMap objects (unwrapped from envelope).
        """
        resp = await self._request("GET", f"/api/v1/chaos/configmaps/{namespace}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("configmaps") or []
        return []

    async def get_configmap(self, namespace: str, name: str) -> dict[str, Any]:
        """Get details of a specific ConfigMap.

        GET /api/v1/chaos/configmaps/:namespace/:name
        """
        resp = await self._request(
            "GET", f"/api/v1/chaos/configmaps/{namespace}/{name}"
        )
        return resp.json()

    async def update_configmap(
        self, namespace: str, name: str, data: dict[str, str]
    ) -> None:
        """Replace the data section of an existing ConfigMap.

        PUT /api/v1/chaos/configmaps/:namespace/:name

        Args:
            namespace: The Kubernetes namespace.
            name: The ConfigMap name.
            data: Key-value pairs to set in the ConfigMap.
        """
        await self._request(
            "PUT",
            f"/api/v1/chaos/configmaps/{namespace}/{name}",
            json={"data": data},
        )

    # ── Services ──────────────────────────────────────────────────────

    async def list_services(self, namespace: str) -> list[dict[str, Any]]:
        """List all services in the given namespace.

        GET /api/v1/chaos/services/:namespace

        Returns:
            List of Service objects (unwrapped from envelope).
        """
        resp = await self._request("GET", f"/api/v1/chaos/services/{namespace}")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("services") or []
        return []

    # ── CRDs (Custom Resource Definitions) ────────────────────────────

    async def list_crds(self) -> list[dict[str, Any]]:
        """List all Custom Resource Definitions in the cluster.

        GET /api/v1/chaos/crds

        Returns:
            List of CRD objects (unwrapped from envelope).
        """
        resp = await self._request("GET", "/api/v1/chaos/crds")
        data = resp.json()
        if isinstance(data, dict):
            return data.get("crds") or []
        return []

    async def list_crd_resources(
        self,
        group: str,
        version: str,
        resource: str,
        namespace: str | None = None,
    ) -> list[dict[str, Any]]:
        """List instances of a specific custom resource.

        GET /api/v1/chaos/crds/:group/:version/:resource?namespace=...

        Args:
            group: CRD API group.
            version: CRD API version.
            resource: CRD resource name (plural).
            namespace: Optional namespace to scope the query.

        Returns:
            List of custom resource objects (unwrapped from envelope).
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = await self._request(
            "GET",
            f"/api/v1/chaos/crds/{group}/{version}/{resource}",
            params=params,
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("resources") or []
        return []

    # ── Kubernetes Events ─────────────────────────────────────────────

    async def list_k8s_events(
        self, namespace: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """List recent Kubernetes events in the given namespace.

        GET /api/v1/chaos/events/:namespace?limit=...

        Args:
            namespace: The Kubernetes namespace.
            limit: Maximum number of events to return.

        Returns:
            List of event objects (unwrapped from envelope).
        """
        params: dict[str, Any] | None = None
        if limit is not None:
            params = {"limit": limit}
        resp = await self._request(
            "GET", f"/api/v1/chaos/events/{namespace}", params=params
        )
        data = resp.json()
        if isinstance(data, dict):
            return data.get("events") or []
        return []

    # ── Operator ──────────────────────────────────────────────────────

    async def get_operator_status(
        self, namespace: str | None = None
    ) -> dict[str, Any]:
        """Get the chaos operator installation status.

        GET /api/v1/chaos/operator/status?namespace=...

        Args:
            namespace: Optional Kubernetes namespace where the operator is deployed.
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = await self._request(
            "GET", "/api/v1/chaos/operator/status", params=params
        )
        return resp.json()

    async def install_operator(self, namespace: str | None = None) -> dict[str, Any]:
        """Generate the operator manifest for manual application.

        POST /api/v1/chaos/operator/install?namespace=...

        Args:
            namespace: Optional K8s namespace for the operator.
        """
        params: dict[str, Any] | None = None
        if namespace is not None:
            params = {"namespace": namespace}
        resp = await self._request(
            "POST", "/api/v1/chaos/operator/install", params=params
        )
        return resp.json()

    async def generate_operator_manifest(
        self, admin_url: str | None = None, image: str | None = None
    ) -> str:
        """Generate a YAML manifest for installing the chaos operator.

        POST /api/v1/chaos/operator/manifest

        Args:
            admin_url: Optional Mockarty admin node URL to embed in the manifest.
            image: Optional custom operator image.

        Returns:
            YAML manifest as a string.
        """
        body: dict[str, Any] = {}
        if admin_url is not None:
            body["adminUrl"] = admin_url
        if image is not None:
            body["image"] = image
        resp = await self._request(
            "POST", "/api/v1/chaos/operator/manifest", json=body or None
        )
        return resp.text
