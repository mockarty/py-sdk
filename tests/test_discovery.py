# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for the test-discovery SDK API + the pytest discovery plugin.

Covers:
    * manifest-builder validation + the wire shape (camelCase keys),
    * ``SyncResult`` parsing,
    * the sync/async ``client.discovery.sync`` transport (path + body +
      namespace override) via respx,
    * the collection-finish hook assembling a manifest from fake
      collected items + posting it through a recording fake client.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from mockarty import (
    AsyncMockartyClient,
    DiscoveryCase,
    MockartyClient,
    SyncResult,
)
from mockarty.api.discovery import _build_case, _build_manifest, _ns_path
from mockarty.testing import discovery_plugin


# ── _build_case ──────────────────────────────────────────────────────────


def test_build_case_from_dataclass_full_shape():
    out = _build_case(
        DiscoveryCase(
            full_name="tests/auth_test.py::test_login",
            name="test_login",
            suite="auth",
            description="logs a user in",
            source_ref="tests/auth_test.py:12",
            labels=["smoke", "auth"],
        )
    )
    assert out == {
        "fullName": "tests/auth_test.py::test_login",
        "name": "test_login",
        "suite": "auth",
        "description": "logs a user in",
        "sourceRef": "tests/auth_test.py:12",
        "labels": ["smoke", "auth"],
    }


def test_build_case_from_snake_case_mapping():
    out = _build_case(
        {
            "full_name": "tests/x.py::test_y",
            "name": "test_y",
            "source_ref": "tests/x.py:3",
        }
    )
    assert out["fullName"] == "tests/x.py::test_y"
    assert out["sourceRef"] == "tests/x.py:3"
    # Optional, unset fields are omitted from the wire shape.
    assert "suite" not in out
    assert "description" not in out
    assert "labels" not in out


def test_build_case_from_wire_camel_case_mapping():
    out = _build_case({"fullName": "a::b", "sourceRef": "a.py:1"})
    assert out["fullName"] == "a::b"
    assert out["sourceRef"] == "a.py:1"


def test_build_case_omits_empty_name():
    # name has no omitempty server-side; the server falls back to fullName,
    # so the SDK only sends name when meaningfully set.
    out = _build_case(DiscoveryCase(full_name="a::b"))
    assert out == {"fullName": "a::b"}


def test_build_case_requires_full_name():
    with pytest.raises(ValueError, match="full_name"):
        _build_case(DiscoveryCase(full_name="   "))
    with pytest.raises(ValueError, match="full_name"):
        _build_case({"name": "no identity"})


def test_build_case_rejects_wrong_type():
    with pytest.raises(TypeError):
        _build_case(42)  # type: ignore[arg-type]


def test_build_case_coerces_label_values_to_str():
    out = _build_case(DiscoveryCase(full_name="a::b", labels=[1, "two"]))  # type: ignore[list-item]
    assert out["labels"] == ["1", "two"]


# ── _build_manifest ────────────────────────────────────────────────────────


def test_build_manifest_minimal():
    body = _build_manifest(
        source="pytest:suite",
        cases=[DiscoveryCase(full_name="a::b")],
        framework=None,
        prune_missing=False,
    )
    assert body == {
        "source": "pytest:suite",
        "cases": [{"fullName": "a::b"}],
    }


def test_build_manifest_full():
    body = _build_manifest(
        source="  pytest:auth-suite  ",
        cases=[DiscoveryCase(full_name="a::b", name="b")],
        framework="pytest",
        prune_missing=True,
    )
    assert body["source"] == "pytest:auth-suite"  # trimmed
    assert body["framework"] == "pytest"
    assert body["pruneMissing"] is True
    assert body["cases"][0]["name"] == "b"


def test_build_manifest_requires_source():
    with pytest.raises(ValueError, match="source"):
        _build_manifest(source="  ", cases=[], framework=None, prune_missing=False)


def test_build_manifest_prune_missing_default_omitted():
    body = _build_manifest(
        source="s", cases=[], framework=None, prune_missing=False
    )
    assert "pruneMissing" not in body


def test_ns_path_quotes_and_requires_namespace():
    assert _ns_path("qa") == "/api/v1/namespaces/qa/tcm/discovery"
    assert _ns_path("a/b") == "/api/v1/namespaces/a%2Fb/tcm/discovery"
    with pytest.raises(ValueError):
        _ns_path("")


