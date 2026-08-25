from __future__ import annotations

import httpx
import respx

from mockarty import MockartyClient


@respx.mock
def test_list_capabilities_returns_canonical_descriptor(client: MockartyClient) -> None:
    route = respx.get("http://localhost:5770/api/v1/capabilities", params={"namespace": "test-ns"}).mock(
        return_value=httpx.Response(
            200,
            json={
                "capabilities": [{
                    "contractVersion": "mockarty.capability/v1",
                    "key": "mission.coder",
                    "version": "1.0.0",
                    "provider": "mockarty.missions",
                    "kind": "mission-component",
                    "title": "Coder",
                    "description": "Codes.",
                    "hosts": ["admin"],
                    "policy": {"sideEffect": "external_write"},
                    "provenance": {"sourceKind": "builtin", "sourceRef": "mockarty:coder", "publisher": "mockarty"},
                    "availability": {"available": True},
                }],
                "count": 1,
                "skipped": 0,
            },
        )
    )

    catalog = client.stats.list_capabilities()
    assert route.called
    assert catalog["count"] == 1
    assert catalog["capabilities"][0]["contractVersion"] == "mockarty.capability/v1"
