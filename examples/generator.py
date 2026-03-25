"""Mock generation from API specifications.

Demonstrates:
  - Generate mocks from OpenAPI/Swagger spec
  - Preview before generating
  - Generate from GraphQL schema
  - Generate from gRPC proto
  - Generate from WSDL (SOAP)
"""

from mockarty import GeneratorRequest, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def generate_from_openapi_url(client: MockartyClient) -> None:
    """Generate mocks from a remote OpenAPI spec URL."""
    request = GeneratorRequest(
        url="https://petstore3.swagger.io/api/v3/openapi.json",
        namespace="sandbox",
        path_prefix="/petstore",
    )
    result = client.generator.generate_openapi(request)
    print(f"OpenAPI generation: created {result.created} mocks")
    if result.message:
        print(f"  Message: {result.message}")
    for mock in result.mocks[:5]:
        if mock.http:
            print(f"  - {mock.id}: {mock.http.http_method} {mock.http.route}")


def generate_from_openapi_spec(client: MockartyClient) -> None:
    """Generate mocks from an inline OpenAPI spec string."""
    spec = """{
  "openapi": "3.0.0",
  "info": { "title": "Payments API", "version": "1.0.0" },
  "paths": {
    "/api/payments": {
      "post": {
        "summary": "Create payment",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "amount": { "type": "number" },
                  "currency": { "type": "string" },
                  "description": { "type": "string" }
                }
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "Payment created",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": { "type": "string" },
                    "status": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/payments/{id}": {
      "get": {
        "summary": "Get payment",
        "parameters": [
          { "name": "id", "in": "path", "required": true, "schema": { "type": "string" } }
        ],
        "responses": {
          "200": {
            "description": "Payment found"
          }
        }
      }
    }
  }
}"""

    request = GeneratorRequest(
        spec=spec,
        namespace="sandbox",
    )
    result = client.generator.generate_openapi(request)
    print(f"Inline OpenAPI: created {result.created} mocks")
    for mock in result.mocks:
        if mock.http:
            print(f"  - {mock.id}: {mock.http.http_method} {mock.http.route}")


def preview_openapi(client: MockartyClient) -> None:
    """Preview mocks that would be generated, without actually creating them.

    Useful for reviewing what will be created before committing.
    """
    request = GeneratorRequest(
        url="https://petstore3.swagger.io/api/v3/openapi.json",
        namespace="sandbox",
    )
    preview = client.generator.preview_openapi(request)
    print(f"Preview: {preview.count} mocks would be created")
    for mock in preview.mocks[:5]:
        if mock.http:
            print(f"  - {mock.http.http_method} {mock.http.route}")


def generate_from_graphql(client: MockartyClient) -> None:
    """Generate mocks from a GraphQL schema or introspection endpoint."""
    request = GeneratorRequest(
        graphql_url="https://countries.trevorblades.com/graphql",
        namespace="sandbox",
    )
    result = client.generator.generate_graphql(request)
    print(f"GraphQL generation: created {result.created} mocks")
    for mock in result.mocks[:5]:
        if mock.graphql:
            print(f"  - {mock.id}: {mock.graphql.operation} {mock.graphql.field}")


def generate_from_grpc(client: MockartyClient) -> None:
    """Generate mocks from a .proto file specification."""
    proto_spec = """
syntax = "proto3";

option go_package = "/example/greeter";

service Greeter {
  rpc SayHello (HelloRequest) returns (HelloReply);
  rpc SayGoodbye (GoodbyeRequest) returns (GoodbyeReply);
}

message HelloRequest {
  string name = 1;
}

message HelloReply {
  string message = 1;
}

message GoodbyeRequest {
  string name = 1;
}

message GoodbyeReply {
  string message = 1;
}
"""
    request = GeneratorRequest(
        spec=proto_spec,
        namespace="sandbox",
    )
    result = client.generator.generate_grpc(request)
    print(f"gRPC generation: created {result.created} mocks")
    for mock in result.mocks:
        if mock.grpc:
            print(f"  - {mock.id}: {mock.grpc.service}/{mock.grpc.method}")


def generate_from_soap(client: MockartyClient) -> None:
    """Generate mocks from a WSDL specification."""
    request = GeneratorRequest(
        url="http://www.dneonline.com/calculator.asmx?WSDL",
        namespace="sandbox",
    )
    result = client.generator.generate_soap(request)
    print(f"SOAP generation: created {result.created} mocks")
    for mock in result.mocks:
        if mock.soap:
            print(f"  - {mock.id}: {mock.soap.service}/{mock.soap.method}")


def generate_with_server_name(client: MockartyClient) -> None:
    """Generate mocks grouped under a specific server name.

    Server names help organize mocks by environment or service.
    """
    request = GeneratorRequest(
        url="https://petstore3.swagger.io/api/v3/openapi.json",
        namespace="sandbox",
        server_name="petstore-staging",
        path_prefix="/staging",
    )
    result = client.generator.generate_openapi(request)
    print(f"Generated {result.created} mocks under server 'petstore-staging'")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        # Preview first (non-destructive)
        preview_openapi(client)
        print()

        # Generate from inline spec
        generate_from_openapi_spec(client)
        print()

        # Uncomment to generate from remote sources:
        # generate_from_openapi_url(client)
        # generate_from_graphql(client)
        # generate_from_grpc(client)
        # generate_from_soap(client)
        # generate_with_server_name(client)

        print("Generator example complete.")


if __name__ == "__main__":
    main()
