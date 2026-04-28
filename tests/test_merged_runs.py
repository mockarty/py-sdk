# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the merged test-run API surface (T-12 / backlog #55)."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MergedRunList, MergedRunView, MockartyClient
from mockarty.api.testruns import (
    MERGED_RUN_REPORT_FORMAT_MARKDOWN,
    MERGED_RUN_REPORT_FORMAT_UNIFIED,
)


# Capitalised JSON keys match the server's emitted shape — ActiveTestRunRow
# has no json tags, so Go falls back to field names.
_RUN_PAYLOAD = {
    "ID": "11111111-1111-1111-1111-111111111111",
    "Namespace": "test-ns",
    "Mode": "merged",
    "Status": "completed",
    "Name": "Release gate",
    "StartedAt": "2026-04-20T10:00:00Z",
    "UpdatedAt": "2026-04-20T10:05:00Z",
    "Progress": 100,
}

_SOURCE_PAYLOAD = {
    "ID": "22222222-2222-2222-2222-222222222222",
    "Namespace": "test-ns",
    "Mode": "functional",
    "Status": "completed",
    "Name": "Smoke suite",
    "StartedAt": "2026-04-20T09:55:00Z",
    "UpdatedAt": "2026-04-20T09:59:00Z",
    "Progress": 100,
}


class TestMergedRunsSync:
    @respx.mock
    def test_merge_runs_posts_source_ids(self, client: MockartyClient) -> None:
        route = respx.post(
            "http://localhost:5770/api/v1/test-runs/merges"
        ).mock(
            return_value=httpx.Response(
                201,
                json={"run": _RUN_PAYLOAD, "sources": [_SOURCE_PAYLOAD]},
            )
        )
        view = client.test_runs.merge_runs(
            name="Release gate",
            source_ids=[_SOURCE_PAYLOAD["ID"]],
        )
        assert isinstance(view, MergedRunView)
        assert view.run is not None
        assert view.run.id == _RUN_PAYLOAD["ID"]
        assert view.run.mode == "merged"
        assert len(view.sources) == 1
        assert view.sources[0].id == _SOURCE_PAYLOAD["ID"]
        assert route.called
        body = route.calls[0].request.content.decode()
        assert "Release gate" in body
        assert _SOURCE_PAYLOAD["ID"] in body
        assert "sourceRunIds" in body

    @respx.mock
    def test_list_merged_runs_envelope(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-runs/merges"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {"run": _RUN_PAYLOAD, "sources": [_SOURCE_PAYLOAD]}
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )
        page = client.test_runs.list_merged_runs()
        assert isinstance(page, MergedRunList)
        assert page.total == 1
        assert page.limit == 50
        assert len(page.items) == 1
        assert page.items[0].run.id == _RUN_PAYLOAD["ID"]

    @respx.mock
    def test_list_merged_runs_passes_pagination(
        self, client: MockartyClient
    ) -> None:
        route = respx.get(
            "http://localhost:5770/api/v1/test-runs/merges"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"items": [], "total": 0, "limit": 5, "offset": 10},
            )
        )
        client.test_runs.list_merged_runs(limit=5, offset=10)
        assert route.called
        query = dict(route.calls[0].request.url.params)
        assert query == {"limit": "5", "offset": "10"}

    @respx.mock
    def test_get_merged_run(self, client: MockartyClient) -> None:
        respx.get(
            f"http://localhost:5770/api/v1/test-runs/merges/{_RUN_PAYLOAD['ID']}"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"run": _RUN_PAYLOAD, "sources": [_SOURCE_PAYLOAD]},
            )
        )
        view = client.test_runs.get_merged_run(_RUN_PAYLOAD["ID"])
        assert view.run.status == "completed"
        assert view.sources[0].id == _SOURCE_PAYLOAD["ID"]

    @respx.mock
    def test_delete_merged_run(self, client: MockartyClient) -> None:
        route = respx.delete(
            f"http://localhost:5770/api/v1/test-runs/merges/{_RUN_PAYLOAD['ID']}"
        ).mock(return_value=httpx.Response(204))
        client.test_runs.delete_merged_run(_RUN_PAYLOAD["ID"])
        assert route.called

    @respx.mock
    def test_get_report_unified_default(self, client: MockartyClient) -> None:
        body = b'{"generatedAt":"2026-04-20T10:10:00Z","mergedRunId":"x"}'
        route = respx.get(
            f"http://localhost:5770/api/v1/test-runs/merges/{_RUN_PAYLOAD['ID']}/report"
        ).mock(
            return_value=httpx.Response(
                200,
                content=body,
                headers={"Content-Type": "application/json"},
            )
        )
        data = client.test_runs.get_merged_run_report(_RUN_PAYLOAD["ID"])
        assert data == body
        assert route.called
        query = dict(route.calls[0].request.url.params)
        assert query == {"format": MERGED_RUN_REPORT_FORMAT_UNIFIED}

    @respx.mock
    def test_get_report_markdown_explicit(self, client: MockartyClient) -> None:
        route = respx.get(
            f"http://localhost:5770/api/v1/test-runs/merges/{_RUN_PAYLOAD['ID']}/report"
        ).mock(
            return_value=httpx.Response(
                200,
                content=b"# merged run\n",
                headers={"Content-Type": "text/markdown"},
            )
        )
        data = client.test_runs.get_merged_run_report(
            _RUN_PAYLOAD["ID"], format=MERGED_RUN_REPORT_FORMAT_MARKDOWN
        )
        assert data.startswith(b"# merged run")
        query = dict(route.calls[0].request.url.params)
        assert query == {"format": MERGED_RUN_REPORT_FORMAT_MARKDOWN}


class TestMergedRunsAsync:
    @pytest.mark.asyncio
    @respx.mock
    async def test_merge_runs_async(self, base_url: str, api_key: str) -> None:
        from mockarty import AsyncMockartyClient

        respx.post(
            "http://localhost:5770/api/v1/test-runs/merges"
        ).mock(
            return_value=httpx.Response(
                201,
                json={"run": _RUN_PAYLOAD, "sources": [_SOURCE_PAYLOAD]},
            )
        )
        async with AsyncMockartyClient(
            base_url=base_url,
            api_key=api_key,
            namespace="test-ns",
            timeout=5.0,
            max_retries=0,
        ) as client:
            view = await client.test_runs.merge_runs(
                name="Release gate",
                source_ids=[_SOURCE_PAYLOAD["ID"]],
            )
            assert view.run.id == _RUN_PAYLOAD["ID"]
            assert view.sources[0].id == _SOURCE_PAYLOAD["ID"]
