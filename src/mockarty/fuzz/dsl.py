# Copyright (c) 2026 Mockarty. All rights reserved.

"""Fluent :class:`Target` builder — the entry point of the fuzz DSL.

Mirrors the architectural pattern from :mod:`mockarty.pact.consumer`:

* The user chains setter methods (``.description(...)``, ``.seeds(...)``,
  ``.mutator(...)``, ``.assertion(...)``) to describe what to fuzz.
* Calling :meth:`Target.to_json` (or the lower-level
  :func:`mockarty.fuzz.transpile.transpile`) produces the canonical
  JSON config the admin server / CLI runs.
* The SDK never executes a fuzz run in-process — see
  :class:`mockarty.fuzz.runner.Runner` for submit/wait/local_spawn.

Thread-safety: per-instance state mutates under a lock so two
parallel pytest workers calling ``.assertion(...)`` on the same target
don't lose entries. Cross-target there is nothing shared, so building
hundreds of targets concurrently is fine.
"""

from __future__ import annotations

import copy
import threading
from datetime import timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from mockarty.fuzz.assertions import Assertion
from mockarty.fuzz.mutators import CustomMutator, Mutator
from mockarty.fuzz.protocols import Endpoint, Protocol
from mockarty.fuzz.seeds import Seed
from mockarty.fuzz.types import SourceType, Strategy


