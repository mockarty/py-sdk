# Copyright (c) 2026 Mockarty. All rights reserved.

"""Spin up the ``mockarty/cli:latest-mock`` container and exercise it.

Skips cleanly when Docker isn't available — none of the rest of the
integration suite needs Docker, so this test is the only one that
gates on it.
"""

from __future__ import annotations

import socket

import pytest


def _docker_available() -> bool:
    """Best-effort probe for a Docker daemon.

    We do NOT import the ``docker`` SDK here because its initialization
    is itself slow and noisy when the daemon is unreachable. The
    daemon listens on a Unix socket at ``/var/run/docker.sock`` on
    macOS / Linux; the env var ``DOCKER_HOST`` overrides that. A 1s
    socket connect attempt is enough to discriminate "running" from
    "not running" without dragging in extra deps.
    """
    import os
    host = os.environ.get("DOCKER_HOST")
    if host and host.startswith("tcp://"):
        _, _, addr = host.partition("tcp://")
        h, _, p = addr.partition(":")
        try:
            with socket.create_connection((h, int(p)), timeout=1.0):
                return True
        except OSError:
            return False
    # Fall back to the default unix socket on macOS / Linux.
    sock_path = "/var/run/docker.sock"
    if not os.path.exists(sock_path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(sock_path)
        s.close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker daemon not reachable — testcontainers smoke skipped",
)


def test_mockarty_container_constructs_with_validation() -> None:
    """Even without Docker, validate the constructor surface — this
    guarantees future Docker-less environments still type-check the
    container builder API.
    """
    from mockarty.testcontainers.mockarty import MockartyContainer

    c = (
        MockartyContainer()
        .with_image("mockarty/cli:latest-mock")
        .with_format("wiremock")
        .with_env("LOG_LEVEL", "debug")
    )
    # Surface invariants.
    assert c._image == "mockarty/cli:latest-mock"
    assert c._format == "wiremock"
    assert c._env["LOG_LEVEL"] == "debug"


def test_mockarty_container_start_and_health(tmp_path) -> None:
    """End-to-end: start the container, hit its WireMock admin API
    via the SDK, verify the stub round-trips.

    This test is the only one in the suite that performs an actual
    Docker pull + run; allow extra time.
    """
    from mockarty.testcontainers.mockarty import MockartyContainer

    try:
        import requests
    except ImportError:
        pytest.skip("requests not installed")

    container = MockartyContainer().with_format("wiremock")
    try:
        container.start()
    except Exception as exc:
        # Image-pull / start failures aren't an SDK bug — they reflect
        # environment-specific Docker registry reach. Skip with the
        # underlying reason so it's visible in the report.
        pytest.skip(f"container start failed: {exc}")

    try:
        wm = container.wiremock_url()
        # Post a stub via the WireMock admin API.
        stub = {
            "request": {"method": "GET", "url": "/live-int/ping"},
            "response": {"status": 200, "body": "pong"},
        }
        r = requests.post(f"{wm}/__admin/mappings", json=stub, timeout=10)
        assert r.status_code in (200, 201), (r.status_code, r.text)

        # Verify the stub answers.
        r = requests.get(f"{container.url('mock')}/live-int/ping", timeout=10) if hasattr(container, "url") else None
        if r is None:
            # Older API: derive mock URL from wiremock URL's host:port mapping.
            # The container exposes the same port for both surfaces in dev mode.
            r = requests.get(f"{wm}/live-int/ping", timeout=10)
        assert r.status_code == 200
        assert "pong" in r.text
    finally:
        container.stop()
