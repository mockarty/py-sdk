# Copyright (c) 2026 Mockarty. All rights reserved.

"""pytest plugin: sync the collected test inventory to Mockarty TCM.

Where the main result-reporting plugin (``mockarty.testing.plugin``)
uploads per-test *outcomes* via ``/tcm/external-runs``, this plugin ships
the full *inventory* of collected tests to ``/tcm/discovery`` so the TCM
catalogue mirrors the code base — including tests that were deselected,
skipped, or simply not run this session.

Opt-in:
    Discovery is gated behind the ``--mockarty-discover`` flag (or the
    ``MOCKARTY_DISCOVER=1`` env var). When neither is set the plugin is a
    pure no-op — it never touches the network and never slows collection.

What it sends (on ``pytest_collection_finish``):
    * ``fullName``  ← ``item.nodeid`` (the deterministic pytest identity).
    * ``name``      ← ``item.name``.
    * ``sourceRef`` ← ``item.location`` → ``"file:line"``.
    * ``suite``     ← the test's class name, else its module name.
    * ``labels``    ← the test's own marker names (own markers only — the
      ``parametrize`` / ``usefixtures`` / ``skip`` / ``skipif`` /
      ``xfail`` builtins are filtered out as noise).

Configuration (CLI flag wins over the ini option wins over the env var):
    * ``--mockarty-discover`` / ``MOCKARTY_DISCOVER`` — enable.
    * ``--mockarty-discover-source`` / ini ``mockarty_discover_source`` /
      ``MOCKARTY_DISCOVER_SOURCE`` — the manifest's ``source`` scope key.
      Defaults to ``pytest:<rootdir-name>``.
    * ``--mockarty-discover-prune`` / ``MOCKARTY_DISCOVER_PRUNE`` — set
      ``pruneMissing=True`` so tests removed from the code (absent from
      this manifest) are orphaned.
    * Base URL / API key / namespace flow through the same env vars the
      rest of the SDK uses (``MOCKARTY_BASE_URL`` / ``MOCKARTY_API_KEY`` /
      ``MOCKARTY_NAMESPACE``) and an optional ``mockarty_client`` fixture
      is *not* consulted here because collection-finish has no per-test
      fixture context.

Fail-soft policy:
    Any HTTP / config error is logged via :mod:`warnings` and swallowed —
    discovery must never fail a test session.

Activation:
    Auto-loaded via a dedicated ``pytest11`` entry point in
    ``pyproject.toml`` alongside the result-reporting plugin; the flag
    keeps it dormant until the user asks for it.
"""

from __future__ import annotations

import os
import warnings
from typing import Any, Optional

import pytest