# ── SyncResult parsing ──────────────────────────────────────────────────────


def test_sync_result_from_response_full():
    r = SyncResult.from_response(
        {"source": "s", "created": 3, "updated": 2, "orphaned": 1, "total": 6}
    )
    assert (r.source, r.created, r.updated, r.orphaned, r.total) == ("s", 3, 2, 1, 6)
    assert r.raw["total"] == 6


def test_sync_result_from_empty_body():
    r = SyncResult.from_response(None)
    assert (r.source, r.created, r.updated, r.orphaned, r.total) == ("", 0, 0, 0, 0)


def test_sync_result_tolerates_bad_counts():
    r = SyncResult.from_response({"created": "nope", "total": None})
    assert r.created == 0
    assert r.total == 0


# ── Transport (sync) ────────────────────────────────────────────────────────


@respx.mock
def test_discovery_sync_posts_correct_path_and_body():
    route = respx.post(
        "http://localhost:5770/api/v1/namespaces/qa/tcm/discovery"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "source": "pytest:auth-suite",
                "created": 1,
                "updated": 0,
                "orphaned": 0,
                "total": 1,
            },
        )
    )

    with MockartyClient(base_url="http://localhost:5770", namespace="qa") as client:
        result = client.discovery.sync(
            source="pytest:auth-suite",
            cases=[
                DiscoveryCase(
                    full_name="tests/auth_test.py::test_login",
                    name="test_login",
                    suite="auth",
                    source_ref="tests/auth_test.py:12",
                    labels=["smoke"],
                )
            ],
            framework="pytest",
            prune_missing=True,
        )

    assert route.called
    assert isinstance(result, SyncResult)
    assert result.created == 1
    assert result.total == 1

    parsed = json.loads(route.calls[0].request.read())
    assert parsed["source"] == "pytest:auth-suite"
    assert parsed["framework"] == "pytest"
    assert parsed["pruneMissing"] is True
    case = parsed["cases"][0]
    assert case["fullName"] == "tests/auth_test.py::test_login"
    assert case["name"] == "test_login"
    assert case["suite"] == "auth"
    assert case["sourceRef"] == "tests/auth_test.py:12"
    assert case["labels"] == ["smoke"]


@respx.mock
def test_discovery_sync_namespace_override():
    route = respx.post(
        "http://localhost:5770/api/v1/namespaces/other-ns/tcm/discovery"
    ).mock(return_value=httpx.Response(200, json={"source": "s", "total": 0}))
    with MockartyClient(base_url="http://localhost:5770", namespace="qa") as client:
        client.discovery.sync(
            source="s",
            cases=[DiscoveryCase(full_name="a::b")],
            namespace="other-ns",
        )
    assert route.called


@respx.mock
def test_discovery_sync_accepts_plain_dict_cases():
    route = respx.post(
        "http://localhost:5770/api/v1/namespaces/qa/tcm/discovery"
    ).mock(return_value=httpx.Response(200, json={"source": "s", "total": 1}))
    with MockartyClient(base_url="http://localhost:5770", namespace="qa") as client:
        client.discovery.sync(
            source="s",
            cases=[{"full_name": "a::b", "name": "b"}],
        )
    assert route.called
    parsed = json.loads(route.calls[0].request.read())
    assert parsed["cases"][0]["fullName"] == "a::b"


@respx.mock
def test_discovery_sync_propagates_429_busy():
    respx.post("http://localhost:5770/api/v1/namespaces/qa/tcm/discovery").mock(
        return_value=httpx.Response(429, json={"error": "busy", "code": "rate_limit"})
    )
    from mockarty import MockartyRateLimitError

    with MockartyClient(
        base_url="http://localhost:5770", namespace="qa", max_retries=0
    ) as client:
        with pytest.raises(MockartyRateLimitError):
            client.discovery.sync(source="s", cases=[DiscoveryCase(full_name="a::b")])


# ── Transport (async) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_discovery_sync_async():
    route = respx.post(
        "http://localhost:5770/api/v1/namespaces/qa/tcm/discovery"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"source": "s", "created": 2, "updated": 0, "orphaned": 0, "total": 2},
        )
    )
    async with AsyncMockartyClient(
        base_url="http://localhost:5770", namespace="qa", max_retries=0
    ) as client:
        result = await client.discovery.sync(
            source="s",
            cases=[
                DiscoveryCase(full_name="a::b"),
                DiscoveryCase(full_name="c::d"),
            ],
            framework="pytest",
        )
    assert route.called
    assert result.created == 2
    parsed = json.loads(route.calls[0].request.read())
    assert len(parsed["cases"]) == 2


