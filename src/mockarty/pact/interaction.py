# Copyright (c) 2026 Mockarty. All rights reserved.

"""Fluent builder for a single Pact interaction.

The builder is mutable on purpose: each chained method returns ``self``
so the user can write:

    pact.given("...") \
        .upon_receiving("...") \
        .with_request("POST", "/charge", body={...}) \
        .will_respond_with(200, body={...})

Once the consumer is started (``Consumer.start()``), the accumulated
interactions are frozen — the mock server resolves incoming requests
against them in registration order.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from mockarty.pact.types import (
    Interaction,
    ProviderState,
    RequestPart,
    ResponsePart,
)


class InteractionBuilder:
    """Fluent builder owning ONE :class:`Interaction`."""

    __slots__ = ("_it",)

    def __init__(self) -> None:
        self._it = Interaction()

    # ── State / description ─────────────────────────────────────────

    def given(self, state: str, **params: Any) -> "InteractionBuilder":
        """Append a provider state.

        V3 collapses the list to its first element on write; V4 emits
        the whole list as ``providerStates``. Calling ``given`` twice
        registers two states.
        """

        if not state:
            raise ValueError("provider state name must be non-empty")
        self._it.provider_states.append(ProviderState(name=state, params=dict(params)))
        return self

    def upon_receiving(self, description: str) -> "InteractionBuilder":
        """Set the interaction's human-readable description.

        The description is also used to derive the V4 ``key``.
        """

        self._it.description = description
        return self

    # ── Request ────────────────────────────────────────────────────

    def with_request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        body: Any = None,
    ) -> "InteractionBuilder":
        """Define the expected HTTP request.

        ``query`` values can be strings, lists, or matchers. Single
        strings are wrapped in a one-element list because Pact's
        ``query`` field is officially ``Dict[str, List[str]]``.
        """

        if not method:
            raise ValueError("method must be a non-empty string")
        if not path or not path.startswith("/"):
            raise ValueError("path must start with '/'")
        self._it.request = RequestPart(
            method=method.upper(),
            path=path,
            query=_normalise_query(query),
            headers=dict(headers or {}),
            body=body,
        )
        return self

    def with_header(self, name: str, value: str) -> "InteractionBuilder":
        """Add a single request header (chainable convenience)."""

        self._it.request.headers[name] = value
        return self

    def with_body(self, body: Any) -> "InteractionBuilder":
        """Replace the request body (useful after ``with_request`` with no body)."""

        self._it.request.body = body
        return self

    # ── Response ───────────────────────────────────────────────────

    def will_respond_with(
        self,
        status: int,
        *,
        headers: Optional[Mapping[str, str]] = None,
        body: Any = None,
    ) -> "InteractionBuilder":
        """Define the response the mock should return."""

        if not 100 <= status < 600:
            raise ValueError(
                f"HTTP status {status!r} out of range (100-599 expected)",
            )
        self._it.response = ResponsePart(
            status=status,
            headers=dict(headers or {}),
            body=body,
        )
        return self

    def with_response_header(self, name: str, value: str) -> "InteractionBuilder":
        """Add a single response header (chainable convenience)."""

        self._it.response.headers[name] = value
        return self

    def with_response_body(self, body: Any) -> "InteractionBuilder":
        """Replace the response body."""

        self._it.response.body = body
        return self

    # ── Bookkeeping ────────────────────────────────────────────────

    def pending(self, flag: bool = True) -> "InteractionBuilder":
        """Mark the interaction as V4 ``pending`` (warn-don't-fail)."""

        self._it.pending = flag
        return self

    def key(self, identifier: str) -> "InteractionBuilder":
        """Set an explicit V4 interaction key (otherwise auto-derived)."""

        self._it.key = identifier
        return self

    def build(self) -> Interaction:
        """Return the accumulated :class:`Interaction`.

        Validates that at least a path + status are set so we fail fast
        if the user forgot a builder step.
        """

        if not self._it.description:
            raise ValueError("interaction is missing `upon_receiving(...)`")
        if not self._it.request.path:
            raise ValueError("interaction is missing `with_request(...)`")
        return self._it


def _normalise_query(query: Optional[Mapping[str, Any]]) -> dict:
    """Normalise the ``query`` arg into ``Dict[str, List[str]]``."""

    if not query:
        return {}
    out: dict = {}
    for k, v in query.items():
        if isinstance(v, (list, tuple)):
            out[str(k)] = [str(x) for x in v]
        else:
            out[str(k)] = [str(v)]
    return out
