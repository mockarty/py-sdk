# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Admitted coder repositories, delivery targets, and deploy missions."""

from __future__ import annotations

from urllib.parse import quote
import httpx
import mimetypes

from mockarty.api._base import AsyncAPIBase, SyncAPIBase


def _mission_path(mission_id: str) -> str:
    mission_id = (mission_id or "").strip()
    if not mission_id:
        raise ValueError("mission_id is required")
    return "/api/v1/coder/missions/" + quote(mission_id, safe="")


def _mission_material_body(product_id: str, filename: str, content: bytes, media_type: str) -> tuple[bytes, str]:
    if not product_id.strip() or not filename.strip() or not content or len(content) > 16 * 1024 * 1024:
        raise ValueError("product, filename and a nonempty material up to 16 MiB are required")
    if not media_type or media_type == "application/octet-stream":
        extension = filename.rsplit(".", 1)[-1].lower()
        media_type = {"md": "text/markdown", "yaml": "application/yaml", "yml": "application/yaml", "js": "text/javascript"}.get(extension) or mimetypes.guess_type(filename)[0]
        if not media_type:
            raise ValueError("unknown material type; specify media_type")
    if "\r" in media_type or "\n" in media_type:
        raise ValueError("invalid media type")
    media_base = media_type.split(";", 1)[0].strip().lower()
    if not media_base.startswith("image/") and media_base != "application/pdf" and len(content) > 64 * 1024:
        raise ValueError("text mission materials must be at most 64 KiB combined")
    request = httpx.Request("POST", "http://127.0.0.1", files={"file": (filename, content, media_type)})
    return request.read(), request.headers["Content-Type"]


def _deploy_reconciliation(outcome: str) -> dict[str, str]:
    outcome = (outcome or "").strip()
    if outcome not in {"applied", "not_applied"}:
        raise ValueError("outcome must be applied or not_applied")
    return {"outcome": outcome}


class CoderDeliveryAPI(SyncAPIBase):
    def upload_mission_material(self, product_id: str, filename: str, content: bytes, media_type: str = "application/octet-stream") -> dict:
        """Upload an original; pass the returned reference in mission artifacts."""
        body, content_type = _mission_material_body(product_id, filename, content, media_type)
        return self._request("POST", "/api/v1/missions/materials", params={"namespace": self._namespace, "productId": product_id}, content=body, headers={"Content-Type": content_type}).json()

    def observability_sources(self) -> dict:
        """List deployed-system observation sources bound to this namespace."""
        return self._request("GET", "/api/v1/observability/sources", params={"namespace": self._namespace}).json()

    def query_observability(self, query: dict) -> dict:
        if not str(query.get("source", "")).strip() or not str(query.get("expression", "")).strip():
            raise ValueError("source and expression are required")
        return self._request("POST", "/api/v1/observability/query", params={"namespace": self._namespace}, json=query).json()

    def get_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return self._request("GET", "/api/v1/coder/delivery-config", params=params).json()

    def put_config(self, config: dict) -> dict:
        return self._request("PUT", "/api/v1/coder/delivery-config", params={"namespace": self._namespace}, json=config).json()

    def delete_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return self._request("DELETE", "/api/v1/coder/delivery-config", params=params).json()

    def start_mission(self, request: dict) -> dict:
        if not str(request.get("goal", "")).strip() or not str(request.get("repoUrl", "")).strip():
            raise ValueError("goal and repoUrl are required")
        return self._request("POST", "/api/v1/coder/missions", params={"namespace": self._namespace}, json=request).json()

    def list_missions(self) -> list[dict]:
        body = self._request("GET", "/api/v1/coder/missions", params={"namespace": self._namespace}).json()
        return body.get("missions") or []

    def get_mission(self, mission_id: str) -> dict:
        return self._request("GET", _mission_path(mission_id), params={"namespace": self._namespace}).json()

    def approve_mission(self, mission_id: str, approve: bool) -> dict:
        return self._request("POST", _mission_path(mission_id) + "/approve", params={"namespace": self._namespace}, json={"approve": approve}).json()

    def add_to_mission(self, mission_id: str, request: dict) -> dict:
        if not request.get("tasks") and not request.get("prompts"):
            raise ValueError("at least one task or prompt is required")
        return self._request("POST", _mission_path(mission_id) + "/add", params={"namespace": self._namespace}, json=request).json()

    def reconcile_deploy(self, mission_id: str, outcome: str) -> dict:
        return self._request("POST", _mission_path(mission_id) + "/deploy-outcome", params={"namespace": self._namespace}, json=_deploy_reconciliation(outcome)).json()


class AsyncCoderDeliveryAPI(AsyncAPIBase):
    async def upload_mission_material(self, product_id: str, filename: str, content: bytes, media_type: str = "application/octet-stream") -> dict:
        """Upload an original; pass the returned reference in mission artifacts."""
        body, content_type = _mission_material_body(product_id, filename, content, media_type)
        return (await self._request("POST", "/api/v1/missions/materials", params={"namespace": self._namespace, "productId": product_id}, content=body, headers={"Content-Type": content_type})).json()

    async def observability_sources(self) -> dict:
        """List deployed-system observation sources bound to this namespace."""
        return (await self._request("GET", "/api/v1/observability/sources", params={"namespace": self._namespace})).json()

    async def query_observability(self, query: dict) -> dict:
        if not str(query.get("source", "")).strip() or not str(query.get("expression", "")).strip():
            raise ValueError("source and expression are required")
        return (await self._request("POST", "/api/v1/observability/query", params={"namespace": self._namespace}, json=query)).json()

    async def get_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return (await self._request("GET", "/api/v1/coder/delivery-config", params=params)).json()

    async def put_config(self, config: dict) -> dict:
        return (await self._request("PUT", "/api/v1/coder/delivery-config", params={"namespace": self._namespace}, json=config)).json()

    async def delete_config(self, *, product_id: str = "") -> dict:
        params = {"namespace": self._namespace}
        if product_id := product_id.strip():
            params["productId"] = product_id
        return (await self._request("DELETE", "/api/v1/coder/delivery-config", params=params)).json()

    async def start_mission(self, request: dict) -> dict:
        if not str(request.get("goal", "")).strip() or not str(request.get("repoUrl", "")).strip():
            raise ValueError("goal and repoUrl are required")
        return (await self._request("POST", "/api/v1/coder/missions", params={"namespace": self._namespace}, json=request)).json()

    async def list_missions(self) -> list[dict]:
        body = (await self._request("GET", "/api/v1/coder/missions", params={"namespace": self._namespace})).json()
        return body.get("missions") or []

    async def get_mission(self, mission_id: str) -> dict:
        return (await self._request("GET", _mission_path(mission_id), params={"namespace": self._namespace})).json()

    async def approve_mission(self, mission_id: str, approve: bool) -> dict:
        return (await self._request("POST", _mission_path(mission_id) + "/approve", params={"namespace": self._namespace}, json={"approve": approve})).json()

    async def add_to_mission(self, mission_id: str, request: dict) -> dict:
        if not request.get("tasks") and not request.get("prompts"):
            raise ValueError("at least one task or prompt is required")
        return (await self._request("POST", _mission_path(mission_id) + "/add", params={"namespace": self._namespace}, json=request)).json()

    async def reconcile_deploy(self, mission_id: str, outcome: str) -> dict:
        return (await self._request("POST", _mission_path(mission_id) + "/deploy-outcome", params={"namespace": self._namespace}, json=_deploy_reconciliation(outcome))).json()
