# Copyright (c) 2026 Mockarty. All rights reserved.

"""Ephemeral threaded HTTP mock server bound to a Pact contract.

The server is intentionally minimal — it is NOT a generic mock server
(that's CLI / admin's job). It only serves the interactions registered
on the parent :class:`Consumer` and only for the duration of a single
test. When the test exits, the consumer writes the pact.json and shuts
the server down.

Stdlib-only on purpose (``http.server`` + ``threading``) so the SDK
doesn't pull aiohttp / starlette into every user project.

Concurrency model
-----------------

* One ``ThreadingHTTPServer`` per ``Consumer.start()`` call.
* Each request is matched against the interaction list in registration
  order; the first match wins. Match counts are tracked so
  :meth:`verify` can fail when an interaction was registered but never
  hit, OR when an unexpected request arrived.
* ``verify`` is thread-safe — the request handler updates the match
  state under a lock. The pact.json file is only written from the
  thread that called ``stop()``, never from the handler.

Strict mode
-----------

When the server is started with ``strict=True`` the handler also walks
the incoming request body through the matchers declared on the
interaction. Any structural / regex / bounds violation is recorded as
a :class:`mockarty.pact.matchers.Mismatch` and surfaced both to the
client (HTTP 400 with a structured JSON envelope) and to
:meth:`verify` (joined into a :class:`PactMismatchError`).

Plugin negotiation
------------------

If the parent ``Consumer`` registered V4 plugins via ``with_plugin``,
the handler dispatches to the registered :class:`Plugin` for the
matching ``Content-Type`` before falling back to the default JSON path.
Plugins are pure-Python adapters (see :mod:`mockarty.pact.plugins`) —
they never invoke native Pact FFI.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlsplit

from mockarty.pact.matchers import Matcher, Mismatch, _validate_value
from mockarty.pact.types import Interaction, PluginEntry


class PactMismatchError(AssertionError):
    """Raised by :meth:`MockServer.verify` when expectations don't match.

    Inherits from ``AssertionError`` so pytest treats it like a normal
    failing assertion (no need for ``pytest.fails`` wrapping).
    """


def _resolve_matchers(body: Any) -> Any:
    """Replace any matcher sentinels inside ``body`` with their example
    values so the mock server returns concrete JSON to the client.
    """

    if isinstance(body, Matcher):
        return _resolve_matchers(body.example)
    if isinstance(body, dict):
        return {k: _resolve_matchers(v) for k, v in body.items()}
    if isinstance(body, list):
        return [_resolve_matchers(v) for v in body]
    return body


def _match_request(
    interaction: Interaction,
    method: str,
    path: str,
    query: Dict[str, List[str]],
) -> bool:
    """Return True if the live request matches the expected interaction.

    Phase 1: method + path must match exactly, query keys must be a
    subset (the user may send extras at their own risk — this is
    consistent with pact-python's permissive default). Body matching is
    NOT done at request-time because the verifier handles it; the
    consumer mock is here so the user's HTTP client gets a real
    response, not to enforce the contract.
    """

    if interaction.request.method.upper() != method.upper():
        return False
    if interaction.request.path != path:
        return False
    for expected_k, expected_vals in interaction.request.query.items():
        actual = query.get(expected_k)
        if actual is None:
            return False
        # Resolve any matchers in the expected values.
        for ev in expected_vals:
            ev_resolved = _resolve_matchers(ev)
            if ev_resolved not in actual and str(ev_resolved) not in actual:
                return False
    return True


def _parse_request_body(headers: Dict[str, str], raw: bytes) -> Tuple[Any, str]:
    """Decode the incoming body using its Content-Type.

    Returns ``(decoded, content_type)``. Decode failures fall back to
    the raw bytes so downstream strict matching can still produce a
    structured mismatch instead of crashing.
    """

    ct = ""
    for k, v in headers.items():
        if k.lower() == "content-type":
            ct = str(v).split(";", 1)[0].strip().lower()
            break
    if not raw:
        return None, ct
    if "json" in ct or ct == "":
        try:
            return json.loads(raw.decode("utf-8")), ct or "application/json"
        except (UnicodeDecodeError, json.JSONDecodeError):
            return raw, ct
    if ct.startswith("text/") or ct.endswith("+xml") or ct == "application/xml":
        try:
            return raw.decode("utf-8"), ct
        except UnicodeDecodeError:
            return raw, ct
    return raw, ct


class _State:
    """Mutable state shared between the server thread and the test."""

    __slots__ = ("lock", "interactions", "hits", "misses", "strict_failures", "strict")

    def __init__(self, interactions: List[Interaction], strict: bool) -> None:
        self.lock = threading.Lock()
        self.interactions = list(interactions)
        self.hits: List[int] = [0] * len(interactions)
        # ``misses`` records (method, path, query) of requests we couldn't match.
        self.misses: List[Tuple[str, str, str]] = []
        # ``strict_failures`` collects (interaction_idx, mismatches) tuples
        # so verify() can surface the full picture.
        self.strict_failures: List[Tuple[int, List[Mismatch]]] = []
        self.strict = strict


def _make_handler(
    state: _State,
    plugins: Sequence[PluginEntry],
    plugin_runtimes: Dict[str, Any],
) -> type:
    """Build a request handler bound to ``state``. We use a closure so
    each ``MockServer`` instance has its own handler class without
    leaking global state across parallel tests.

    ``plugin_runtimes`` is a name→:class:`Plugin` map. The handler picks
    the first plugin whose ``supported_content_types`` includes the
    incoming Content-Type and delegates request validation +
    response generation to it.
    """

    # Build content-type → plugin lookup once.
    ct_map: Dict[str, Any] = {}
    for entry in plugins:
        runtime = plugin_runtimes.get(entry.name)
        if runtime is None:
            continue
        for ct in runtime.supported_content_types:
            ct_map[ct.lower()] = runtime

    class Handler(BaseHTTPRequestHandler):
        # Silence the default per-request stderr log so test output stays clean.
        def log_message(self, *_args: Any, **_kwargs: Any) -> None:  # noqa: D401
            return

        def _send_error_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve(self, method: str) -> None:
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            length = int(self.headers.get("Content-Length") or 0)
            raw_body = self.rfile.read(length) if length else b""
            req_headers = {k: v for k, v in self.headers.items()}

            with state.lock:
                idx = next(
                    (
                        i
                        for i, it in enumerate(state.interactions)
                        if _match_request(it, method, parsed.path, query)
                    ),
                    -1,
                )
                if idx < 0:
                    state.misses.append((method, parsed.path, parsed.query))
                    self._send_error_json(
                        500,
                        {
                            "error": "no matching pact interaction",
                            "method": method,
                            "path": parsed.path,
                        },
                    )
                    return
                interaction = state.interactions[idx]
                strict = state.strict

            # Strict body / plugin validation runs outside the state lock
            # so a slow regex doesn't serialise other in-flight requests.
            if strict and interaction.request.body is not None:
                plugin_runtime = ct_map.get(
                    _content_type_of(req_headers).lower(),
                )
                if plugin_runtime is not None:
                    mismatches = plugin_runtime.match_request(
                        expected=interaction.request.body,
                        actual=raw_body,
                        headers=req_headers,
                    )
                else:
                    decoded, _ct = _parse_request_body(req_headers, raw_body)
                    mismatches = _validate_value(
                        interaction.request.body,
                        decoded,
                        "$.body",
                    )
                if mismatches:
                    with state.lock:
                        state.strict_failures.append((idx, mismatches))
                    self._send_error_json(
                        400,
                        {
                            "error": "strict pact mismatch",
                            "method": method,
                            "path": parsed.path,
                            "mismatches": [
                                {
                                    "path": m.path,
                                    "expected": m.expected,
                                    "actual": m.actual,
                                }
                                for m in mismatches
                            ],
                        },
                    )
                    return

            with state.lock:
                state.hits[idx] += 1
                response = state.interactions[idx].response

            # Plugin-driven response generation (if any plugin handles the
            # response Content-Type).
            response_ct = ""
            for k, v in response.headers.items():
                if k.lower() == "content-type":
                    response_ct = str(v).split(";", 1)[0].strip().lower()
                    break
            response_plugin = ct_map.get(response_ct)
            if response_plugin is not None:
                payload, response_headers = response_plugin.generate_response(
                    template=response.body,
                    headers=dict(response.headers),
                )
                self.send_response(response.status)
                for k, v in response_headers.items():
                    self.send_header(k, str(v))
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)
                return

            resolved_body = _resolve_matchers(response.body)
            payload: bytes
            if resolved_body is None:
                payload = b""
            elif isinstance(resolved_body, (dict, list)):
                payload = json.dumps(resolved_body, ensure_ascii=False).encode("utf-8")
            elif isinstance(resolved_body, bytes):
                payload = resolved_body
            else:
                payload = str(resolved_body).encode("utf-8")

            self.send_response(response.status)
            # Make sure Content-Type defaults to JSON when the body is
            # structured; user-supplied headers always win.
            sent_ct = False
            for k, v in response.headers.items():
                self.send_header(k, str(v))
                if k.lower() == "content-type":
                    sent_ct = True
            if not sent_ct and isinstance(resolved_body, (dict, list)):
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 — stdlib API
            self._serve("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._serve("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._serve("PUT")

        def do_DELETE(self) -> None:  # noqa: N802
            self._serve("DELETE")

        def do_PATCH(self) -> None:  # noqa: N802
            self._serve("PATCH")

        def do_HEAD(self) -> None:  # noqa: N802
            self._serve("HEAD")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._serve("OPTIONS")

    return Handler


def _content_type_of(headers: Dict[str, str]) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return str(v).split(";", 1)[0].strip()
    return ""


class MockServer:
    """Threaded ephemeral mock server.

    Use either as a context manager:

        with MockServer(interactions) as server:
            requests.post(server.url, ...)
            server.verify()

    or manually via :meth:`start` / :meth:`stop`. The context-manager
    form is the recommended one — it calls ``verify`` automatically on
    a clean exit and re-raises mismatches.

    Parameters
    ----------
    interactions:
        The list of expected interactions (each with optional matchers
        in its request/response body).
    host:
        Interface to bind. ``127.0.0.1`` by default (avoids IPv6
        resolution differences across CI runners).
    strict:
        When ``True``, the handler validates each incoming request
        body against the interaction's matchers and returns HTTP 400
        on mismatch. The mismatches are also collected and surfaced
        via :meth:`verify`. Off by default — the legacy mode just
        echoes the response.
    plugins:
        Optional sequence of :class:`PluginEntry` declarations + the
        backing runtime registry. The handler delegates to a plugin
        when an incoming / outgoing ``Content-Type`` matches.
    """

    __slots__ = (
        "_interactions",
        "_host",
        "_state",
        "_server",
        "_thread",
        "_plugins",
        "_plugin_runtimes",
    )

    def __init__(
        self,
        interactions: List[Interaction],
        host: str = "127.0.0.1",
        *,
        strict: bool = False,
        plugins: Optional[Sequence[PluginEntry]] = None,
        plugin_runtimes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._interactions = interactions
        self._host = host
        self._state = _State(interactions, strict=strict)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._plugins: List[PluginEntry] = list(plugins or [])
        self._plugin_runtimes: Dict[str, Any] = dict(plugin_runtimes or {})

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> "MockServer":
        """Bind a free port and start serving in a background thread."""

        if self._server is not None:
            raise RuntimeError("MockServer already started")
        handler_cls = _make_handler(self._state, self._plugins, self._plugin_runtimes)
        # Port 0 → OS picks a free port.
        self._server = ThreadingHTTPServer((self._host, 0), handler_cls)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"pact-mock-{self.port}",
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Shut down the server. Safe to call multiple times."""

        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._server = None
        self._thread = None

    # ── Public surface ─────────────────────────────────────────────

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("MockServer not started")
        return self._server.server_address[1]

    @property
    def host(self) -> str:
        return self._host

    @property
    def url(self) -> str:
        """Base URL the user points their HTTP client at."""

        return f"http://{self.host}:{self.port}"

    @property
    def strict(self) -> bool:
        return self._state.strict

    # ── Verification ───────────────────────────────────────────────

    def verify(self) -> None:
        """Assert all expectations met. Raises :class:`PactMismatchError`."""

        with self._state.lock:
            unhit = [
                it.description
                for it, n in zip(self._state.interactions, self._state.hits)
                if n == 0
            ]
            misses = list(self._state.misses)
            strict_failures = list(self._state.strict_failures)
        problems: List[str] = []
        if unhit:
            problems.append("unhit interactions: " + ", ".join(repr(d) for d in unhit))
        if misses:
            shown = ", ".join(f"{m[0]} {m[1]}" for m in misses[:5])
            more = f" (+{len(misses) - 5} more)" if len(misses) > 5 else ""
            problems.append(f"unmatched requests: {shown}{more}")
        if strict_failures:
            lines: List[str] = []
            for idx, mms in strict_failures:
                desc = (
                    self._state.interactions[idx].description
                    if 0 <= idx < len(self._state.interactions)
                    else f"#{idx}"
                )
                for m in mms:
                    lines.append(
                        f"  - [{desc}] {m.path}: expected {m.expected}, got {m.actual!r}",
                    )
            problems.append("strict mismatches:\n" + "\n".join(lines))
        if problems:
            raise PactMismatchError("; ".join(problems))

    def reset(self) -> None:
        """Clear hit counts + misses (useful between sub-tests sharing one server)."""

        with self._state.lock:
            self._state.hits = [0] * len(self._state.interactions)
            self._state.misses.clear()
            self._state.strict_failures.clear()

    @property
    def mismatches(self) -> List[Mismatch]:
        """Snapshot of every strict mismatch seen so far (read-only)."""

        with self._state.lock:
            out: List[Mismatch] = []
            for _idx, mms in self._state.strict_failures:
                out.extend(mms)
            return out

    # ── Context manager ────────────────────────────────────────────

    def __enter__(self) -> "MockServer":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if exc_type is None:
                # Only verify on a clean exit — if the user's code already
                # failed, re-raising a Pact mismatch on top would just
                # obscure the original error.
                self.verify()
        finally:
            self.stop()
