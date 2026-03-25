"""GraphQL mock examples.

Demonstrates:
  - Query mock with operation name and field
  - Mutation mock
  - GraphQL error responses
"""

from mockarty import (
    AssertAction,
    ContentResponse,
    GraphQLRequestContext,
    Mock,
    MockBuilder,
    MockartyClient,
)
from mockarty.models.mock import GraphQLError, GraphQLErrorLocation

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def query_mock(client: MockartyClient) -> None:
    """GraphQL query: getUser operation."""
    mock = (
        MockBuilder.graphql("query", field="getUser")
        .id("graphql-get-user")
        .respond(200, body={
            "data": {
                "getUser": {
                    "id": "$.fake.UUID",
                    "name": "$.fake.FirstName",
                    "email": "$.fake.Email",
                    "createdAt": "$.fake.DateISO",
                }
            }
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GraphQL query getUser")


def query_with_conditions(client: MockartyClient) -> None:
    """GraphQL query with variable conditions."""
    mock = (
        MockBuilder.graphql("query", field="listProducts")
        .id("graphql-list-products")
        .condition("category", AssertAction.EQUALS, "electronics")
        .respond(200, body={
            "data": {
                "listProducts": {
                    "edges": [
                        {
                            "node": {
                                "id": "$.fake.UUID",
                                "name": "$.fake.Word",
                                "price": 99.99,
                                "category": "electronics",
                            }
                        },
                    ],
                    "pageInfo": {
                        "hasNextPage": True,
                        "endCursor": "$.fake.UUID",
                    },
                }
            }
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GraphQL query listProducts (with condition)")


def mutation_mock(client: MockartyClient) -> None:
    """GraphQL mutation: createPost."""
    mock = (
        MockBuilder.graphql("mutation", field="createPost")
        .id("graphql-create-post")
        .respond(200, body={
            "data": {
                "createPost": {
                    "id": "$.fake.UUID",
                    "title": "$.req.title",
                    "content": "$.req.content",
                    "author": {
                        "id": "$.fake.UUID",
                        "name": "$.fake.FirstName",
                    },
                    "publishedAt": "$.fake.DateISO",
                }
            }
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: GraphQL mutation createPost")


def graphql_error_response(client: MockartyClient) -> None:
    """Return a GraphQL-spec-compliant error response.

    Uses the ContentResponse model directly for the graphql_errors field.
    """
    mock = Mock(
        id="graphql-delete-forbidden",
        graphql=GraphQLRequestContext(
            operation="mutation",
            field="deleteUser",
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "data": None,
            },
            graphql_errors=[
                GraphQLError(
                    message="You do not have permission to delete users",
                    path=["deleteUser"],
                    locations=[GraphQLErrorLocation(line=1, column=1)],
                    extensions={"code": "FORBIDDEN", "statusCode": 403},
                ),
            ],
        ),
    )
    client.mocks.create(mock)
    print("Created: GraphQL mutation deleteUser (error response)")


def graphql_partial_error(client: MockartyClient) -> None:
    """Return partial data with errors (common GraphQL pattern)."""
    mock = Mock(
        id="graphql-partial-error",
        graphql=GraphQLRequestContext(
            operation="query",
            field="dashboard",
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "data": {
                    "dashboard": {
                        "stats": {"users": 1234, "revenue": 56789},
                        "notifications": None,
                    }
                },
            },
            graphql_errors=[
                GraphQLError(
                    message="Failed to load notifications service",
                    path=["dashboard", "notifications"],
                    extensions={"code": "SERVICE_UNAVAILABLE"},
                ),
            ],
        ),
    )
    client.mocks.create(mock)
    print("Created: GraphQL query dashboard (partial error)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        query_mock(client)
        query_with_conditions(client)
        mutation_mock(client)
        graphql_error_response(client)
        graphql_partial_error(client)

        # Clean up
        mock_ids = [
            "graphql-get-user", "graphql-list-products",
            "graphql-create-post", "graphql-delete-forbidden",
            "graphql-partial-error",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll GraphQL example mocks cleaned up.")


if __name__ == "__main__":
    main()
