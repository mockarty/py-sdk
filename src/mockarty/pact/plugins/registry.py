# Copyright (c) 2026 Mockarty. All rights reserved.

"""Process-wide plugin registry for the V4 mock-server runtime.

The registry is a thread-safe dict keyed by plugin name. The mock
server resolves plugins through :func:`get` at start-time; plugins
register themselves through :func:`register` (typically at import).

We intentionally keep this dynamic (no hard-coded plugin list) so a
user can ship their own plugin in their own pip package and pull it
in via ``import their_plugin`` — see :doc:`./README` for the recipe.

Concurrency
-----------

Registration is rare (once per process at import time); lookups are
hot (every mock server start). We lock both paths to avoid the
``RuntimeError: dictionary changed size during iteration`` race in
:func:`each` when a test registers a stub plugin mid-flight.
"""

from __future__ import annotations

import threading
from typing import Dict, Iterable, List, Optional

from mockarty.pact.plugins.spi import Plugin


_lock = threading.RLock()
_plugins: Dict[str, Plugin] = {}


class PluginAlreadyRegistered(RuntimeError):
    """Raised when two plugins try to register under the same name.

    Forces the user to make a conscious choice via :func:`unregister`
    before swapping out a plugin — accidental shadowing is a frequent
    bug in plugin systems that auto-replace on second register.
    """


def register(plugin: Plugin, *, replace: bool = False) -> None:
    """Add ``plugin`` to the registry.

    ``replace=True`` permits overwriting an existing entry (useful in
    tests that swap in a stub). Otherwise re-registering raises
    :class:`PluginAlreadyRegistered` so collisions surface loudly.
    """

    if not isinstance(plugin, Plugin):
        raise TypeError(
            f"object of type {type(plugin).__name__} does not satisfy the Plugin protocol",
        )
    name = plugin.name
    if not name or not isinstance(name, str):
        raise ValueError("plugin.name must be a non-empty string")
    with _lock:
        if not replace and name in _plugins:
            raise PluginAlreadyRegistered(
                f"plugin {name!r} already registered; pass replace=True to override",
            )
        _plugins[name] = plugin


def unregister(name: str) -> bool:
    """Remove a plugin from the registry. Returns ``True`` if removed."""

    with _lock:
        return _plugins.pop(name, None) is not None


def get(name: str) -> Optional[Plugin]:
    """Look up a plugin by name, returning ``None`` when not present."""

    with _lock:
        return _plugins.get(name)


def names() -> List[str]:
    """Return the registered plugin names, sorted for determinism."""

    with _lock:
        return sorted(_plugins.keys())


def each() -> Iterable[Plugin]:
    """Iterate over the registered plugins (snapshot — thread-safe)."""

    with _lock:
        return list(_plugins.values())


def reset() -> None:
    """Clear the whole registry. Test-only helper — do NOT call from
    production code; plugins normally register once and stay."""

    with _lock:
        _plugins.clear()


__all__ = [
    "PluginAlreadyRegistered",
    "each",
    "get",
    "names",
    "register",
    "reset",
    "unregister",
]
