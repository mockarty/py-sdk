# Copyright (c) 2026 Mockarty. All rights reserved.

"""Optional pytest fixtures for :class:`MockartyContainer`.

Users opt in by adding ``from mockarty.testcontainers.pytest_plugin
import mockarty_container`` to their ``conftest.py`` -- the fixture is
NOT registered through ``pyproject.toml`` ``pytest11`` so we do not
force every Mockarty SDK user to pull docker on a slim install.

Two fixtures are offered:

* :func:`mockarty_container` -- session-scoped, auto-started + auto-
  stopped, configured from environment variables (``MOCKARTY_IMAGE``,
  ``MOCKARTY_STUB_FORMAT``).
* :func:`mockarty_container_factory` -- function-scoped factory for
  tests that need a fresh container per case.
"""

from __future__ import annotations

import os
from typing import Callable, Iterator

import pytest

from mockarty.testcontainers.mockarty import (
    DEFAULT_IMAGE,
    FORMAT_AUTO,
    MockartyContainer,
)


def _docker_available() -> bool:
    if os.environ.get("DOCKER_HOST"):
        return True
    return os.path.exists("/var/run/docker.sock")


def _skip_without_docker() -> None:
    if not _docker_available():
        pytest.skip(
            "docker daemon not reachable -- set DOCKER_HOST or mount "
            "/var/run/docker.sock to run MockartyContainer fixtures"
        )


@pytest.fixture(scope="session")
def mockarty_container() -> Iterator[MockartyContainer]:
    """Session-scoped container, configured from env.

    Environment variables:

    * ``MOCKARTY_IMAGE`` -- override docker image (default
      ``mockarty/cli:latest-mock``).
    * ``MOCKARTY_STUB_FORMAT`` -- ``auto`` / ``wiremock`` / ``mockarty``
      / ``mockoon``.
    """
    _skip_without_docker()
    image = os.environ.get("MOCKARTY_IMAGE", DEFAULT_IMAGE)
    fmt = os.environ.get("MOCKARTY_STUB_FORMAT", FORMAT_AUTO)
    c = MockartyContainer(image=image, fmt=fmt)
    try:
        c.start()
        yield c
    finally:
        c.stop()


@pytest.fixture()
def mockarty_container_factory() -> Iterator[Callable[..., MockartyContainer]]:
    """Function-scoped factory.

    Tests call::

        def test_x(mockarty_container_factory):
            c = mockarty_container_factory(fmt="wiremock")
            ...
    """
    _skip_without_docker()
    spawned: list[MockartyContainer] = []

    def factory(**kwargs) -> MockartyContainer:
        c = MockartyContainer(**kwargs)
        c.start()
        spawned.append(c)
        return c

    try:
        yield factory
    finally:
        for c in spawned:
            c.stop()
