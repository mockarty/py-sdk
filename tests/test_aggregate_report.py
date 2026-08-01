# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the stateless aggregate-report API.

The persistent merge surface (POST/GET/DELETE /test-runs/merges*) was removed
server-side in migration 100. ``aggregate_runs_report`` is the replacement:
a transient report over several run IDs, recomputed per call, nothing persisted.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient
from mockarty.api.testruns import (
    AGGREGATE_REPORT_FORMAT_MARKDOWN,
    AGGREGATE_REPORT_FORMAT_UNIFIED,
)

_AGG_URL = "http://localhost:5770/api/v1/test-runs/reports/aggregate"


class TestAggregateReportSync:
    @respx.mock
    def test_posts_run_ids_and_format(self, client: MockartyClient) -> None:
        route = respx.post(_AGG_URL).mock(
            return_value=httpx.Response(200, text="# Aggregate test run: nightly\n")
        )
        data = client.test_runs.aggregate_runs_report(
            run_ids=["r1", "r2"],
            format=AGGREGATE_REPORT_FORMAT_MARKDOWN,
            name="nightly",
        )
        assert b"Aggregate test run: nightly" in data
        assert route.called
        req = route.calls[0].request
        assert req.url.params.get("format") == "markdown"
        body = req.content.decode()
        assert '"run_ids"' in body
        assert "r1" in body and "r2" in body
        assert '"name":"nightly"' in body.replace(" ", "")

    @respx.mock
    def test_defaults_to_unified(self, client: MockartyClient) -> None:
        route = respx.post(_AGG_URL).mock(
            return_value=httpx.Response(200, json={"totals": {"sources": 0}})
        )
        client.test_runs.aggregate_runs_report(run_ids=["r1"])
        assert route.calls[0].request.url.params.get("format") == (
            AGGREGATE_REPORT_FORMAT_UNIFIED
        )

    @respx.mock
    def test_name_omitted_when_none(self, client: MockartyClient) -> None:
        route = respx.post(_AGG_URL).mock(
            return_value=httpx.Response(200, json={})
        )
        client.test_runs.aggregate_runs_report(run_ids=["r1"])
        assert '"name"' not in route.calls[0].request.content.decode()

    def test_empty_run_ids_raises(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError):
            client.test_runs.aggregate_runs_report(run_ids=[])


class TestAggregateReportAsync:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_posts_run_ids(self, base_url: str, api_key: str) -> None:
        from mockarty import AsyncMockartyClient

        route = respx.post(_AGG_URL).mock(
            return_value=httpx.Response(200, text="ok")
        )
        async with AsyncMockartyClient(
            base_url=base_url,
            api_key=api_key,
            namespace="test-ns",
            timeout=5.0,
            max_retries=0,
        ) as client:
            data = await client.test_runs.aggregate_runs_report(
                run_ids=["r1"], format=AGGREGATE_REPORT_FORMAT_MARKDOWN
            )
        assert data == b"ok"
        assert route.calls[0].request.url.params.get("format") == "markdown"

    @pytest.mark.asyncio
    async def test_async_empty_run_ids_raises(
        self, base_url: str, api_key: str
    ) -> None:
        from mockarty import AsyncMockartyClient

        async with AsyncMockartyClient(
            base_url=base_url, api_key=api_key, namespace="test-ns"
        ) as client:
            with pytest.raises(ValueError):
                await client.test_runs.aggregate_runs_report(run_ids=[])
