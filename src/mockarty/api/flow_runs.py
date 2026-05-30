# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Server-side IR runner client (``POST /api/v1/api-tester/flow-runs``).

Companion to the admin handler in
``internal/webui/api_tester_flow_run_handler.go``. Lets a Python caller
ship a Mockarty canonical IR Flow at the server and receive the
aggregated RunResult without dragging a goja runtime into the test
process.

Wire shape mirrors the Go SDK's ``FlowRunResponse`` 1:1 so multi-
language harnesses stay portable. Flow is opaque to the SDK — accepted
as either a dict or a pre-serialised JSON string so callers can use
whatever IR they have on hand.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Union

from mockarty.api._base import AsyncAPIBase, SyncAPIBase

_FLOW_RUNS_PATH = "/api/v1/api-tester/flow-runs"


def _coerce_flow(flow: Union[dict[str, Any], str, bytes]) -> dict[str, Any]:
    """Normalise the caller's flow into a JSON-serialisable dict.

    Accepts a dict, a JSON-encoded ``str``, or ``bytes``. Anything else
    raises ``TypeError`` so the failure is local and obvious.
    """
    if isinstance(flow, dict):
        return flow
    if isinstance(flow, (str, bytes)):
        decoded = flow.decode("utf-8") if isinstance(flow, bytes) else flow
        try:
            parsed = json.loads(decoded)
        except json.JSONDecodeError as e:
            raise ValueError(f"flow_runs.execute: flow is not valid JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("flow_runs.execute: flow must decode to a JSON object")
        return parsed
    raise TypeError("flow_runs.execute: flow must be a dict, JSON string, or bytes")


def _build_body(
    flow: Union[dict[str, Any], str, bytes],
    base_url: Optional[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {"flow": _coerce_flow(flow)}
    if base_url:
        body["base_url"] = base_url
    return body


class FlowRunsAPI(SyncAPIBase):
    """Sync client for POST /api/v1/api-tester/flow-runs."""

    def execute(
        self,
        flow: Union[dict[str, Any], str, bytes],
        *,
        base_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Ship ``flow`` at the server runner and return the aggregated RunResult.

        ``flow`` can be a dict (preferred), a JSON-encoded ``str``, or
        ``bytes``. ``base_url`` overrides the URL prefix injected into
        the generated JS (equivalent to iruir.RunIROptions.BaseURL).

        Returns the raw JSON envelope with keys:
        ``status``, ``variables``, ``logs``, ``errors``, ``startedAt``,
        ``finishedAt``, ``durationMs``. Caller decides what to do with
        a non-``passed`` status — the SDK does not raise on that path
        (network/HTTP errors still raise via the base client).
        """
        body = _build_body(flow, base_url)
        response = self._request("POST", _FLOW_RUNS_PATH, json=body)
        return response.json()


class AsyncFlowRunsAPI(AsyncAPIBase):
    """Async counterpart of :class:`FlowRunsAPI`."""

    async def execute(
        self,
        flow: Union[dict[str, Any], str, bytes],
        *,
        base_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Async version of :meth:`FlowRunsAPI.execute`."""
        body = _build_body(flow, base_url)
        response = await self._request("POST", _FLOW_RUNS_PATH, json=body)
        return response.json()