# ── Collection-finish hook ──────────────────────────────────────────────────


class _FakeMarker:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeItem:
    """Minimal stand-in for a collected pytest.Function item."""

    def __init__(
        self,
        nodeid: str,
        name: str,
        location: tuple,
        own_markers: list,
        cls=None,
        module=None,
    ) -> None:
        self.nodeid = nodeid
        self.name = name
        self.location = location
        self.own_markers = own_markers
        self.cls = cls
        self.module = module


class _FakeModule:
    def __init__(self, name: str) -> None:
        self.__name__ = name


class _FakeClass:
    pass


def test_build_manifest_cases_from_items():
    module = _FakeModule("tests.auth_test")
    items = [
        _FakeItem(
            nodeid="tests/auth_test.py::test_login",
            name="test_login",
            location=("tests/auth_test.py", 11, "test_login"),  # 0-based -> 12
            own_markers=[_FakeMarker("smoke"), _FakeMarker("parametrize")],
            module=module,
        ),
        _FakeItem(
            nodeid="tests/auth_test.py::TestSession::test_logout",
            name="test_logout",
            location=("tests/auth_test.py", 41, "test_logout"),  # -> 42
            own_markers=[_FakeMarker("allure_label"), _FakeMarker("regression")],
            cls=_FakeClass,
            module=module,
        ),
    ]
    cases = discovery_plugin.build_manifest_cases(items)
    assert len(cases) == 2

    first = cases[0]
    assert first["full_name"] == "tests/auth_test.py::test_login"
    assert first["name"] == "test_login"
    assert first["source_ref"] == "tests/auth_test.py:12"  # 1-based
    assert first["suite"] == "tests.auth_test"  # module name (no class)
    # builtin 'parametrize' filtered, 'smoke' kept.
    assert first["labels"] == ["smoke"]

    second = cases[1]
    assert second["suite"] == "_FakeClass"  # class wins over module
    # 'allure_*' filtered, 'regression' kept.
    assert second["labels"] == ["regression"]


def test_build_manifest_cases_skips_items_without_nodeid():
    items = [_FakeItem(nodeid="", name="x", location=(), own_markers=[])]
    assert discovery_plugin.build_manifest_cases(items) == []


def test_build_manifest_cases_handles_missing_location():
    items = [
        _FakeItem(
            nodeid="a::b", name="b", location=None, own_markers=[]
        )
    ]
    cases = discovery_plugin.build_manifest_cases(items)
    assert cases[0]["full_name"] == "a::b"
    assert "source_ref" not in cases[0]


class _RecordingDiscovery:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def sync(self, **kwargs):
        self.calls.append(kwargs)
        return SyncResult(source=kwargs["source"], created=1, updated=0, orphaned=0, total=1, raw={})


class _RecordingClient:
    def __init__(self) -> None:
        self.discovery = _RecordingDiscovery()
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeConfig:
    def __init__(self, *, enabled: bool, source=None, prune=False, rootname="proj") -> None:
        self._opts = {
            "mockarty_discover": enabled,
            "mockarty_discover_source": source,
            "mockarty_discover_prune": prune,
        }
        self._ini = {"mockarty_discover_source": None}

        class _Root:
            name = rootname

        self.rootpath = _Root()

        class _PM:
            def get_plugin(self, _name):
                return None

        self.pluginmanager = _PM()

    def getoption(self, name, default=None):
        return self._opts.get(name, default)

    def getini(self, name):
        return self._ini.get(name)


class _FakeSession:
    def __init__(self, config, items) -> None:
        self.config = config
        self.items = items


def test_collection_finish_noop_when_disabled(monkeypatch):
    """When neither the flag nor the env var is set, nothing is built/posted."""
    monkeypatch.delenv("MOCKARTY_DISCOVER", raising=False)
    called = {"build": False}

    def _spy(_items):
        called["build"] = True
        return []

    monkeypatch.setattr(discovery_plugin, "build_manifest_cases", _spy)
    config = _FakeConfig(enabled=False)
    discovery_plugin.pytest_collection_finish(_FakeSession(config, []))
    assert called["build"] is False


