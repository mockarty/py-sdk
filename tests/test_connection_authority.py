import asyncio
from unittest.mock import AsyncMock, Mock

import httpx

from mockarty.api.connection_authority import AsyncConnectionAuthorityAPI, ConnectionAuthorityAPI


def _response(payload=None, status=200):
    return httpx.Response(status, json=payload or {}, request=httpx.Request("GET", "http://test"))


def test_connection_authority_lifecycle_normalizes_server_owned_identity():
    http = Mock()
    http.request.side_effect = [_response({"frozen": True}), _response({"frozen": True}), _response({"frozen": True}), _response(status=204)]
    api = ConnectionAuthorityAPI(http, "team-a")
    descriptor = {"namespace": "team-a", "id": "gitlab-prod", "revision": 9, "kind": "gitlab"}

    api.create(descriptor)
    api.advance("gitlab-prod", descriptor, 1)
    api.get_current("gitlab-prod")
    api.revoke("gitlab-prod", 2)

    create = http.request.call_args_list[0]
    assert create.args[:2] == ("POST", "/api/v1/namespaces/team-a/connections")
    assert create.kwargs["json"] == {"id": "gitlab-prod", "kind": "gitlab"}
    advance = http.request.call_args_list[1]
    assert advance.args[:2] == ("PUT", "/api/v1/namespaces/team-a/connections/gitlab-prod")
    assert advance.kwargs["params"] == {"expectedRevision": 1}
    assert advance.kwargs["json"] == {"kind": "gitlab"}
    assert http.request.call_args_list[3].kwargs["params"] == {"revision": 2}


def test_connection_authority_rejects_global_namespace_and_zero_revision():
    api = ConnectionAuthorityAPI(Mock(), "*")
    try:
        api.get_current("x")
        assert False, "global namespace accepted"
    except ValueError:
        pass
    try:
        api.revoke("x", 0, namespace="team-a")
        assert False, "zero revision accepted"
    except ValueError:
        pass


def test_async_connection_authority_has_exact_sync_parity():
    http = Mock()
    http.request = AsyncMock(side_effect=[_response({"frozen": True}), _response({"frozen": True}), _response({"frozen": True}), _response(status=204)])
    api = AsyncConnectionAuthorityAPI(http, "team-a")
    descriptor = {"namespace": "team-a", "id": "gitlab-prod", "revision": 9, "kind": "gitlab"}

    async def lifecycle():
        await api.create(descriptor)
        await api.advance("gitlab-prod", descriptor, 1)
        await api.get_current("gitlab-prod")
        await api.revoke("gitlab-prod", 2)

    asyncio.run(lifecycle())
    assert http.request.await_args_list[0].args[:2] == ("POST", "/api/v1/namespaces/team-a/connections")
    assert http.request.await_args_list[1].kwargs["params"] == {"expectedRevision": 1}
    assert http.request.await_args_list[3].kwargs["params"] == {"revision": 2}
