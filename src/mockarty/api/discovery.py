# Copyright (c) 2026 Mockarty. All rights reserved.

"""Test-discovery sync API for the Mockarty TCM catalogue.

Where :mod:`mockarty.api.external_runs` ingests per-test *results*, this
module ingests a manifest of the *full* test inventory an SDK/CI adapter
knows about (including tests that did not run), so the TCM catalogue
mirrors the code base.

What the server does with a manifest (see
``internal/tcm/discovery/discovery.go``):

* New tests (matched by ``fullName``) are created.
* Existing tests keep their human-authored metadata; only the discovery
  stamp (state / source / source-ref) is refreshed.
* When ``prune_missing`` is true, discovered tests for the same ``source``
  that are absent from the manifest are marked *orphaned* (never deleted).

Identity reuses the same ``external_full_name`` column as external-runs
(migration 321), so a test discovered here and later executed via
``/tcm/external-runs`` lands on the same case.

The wire shape is defined server-side in
``internal/tcm/discovery/discovery.go`` (``Manifest`` / ``ManifestCase`` /
``SyncResult``). This module is the typed Python facade. Field names use
camelCase to match the Go struct's JSON tags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Union
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase

# A single case in a discovery manifest can be supplied either as a
# ``DiscoveryCase`` dataclass or as a plain mapping already in (or close
# to) the wire shape — both are normalised by ``_build_case``.
CaseLike = Union["DiscoveryCase", Mapping[str, Any]]


@dataclass
class DiscoveryCase:
    """One test the adapter reported at collection time.

    Mirrors the server's ``ManifestCase``. ``full_name`` is the only
    required field — it is the deterministic per-test identity used to
    match a discovered test across syncs and to later execution results.
    """

    full_name: str
    name: str = ""
    suite: str = ""
    description: str = ""
    source_ref: str = ""
    labels: Optional[list[str]] = None


@dataclass
class SyncResult:
    """Per-sync summary returned by ``POST /tcm/discovery``.

    Mirrors the server's ``SyncResult`` (all fields lowercase on the
    wire). ``raw`` retains the unparsed envelope for forward-compat with
    server-side additions.
    """

    source: str
    created: int
    updated: int
    orphaned: int
    total: int
    raw: dict[str, Any]

    @classmethod
    def from_response(cls, body: Optional[dict[str, Any]]) -> "SyncResult":
        """Parse a server response envelope into a :class:`SyncResult`.

        Tolerant of a missing / empty body (returns a zeroed result) and
        of unexpected non-int counts (coerced via ``int`` with a 0
        fallback) so a slightly-off server build never raises here.
        """
        body = body or {}

        def _int(key: str) -> int:
            try:
                return int(body.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0

        return cls(
            source=str(body.get("source", "") or ""),
            created=_int("created"),
            updated=_int("updated"),
            orphaned=_int("orphaned"),
            total=_int("total"),
            raw=dict(body),
        )


def _ns_path(namespace: str) -> str:
    """Return the namespace-scoped ``/tcm/discovery`` path.

    Namespaces are URL-quoted so a user-supplied value with slashes or
    other reserved characters cannot inject path segments — the server
    already validates the slug, but the SDK should be defensive.
    """
    if not namespace:
        raise ValueError("namespace is required")
    return f"/api/v1/namespaces/{quote(namespace, safe='')}/tcm/discovery"


def _build_case(case: CaseLike) -> dict[str, Any]:
    """Normalise one case into the wire shape (camelCase keys).

    Accepts a :class:`DiscoveryCase` or a mapping. A mapping may use
    either snake_case (``full_name``/``source_ref``) or the wire
    camelCase (``fullName``/``sourceRef``) keys. ``fullName`` is required
    and must be non-empty.
    """
    if isinstance(case, DiscoveryCase):
        full_name = case.full_name
        name = case.name
        suite = case.suite
        description = case.description
        source_ref = case.source_ref
        labels = case.labels
    elif isinstance(case, Mapping):
        full_name = case.get("full_name") or case.get("fullName") or ""
        name = case.get("name") or ""
        suite = case.get("suite") or ""
        description = case.get("description") or ""
        source_ref = case.get("source_ref") or case.get("sourceRef") or ""
        labels = case.get("labels")
    else:
        raise TypeError("case must be a DiscoveryCase or a mapping")

    full_name = (full_name or "").strip()
    if not full_name:
        raise ValueError("every case requires a non-empty full_name / fullName")

    out: dict[str, Any] = {"fullName": full_name}
    # ``name`` has no omitempty on the wire; the server falls back to
    # fullName when empty, so we only send it when meaningfully set.
    if name:
        out["name"] = name
    if suite:
        out["suite"] = suite
    if description:
        out["description"] = description
    if source_ref:
        out["sourceRef"] = source_ref
    if labels:
        out["labels"] = [str(lbl) for lbl in labels]
    return out


def _build_manifest(
    *,
    source: str,
    cases: Iterable[CaseLike],
    framework: Optional[str],
    prune_missing: bool,
) -> dict[str, Any]:
    """Assemble the manifest body. ``source`` is required."""
    if not source or not str(source).strip():
        raise ValueError("source is required")
    payload: dict[str, Any] = {
        "source": str(source).strip(),
        "cases": [_build_case(c) for c in cases],
    }
    if framework:
        payload["framework"] = framework
    if prune_missing:
        payload["pruneMissing"] = True
    return payload


class DiscoveryAPI(SyncAPIBase):
    """Sync client for ``POST /tcm/discovery``."""

    def sync(
        self,
        *,
        source: str,
        cases: Iterable[CaseLike],
        framework: Optional[str] = None,
        prune_missing: bool = False,
        namespace: Optional[str] = None,
    ) -> SyncResult:
        """Sync a test-discovery manifest into the TCM catalogue.

        Args:
            source: scope key identifying this manifest's origin (e.g.
                ``"pytest:auth-suite"``). Pruning is scoped to a single
                source, so one suite's manifest never orphans another's
                cases. **Required.**
            cases: the full inventory the adapter knows about. Each item
                is a :class:`DiscoveryCase` or a mapping; every case
                requires a non-empty ``full_name`` / ``fullName``.
            framework: informational framework label (``pytest`` / ``junit`` / ...).
            prune_missing: when True, discovered cases for ``source`` that
                are absent from ``cases`` are marked orphaned (never
                deleted). When False the sync is additive only.
            namespace: target Mockarty namespace (falls back to the
                client default).

        Returns:
            A :class:`SyncResult` with ``source`` / ``created`` /
            ``updated`` / ``orphaned`` / ``total`` counts.
        """
        ns = namespace or self._namespace
        body = _build_manifest(
            source=source,
            cases=cases,
            framework=framework,
            prune_missing=prune_missing,
        )
        resp = self._request("POST", _ns_path(ns), json=body)
        return SyncResult.from_response(resp.json() if resp.content else {})


class AsyncDiscoveryAPI(AsyncAPIBase):
    """Async counterpart of :class:`DiscoveryAPI`."""

    async def sync(
        self,
        *,
        source: str,
        cases: Iterable[CaseLike],
        framework: Optional[str] = None,
        prune_missing: bool = False,
        namespace: Optional[str] = None,
    ) -> SyncResult:
        """Async counterpart of :meth:`DiscoveryAPI.sync`."""
        ns = namespace or self._namespace
        body = _build_manifest(
            source=source,
            cases=cases,
            framework=framework,
            prune_missing=prune_missing,
        )
        resp = await self._request("POST", _ns_path(ns), json=body)
        return SyncResult.from_response(resp.json() if resp.content else {})