class Target:
    """Describe a single fuzz target. Immutable after :meth:`to_json`.

    Example::

        from datetime import timedelta
        from mockarty.fuzz import Target, Seed, Mutator, AssertStatus

        target = (
            Target("login-flow")
            .description("Stress-test login endpoint")
            .http_endpoint("POST", "/api/v1/login")
            .seeds([
                Seed("valid", '{"username":"admin","password":"secret"}'),
                Seed("missing-pw", '{"username":"admin"}'),
            ])
            .mutator(Mutator.JSON)
            .duration(timedelta(minutes=5))
            .stop_on_finding(True)
            .reporter("allure")
            .assertion(AssertStatus(range(200, 300)))
        )
    """

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("target name must be non-empty")
        self._lock = threading.RLock()
        self._name = name
        self._description = ""
        self._namespace = ""
        self._source_type: str = SourceType.MANUAL.value
        self._strategy: str = Strategy.ALL.value
        self._endpoint: Optional[Endpoint] = None
        self._seeds: List[Seed] = []
        self._mutators: List[Union[Mutator, CustomMutator]] = []
        self._assertions: List[Assertion] = []
        self._duration: Optional[timedelta] = None
        self._timeout_per_req: Optional[timedelta] = None
        self._max_requests: int = 0
        self._max_rps: int = 0
        self._concurrency: int = 0
        self._mutation_depth: int = 0
        self._follow_redirects: bool = False
        self._stop_on_finding: bool = False
        self._verify_findings: bool = False
        self._auth_header: str = ""
        self._custom_headers: Dict[str, str] = {}
        self._include_routes: List[str] = []
        self._exclude_routes: List[str] = []
        self._status_code_alerts: List[int] = []
        self._response_time_alert_ms: int = 0
        self._detect_patterns: List[str] = []
        self._reporters: List[str] = []
        self._llm_enabled: bool = False
        self._llm_profile_id: str = ""
        self._baseline_run_id: str = ""
        self._openapi_spec: Optional[str] = None
        self._extra: Dict[str, Any] = {}

    # ── Identification ────────────────────────────────────────────

    def description(self, text: str) -> "Target":
        with self._lock:
            self._description = str(text)
        return self

    def namespace(self, ns: str) -> "Target":
        with self._lock:
            self._namespace = str(ns)
        return self

    def strategy(self, strategy: Union[str, Strategy]) -> "Target":
        with self._lock:
            self._strategy = (
                strategy.value if isinstance(strategy, Strategy) else str(strategy)
            )
        return self

    def source_type(self, source: Union[str, SourceType]) -> "Target":
        with self._lock:
            self._source_type = (
                source.value if isinstance(source, SourceType) else str(source)
            )
        return self

    # ── Protocol endpoints ────────────────────────────────────────

    def http_endpoint(
        self,
        method: str,
        path: str,
        *,
        base_url: str = "",
    ) -> "Target":
        """Bind to an HTTP endpoint. ``base_url`` may be absolute (then
        ``path`` is just the URL suffix) or empty (then ``path`` is the
        full path on a server-supplied base URL).
        """

        with self._lock:
            self._endpoint = Endpoint(
                Protocol.HTTP,
                method=method.upper(),
                url=base_url,
                path=path,
            )
        return self

    def grpc_endpoint(
        self,
        service: str,
        rpc_method: str,
        *,
        address: str = "",
        use_tls: bool = False,
    ) -> "Target":
        with self._lock:
            self._endpoint = Endpoint(
                Protocol.GRPC,
                service=service,
                rpc_method=rpc_method,
                url=address,
                use_tls=use_tls,
            )
        return self

    def graphql_endpoint(
        self,
        url: str,
        *,
        path: str = "",
    ) -> "Target":
        with self._lock:
            self._endpoint = Endpoint(
                Protocol.GRAPHQL,
                url=url,
                path=path,
            )
        return self

    def kafka_endpoint(self, address: str, topic: str) -> "Target":
        with self._lock:
            self._endpoint = Endpoint(
                Protocol.KAFKA,
                url=address,
                topic=topic,
            )
        return self

    def rabbitmq_endpoint(
        self,
        address: str,
        *,
        queue: str = "",
        exchange: str = "",
    ) -> "Target":
        if not queue and not exchange:
            raise ValueError("rabbitmq_endpoint requires queue or exchange")
        with self._lock:
            self._endpoint = Endpoint(
                Protocol.RABBITMQ,
                url=address,
                queue=queue,
                exchange=exchange,
            )
        return self

    def soap_endpoint(
        self,
        url: str,
        *,
        soap_action: str = "",
    ) -> "Target":
        with self._lock:
            self._endpoint = Endpoint(
                Protocol.SOAP,
                url=url,
                soap_action=soap_action,
            )
        return self

    def websocket_endpoint(
        self,
        url: str,
        *,
        subprotocol: str = "",
    ) -> "Target":
        with self._lock:
            self._endpoint = Endpoint(
                Protocol.WEBSOCKET,
                url=url,
                ws_subprotocol=subprotocol,
            )
        return self

    # ── Corpus ────────────────────────────────────────────────────

    def seeds(self, seeds: Iterable[Union[Seed, str, bytes]]) -> "Target":
        """Replace the seed list with ``seeds``.

        Strings / bytes get auto-wrapped into anonymous :class:`Seed`
        instances with auto-generated names (``seed-0`` …).
        """

        normalised: List[Seed] = []
        for i, s in enumerate(seeds):
            if isinstance(s, Seed):
                normalised.append(s)
            elif isinstance(s, (bytes, bytearray)):
                normalised.append(Seed(f"seed-{i}", bytes(s)))
            else:
                normalised.append(Seed(f"seed-{i}", str(s)))
        with self._lock:
            self._seeds = normalised
        return self

    def add_seed(self, seed: Seed) -> "Target":
        """Append a single seed to the existing list."""

        if not isinstance(seed, Seed):
            raise TypeError("add_seed expects a Seed instance")
        with self._lock:
            self._seeds.append(seed)
        return self

    # ── Mutators ──────────────────────────────────────────────────

    def mutator(self, mutator: Union[Mutator, CustomMutator, str]) -> "Target":
        """Append a mutator. Accepts the :class:`Mutator` enum, a
        :class:`CustomMutator` descriptor, or a raw string (forwarded
        verbatim — useful when the server adds a new category before
        the SDK does).
        """

        with self._lock:
            if isinstance(mutator, (Mutator, CustomMutator)):
                self._mutators.append(mutator)
            elif isinstance(mutator, str):
                if not mutator:
                    raise ValueError("mutator string must be non-empty")
                self._mutators.append(Mutator.custom(mutator))
            else:
                raise TypeError(f"unsupported mutator: {type(mutator).__name__}")
        return self

    def mutators(
        self, mutators: Iterable[Union[Mutator, CustomMutator, str]]
    ) -> "Target":
        """Replace the mutator list."""

        with self._lock:
            self._mutators = []
        for m in mutators:
            self.mutator(m)
        return self

    # ── Assertions ────────────────────────────────────────────────

    def assertion(self, assertion: Assertion) -> "Target":
        if not isinstance(assertion, Assertion):
            raise TypeError("assertion expects an Assertion instance")
        with self._lock:
            self._assertions.append(assertion)
        return self

    def assertions(self, assertions: Iterable[Assertion]) -> "Target":
        normalised = list(assertions)
        for a in normalised:
            if not isinstance(a, Assertion):
                raise TypeError("assertions expects Assertion instances")
        with self._lock:
            self._assertions = normalised
        return self

    # ── Limits ────────────────────────────────────────────────────

    def duration(self, value: Union[timedelta, float, int]) -> "Target":
        """Wall-clock limit for the run.

        Accepts :class:`timedelta` or a number of seconds.
        """

        if isinstance(value, timedelta):
            d = value
        else:
            d = timedelta(seconds=float(value))
        if d.total_seconds() <= 0:
            raise ValueError("duration must be positive")
        with self._lock:
            self._duration = d
        return self

    def timeout_per_request(self, value: Union[timedelta, float, int]) -> "Target":
        if isinstance(value, timedelta):
            d = value
        else:
            d = timedelta(seconds=float(value))
        if d.total_seconds() <= 0:
            raise ValueError("timeout_per_request must be positive")
        with self._lock:
            self._timeout_per_req = d
        return self

    def max_requests(self, n: int) -> "Target":
        if n < 0:
            raise ValueError("max_requests must be non-negative")
        with self._lock:
            self._max_requests = int(n)
        return self

    def max_rps(self, n: int) -> "Target":
        if n < 0:
            raise ValueError("max_rps must be non-negative")
        with self._lock:
            self._max_rps = int(n)
        return self

    def concurrency(self, n: int) -> "Target":
        if n < 0:
            raise ValueError("concurrency must be non-negative")
        with self._lock:
            self._concurrency = int(n)
        return self

    def mutation_depth(self, n: int) -> "Target":
        if n < 0:
            raise ValueError("mutation_depth must be non-negative")
        with self._lock:
            self._mutation_depth = int(n)
        return self

    # ── Behaviour toggles ─────────────────────────────────────────

    def follow_redirects(self, on: bool = True) -> "Target":
        with self._lock:
            self._follow_redirects = bool(on)
        return self

    def stop_on_finding(self, on: bool = True) -> "Target":
        with self._lock:
            self._stop_on_finding = bool(on)
        return self

    def verify_findings(self, on: bool = True) -> "Target":
        with self._lock:
            self._verify_findings = bool(on)
        return self

    # ── HTTP-style options ────────────────────────────────────────

    def auth_header(self, value: str) -> "Target":
        with self._lock:
            self._auth_header = str(value)
        return self

    def custom_headers(self, headers: Dict[str, str]) -> "Target":
        with self._lock:
            self._custom_headers = {str(k): str(v) for k, v in headers.items()}
        return self

    def include_routes(self, routes: Iterable[str]) -> "Target":
        with self._lock:
            self._include_routes = [str(r) for r in routes]
        return self

    def exclude_routes(self, routes: Iterable[str]) -> "Target":
        with self._lock:
            self._exclude_routes = [str(r) for r in routes]
        return self

    def status_code_alerts(self, codes: Iterable[int]) -> "Target":
        with self._lock:
            self._status_code_alerts = sorted({int(c) for c in codes})
        return self

    def response_time_alert(self, value: Union[timedelta, float, int]) -> "Target":
        if isinstance(value, timedelta):
            ms = int(value.total_seconds() * 1000)
        else:
            ms = int(float(value) * 1000)
        if ms <= 0:
            raise ValueError("response_time_alert must be positive")
        with self._lock:
            self._response_time_alert_ms = ms
        return self

    def detect_patterns(self, patterns: Iterable[str]) -> "Target":
        with self._lock:
            self._detect_patterns = [str(p) for p in patterns]
        return self

    # ── Reporting ────────────────────────────────────────────────

    def reporter(self, name: str) -> "Target":
        """Append a reporter ('allure', 'junit', 'sarif', etc.).

        Reporters are SDK-side metadata — the server emits a unified
        :class:`Result` and the runner formats it for the chosen
        reporter at result-fetch time.
        """

        if not name:
            raise ValueError("reporter name must be non-empty")
        with self._lock:
            self._reporters.append(str(name))
        return self

    # ── LLM / baseline / OpenAPI ─────────────────────────────────

    def llm(self, profile_id: str, *, enabled: bool = True) -> "Target":
        with self._lock:
            self._llm_enabled = bool(enabled)
            self._llm_profile_id = str(profile_id)
        return self

    def baseline(self, run_id: str) -> "Target":
        with self._lock:
            self._baseline_run_id = str(run_id)
        return self

    def openapi_spec(self, spec: str) -> "Target":
        with self._lock:
            self._openapi_spec = str(spec)
        return self

    # ── Free-form extras ─────────────────────────────────────────

    def extra(self, key: str, value: Any) -> "Target":
        """Attach a free-form key/value pair to ``_sdkMeta.extra``.

        Useful for forward-compat (new server fields the SDK doesn't
        know yet) and for routing reporter-specific options.
        """

        if not key:
            raise ValueError("extra key must be non-empty")
        with self._lock:
            self._extra[str(key)] = value
        return self

    # ── Snapshots ────────────────────────────────────────────────

    def snapshot(self) -> "Target":
        """Return a deep copy. Useful when building a base target and
        forking it for variant runs.
        """

        with self._lock:
            new = Target(self._name)
            # copy.deepcopy traverses everything; the lock is fresh.
            for slot in (
                "_description",
                "_namespace",
                "_source_type",
                "_strategy",
                "_max_requests",
                "_max_rps",
                "_concurrency",
                "_mutation_depth",
                "_follow_redirects",
                "_stop_on_finding",
                "_verify_findings",
                "_auth_header",
                "_response_time_alert_ms",
                "_llm_enabled",
                "_llm_profile_id",
                "_baseline_run_id",
                "_openapi_spec",
            ):
                setattr(new, slot, getattr(self, slot))
            new._endpoint = copy.deepcopy(self._endpoint)
            new._seeds = copy.deepcopy(self._seeds)
            new._mutators = list(self._mutators)
            new._assertions = list(self._assertions)
            new._duration = self._duration
            new._timeout_per_req = self._timeout_per_req
            new._custom_headers = dict(self._custom_headers)
            new._include_routes = list(self._include_routes)
            new._exclude_routes = list(self._exclude_routes)
            new._status_code_alerts = list(self._status_code_alerts)
            new._detect_patterns = list(self._detect_patterns)
            new._reporters = list(self._reporters)
            new._extra = copy.deepcopy(self._extra)
            return new

    # ── Transpile ────────────────────────────────────────────────

    def to_json(self) -> Dict[str, Any]:
        """Render to the canonical fuzz config dict.

        Delegates to :func:`mockarty.fuzz.transpile.transpile` so the
        method body stays one line — the heavy lifting (validation,
        protocol-specific options, etc.) is unit-tested in isolation.
        """

        from mockarty.fuzz.transpile import transpile  # local import = avoid cycle

        return transpile(self)

    # ── Introspection ────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def endpoint(self) -> Optional[Endpoint]:
        return self._endpoint

    @property
    def seeds_list(self) -> List[Seed]:
        return list(self._seeds)

    @property
    def mutators_list(self) -> List[Union[Mutator, CustomMutator]]:
        return list(self._mutators)

    @property
    def assertions_list(self) -> List[Assertion]:
        return list(self._assertions)

    def __repr__(self) -> str:
        return (
            f"Target(name={self._name!r}, "
            f"endpoint={self._endpoint!r}, "
            f"seeds={len(self._seeds)}, "
            f"mutators={len(self._mutators)}, "
            f"assertions={len(self._assertions)})"
        )


# Re-export `Callable` placeholder for forward-compat typing in user code.
__all__ = ["Target"]
_ = Callable  # silence "imported but unused" — kept for type-stub authors
