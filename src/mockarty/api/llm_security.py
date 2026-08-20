"""Layered prompt-security management API."""

from __future__ import annotations

from urllib.parse import quote

from pydantic import BaseModel

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.llm_security import (
    LLMSecurityEventsResponse,
    LLMSecurityPolicyRequest,
    LLMSecurityPolicyResponse,
    LLMSecuritySandboxRequest,
    LLMSecuritySandboxResponse,
)

_ADMIN_PATH = "/api/v1/admin/llm-security/policy"


def _namespace_path(default_namespace: str, namespace: str) -> str:
    resolved = namespace.strip() or default_namespace
    return f"/api/v1/namespaces/{quote(resolved, safe='')}/llm-security"


def _json(model: BaseModel) -> dict[str, object]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


class LLMSecurityAPI(SyncAPIBase):
    def list_namespace_events(
        self, namespace: str = "", limit: int = 100
    ) -> LLMSecurityEventsResponse:
        _validate_limit(limit)
        response = self._request(
            "GET",
            f"{_namespace_path(self._namespace, namespace)}/events",
            params={"limit": limit},
        )
        return LLMSecurityEventsResponse.model_validate(response.json())

    def get_namespace_policy(self, namespace: str = "") -> LLMSecurityPolicyResponse:
        response = self._request(
            "GET", f"{_namespace_path(self._namespace, namespace)}/policy"
        )
        return LLMSecurityPolicyResponse.model_validate(response.json())

    def save_namespace_policy(
        self, request: LLMSecurityPolicyRequest, namespace: str = ""
    ) -> LLMSecurityPolicyResponse:
        response = self._request(
            "PUT",
            f"{_namespace_path(self._namespace, namespace)}/policy",
            json=_json(request),
        )
        return LLMSecurityPolicyResponse.model_validate(response.json())

    def preview_namespace_policy(
        self, request: LLMSecurityPolicyRequest, namespace: str = ""
    ) -> LLMSecurityPolicyResponse:
        response = self._request(
            "POST",
            f"{_namespace_path(self._namespace, namespace)}/preview",
            json=_json(request),
        )
        return LLMSecurityPolicyResponse.model_validate(response.json())

    def test_namespace_text(
        self, request: LLMSecuritySandboxRequest, namespace: str = ""
    ) -> LLMSecuritySandboxResponse:
        response = self._request(
            "POST",
            f"{_namespace_path(self._namespace, namespace)}/sandbox",
            json=_json(request),
        )
        return LLMSecuritySandboxResponse.model_validate(response.json())

    def get_installation_policy(self) -> LLMSecurityPolicyResponse:
        return LLMSecurityPolicyResponse.model_validate(
            self._request("GET", _ADMIN_PATH).json()
        )

    def save_installation_policy(
        self, request: LLMSecurityPolicyRequest
    ) -> LLMSecurityPolicyResponse:
        return LLMSecurityPolicyResponse.model_validate(
            self._request("PUT", _ADMIN_PATH, json=_json(request)).json()
        )

    def list_installation_events(self, limit: int = 100) -> LLMSecurityEventsResponse:
        _validate_limit(limit)
        return LLMSecurityEventsResponse.model_validate(
            self._request(
                "GET", "/api/v1/admin/llm-security/events", params={"limit": limit}
            ).json()
        )


class AsyncLLMSecurityAPI(AsyncAPIBase):
    async def list_namespace_events(
        self, namespace: str = "", limit: int = 100
    ) -> LLMSecurityEventsResponse:
        _validate_limit(limit)
        response = await self._request(
            "GET",
            f"{_namespace_path(self._namespace, namespace)}/events",
            params={"limit": limit},
        )
        return LLMSecurityEventsResponse.model_validate(response.json())

    async def get_namespace_policy(
        self, namespace: str = ""
    ) -> LLMSecurityPolicyResponse:
        response = await self._request(
            "GET", f"{_namespace_path(self._namespace, namespace)}/policy"
        )
        return LLMSecurityPolicyResponse.model_validate(response.json())

    async def save_namespace_policy(
        self, request: LLMSecurityPolicyRequest, namespace: str = ""
    ) -> LLMSecurityPolicyResponse:
        response = await self._request(
            "PUT",
            f"{_namespace_path(self._namespace, namespace)}/policy",
            json=_json(request),
        )
        return LLMSecurityPolicyResponse.model_validate(response.json())

    async def preview_namespace_policy(
        self, request: LLMSecurityPolicyRequest, namespace: str = ""
    ) -> LLMSecurityPolicyResponse:
        response = await self._request(
            "POST",
            f"{_namespace_path(self._namespace, namespace)}/preview",
            json=_json(request),
        )
        return LLMSecurityPolicyResponse.model_validate(response.json())

    async def test_namespace_text(
        self, request: LLMSecuritySandboxRequest, namespace: str = ""
    ) -> LLMSecuritySandboxResponse:
        response = await self._request(
            "POST",
            f"{_namespace_path(self._namespace, namespace)}/sandbox",
            json=_json(request),
        )
        return LLMSecuritySandboxResponse.model_validate(response.json())

    async def get_installation_policy(self) -> LLMSecurityPolicyResponse:
        return LLMSecurityPolicyResponse.model_validate(
            (await self._request("GET", _ADMIN_PATH)).json()
        )

    async def save_installation_policy(
        self, request: LLMSecurityPolicyRequest
    ) -> LLMSecurityPolicyResponse:
        return LLMSecurityPolicyResponse.model_validate(
            (await self._request("PUT", _ADMIN_PATH, json=_json(request))).json()
        )

    async def list_installation_events(
        self, limit: int = 100
    ) -> LLMSecurityEventsResponse:
        _validate_limit(limit)
        return LLMSecurityEventsResponse.model_validate(
            (
                await self._request(
                    "GET", "/api/v1/admin/llm-security/events", params={"limit": limit}
                )
            ).json()
        )


def _validate_limit(limit: int) -> None:
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
