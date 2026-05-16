# Copyright (c) 2026 Mockarty. All rights reserved.

"""Language-side fuzz DSL for Mockarty's Python SDK.

Build a :class:`Target`, describe its seeds / mutators / assertions /
limits, then either submit it to a running admin server or hand it to
``mockarty-cli`` via :class:`Runner`. The SDK never executes a fuzz
run in-process — see ``feedback_sdk_thin_layer.md``.

Quick start::

    from datetime import timedelta
    from mockarty.fuzz import (
        Target,
        Seed,
        Mutator,
        AssertStatus,
        AssertNoCrash,
    )

    target = (
        Target("login-flow")
        .description("Stress-test login endpoint")
        .http_endpoint("POST", "/api/v1/login", base_url="https://api.example.com")
        .seeds([
            Seed("valid", '{"username":"admin","password":"secret"}'),
            Seed("missing-pw", '{"username":"admin"}'),
        ])
        .mutator(Mutator.JSON)
        .duration(timedelta(minutes=5))
        .stop_on_finding(True)
        .reporter("allure")
        .assertion(AssertStatus(range(200, 300)))
        .assertion(AssertNoCrash())
    )

    payload = target.to_json()  # canonical fuzz config dict

See :doc:`./README` for the surface table, hybrid pattern and Phase 2
roadmap.
"""

from __future__ import annotations

from mockarty.fuzz.assertions import (
    AssertNoCrash,
    AssertNoErrorInBody,
    AssertResponseTimeUnder,
    AssertStatus,
    Assertion,
    assertion,
)
from mockarty.fuzz.dsl import Target
from mockarty.fuzz.mutators import CustomMutator, Mutator
from mockarty.fuzz.protocols import Endpoint, Protocol
from mockarty.fuzz.result import Finding, Result
from mockarty.fuzz.runner import JobID, LocalSpawnResult, Runner, write_to
from mockarty.fuzz.seeds import Seed
from mockarty.fuzz.transpile import parse, transpile
from mockarty.fuzz.types import (
    FuzzConfig,
    FuzzOptions,
    FuzzSeedRequest,
    SourceType,
    Strategy,
)

__all__ = [
    # DSL
    "Target",
    "Seed",
    "Mutator",
    "CustomMutator",
    "Endpoint",
    "Protocol",
    # Assertions
    "Assertion",
    "AssertStatus",
    "AssertNoCrash",
    "AssertResponseTimeUnder",
    "AssertNoErrorInBody",
    "assertion",
    # Results
    "Result",
    "Finding",
    # Runner
    "Runner",
    "LocalSpawnResult",
    "JobID",
    "write_to",
    # Types / transpile
    "FuzzConfig",
    "FuzzOptions",
    "FuzzSeedRequest",
    "Strategy",
    "SourceType",
    "transpile",
    "parse",
]
