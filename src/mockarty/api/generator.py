# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

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

    def from_openapi(
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

    def from_graphql(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a GraphQL schema or introspection URL."""
        resp = self._request("POST", "/api/v1/generators/graphql", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def from_proto(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a proto file specification."""
        resp = self._request("POST", "/api/v1/generators/grpc", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def from_wsdl(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a WSDL specification."""
        resp = self._request("POST", "/api/v1/generators/soap", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def from_har(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from an HTTP Archive (HAR) file."""
        resp = self._request("POST", "/api/v1/generators/har", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def from_mcp(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from an MCP (Model Context Protocol) specification."""
        resp = self._request("POST", "/api/v1/generators/mcp", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def from_socket(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks for WebSocket/TCP/UDP from a specification."""
        resp = self._request("POST", "/api/v1/generators/socket", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def _parse_preview(self, data: dict[str, Any]) -> GeneratorPreview:
        if isinstance(data, dict):
            mocks_raw = data.get("mocks") or []
            mocks = [Mock.model_validate(m) for m in mocks_raw]
            return GeneratorPreview(mocks=mocks, count=data.get("count", len(mocks)))
        return GeneratorPreview()

    def preview_graphql(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from a GraphQL schema."""
        resp = self._request("POST", "/api/v1/generators/graphql/preview", json=request)
        return self._parse_preview(resp.json())

    def preview_proto(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from a proto specification."""
        resp = self._request("POST", "/api/v1/generators/grpc/preview", json=request)
        return self._parse_preview(resp.json())

    def preview_wsdl(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from a WSDL specification."""
        resp = self._request("POST", "/api/v1/generators/soap/preview", json=request)
        return self._parse_preview(resp.json())

    def preview_har(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from an HAR file."""
        resp = self._request("POST", "/api/v1/generators/har/preview", json=request)
        return self._parse_preview(resp.json())

    def preview_mcp(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from an MCP specification."""
        resp = self._request("POST", "/api/v1/generators/mcp/preview", json=request)
        return self._parse_preview(resp.json())

    def load_graphql_schema_from_url(self, graphql_url: str) -> dict[str, Any]:
        """Introspect a live GraphQL endpoint's schema via its URL.

        Parity with Go LoadGraphQLSchemaFromURL / Java loadGraphQLSchemaFromURL.
        """
        resp = self._request(
            "POST", "/api/v1/generators/graphql/schema", json={"graphqlUrl": graphql_url}
        )
        return resp.json()


class AsyncGeneratorAPI(AsyncAPIBase):
    """Asynchronous Generator API resource."""

    async def from_openapi(
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

    async def from_graphql(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a GraphQL schema or introspection URL."""
        resp = await self._request("POST", "/api/v1/generators/graphql", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def from_proto(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a proto file specification."""
        resp = await self._request("POST", "/api/v1/generators/grpc", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def from_wsdl(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from a WSDL specification."""
        resp = await self._request("POST", "/api/v1/generators/soap", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def from_har(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from an HTTP Archive (HAR) file."""
        resp = await self._request("POST", "/api/v1/generators/har", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def from_mcp(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks from an MCP specification."""
        resp = await self._request("POST", "/api/v1/generators/mcp", json=request)
        return GeneratorResponse.model_validate(resp.json())

    async def from_socket(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorResponse:
        """Generate mocks for WebSocket/TCP/UDP."""
        resp = await self._request("POST", "/api/v1/generators/socket", json=request)
        return GeneratorResponse.model_validate(resp.json())

    def _parse_preview(self, data: dict[str, Any]) -> GeneratorPreview:
        if isinstance(data, dict):
            mocks_raw = data.get("mocks") or []
            mocks = [Mock.model_validate(m) for m in mocks_raw]
            return GeneratorPreview(mocks=mocks, count=data.get("count", len(mocks)))
        return GeneratorPreview()

    async def preview_graphql(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from a GraphQL schema."""
        resp = await self._request(
            "POST", "/api/v1/generators/graphql/preview", json=request
        )
        return self._parse_preview(resp.json())

    async def preview_proto(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from a proto specification."""
        resp = await self._request(
            "POST", "/api/v1/generators/grpc/preview", json=request
        )
        return self._parse_preview(resp.json())

    async def preview_wsdl(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from a WSDL specification."""
        resp = await self._request(
            "POST", "/api/v1/generators/soap/preview", json=request
        )
        return self._parse_preview(resp.json())

    async def preview_har(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from an HAR file."""
        resp = await self._request(
            "POST", "/api/v1/generators/har/preview", json=request
        )
        return self._parse_preview(resp.json())

    async def preview_mcp(
        self, request: GeneratorRequest | dict[str, Any]
    ) -> GeneratorPreview:
        """Preview mocks from an MCP specification."""
        resp = await self._request(
            "POST", "/api/v1/generators/mcp/preview", json=request
        )
        return self._parse_preview(resp.json())

    async def load_graphql_schema_from_url(self, graphql_url: str) -> dict[str, Any]:
        """Introspect a live GraphQL endpoint's schema via its URL. Parity: Go/Java."""
        resp = await self._request(
            "POST", "/api/v1/generators/graphql/schema", json={"graphqlUrl": graphql_url}
        )
        return resp.json()
