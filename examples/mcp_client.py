# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Example: drive Mockarty's agent-facing MCP tool surface from the SDK.

Connects to the admin node's streamable-HTTP ``/mcp`` endpoint, lists every
tool the server advertises, then calls one and reads its structured result.
The MCP client reuses the SDK client's server URL + API key; feature/licence
gating for the tools is enforced server-side.

Run:
    MOCKARTY_SERVER=http://localhost:5770 MOCKARTY_API_KEY=mk_... python mcp_client.py
"""

from __future__ import annotations

import os

from mockarty import MockartyClient


def main() -> None:
    client = MockartyClient(
        base_url=os.environ.get("MOCKARTY_SERVER", "http://localhost:5770"),
        api_key=os.environ.get("MOCKARTY_API_KEY"),
    )
    mcp = client.mcp

    # 1. Discover the tools the server exposes.
    tools = mcp.list_tools()
    print(f"Server advertises {len(tools)} MCP tools:")
    for t in tools:
        print(f"  - {t.name:<28} {t.description}")

    # 2. Call a read-only tool and read its JSON result.
    result = mcp.call_tool("list_mocks", {})
    if result.is_error:
        raise SystemExit(f"tool returned an error: {result.text}")
    print("\nlist_mocks result:")
    print(result.text)


if __name__ == "__main__":
    main()
