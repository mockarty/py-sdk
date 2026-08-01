# Copyright (c) 2026 Mockarty. All rights reserved.

"""Contract tests for the mock version-history endpoints.

The version endpoints return revision ROWS, not mocks: the mock body of a
revision hangs off the row's ``mock`` key, and the list comes wrapped in
``{mock_id, versions, count}``. The SDK used to treat the list envelope as a
bare array — so ``list_versions`` returned ``[]`` for every mock that had a
history, with no error to show for it.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient
from mockarty.models.mock import MockVersion


_VERSIONS_ENVELOPE = {
    "mock_id": "versioned-mock",
    "count": 2,
    "versions": [
        {
            "id": "ver-2",
            "mock_id": "versioned-mock",
            "version": 2,
            "created_at": 1700000200,
            "lifecycle_state": "active",
            "tags": ["v2"],
            "mock": {"id": "versioned-mock", "namespace": "sandbox", "tags": ["v2"]},
        },
        {
            "id": "ver-1",
            "mock_id": "versioned-mock",
            "version": 1,
            "created_at": 1700000100,
            "lifecycle_state": "active",
            "tags": ["v1"],
            "mock": {"id": "versioned-mock", "namespace": "sandbox", "tags": ["v1"]},
        },
    ],
}


class TestListVersions:
    @respx.mock
    def test_unwraps_envelope_into_revision_rows(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/mocks/versioned-mock/versions"
        ).mock(return_value=httpx.Response(200, json=_VERSIONS_ENVELOPE))

        versions = client.mocks.list_versions("versioned-mock")

        assert len(versions) == 2, "the {versions: [...]} envelope must be unwrapped"
        assert all(isinstance(v, MockVersion) for v in versions)
        assert [v.version for v in versions] == [2, 1]
        assert versions[0].id == "ver-2"
        assert versions[0].mock_id == "versioned-mock"
        assert versions[0].created_at == 1700000200
        # The revision's mock body must survive the decode — this is what the
        # old list[Mock] handling threw away.
        assert versions[0].mock is not None
        assert versions[0].mock.namespace == "sandbox"
        assert versions[1].tags == ["v1"]

    @respx.mock
    def test_accepts_bare_list_from_older_servers(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/mocks/versioned-mock/versions"
        ).mock(
            return_value=httpx.Response(200, json=_VERSIONS_ENVELOPE["versions"])
        )
        assert len(client.mocks.list_versions("versioned-mock")) == 2


class TestGetVersion:
    @respx.mock
    def test_unwraps_version_envelope(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/mocks/versioned-mock/versions/2"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "version": _VERSIONS_ENVELOPE["versions"][0],
                    "previous_version": _VERSIONS_ENVELOPE["versions"][1],
                },
            )
        )

        current = client.mocks.get_version("versioned-mock", 2)
        assert current.version == 2
        assert current.mock is not None and current.mock.namespace == "sandbox"

    @respx.mock
    def test_with_previous_returns_both(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/mocks/versioned-mock/versions/2"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "version": _VERSIONS_ENVELOPE["versions"][0],
                    "previous_version": _VERSIONS_ENVELOPE["versions"][1],
                },
            )
        )
        current, previous = client.mocks.get_version_with_previous("versioned-mock", 2)
        assert current.version == 2
        assert previous is not None and previous.version == 1

    @respx.mock
    def test_first_revision_has_no_previous(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/mocks/versioned-mock/versions/1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "version": _VERSIONS_ENVELOPE["versions"][1],
                    "previous_version": None,
                },
            )
        )
        _, previous = client.mocks.get_version_with_previous("versioned-mock", 1)
        assert previous is None

    @respx.mock
    def test_missing_revision_raises(self, client: MockartyClient) -> None:
        # A null "version" means the revision does not exist. Returning an
        # empty row would read as "revision 0 exists".
        respx.get(
            "http://localhost:5770/api/v1/mocks/versioned-mock/versions/9"
        ).mock(
            return_value=httpx.Response(
                200, json={"version": None, "previous_version": None}
            )
        )
        with pytest.raises(ValueError):
            client.mocks.get_version("versioned-mock", 9)
