# Copyright (c) 2024-2026 Mockarty. All rights reserved.

"""Generator API resource for creating mocks from specifications."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.generator import (
    GeneratorPreview,
    GeneratorRequest,
    GeneratorResponse,
)
from mockarty.models.mock import Mock


class GeneratorAPI(SyncAPIBase):
    """Synchronous Generator API resource."""

    def generate_openapi(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from an OpenAPI/Swagger specification."""
        resp = self._request("POST", "/api/v1/generators/openapi", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def preview_openapi(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks that would be generated from an OpenAPI spec."""
        resp = self._request("POST", "/api/v1/generators/openapi/preview", json=request)
        data = resp.json()
        if isinstance(data, dict):
            mocks_raw = data.get("mocks") or []
            mocks = [Mock.model_validate(m) for m in mocks_raw]
            return GeneratorPreview(mocks=mocks, count=data.get("count", len(mocks)))
        return GeneratorPreview()

    def generate_graphql(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a GraphQL schema or introspection URL."""
        resp = self._request("POST", "/api/v1/generators/graphql", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def generate_grpc(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a proto file specification."""
        resp = self._request("POST", "/api/v1/generators/grpc", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def generate_soap(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a WSDL specification."""
        resp = self._request("POST", "/api/v1/generators/soap", json=request)
        return GeneratorResponse.model_validate(resp.json())


class AsyncGeneratorAPI(AsyncAPIBase):
    """Asynchronous Generator API resource."""

    async def generate_openapi(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from an OpenAPI/Swagger specification."""
        resp = await self._request("POST", "/api/v1/generators/openapi", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def preview_openapi(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks that would be generated from an OpenAPI spec."""
        resp = await self._request(
            "POST", "/api/v1/generators/openapi/preview", json=request
        )
        data = resp.json()
        if isinstance(data, dict):
            mocks_raw = data.get("mocks") or []
            mocks = [Mock.model_validate(m) for m in mocks_raw]
            return GeneratorPreview(mocks=mocks, count=data.get("count", len(mocks)))
        return GeneratorPreview()

    async def generate_graphql(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a GraphQL schema or introspection URL."""
        resp = await self._request("POST", "/api/v1/generators/graphql", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def generate_grpc(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a proto file specification."""
        resp = await self._request("POST", "/api/v1/generators/grpc", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def generate_soap(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a WSDL specification."""
        resp = await self._request("POST", "/api/v1/generators/soap", json=request)
        return GeneratorResponse.model_validate(resp.json())
