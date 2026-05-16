# Copyright (c) 2026 Mockarty. All rights reserved.

"""Seed builders for the fuzz DSL.

A :class:`Seed` is a named payload that the engine will mutate. Seeds
carry the canonical method/URL/body trio plus optional headers and
query parameters; everything not set defaults to the values configured
on the :class:`~mockarty.fuzz.dsl.Target`.

Helpers:

* ``Seed(name, payload)`` — basic constructor (payload = body string).
* ``Seed.from_file(path)`` — read body from disk; seed name = filename.
* ``Seed.bytes(name, b)`` — binary seed; encoded as latin-1 string so
  it survives JSON round-trip without corruption.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from mockarty.fuzz.types import FuzzSeedRequest


class Seed:
    """One seed corpus entry.

    Carrier object that converts to a :class:`FuzzSeedRequest` via
    :meth:`to_request`. The DSL stores ``Seed`` instances directly so
    the user can keep editing them after attaching to a target.
    """

    __slots__ = (
        "name",
        "payload",
        "method",
        "url",
        "path",
        "headers",
        "query_params",
        "path_params",
        "content_type",
    )

    def __init__(
        self,
        name: str,
        payload: Union[str, bytes, bytearray] = "",
        *,
        method: str = "",
        url: str = "",
        path: str = "",
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        path_params: Optional[Dict[str, str]] = None,
        content_type: str = "",
    ) -> None:
        if not name:
            raise ValueError("seed name must be non-empty")
        self.name = name
        if isinstance(payload, (bytes, bytearray)):
            # latin-1 is byte-preserving — it's the only safe codec for
            # arbitrary binary into a JSON string field. Server side
            # treats body as opaque bytes for mutation either way.
            self.payload = bytes(payload).decode("latin-1")
        else:
            self.payload = str(payload)
        self.method = method
        self.url = url
        self.path = path
        self.headers = dict(headers or {})
        self.query_params = dict(query_params or {})
        self.path_params = dict(path_params or {})
        self.content_type = content_type

    # ── Alternate constructors ─────────────────────────────────────

    @classmethod
    def from_file(
        cls,
        path: Union[str, os.PathLike[str]],
        *,
        name: str = "",
        content_type: str = "",
    ) -> "Seed":
        """Load a seed body from ``path``. Name defaults to the filename."""

        p = Path(path)
        data = p.read_bytes()
        seed_name = name or p.stem or p.name
        return cls(seed_name, data, content_type=content_type)

    @classmethod
    def bytes(cls, name: str, data: Union[bytes, bytearray]) -> "Seed":
        """Convenience constructor for explicit binary seeds."""

        return cls(name, bytes(data))

    # ── Transpile ──────────────────────────────────────────────────

    def to_request(
        self,
        *,
        default_method: str = "GET",
        default_url: str = "",
        default_path: str = "",
        default_content_type: str = "",
    ) -> FuzzSeedRequest:
        """Convert to wire :class:`FuzzSeedRequest`. Missing fields
        fall back to the per-target defaults provided by the caller.
        """

        return FuzzSeedRequest(
            id=self.name,
            method=(self.method or default_method or "GET").upper(),
            url=self.url or default_url,
            path=self.path or default_path,
            body=self.payload,
            content_type=self.content_type or default_content_type,
            headers=dict(self.headers),
            query_params=dict(self.query_params),
            path_params=dict(self.path_params),
        )

    # ── Introspection ──────────────────────────────────────────────

    def __repr__(self) -> str:
        preview = self.payload[:32].replace("\n", "\\n")
        if len(self.payload) > 32:
            preview += "..."
        return f"Seed(name={self.name!r}, payload={preview!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Seed):
            return NotImplemented
        return (
            self.name == other.name
            and self.payload == other.payload
            and self.method == other.method
            and self.url == other.url
            and self.path == other.path
            and self.headers == other.headers
            and self.query_params == other.query_params
            and self.path_params == other.path_params
            and self.content_type == other.content_type
        )

    def __hash__(self) -> int:
        return hash((self.name, self.payload, self.method, self.url, self.path))
