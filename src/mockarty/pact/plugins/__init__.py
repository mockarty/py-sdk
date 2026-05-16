# Copyright (c) 2026 Mockarty. All rights reserved.

"""V4 plugin runtime for Mockarty Pact SDK.

A plugin is a per-content-type adapter the mock server invokes for
non-JSON payloads (protobuf, gRPC, anything custom the user ships in
their own module). The SPI is in :mod:`spi`, the process-wide
registry in :mod:`registry`, and the two built-in plugins —
:class:`ProtobufPlugin` and :class:`GRPCPlugin` — auto-register at
import.

Adding a new plugin = three steps:

1. Implement the :class:`Plugin` Protocol in your own module.
2. ``from mockarty.pact.plugins.registry import register; register(MyPlugin())``.
3. ``consumer.with_plugin("my-plugin")`` — the registry lookup wires
   the runtime in automatically.

The mock server never imports plugin implementations directly; it
walks :func:`registry.get` so plugins shipped by user code are
fully first-class.
"""

from __future__ import annotations

from mockarty.pact.plugins import registry
from mockarty.pact.plugins.grpc import GRPCPlugin
from mockarty.pact.plugins.protobuf import ProtobufPlugin
from mockarty.pact.plugins.registry import (
    PluginAlreadyRegistered,
    each,
    get,
    names,
    register,
    reset,
    unregister,
)
from mockarty.pact.plugins.spi import Plugin, coerce_to_bytes


def _register_builtins() -> None:
    """Idempotent registration of the two stdlib plugins.

    Calling :func:`registry.reset` (typically from a test) wipes the
    map; we re-add the built-ins on the next import or via
    :func:`reset_to_builtins`.
    """

    for plugin in (ProtobufPlugin(), GRPCPlugin()):
        if registry.get(plugin.name) is None:
            registry.register(plugin)


def reset_to_builtins() -> None:
    """Tests use this to recover a clean registry between cases."""

    registry.reset()
    _register_builtins()


_register_builtins()


__all__ = [
    "GRPCPlugin",
    "Plugin",
    "PluginAlreadyRegistered",
    "ProtobufPlugin",
    "coerce_to_bytes",
    "each",
    "get",
    "names",
    "register",
    "reset",
    "reset_to_builtins",
    "unregister",
]
