# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Import API resource for importing collections from external tools."""

from __future__ import annotations

from typing import Any

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.imports import ImportResult


class ImportAPI(SyncAPIBase):
    """Synchronous Import API resource."""

    def postman(self, collection: dict[str, Any]) -> ImportResult:
        """Import a Postman collection."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/postman", json=collection
        )
        return ImportResult.model_validate(resp.json())

    def postman_with_options(
        self, collection: dict[str, Any], options: dict[str, Any] | None = None
    ) -> ImportResult:
        """Import a Postman collection with tuning options for CI/CD.

        Options keys: collectionName, mode ('performance'), seedMocks,
        seedMocksNamespace, seedMocksMatchHeaders, seedMocksPriority.
        Parity with Go PostmanWithOptions / Java postmanWithOptions.
        """
        body: dict[str, Any] = {"collectionJson": collection}
        if options:
            body.update(options)
        resp = self._request("POST", "/api/v1/api-tester/import/postman", json=body)
        return ImportResult.model_validate(resp.json())

    def insomnia(self, collection: dict[str, Any]) -> ImportResult:
        """Import an Insomnia collection."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/insomnia", json=collection
        )
        return ImportResult.model_validate(resp.json())

    def har(self, data: dict[str, Any]) -> ImportResult:
        """Import a HAR (HTTP Archive) file."""
        resp = self._request("POST", "/api/v1/api-tester/import/har", json=data)
        return ImportResult.model_validate(resp.json())

    def curl(self, commands: list[str]) -> ImportResult:
        """Import from cURL commands."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/curl", json={"commands": commands}
        )
        return ImportResult.model_validate(resp.json())

    def openapi(self, spec: str) -> ImportResult:
        """Import an OpenAPI/Swagger spec (raw YAML/JSON). Parity: Go OpenAPI / Java openAPI."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/openapi", json={"content": spec}
        )
        return ImportResult.model_validate(resp.json())

    def wsdl(self, spec: str) -> ImportResult:
        """Import a WSDL (SOAP) spec (raw XML). Parity: Go WSDL / Java wsdl."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/wsdl", json={"content": spec}
        )
        return ImportResult.model_validate(resp.json())

    def grpc_proto(self, spec: str) -> ImportResult:
        """Import a gRPC .proto definition (raw text). Parity: Go GrpcProto / Java grpcProto."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/grpc", json={"content": spec}
        )
        return ImportResult.model_validate(resp.json())

    def graphql(self, spec: str) -> ImportResult:
        """Import a GraphQL SDL schema (raw text). Parity: Go GraphQL / Java graphQL."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/graphql", json={"content": spec}
        )
        return ImportResult.model_validate(resp.json())

    def mcp(self, spec: str) -> ImportResult:
        """Import an MCP tool manifest (raw JSON). Parity: Go MCP / Java mcp."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/mcp", json={"content": spec}
        )
        return ImportResult.model_validate(resp.json())

    def mockarty(self, spec: str) -> ImportResult:
        """Import a Mockarty-native export (raw JSON). Parity: Go Mockarty / Java mockarty."""
        resp = self._request(
            "POST", "/api/v1/api-tester/import/mockarty", json={"content": spec}
        )
        return ImportResult.model_validate(resp.json())


class AsyncImportAPI(AsyncAPIBase):
    """Asynchronous Import API resource."""

    async def postman_with_options(
        self, collection: dict[str, Any], options: dict[str, Any] | None = None
    ) -> ImportResult:
        """Import a Postman collection with tuning options. Parity: Go/Java."""
        body: dict[str, Any] = {"collectionJson": collection}
        if options:
            body.update(options)
        resp = await self._request("POST", "/api/v1/api-tester/import/postman", json=body)
        return ImportResult.model_validate(resp.json())

    async def postman(self, collection: dict[str, Any]) -> ImportResult:
        """Import a Postman collection."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/import/postman", json=collection
        )
        return ImportResult.model_validate(resp.json())

    async def insomnia(self, collection: dict[str, Any]) -> ImportResult:
        """Import an Insomnia collection."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/import/insomnia", json=collection
        )
        return ImportResult.model_validate(resp.json())

    async def har(self, data: dict[str, Any]) -> ImportResult:
        """Import a HAR (HTTP Archive) file."""
        resp = await self._request("POST", "/api/v1/api-tester/import/har", json=data)
        return ImportResult.model_validate(resp.json())

    async def curl(self, commands: list[str]) -> ImportResult:
        """Import from cURL commands."""
        resp = await self._request(
            "POST", "/api/v1/api-tester/import/curl", json={"commands": commands}
        )
        return ImportResult.model_validate(resp.json())

    async def openapi(self, spec: str) -> ImportResult:
        """Import an OpenAPI/Swagger spec. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/import/openapi", json={"content": spec})
        return ImportResult.model_validate(resp.json())

    async def wsdl(self, spec: str) -> ImportResult:
        """Import a WSDL spec. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/import/wsdl", json={"content": spec})
        return ImportResult.model_validate(resp.json())

    async def grpc_proto(self, spec: str) -> ImportResult:
        """Import a gRPC .proto. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/import/grpc", json={"content": spec})
        return ImportResult.model_validate(resp.json())

    async def graphql(self, spec: str) -> ImportResult:
        """Import a GraphQL SDL. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/import/graphql", json={"content": spec})
        return ImportResult.model_validate(resp.json())

    async def mcp(self, spec: str) -> ImportResult:
        """Import an MCP manifest. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/import/mcp", json={"content": spec})
        return ImportResult.model_validate(resp.json())

    async def mockarty(self, spec: str) -> ImportResult:
        """Import a Mockarty-native export. Parity: Go/Java."""
        resp = await self._request("POST", "/api/v1/api-tester/import/mockarty", json={"content": spec})
        return ImportResult.model_validate(resp.json())
