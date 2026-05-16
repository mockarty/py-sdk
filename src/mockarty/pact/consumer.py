# Copyright (c) 2026 Mockarty. All rights reserved.

"""High-level :class:`Consumer` class — the entry point of the DSL.

Usage::

    from mockarty.pact import Consumer, Like

    pact = (
        Consumer("OrderService")
        .with_provider("PaymentService")
        .with_spec_version("V4")
        .with_output_dir("./pacts")
    )

    (
        pact.given("payment service is up")
            .upon_receiving("a charge request")
            .with_request("POST", "/charge", body={"amount": Like(100)})
            .will_respond_with(200, body={"id": Like("abc")})
    )

    with pact.start() as server:
        # point your real client at server.url
        resp = requests.post(f"{server.url}/charge", json={"amount": 42})
        assert resp.status_code == 200
        # auto-verifies on ctx exit, writes pact.json to ./pacts/
"""

from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType
from typing import List, Optional, Type, Union
from warnings import warn

from mockarty.pact.interaction import InteractionBuilder
from mockarty.pact.mock_server import MockServer
from mockarty.pact.plugins import registry as plugin_registry
from mockarty.pact.types import (
    Metadata,
    Pact,
    Pacticipant,
    PactSpecification,
    PluginEntry,
    SpecVersion,
    coerce_spec_version,
)
from mockarty.pact.writer import write


class Consumer:
    """Fluent entry point. One ``Consumer`` builds one pact.json file."""

    __slots__ = (
        "_consumer_name",
        "_provider_name",
        "_spec",
        "_output_dir",
        "_interactions",
        "_filename",
        "_plugins",
        "_pending_states",
    )

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("consumer name must be non-empty")
        self._consumer_name = name
        self._provider_name = ""
        self._spec = SpecVersion.V4
        self._output_dir: Path = Path("./pacts")
        self._interactions: List[InteractionBuilder] = []
        self._filename: Optional[str] = None
        self._plugins: List[PluginEntry] = []
        self._pending_states: List[tuple] = []

    # ── Fluent configuration ───────────────────────────────────────

    def with_provider(self, name: str) -> "Consumer":
        """Set the provider this contract is *with*."""

        if not name:
            raise ValueError("provider name must be non-empty")
        self._provider_name = name
        return self

    def with_spec_version(self, version: Union[str, SpecVersion]) -> "Consumer":
        """Choose V3 (legacy) or V4 (current). Default is V4.

        Accepts the string forms ``"V3"`` / ``"v3"`` / ``"3"`` / ``"3.0.0"``
        and the V4 equivalents, plus the :class:`SpecVersion` enum.
        """

        self._spec = coerce_spec_version(version)
        return self

    def with_output_dir(self, path: Union[str, os.PathLike[str]]) -> "Consumer":
        """Directory where pact.json will be written. Created on demand."""

        self._output_dir = Path(path)
        return self

    def with_filename(self, name: str) -> "Consumer":
        """Override the default ``<consumer>-<provider>.json`` filename."""

        if not name:
            raise ValueError("filename must be non-empty")
        self._filename = name
        return self

    def with_plugin(
        self,
        name: str,
        version: str = "",
        **configuration: object,
    ) -> "Consumer":
        """Register a V4 plugin for this consumer.

        ``name`` must resolve to a plugin already in the process-wide
        :mod:`mockarty.pact.plugins.registry` — the built-ins
        (``"protobuf"`` / ``"grpc"``) are auto-registered on import,
        and user plugins must call
        :func:`mockarty.pact.plugins.registry.register` before this
        method is invoked. The plugin metadata is also persisted in
        the pact.json so a verifier can refuse to run when the named
        plugin is unavailable on its side.

        ``configuration`` is stored verbatim (Pact V4 schema allows
        arbitrary plugin-specific config) and surfaced to the plugin
        runtime through :class:`PluginEntry`.

        Falls back to a UserWarning (not an error) when the plugin name
        is unknown — that way a CI environment without the optional
        plugin can still parse the pact.json, and the test author sees
        the lookup failure but isn't blocked from authoring.
        """

        if self._spec is SpecVersion.V3:
            raise ValueError("plugins are V4-only; switch spec_version first")
        if not name or not isinstance(name, str):
            raise ValueError("plugin name must be a non-empty string")
        if version and not isinstance(version, str):
            raise TypeError("plugin version must be a string")
        runtime = plugin_registry.get(name)
        if runtime is None:
            warn(
                f"plugin {name!r} not in registry — metadata recorded but "
                "runtime validation will be skipped (call "
                "mockarty.pact.plugins.registry.register first)",
                UserWarning,
                stacklevel=2,
            )
        elif version and runtime.version and version != runtime.version:
            warn(
                f"plugin {name!r} version mismatch (requested {version!r}, "
                f"registry has {runtime.version!r}); using registered runtime",
                UserWarning,
                stacklevel=2,
            )
        self._plugins.append(
            PluginEntry(
                name=name,
                version=version or (runtime.version if runtime else ""),
                configuration=dict(configuration),
            ),
        )
        return self

    # ── Interaction creation ───────────────────────────────────────

    def given(self, state: str, **params: object) -> InteractionBuilder:
        """Start a new interaction with the given provider state.

        Returns the :class:`InteractionBuilder` so the user can chain
        ``upon_receiving`` / ``with_request`` / ``will_respond_with``.
        The interaction is appended to the consumer's list eagerly so
        forgetting to assign the return value still records the work.
        """

        builder = InteractionBuilder().given(state, **params)
        self._interactions.append(builder)
        return builder

    def upon_receiving(self, description: str) -> InteractionBuilder:
        """Start a new interaction with no provider state."""

        builder = InteractionBuilder().upon_receiving(description)
        self._interactions.append(builder)
        return builder

    def add_interaction(self) -> InteractionBuilder:
        """Lower-level entry point for users who want to build the
        interaction step-by-step without an initial ``given`` / ``upon_receiving``.
        """

        builder = InteractionBuilder()
        self._interactions.append(builder)
        return builder

    # ── Snapshot ───────────────────────────────────────────────────

    def to_pact(self) -> Pact:
        """Materialise the in-memory :class:`Pact` model (no file IO)."""

        if not self._provider_name:
            raise ValueError("provider name not set — call .with_provider(...)")
        return Pact(
            consumer=Pacticipant(name=self._consumer_name),
            provider=Pacticipant(name=self._provider_name),
            interactions=[b.build() for b in self._interactions],
            metadata=Metadata(
                pactSpecification=PactSpecification(version=self._spec.value),
                plugins=self._plugins or None,
            ),
        )

    # ── Mock server lifecycle ──────────────────────────────────────

    def start(
        self,
        host: str = "127.0.0.1",
        *,
        strict: bool = False,
    ) -> "_StartedConsumer":
        """Spin up a mock server bound to this consumer's interactions.

        Returns a :class:`_StartedConsumer` context manager that wraps
        the mock server and writes pact.json on exit.

        ``strict=True`` enables request-body validation against the
        declared matchers — any mismatch is surfaced both to the live
        HTTP client (400 with a structured envelope) and to
        :meth:`MockServer.verify` on context exit.
        """

        pact = self.to_pact()
        runtimes = {
            entry.name: runtime
            for entry in self._plugins
            for runtime in [plugin_registry.get(entry.name)]
            if runtime is not None
        }
        server = MockServer(
            pact.interactions,
            host=host,
            strict=strict,
            plugins=self._plugins,
            plugin_runtimes=runtimes,
        ).start()
        return _StartedConsumer(self, server, pact)

    # ── Writing without a mock server ──────────────────────────────

    def write(self) -> Path:
        """Write the pact.json without starting a mock server.

        Useful when the user drives consumer expectations against an
        external WireMock-style mock (e.g. Mockarty CLI) and only needs
        the contract file for publication.
        """

        return write(
            self.to_pact(),
            self._spec,
            self._output_dir,
            filename=self._filename,
        )

    # ── Introspection ──────────────────────────────────────────────

    @property
    def spec_version(self) -> SpecVersion:
        return self._spec

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    @property
    def consumer_name(self) -> str:
        return self._consumer_name

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def interactions(self) -> List[InteractionBuilder]:
        """Live list of interaction builders (mutating it is fine)."""

        return self._interactions


