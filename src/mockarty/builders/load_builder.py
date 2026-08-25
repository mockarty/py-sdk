# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Fluent load-test builder DSL.

Describe a load test in idiomatic Python and emit either a k6-compatible
JavaScript script or a perf-config JSON object that ``mockarty-cli perf run``
runs locally (and that the server's ``/api/v1/perf`` endpoints accept too).

Example
-------
::

    from mockarty import LoadTest

    profile = (
        LoadTest("checkout-load")
        .target("https://api.example.com")
        .get("/health")
        .post("/cart", body={"sku": "abc"})
        .stages([("30s", 50), ("1m", 50), ("10s", 0)])
        .threshold("http_req_duration", "p(95)<800")
        .threshold("http_req_failed", "rate<0.01")
        .think_time(0.5)
    )

    # Run it locally via the CLI:
    profile.save("checkout.json")
    #   $ mockarty-cli perf run --from-config checkout.json

    # Or submit to a Mockarty server through the SDK:
    client.perf.run(profile.to_perf_config())

The builder is a thin, pleasant wrapper around the existing perf engine — it
does NOT run anything itself. ``to_k6_script()`` produces a string the engine's
k6-compat loader accepts; ``to_perf_config()`` produces the
:class:`~mockarty.models.common.PerfConfig`-shaped dict the CLI ``--from-config``
flag and the server endpoints consume.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Union

__all__ = ["LoadTest", "LoadRequest"]

# A stage is (duration, target-VUs); duration is a k6-style string ("30s",
# "1m"). Accept a (duration, target) tuple or a dict for ergonomics.
StageInput = Union[tuple[str, int], dict[str, Any]]


class LoadRequest:
    """One HTTP request in the load scenario's iteration body."""

    __slots__ = ("method", "path", "body", "headers", "checks")

    def __init__(
        self,
        method: str,
        path: str,
        body: Optional[Union[str, dict[str, Any], list[Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.method = method.upper()
        self.path = path
        self.body = body
        self.headers = headers or {}
        # List of (name, expr) per-request k6 checks. When non-empty they
        # replace the default `status < 400` assertion.
        self.checks: list[tuple[str, str]] = []


def _js_str(s: str) -> str:
    """Quote a string as a JS template/literal-safe single-quoted literal."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


class LoadTest:
    """Fluent builder for a load test.

    All mutators return ``self`` for chaining. The terminal methods are
    :meth:`to_k6_script`, :meth:`to_perf_config`, :meth:`to_json` and
    :meth:`save`.
    """

    def __init__(self, name: str = "load-test") -> None:
        self._name = name
        self._base_url: Optional[str] = None
        self._requests: list[LoadRequest] = []
        self._stages: list[dict[str, Any]] = []
        self._vus: Optional[int] = None
        self._duration: Optional[str] = None
        self._rps: Optional[int] = None
        self._max_vus: Optional[int] = None
        self._thresholds: dict[str, list[str]] = {}
        self._env: dict[str, str] = {}
        self._think: Optional[float] = None

    # -- target / requests ---------------------------------------------------

    def target(self, base_url: str) -> "LoadTest":
        """Set the base URL. Request paths are joined onto it.

        The base URL is exposed to the script as ``__ENV.BASE_URL`` so the
        same scenario can be re-pointed at staging/prod without re-emitting.
        """
        self._base_url = base_url.rstrip("/")
        self._env.setdefault("BASE_URL", self._base_url)
        return self

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Union[str, dict[str, Any], list[Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> "LoadTest":
        """Append an arbitrary request to the iteration body."""
        self._requests.append(LoadRequest(method, path, body, headers))
        return self

    def get(self, path: str, headers: Optional[dict[str, str]] = None) -> "LoadTest":
        return self.request("GET", path, headers=headers)

    def post(
        self,
        path: str,
        body: Optional[Union[str, dict[str, Any], list[Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> "LoadTest":
        return self.request("POST", path, body=body, headers=headers)

    def put(
        self,
        path: str,
        body: Optional[Union[str, dict[str, Any], list[Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> "LoadTest":
        return self.request("PUT", path, body=body, headers=headers)

    def patch(
        self,
        path: str,
        body: Optional[Union[str, dict[str, Any], list[Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> "LoadTest":
        return self.request("PATCH", path, body=body, headers=headers)

    def delete(self, path: str, headers: Optional[dict[str, str]] = None) -> "LoadTest":
        return self.request("DELETE", path, headers=headers)

    def check(self, name: str, expr: str) -> "LoadTest":
        """Attach a named assertion to the MOST RECENTLY added request. ``name``
        is the check label; ``expr`` is a JavaScript boolean expression that may
        reference the response as ``res`` (e.g. ``res.json().id !== undefined``).
        When a request has one or more checks they REPLACE the default
        ``status < 400`` check. No-op if no request has been added yet."""
        if self._requests:
            self._requests[-1].checks.append((name, expr))
        return self

    def expect_status(self, code: int) -> "LoadTest":
        """Shorthand for :meth:`check` asserting the response status code."""
        return self.check(f"status is {code}", f"res.status === {code}")

    # -- load profile --------------------------------------------------------

    def vus(self, n: int) -> "LoadTest":
        """Set a constant virtual-user count (ignored when stages are set)."""
        self._vus = n
        return self

    def duration(self, d: str) -> "LoadTest":
        """Set a constant run duration ("30s", "5m"); ignored with stages."""
        self._duration = d
        return self

    def rps(self, n: int) -> "LoadTest":
        """Target a steady requests-per-second rate (arrival-rate mode)."""
        self._rps = n
        return self

    def max_vus(self, n: int) -> "LoadTest":
        """Cap concurrent VUs (mostly relevant in RPS / arrival-rate mode)."""
        self._max_vus = n
        return self

    def stage(self, duration: str, target: int) -> "LoadTest":
        """Append one ramp stage: reach ``target`` VUs over ``duration``."""
        self._stages.append({"duration": duration, "target": int(target)})
        return self

    def stages(self, stages: list[StageInput]) -> "LoadTest":
        """Set the full ramp profile, replacing any prior stages.

        Each entry is a ``(duration, target)`` tuple or a
        ``{"duration": ..., "target": ...}`` dict.
        """
        self._stages = []
        for s in stages:
            if isinstance(s, dict):
                self._stages.append(
                    {"duration": str(s["duration"]), "target": int(s.get("target", 0))}
                )
            else:
                duration, target = s
                self._stages.append({"duration": str(duration), "target": int(target)})
        return self

    # -- thresholds / env ----------------------------------------------------

    def threshold(self, metric: str, expr: str) -> "LoadTest":
        """Add a pass/fail threshold expression on a metric.

        e.g. ``.threshold("http_req_duration", "p(95)<500")``.
        """
        self._thresholds.setdefault(metric, []).append(expr)
        return self

    def thresholds(self, thresholds: dict[str, Union[str, list[str]]]) -> "LoadTest":
        """Set thresholds in bulk; values may be a single expr or a list."""
        for metric, exprs in thresholds.items():
            if isinstance(exprs, str):
                exprs = [exprs]
            self._thresholds[metric] = list(exprs)
        return self

    def env(self, **kwargs: str) -> "LoadTest":
        """Add environment variables, exposed as ``__ENV.<KEY>`` in the script."""
        for k, v in kwargs.items():
            self._env[k] = str(v)
        return self

    def think_time(self, seconds: float) -> "LoadTest":
        """Add a ``sleep(seconds)`` at the end of each iteration."""
        self._think = float(seconds)
        return self

    # -- emit ----------------------------------------------------------------

    def _resolved_requests(self) -> list[LoadRequest]:
        if self._requests:
            return self._requests
        # A target with no explicit requests defaults to a single GET / — the
        # simplest useful smoke load.
        return [LoadRequest("GET", "/")]

    def to_k6_script(self) -> str:
        """Emit a k6-compatible JS script with ``export const options``.

        The script imports ``k6/http`` + ``k6`` (the engine's k6-compat loader
        rewrites these), encodes the load profile in ``options``, and issues
        each configured request inside ``export default function``.
        """
        lines: list[str] = [
            "import http from 'k6/http';",
            "import { check, sleep } from 'k6';",
            "",
            "export const options = " + self._options_js() + ";",
            "",
        ]
        # Bake the target() base URL as a runnable default so the exported
        # script works out of the box (matching the perf engine's own builder
        # pattern), while staying overridable via `-e BASE_URL=...` / __ENV.
        if self._base_url is not None:
            lines.append(f"const BASE_URL = __ENV.BASE_URL || {_js_str(self._base_url)};")
            lines.append("")
        lines += [
            "export default function () {",
            "  let r;",
        ]
        for req in self._resolved_requests():
            lines.extend(self._request_js(req))
        if self._think is not None:
            lines.append(f"  sleep({self._think});")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    def _options_js(self) -> str:
        opts: dict[str, Any] = {}
        if self._stages:
            opts["stages"] = self._stages
        else:
            if self._vus is not None:
                opts["vus"] = self._vus
            if self._duration is not None:
                opts["duration"] = self._duration
        if self._rps is not None:
            opts["rps"] = self._rps
        if self._max_vus is not None:
            opts["maxVUs"] = self._max_vus
        if self._thresholds:
            opts["thresholds"] = self._thresholds
        if not opts:
            opts = {"vus": 1, "duration": "30s"}
        return json.dumps(opts, separators=(",", ":"))

    def _request_js(self, req: LoadRequest) -> list[str]:
        # URL: ${BASE_URL}/path when a base URL is set, else literal.
        path = req.path
        if self._base_url is not None and not path.startswith("http"):
            if path and not path.startswith("/"):
                path = "/" + path
            url = "`${BASE_URL}" + path + "`"
        else:
            url = _js_str(path)

        params_parts: list[str] = []
        headers = dict(req.headers)
        if isinstance(req.body, (dict, list)) and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        if headers:
            hdr = ", ".join(f"{_js_str(k)}: {_js_str(v)}" for k, v in headers.items())
            params_parts.append("headers: {" + hdr + "}")
        params = "{" + ", ".join(params_parts) + "}" if params_parts else None

        method = req.method.lower()
        out: list[str] = []
        if req.body is None:
            if params:
                out.append(f"  r = http.{method}({url}, null, {params});")
            else:
                out.append(f"  r = http.{method}({url});")
        else:
            if isinstance(req.body, (dict, list)):
                # Compact separators keep the emitted body byte-identical to the
                # Go/Java SDKs ({"amount":100}, not {"amount": 100}).
                body_lit = _js_str(json.dumps(req.body, separators=(",", ":")))
            else:
                body_lit = _js_str(str(req.body))
            if params:
                out.append(f"  r = http.{method}({url}, {body_lit}, {params});")
            else:
                out.append(f"  r = http.{method}({url}, {body_lit});")
        out.append(self._check_js(req.checks))
        return out

    @staticmethod
    def _check_js(checks: list[tuple[str, str]]) -> str:
        """Emit the k6 ``check(r, { ... })`` line for a request. With no custom
        checks it emits the default ``status < 400`` assertion (backward
        compatible); otherwise every custom check in insertion order. Kept
        byte-identical across the Go/Python/Java SDKs."""
        if not checks:
            return "  check(r, { 'status < 400': (res) => res.status < 400 });"
        parts = [f"{_js_str(name)}: (res) => {expr}" for name, expr in checks]
        return "  check(r, { " + ", ".join(parts) + " });"

    def to_perf_config(self) -> dict[str, Any]:
        """Emit the perf-config dict consumed by the CLI ``--from-config`` flag
        and the server ``/api/v1/perf`` endpoints.

        Carries the full profile (script + vus/duration/stages/thresholds/
        environment) so a staged ramp survives the round-trip — unlike a bare
        script, whose profile would otherwise live only in CLI flags.
        """
        cfg: dict[str, Any] = {
            "name": self._name,
            "script": self.to_k6_script(),
        }
        if self._stages:
            cfg["stages"] = list(self._stages)
        else:
            if self._vus is not None:
                cfg["vus"] = self._vus
            if self._duration is not None:
                cfg["duration"] = self._duration
        if self._rps is not None:
            cfg["rps"] = self._rps
        if self._max_vus is not None:
            cfg["maxVUs"] = self._max_vus
        if self._thresholds:
            cfg["thresholds"] = {k: list(v) for k, v in self._thresholds.items()}
        if self._env:
            cfg["environment"] = dict(self._env)
        return cfg

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Serialize :meth:`to_perf_config` to a JSON string."""
        return json.dumps(self.to_perf_config(), indent=indent)

    def save(self, path: str, *, indent: Optional[int] = 2) -> str:
        """Write the perf-config JSON to ``path``; return the path.

        Run it with ``mockarty-cli perf run --from-config <path>``.
        """
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json(indent=indent))
        return path
