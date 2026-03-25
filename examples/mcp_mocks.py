"""MCP (Model Context Protocol) mock examples.

Demonstrates:
  - Tool mock
  - Resource mock
  - MCP error responses
"""

from mockarty import (
    AssertAction,
    ContentResponse,
    MCPRequestContext,
    Mock,
    MockBuilder,
    MockartyClient,
)

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def tool_mock(client: MockartyClient) -> None:
    """Mock an MCP tool: get_weather.

    MCP tools are invoked via ``tools/call`` with a tool name.
    """
    mock = (
        MockBuilder.mcp("get_weather")
        .id("mcp-get-weather")
        .respond(200, body={
            "content": [
                {
                    "type": "text",
                    "text": "Current weather in $.req.city: 22C, sunny skies.",
                }
            ],
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: MCP tool get_weather")


def tool_with_conditions(client: MockartyClient) -> None:
    """MCP tool with argument conditions."""
    mock = (
        MockBuilder.mcp("search_database")
        .id("mcp-search-db")
        .condition("query", AssertAction.NOT_EMPTY)
        .condition("limit", AssertAction.NOT_EMPTY)
        .respond(200, body={
            "content": [
                {
                    "type": "text",
                    "text": "Found 42 results for '$.req.query'",
                },
            ],
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: MCP tool search_database (with conditions)")


def resource_mock(client: MockartyClient) -> None:
    """Mock an MCP resource: config://app/settings.

    Resources use ``resources/read`` as the MCP method.
    """
    mock = Mock(
        id="mcp-app-settings",
        mcp=MCPRequestContext(
            method="resources/read",
            resource="config://app/settings",
            description="Application configuration settings",
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "contents": [
                    {
                        "uri": "config://app/settings",
                        "mimeType": "application/json",
                        "text": '{"theme": "dark", "language": "en", "notifications": true}',
                    }
                ],
            },
        ),
    )
    client.mocks.create(mock)
    print("Created: MCP resource config://app/settings")


def tool_error_response(client: MockartyClient) -> None:
    """Return an MCP error response using the isError flag."""
    mock = Mock(
        id="mcp-tool-error",
        mcp=MCPRequestContext(
            method="tools/call",
            tool="delete_file",
            description="Delete a file from the filesystem",
        ),
        response=ContentResponse(
            status_code=200,
            payload={
                "content": [
                    {
                        "type": "text",
                        "text": "Permission denied: cannot delete system files",
                    }
                ],
            },
            mcp_is_error=True,
        ),
    )
    client.mocks.create(mock)
    print("Created: MCP tool delete_file (error response)")


def tool_with_structured_output(client: MockartyClient) -> None:
    """MCP tool returning structured JSON content."""
    mock = (
        MockBuilder.mcp("analyze_code")
        .id("mcp-analyze-code")
        .respond(200, body={
            "content": [
                {
                    "type": "text",
                    "text": "Analysis complete. Found 3 issues.",
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": "analysis://results/$.fake.UUID",
                        "mimeType": "application/json",
                        "text": '{"issues": 3, "warnings": 7, "score": 85}',
                    },
                },
            ],
        })
        .build()
    )
    client.mocks.create(mock)
    print("Created: MCP tool analyze_code (structured output)")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        tool_mock(client)
        tool_with_conditions(client)
        resource_mock(client)
        tool_error_response(client)
        tool_with_structured_output(client)

        # Clean up
        mock_ids = [
            "mcp-get-weather", "mcp-search-db", "mcp-app-settings",
            "mcp-tool-error", "mcp-analyze-code",
        ]
        for mid in mock_ids:
            try:
                client.mocks.delete(mid)
            except Exception:
                pass
        print("\nAll MCP example mocks cleaned up.")


if __name__ == "__main__":
    main()