class _StartedConsumer:
    """Context manager returned by :meth:`Consumer.start`.

    On clean exit it calls :meth:`MockServer.verify` (raising on
    mismatch) and writes the pact.json file. On exceptional exit it
    skips verification but still stops the server and best-effort
    writes the contract so the user can inspect what was generated.
    """

    __slots__ = ("_consumer", "_server", "_pact", "_written")

    def __init__(
        self,
        consumer: Consumer,
        server: MockServer,
        pact: Pact,
    ) -> None:
        self._consumer = consumer
        self._server = server
        self._pact = pact
        self._written: Optional[Path] = None

    # Forwarded server surface ─ kept narrow on purpose so the user
    # doesn't accidentally start fiddling with internal server state.

    @property
    def url(self) -> str:
        return self._server.url

    @property
    def port(self) -> int:
        return self._server.port

    @property
    def host(self) -> str:
        return self._server.host

    @property
    def written_to(self) -> Optional[Path]:
        """Path of the pact.json written on context exit (None until then)."""

        return self._written

    def verify(self) -> None:
        """Forwarded :meth:`MockServer.verify`."""

        self._server.verify()

    def reset(self) -> None:
        """Forwarded :meth:`MockServer.reset`."""

        self._server.reset()

    def write_pact(self) -> Path:
        """Force an immediate pact.json write (also done on ctx exit)."""

        self._written = write(
            self._pact,
            self._consumer.spec_version,
            self._consumer.output_dir,
            filename=self._consumer._filename,
        )
        return self._written

    # Context manager forwarders ──────────────────────────────────

    def __enter__(self) -> "_StartedConsumer":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        try:
            if exc_type is None:
                self._server.verify()
                self.write_pact()
            else:
                # Best-effort write so the user can see what was captured
                # — swallow any IO error so it doesn't mask the original.
                try:
                    self.write_pact()
                except Exception:  # pragma: no cover — defensive
                    pass
        finally:
            self._server.stop()
