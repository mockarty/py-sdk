# Copyright (c) 2026 Mockarty. All rights reserved.

"""Opt-in pytest fixtures for the fuzz DSL.

The main ``mockarty`` pytest plugin (``mockarty.testing.plugin``) is
auto-loaded via the ``pytest11`` entry point. This module ships a few
extras that users explicitly import — same pattern as
:mod:`mockarty.pact.pytest_plugin`.

Fixtures:

* ``mockarty_fuzz_target_factory`` — build a fresh :class:`Target`
  pre-named after the current test.
* ``mockarty_fuzz_runner`` — a :class:`Runner` wired to whatever HTTP
  client the user's project already provides via the
  ``mockarty_client`` fixture (or ``None`` for local-spawn-only use).
* ``mockarty_fuzz_output_dir`` — function-scoped tmp dir for written
  configs / artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from mockarty.fuzz.dsl import Target
from mockarty.fuzz.runner import Runner


@pytest.fixture
def mockarty_fuzz_output_dir(tmp_path: Path) -> Path:
    """Function-scoped directory for fuzz JSON / artifact files."""

    out = tmp_path / "fuzz"
    out.mkdir(exist_ok=True)
    return out


@pytest.fixture
def mockarty_fuzz_target_factory(
    request: pytest.FixtureRequest,
) -> Callable[..., Target]:
    """Return a callable that builds a :class:`Target` pre-named after
    the active test.
    """

    def _make(name: Optional[str] = None) -> Target:
        return Target(name or request.node.name)

    return _make


@pytest.fixture
def mockarty_fuzz_runner(request: pytest.FixtureRequest) -> Runner:
    """Return a :class:`Runner` wired to the project's HTTP client.

    Looks up the optional ``mockarty_client`` fixture — projects that
    set one up via :mod:`mockarty.testing` get an HTTP-capable runner;
    projects that don't get a local-spawn-only runner (``submit`` will
    raise, ``local_spawn`` works).
    """

    client: Optional[Any] = None
    try:
        client = request.getfixturevalue("mockarty_client")
    except pytest.FixtureLookupError:
        client = None
    return Runner(client)
