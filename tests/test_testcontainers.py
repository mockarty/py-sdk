# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for :mod:`mockarty.testcontainers`.

Docker-touching paths are gated behind ``DOCKER_HOST`` /
``MOCKARTY_SDK_DOCKER_SMOKE`` env-vars and skip cleanly on shards
without docker. The unit tests below cover everything else: builder
validation, URL formatting, lifecycle errors, and the pytest fixture's
skip-when-no-docker branch.
"""

from __future__ import annotations

import http.server
import json
import os
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from mockarty.testcontainers import (
    DEFAULT_IMAGE,
    FORMAT_AUTO,
    FORMAT_MOCKARTY,
    FORMAT_MOCKOON,
    FORMAT_WIREMOCK,
    MockartyContainer,
)
from mockarty.testcontainers.mockarty import _VALID_FORMATS


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_defaults():
    c = MockartyContainer()
    assert c._image == DEFAULT_IMAGE
    assert c._format == FORMAT_AUTO
    assert c._env == {}
    assert c._stub_files == []
    assert c._cmd == []


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_image_rejects_empty(bad):
    with pytest.raises((ValueError, TypeError)):
        MockartyContainer(image=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "fmt",
    [FORMAT_AUTO, FORMAT_WIREMOCK, FORMAT_MOCKARTY, FORMAT_MOCKOON],
)
def test_accepts_known_formats(fmt):
    c = MockartyContainer(fmt=fmt)
    assert c._format == fmt


@pytest.mark.parametrize("bad", ["zzz", "", "WIREMOCK"])
def test_rejects_unknown_format(bad):
    with pytest.raises(ValueError):
        MockartyContainer(fmt=bad)


def test_valid_formats_constant_kept_in_sync():
    # Guard against a future format being added in one place and not
    # the other.
    assert _VALID_FORMATS == frozenset(
        {FORMAT_AUTO, FORMAT_WIREMOCK, FORMAT_MOCKARTY, FORMAT_MOCKOON}
    )


# ---------------------------------------------------------------------------
# Builder methods
# ---------------------------------------------------------------------------


def test_with_image_override():
    c = MockartyContainer().with_image("ghcr.io/acme/x:1.0")
    assert c._image == "ghcr.io/acme/x:1.0"


def test_with_image_empty_rejected():
    with pytest.raises(ValueError):
        MockartyContainer().with_image("")


def test_with_format_chainable():
    c = MockartyContainer().with_format(FORMAT_WIREMOCK)
    assert c._format == FORMAT_WIREMOCK


def test_with_format_invalid():
    with pytest.raises(ValueError):
        MockartyContainer().with_format("zzz")


def test_with_stub_file_resolved(tmp_path):
    p = tmp_path / "stubs.json"
    p.write_text("[]")
    c = MockartyContainer().with_stub_file(str(p))
    assert c._stub_files == [p.resolve()]


def test_with_stub_file_multiple(tmp_path):
    a = tmp_path / "a.json"
    a.write_text("[]")
    b = tmp_path / "b.json"
    b.write_text("[]")
    c = MockartyContainer().with_stub_file(str(a)).with_stub_file(str(b))
    assert len(c._stub_files) == 2


def test_with_env_chain():
    c = MockartyContainer().with_env("FOO", "bar").with_env("FOO", "baz")
    assert c._env == {"FOO": "baz"}  # last writer wins


def test_with_env_empty_key_rejected():
    with pytest.raises(ValueError):
        MockartyContainer().with_env("", "x")


def test_with_cmd():
    c = MockartyContainer().with_cmd("serve", "--verbose")
    assert c._cmd == ["serve", "--verbose"]


# ---------------------------------------------------------------------------
# URL helpers — drive directly with a stub _container
# ---------------------------------------------------------------------------


class _FakeContainer:
    def __init__(self, host="127.0.0.1", mock_port="49152", metrics_port="49153"):
        self._host = host
        self._mock = mock_port
        self._metrics = metrics_port
        self._stopped = False

    def get_container_host_ip(self) -> str:
        return self._host

    def get_exposed_port(self, p: int) -> str:
        return {8080: self._mock, 9090: self._metrics}[p]

    def stop(self) -> None:
        self._stopped = True

    def get_logs(self):
        return (b"hello\n", b"")


def test_url_helpers_render_correctly():
    c = MockartyContainer()
    c._container = _FakeContainer()
    assert c.url() == "http://127.0.0.1:49152"
    assert c.wiremock_url() == "http://127.0.0.1:49152/__admin"
    assert c.mockarty_url() == "http://127.0.0.1:49152/api/v1"
    assert c.metrics_url() == "http://127.0.0.1:49153"


def test_url_before_start_raises():
    c = MockartyContainer()
    with pytest.raises(RuntimeError, match="not been started"):
        c.url()


def test_stop_idempotent():
    c = MockartyContainer()
    c._container = _FakeContainer()
    c.stop()
    assert c._container is None
    c.stop()  # second call must not raise
    assert c._container is None


def test_logs_decodes_bytes():
    c = MockartyContainer()
    c._container = _FakeContainer()
    assert c.logs() == "hello\n"


# ---------------------------------------------------------------------------
# apply() + reset() against an in-process HTTP server
# ---------------------------------------------------------------------------


class _StubAdmin(http.server.BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []
    status_code = 200

    def do_POST(self):  # noqa: N802 -- http.server API
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        self.__class__.received.append(
            {
                "path": self.path,
                "body": raw.decode("utf-8") if raw else "",
                "content_type": self.headers.get("Content-Type", ""),
            }
        )
        self.send_response(self.__class__.status_code)
        self.end_headers()
        self.wfile.write(b"")

    def log_message(self, *a, **kw):  # silence noise
        pass


@pytest.fixture()
def admin_server():
    _StubAdmin.received.clear()
    _StubAdmin.status_code = 200
    srv = http.server.HTTPServer(("127.0.0.1", 0), _StubAdmin)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def test_apply_posts_json(admin_server):
    host, port = admin_server.server_address
    c = MockartyContainer()
    c._container = _FakeContainer(
        host=host, mock_port=str(port), metrics_port=str(port)
    )
    c.apply({"http": {"request": {"method": "GET", "path": "/x"}}})
    received = _StubAdmin.received
    assert len(received) == 1
    assert received[0]["path"] == "/api/v1/mocks"
    assert received[0]["content_type"] == "application/json"
    assert json.loads(received[0]["body"]) == {
        "http": {"request": {"method": "GET", "path": "/x"}}
    }


def test_reset_posts_admin_reset(admin_server):
    host, port = admin_server.server_address
    c = MockartyContainer()
    c._container = _FakeContainer(
        host=host, mock_port=str(port), metrics_port=str(port)
    )
    c.reset()
    assert _StubAdmin.received[0]["path"] == "/__admin/reset"


def test_apply_rejects_none():
    c = MockartyContainer()
    c._container = _FakeContainer()
    with pytest.raises(ValueError):
        c.apply(None)


def test_apply_pydantic_model_dump(admin_server):
    class Fake:
        def model_dump(self, exclude_none=True):
            return {"http": {"request": {"method": "GET", "path": "/x"}}}

    host, port = admin_server.server_address
    c = MockartyContainer()
    c._container = _FakeContainer(
        host=host, mock_port=str(port), metrics_port=str(port)
    )
    c.apply(Fake())
    assert json.loads(_StubAdmin.received[0]["body"]) == {
        "http": {"request": {"method": "GET", "path": "/x"}}
    }


def test_apply_pydantic_v1_dict(admin_server):
    class FakeV1:
        def dict(self, exclude_none=True):
            return {"http": {}}

    host, port = admin_server.server_address
    c = MockartyContainer()
    c._container = _FakeContainer(
        host=host, mock_port=str(port), metrics_port=str(port)
    )
    c.apply(FakeV1())
    assert json.loads(_StubAdmin.received[0]["body"]) == {"http": {}}


def test_apply_surfaces_4xx(admin_server):
    _StubAdmin.status_code = 422
    host, port = admin_server.server_address
    c = MockartyContainer()
    c._container = _FakeContainer(
        host=host, mock_port=str(port), metrics_port=str(port)
    )
    with pytest.raises(RuntimeError, match="422"):
        c.apply({"x": 1})


# ---------------------------------------------------------------------------
# pytest plugin fixture -- skip-without-docker branch
# ---------------------------------------------------------------------------


def test_fixture_skips_without_docker(monkeypatch):
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    from mockarty.testcontainers.pytest_plugin import _docker_available

    assert _docker_available() is False


def test_fixture_detects_docker_host_env(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:2375")
    from mockarty.testcontainers.pytest_plugin import _docker_available

    assert _docker_available() is True


# ---------------------------------------------------------------------------
# Smoke test -- opt-in (requires docker + the CLI image)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("MOCKARTY_SDK_DOCKER_SMOKE", "") == "",
    reason="MOCKARTY_SDK_DOCKER_SMOKE not set -- skipping docker smoke",
)
def test_smoke_start_stop():
    c = MockartyContainer().with_format(FORMAT_AUTO)
    try:
        c.start()
        assert c.url().startswith("http://")
    finally:
        c.stop()