def test_collection_finish_posts_manifest(monkeypatch):
    """Enabled + items present + client reachable → one sync call."""
    monkeypatch.delenv("MOCKARTY_DISCOVER", raising=False)
    monkeypatch.delenv("MOCKARTY_DISCOVER_PRUNE", raising=False)
    monkeypatch.delenv("MOCKARTY_DISCOVER_SOURCE", raising=False)
    recording = _RecordingClient()
    monkeypatch.setattr(discovery_plugin, "_build_client", lambda: recording)

    items = [
        _FakeItem(
            nodeid="tests/x.py::test_a",
            name="test_a",
            location=("tests/x.py", 0, "test_a"),
            own_markers=[_FakeMarker("smoke")],
            module=_FakeModule("tests.x"),
        )
    ]
    config = _FakeConfig(enabled=True, source="pytest:mine", prune=True)
    discovery_plugin.pytest_collection_finish(_FakeSession(config, items))

    assert len(recording.discovery.calls) == 1
    call = recording.discovery.calls[0]
    assert call["source"] == "pytest:mine"
    assert call["framework"] == "pytest"
    assert call["prune_missing"] is True
    assert call["cases"][0]["full_name"] == "tests/x.py::test_a"
    assert call["cases"][0]["source_ref"] == "tests/x.py:1"
    assert recording.closed is True


def test_collection_finish_skips_empty_inventory(monkeypatch):
    """No collected items → no sync (and we never orphan a whole source)."""
    monkeypatch.setenv("MOCKARTY_DISCOVER", "1")
    recording = _RecordingClient()
    monkeypatch.setattr(discovery_plugin, "_build_client", lambda: recording)
    config = _FakeConfig(enabled=False)  # env var drives enablement here
    discovery_plugin.pytest_collection_finish(_FakeSession(config, []))
    assert recording.discovery.calls == []


def test_collection_finish_env_var_enables(monkeypatch):
    monkeypatch.setenv("MOCKARTY_DISCOVER", "true")
    recording = _RecordingClient()
    monkeypatch.setattr(discovery_plugin, "_build_client", lambda: recording)
    items = [
        _FakeItem("a::b", "b", ("a.py", 0, "b"), [], module=_FakeModule("a"))
    ]
    config = _FakeConfig(enabled=False)
    discovery_plugin.pytest_collection_finish(_FakeSession(config, items))
    assert len(recording.discovery.calls) == 1


def test_collection_finish_swallows_sync_error(monkeypatch):
    """A failing sync must not raise out of the hook."""
    monkeypatch.setenv("MOCKARTY_DISCOVER", "1")

    class _Boom(_RecordingClient):
        def __init__(self):
            super().__init__()

            class _D:
                def sync(self_inner, **_kw):
                    raise RuntimeError("server exploded")

            self.discovery = _D()

    boom = _Boom()
    monkeypatch.setattr(discovery_plugin, "_build_client", lambda: boom)
    items = [_FakeItem("a::b", "b", ("a.py", 0, "b"), [], module=_FakeModule("a"))]
    config = _FakeConfig(enabled=False)
    with pytest.warns(RuntimeWarning, match="discovery sync failed"):
        discovery_plugin.pytest_collection_finish(_FakeSession(config, items))
    assert boom.closed is True


def test_resolve_source_default(monkeypatch):
    monkeypatch.delenv("MOCKARTY_DISCOVER_SOURCE", raising=False)
    config = _FakeConfig(enabled=True, rootname="my-project")
    assert discovery_plugin._resolve_source(config) == "pytest:my-project"


def test_resolve_source_env_over_default(monkeypatch):
    monkeypatch.setenv("MOCKARTY_DISCOVER_SOURCE", "env-source")
    config = _FakeConfig(enabled=True, rootname="ignored")
    assert discovery_plugin._resolve_source(config) == "env-source"


def test_resolve_source_flag_wins(monkeypatch):
    monkeypatch.setenv("MOCKARTY_DISCOVER_SOURCE", "env-source")
    config = _FakeConfig(enabled=True, source="flag-source")
    assert discovery_plugin._resolve_source(config) == "flag-source"


def test_build_client_returns_none_without_base_url(monkeypatch):
    monkeypatch.delenv("MOCKARTY_BASE_URL", raising=False)
    assert discovery_plugin._build_client() is None