# Marker names that are pytest/builtin plumbing rather than meaningful
# test labels — filtered out of the discovery ``labels`` list.
_BUILTIN_MARKERS = frozenset(
    {
        "parametrize",
        "usefixtures",
        "skip",
        "skipif",
        "xfail",
        "filterwarnings",
        "tryfirst",
        "trylast",
        "asyncio",
    }
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the discovery CLI flags + ini options."""
    group = parser.getgroup("mockarty", "Mockarty TCM integration")
    group.addoption(
        "--mockarty-discover",
        action="store_true",
        default=False,
        dest="mockarty_discover",
        help=(
            "Sync the collected test inventory to Mockarty TCM "
            "(POST /tcm/discovery) after collection."
        ),
    )
    group.addoption(
        "--mockarty-discover-source",
        action="store",
        default=None,
        dest="mockarty_discover_source",
        help=(
            "Discovery manifest 'source' scope key (e.g. 'pytest:auth-suite'). "
            "Defaults to 'pytest:<rootdir-name>'."
        ),
    )
    group.addoption(
        "--mockarty-discover-prune",
        action="store_true",
        default=False,
        dest="mockarty_discover_prune",
        help=(
            "Set pruneMissing=True: tests absent from this manifest are "
            "marked orphaned in TCM (never deleted)."
        ),
    )
    parser.addini(
        "mockarty_discover_source",
        help="Default discovery manifest 'source' scope key.",
        default=None,
    )


def _truthy_env(name: str) -> bool:
    """Return True for a set, non-falsey env var."""
    val = os.environ.get(name)
    if val is None:
        return False
    return val.strip().lower() not in ("", "0", "false", "no", "off")


def _discovery_enabled(config: pytest.Config) -> bool:
    """Discovery runs when the flag is passed OR MOCKARTY_DISCOVER is set."""
    if config.getoption("mockarty_discover", default=False):
        return True
    return _truthy_env("MOCKARTY_DISCOVER")


def _resolve_source(config: pytest.Config) -> str:
    """Resolve the manifest source: flag > env > ini > default."""
    flag = config.getoption("mockarty_discover_source", default=None)
    if flag:
        return str(flag)
    env = os.environ.get("MOCKARTY_DISCOVER_SOURCE")
    if env and env.strip():
        return env.strip()
    ini = config.getini("mockarty_discover_source")
    if ini:
        return str(ini)
    rootname = getattr(config.rootpath, "name", None) or "pytest"
    return f"pytest:{rootname}"


def _resolve_prune(config: pytest.Config) -> bool:
    if config.getoption("mockarty_discover_prune", default=False):
        return True
    return _truthy_env("MOCKARTY_DISCOVER_PRUNE")


def _location_ref(item: pytest.Item) -> str:
    """Build a ``file:line`` source reference from ``item.location``.

    ``item.location`` is ``(relpath, lineno, testname)`` where ``lineno``
    is 0-based (or ``None``). We render it 1-based to match how editors /
    "jump to source" expect line numbers.
    """
    loc = getattr(item, "location", None)
    if not loc:
        return ""
    path = loc[0] if len(loc) > 0 else ""
    lineno = loc[1] if len(loc) > 1 else None
    if not path:
        return ""
    if isinstance(lineno, int):
        return f"{path}:{lineno + 1}"
    return str(path)


def _suite_of(item: pytest.Item) -> str:
    """Grouping hint: the test's class name, else its module name."""
    cls = getattr(item, "cls", None)
    if cls is not None:
        return cls.__name__
    module = getattr(item, "module", None)
    if module is not None:
        return getattr(module, "__name__", "") or ""
    return ""


def _labels_of(item: pytest.Item) -> list[str]:
    """Own marker names, minus pytest/builtin plumbing markers.

    ``own_markers`` excludes markers inherited from the module/class so a
    discovered test's labels reflect what the author put on that test (or
    its enclosing scope, which ``own_markers`` does include at the
    function level). Deduped, order-preserving.
    """
    seen: set[str] = set()
    out: list[str] = []
    for marker in getattr(item, "own_markers", []) or []:
        name = getattr(marker, "name", "")
        if not name or name in _BUILTIN_MARKERS or name.startswith("allure_"):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def build_manifest_cases(items: list[pytest.Item]) -> list[dict[str, Any]]:
    """Assemble discovery-case dicts from collected pytest items.

    Pure (no network, no config) so it is unit-testable against fake
    collected items. Non-``Function`` items (e.g. doctest collectors that
    surface oddly) are skipped. Returns the ``cases`` list ready to hand
    to ``client.discovery.sync``.
    """
    cases: list[dict[str, Any]] = []
    for item in items:
        node_id = getattr(item, "nodeid", "") or ""
        if not node_id:
            continue
        case: dict[str, Any] = {
            "full_name": node_id,
            "name": getattr(item, "name", "") or node_id,
        }
        suite = _suite_of(item)
        if suite:
            case["suite"] = suite
        source_ref = _location_ref(item)
        if source_ref:
            case["source_ref"] = source_ref
        labels = _labels_of(item)
        if labels:
            case["labels"] = labels
        cases.append(case)
    return cases


def _build_client() -> Optional[Any]:
    """Construct an ad-hoc MockartyClient from env config.

    Returns None when no base URL is configured (the SDK default base URL
    is only used when explicitly provided — we don't want to POST to
    ``localhost:5770`` by accident from CI). Namespace flows through
    ``MOCKARTY_NAMESPACE`` and otherwise the client default.
    """
    base_url = os.environ.get("MOCKARTY_BASE_URL")
    if not base_url:
        return None
    api_key = os.environ.get("MOCKARTY_API_KEY")
    namespace = os.environ.get("MOCKARTY_NAMESPACE")
    try:
        from mockarty.client import MockartyClient

        if namespace:
            return MockartyClient(base_url=base_url, api_key=api_key, namespace=namespace)
        return MockartyClient(base_url=base_url, api_key=api_key)
    except Exception:  # pragma: no cover — defensive
        return None


_warned_no_client = False


def _warn_once_no_client() -> None:
    global _warned_no_client
    if _warned_no_client:
        return
    _warned_no_client = True
    warnings.warn(
        "mockarty: --mockarty-discover is enabled but no MockartyClient is "
        "reachable (MOCKARTY_BASE_URL unset). The test inventory was NOT "
        "synced. Set MOCKARTY_BASE_URL and MOCKARTY_API_KEY to enable "
        "discovery sync.",
        RuntimeWarning,
        stacklevel=2,
    )


def pytest_collection_finish(session: pytest.Session) -> None:
    """After collection, sync the inventory to TCM when discovery is on.

    Best-effort throughout: a missing client, a transport failure, or a
    server error is warned-and-swallowed so a discovery sync never fails
    the session.
    """
    config = session.config
    if not _discovery_enabled(config):
        return

    cases = build_manifest_cases(list(session.items))
    if not cases:
        # Nothing collected (e.g. --collect-only with a filter that matched
        # nothing). Sending an empty manifest with pruneMissing would orphan
        # the whole source, which is almost never what the user wants here —
        # skip silently.
        return

    client = _build_client()
    if client is None:
        _warn_once_no_client()
        return

    source = _resolve_source(config)
    prune = _resolve_prune(config)

    try:
        result = client.discovery.sync(
            source=source,
            cases=cases,
            framework="pytest",
            prune_missing=prune,
        )
        reporter = config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"mockarty discovery [{source}]: "
                f"{result.created} new, {result.updated} updated, "
                f"{result.orphaned} orphaned ({result.total} total)",
                green=True,
            )
    except Exception as exc:  # best-effort — never fail the session
        warnings.warn(
            f"mockarty: discovery sync failed for source {source!r}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
    finally:
        try:
            client.close()
        except Exception:  # pragma: no cover — defensive
            pass
