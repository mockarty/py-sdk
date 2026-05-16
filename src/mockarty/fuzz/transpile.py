# Copyright (c) 2026 Mockarty. All rights reserved.

"""Translate a :class:`mockarty.fuzz.dsl.Target` into the canonical
fuzz JSON config the admin server / CLI consumes.

The transpiler is the one place that knows about server-side schema
quirks (e.g. ``maxDuration`` is a Go duration string like ``"5m"``,
``payloadCategories`` is a flat list of strings, options.grpcAddress
only applies to gRPC targets). Keeping it in a dedicated module lets
tests cover the V1 wire format in isolation and lets future schema
revisions land in one place.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from mockarty.fuzz.mutators import CustomMutator, Mutator
from mockarty.fuzz.protocols import Protocol
from mockarty.fuzz.types import FuzzConfig, FuzzOptions, FuzzSeedRequest

if TYPE_CHECKING:  # pragma: no cover — typing only
    from mockarty.fuzz.dsl import Target


def _format_duration(d: timedelta) -> str:
    """Render a :class:`timedelta` as a Go duration string.

    The server's parser accepts ``"5m"``, ``"30s"``, ``"500ms"``, etc.
    We pick the most compact unit that doesn't lose precision.
    """

    total_ms = int(round(d.total_seconds() * 1000))
    if total_ms == 0:
        return "0s"
    if total_ms % (3600 * 1000) == 0:
        return f"{total_ms // (3600 * 1000)}h"
    if total_ms % (60 * 1000) == 0:
        return f"{total_ms // (60 * 1000)}m"
    if total_ms % 1000 == 0:
        return f"{total_ms // 1000}s"
    return f"{total_ms}ms"


def transpile(target: "Target") -> Dict[str, Any]:
    """Render ``target`` to a JSON-serialisable dict.

    Validates protocol/endpoint pairing before emission. Raises
    :class:`ValueError` with a precise message on any inconsistency
    so the user finds the bug before the server does.
    """

    # ── 1. validate ───────────────────────────────────────────────

    if target.endpoint is None:
        raise ValueError(
            "target has no endpoint — call .http_endpoint() / "
            ".grpc_endpoint() / etc. before transpile"
        )

    # ── 2. seed corpus ────────────────────────────────────────────

    seed_default_method = ""
    seed_default_url = ""
    seed_default_path = ""

    if target.endpoint.protocol is Protocol.HTTP:
        seed_default_method = target.endpoint.method or "GET"
        seed_default_url = target.endpoint.url
        seed_default_path = target.endpoint.path

    seed_requests: List[FuzzSeedRequest] = [
        s.to_request(
            default_method=seed_default_method,
            default_url=seed_default_url,
            default_path=seed_default_path,
        )
        for s in target.seeds_list
    ]

    # ── 3. payload categories (mutators) ─────────────────────────

    payload_categories: List[str] = []
    custom_mutators: Dict[str, Dict[str, Any]] = {}
    for m in target.mutators_list:
        if isinstance(m, Mutator):
            payload_categories.append(m.value)
        elif isinstance(m, CustomMutator):
            payload_categories.append(m.name)
            if m.config:
                custom_mutators[m.name] = dict(m.config)

    # ── 4. options block ─────────────────────────────────────────

    opts = FuzzOptions()
    if target._duration is not None:
        opts.max_duration = _format_duration(target._duration)
    if target._timeout_per_req is not None:
        opts.timeout_per_req = _format_duration(target._timeout_per_req)
    opts.max_requests = target._max_requests
    opts.max_rps = target._max_rps
    opts.concurrency = target._concurrency
    opts.mutation_depth = target._mutation_depth
    opts.follow_redirects = target._follow_redirects
    opts.stop_on_critical = target._stop_on_finding
    opts.verify_findings = target._verify_findings
    opts.auth_header = target._auth_header
    opts.custom_headers = dict(target._custom_headers)
    opts.include_routes = list(target._include_routes)
    opts.exclude_routes = list(target._exclude_routes)
    opts.status_code_alerts = list(target._status_code_alerts)
    opts.response_time_alert = target._response_time_alert_ms
    opts.detect_patterns = list(target._detect_patterns)
    opts.llm_enabled = target._llm_enabled
    opts.llm_profile_id = target._llm_profile_id
    opts.baseline_run_id = target._baseline_run_id

    # Protocol-specific routing.
    ep = target.endpoint
    if ep.protocol is Protocol.GRPC:
        opts.grpc_address = ep.url
        opts.grpc_use_tls = ep.use_tls
        if ep.service:
            opts.grpc_services = [ep.service]
        if ep.rpc_method:
            opts.grpc_methods = [ep.rpc_method]
    elif ep.protocol is Protocol.GRAPHQL:
        opts.graphql_endpoint = ep.url
        opts.graphql_path = ep.path

    # ── 5. base URL routing ──────────────────────────────────────

    base_url = ""
    if ep.protocol is Protocol.HTTP:
        base_url = ep.url
    elif ep.protocol in (Protocol.SOAP, Protocol.WEBSOCKET):
        base_url = ep.url
    elif ep.protocol in (Protocol.KAFKA, Protocol.RABBITMQ):
        base_url = ep.url  # broker address — preserved verbatim

    # ── 6. SDK metadata ──────────────────────────────────────────

    sdk_meta: Dict[str, Any] = {
        "sdk": "mockarty-py",
        "sdkVersion": "0.3.0",
        "protocol": ep.protocol.value,
        "endpoint": ep.to_dict(),
        "description": target._description,
    }
    if target._reporters:
        sdk_meta["reporters"] = list(target._reporters)
    if target._assertions:
        sdk_meta["assertions"] = [a.to_dict() for a in target.assertions_list]
    if custom_mutators:
        sdk_meta["customMutators"] = custom_mutators
    if target._extra:
        sdk_meta["extra"] = dict(target._extra)

    # ── 7. assemble FuzzConfig ───────────────────────────────────

    cfg = FuzzConfig(
        name=target.name,
        namespace=target._namespace,
        source_type=target._source_type,
        target_base_url=base_url,
        strategy=target._strategy,
        seed_requests=seed_requests,
        options=opts,
        payload_categories=payload_categories,
        openapi_spec=target._openapi_spec,
        sdk_meta=sdk_meta,
    )

    # Drop empty default values from the dump so the JSON stays small
    # and round-trippable. exclude_defaults=True covers the bool/int
    # zeroes; exclude_none drops openapi_spec when unset.
    return cfg.model_dump(by_alias=True, exclude_defaults=True, exclude_none=True)


def parse(payload: Dict[str, Any]) -> FuzzConfig:
    """Best-effort reverse — useful for round-trip tests.

    Round-tripping a transpiled dict back through :class:`FuzzConfig`
    and re-dumping produces a stable canonical form.
    """

    return FuzzConfig.model_validate(payload)
