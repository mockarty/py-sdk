# Copyright (c) 2026 Mockarty. All rights reserved.

"""End-to-end: drive the pytest plugin in a subprocess and verify that
the configured ``allure-results`` directory is populated with one
result per test, including parameterised iterations.

Uses ``pytester`` (provided by pytest itself) so each test runs an
isolated, fresh pytest session — no leaked plugin state between tests.
"""

from __future__ import annotations

import glob
import json
import os

import pytest

pytester = pytest.importorskip("_pytest.pytester")
pytest_plugins = ["pytester"]


def _read_results(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*-result.json"))):
        with open(p, "r", encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


def test_plugin_emits_one_result_per_test(pytester, tmp_path, monkeypatch):
    out_dir = tmp_path / "allure-results"
    monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(out_dir))
    # Disable Allure mirror to keep the test deterministic — we just want
    # to verify our native writer path works through the plugin.
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")

    pytester.makepyfile(
        """
        from mockarty.testing import test_case as _tcase, step as _step

        @_tcase("CASE-X1", plan="qa")
        def test_alpha():
            with _step("inner"):
                assert 1 == 1

        @_tcase(name="auto thing", auto_create=True)
        def test_beta():
            assert True
        """
    )
    result = pytester.runpytest_inprocess("-q", "-p", "mockarty.testing.plugin")
    result.assert_outcomes(passed=2)
    docs = _read_results(str(out_dir))
    assert len(docs) == 2
    names = {d["name"] for d in docs}
    assert "test_alpha" in names
    assert "test_beta" in names
    # Step recorded for the alpha test.
    alpha = next(d for d in docs if d["name"] == "test_alpha")
    assert any(s.get("name") == "inner" for s in alpha.get("steps", []))


def test_plugin_parametrize_each_iteration_emits_distinct_result(pytester, tmp_path, monkeypatch):
    out_dir = tmp_path / "allure-results"
    monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(out_dir))
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")

    pytester.makepyfile(
        """
        import pytest
        from mockarty.testing import test_case as _tcase

        @pytest.mark.parametrize("x", [1, 2, 3])
        @_tcase(name="param test", auto_create=True)
        def test_param(x):
            assert x in (1, 2, 3)
        """
    )
    result = pytester.runpytest("-q", "-p", "mockarty.testing.plugin")
    result.assert_outcomes(passed=3)
    docs = _read_results(str(out_dir))
    assert len(docs) == 3
    # historyId differs across iterations (different param values).
    hids = {d.get("historyId") for d in docs}
    assert len(hids) == 3
    # Each result has the parametrize value recorded as a Parameter.
    for d in docs:
        assert any(p["name"] == "x" for p in d.get("parameters", []))


def test_plugin_failed_test_records_status(pytester, tmp_path, monkeypatch):
    out_dir = tmp_path / "allure-results"
    monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(out_dir))
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")

    pytester.makepyfile(
        """
        from mockarty.testing import test_case as _tcase

        @_tcase(name="bad", auto_create=True)
        def test_bad():
            assert False, "deliberate failure"
        """
    )
    result = pytester.runpytest("-q", "-p", "mockarty.testing.plugin")
    result.assert_outcomes(failed=1)
    docs = _read_results(str(out_dir))
    assert len(docs) == 1
    assert docs[0]["status"] == "failed"
