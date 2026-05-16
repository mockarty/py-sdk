# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for :mod:`mockarty.behave`.

We don't depend on the ``behave`` package itself — instead we exercise
the adapter via SimpleNamespace stand-ins for behave's ``context`` /
``feature`` / ``scenario`` / ``step`` objects. This keeps the adapter
unit-testable without dragging in the BDD runtime.
"""

from __future__ import annotations

import glob
import json
import os
from types import SimpleNamespace

import pytest

from mockarty import behave as adapter
from mockarty.testing import context as _ctx


def _ns(**kw):
    return SimpleNamespace(**kw)


@pytest.fixture(autouse=True)
def _reset_state(tmp_path, monkeypatch):
    monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(tmp_path))
    _ctx.reset_for_test()
    yield
    _ctx.reset_for_test()


def _read_results(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*-result.json"))):
        with open(p, "r", encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


class TestBehaveHooks:
    def test_scenario_emits_passed_result(self, tmp_path):
        ctx = _ns()
        adapter.before_all(ctx)
        feat = _ns(name="Login")
        adapter.before_feature(ctx, feat)
        steps = [
            _ns(keyword="Given", name="a user", status="passed"),
            _ns(keyword="When", name="they login", status="passed"),
        ]
        scenario = _ns(name="happy path", tags=["smoke"], steps=steps, status="passed")
        adapter.before_scenario(ctx, scenario)
        adapter.after_scenario(ctx, scenario)
        adapter.after_feature(ctx, feat)
        adapter.after_all(ctx)
        results = _read_results(str(tmp_path))
        assert len(results) == 1
        r = results[0]
        assert r["status"] == "passed"
        assert r["name"] == "happy path"
        # Tag + parent suite labels propagated.
        label_names = {l["name"] for l in r["labels"]}
        assert "tag" in label_names
        assert "parentSuite" in label_names
        # Steps come from scenario.steps.
        step_names = [s["name"] for s in r["steps"]]
        assert any("a user" in n for n in step_names)

    def test_failed_scenario_recorded(self, tmp_path):
        ctx = _ns()
        adapter.before_all(ctx)
        feat = _ns(name="Login")
        adapter.before_feature(ctx, feat)
        steps = [
            _ns(
                keyword="Then",
                name="see homepage",
                status="failed",
                error_message="assertion failed: not home",
            ),
        ]
        scenario = _ns(name="bad path", tags=[], steps=steps, status="failed")
        adapter.before_scenario(ctx, scenario)
        adapter.after_scenario(ctx, scenario)
        adapter.after_feature(ctx, feat)
        adapter.after_all(ctx)
        results = _read_results(str(tmp_path))
        assert len(results) == 1
        r = results[0]
        assert r["status"] == "failed"
        assert any("see homepage" in s["name"] for s in r["steps"])
        # Step error_message surfaced.
        assert any("assertion failed" in (s.get("statusDetails", {}) or {}).get("message", "") for s in r["steps"])

    def test_install_hooks_into_namespace(self):
        ns: dict = {}
        adapter.install_hooks(ns)
        for h in ("before_all", "before_feature", "before_scenario",
                  "after_scenario", "after_feature", "after_all"):
            assert callable(ns[h])

    def test_install_hooks_chains_existing(self):
        called = []

        def user_after_scenario(context, scenario):
            called.append("user")

        ns = {"after_scenario": user_after_scenario}
        adapter.install_hooks(ns)
        # Adapter runs first then user's.
        ctx = _ns()
        adapter.before_all(ctx)
        feat = _ns(name="F")
        adapter.before_feature(ctx, feat)
        scenario = _ns(name="s", tags=[], steps=[], status="passed")
        adapter.before_scenario(ctx, scenario)
        ns["after_scenario"](ctx, scenario)
        assert called == ["user"]


class TestStatusMapping:
    @pytest.mark.parametrize("raw,expected", [
        ("passed", "passed"),
        ("failed", "failed"),
        ("skipped", "skipped"),
        ("untested", "skipped"),
        ("undefined", "broken"),
    ])
    def test_status_map(self, raw, expected):
        # Internal helper; exercised here for stability.
        assert adapter._behave_status(raw) == expected
