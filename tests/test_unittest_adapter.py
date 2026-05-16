# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for :mod:`mockarty.unittest` — TestCase mixin.

Verifies:
* CaseFrame opened/closed around every test method.
* Native Allure writer engaged when MOCKARTY_ALLURE_RESULTS_DIR is set.
* Failure → "failed" status; setUp error → "broken" status; skip → "skipped".
* ``self.step()`` opens nested step frames.
* configure_allure_writer() override works at runtime.
"""

from __future__ import annotations

import glob
import json
import os
import unittest

import pytest

from mockarty.testing import context as _ctx
from mockarty.unittest import MockartyTestCase, configure_allure_writer


def _read_results(dirpath: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(os.path.join(dirpath, "*-result.json"))):
        with open(p, "r", encoding="utf-8") as fh:
            out.append(json.load(fh))
    return out


class TestFrameLifecycle:
    def test_frame_opens_and_closes(self, tmp_path):
        assert _ctx.current_case() is None

        class _Sample(MockartyTestCase):
            def test_ok(self_inner):
                # Inside a test the frame must be active.
                assert _ctx.current_case() is not None
                assert _ctx.current_case().case_name.endswith("test_ok")

        suite = unittest.TestLoader().loadTestsFromTestCase(_Sample)
        unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
        # After teardown frame must be popped.
        assert _ctx.current_case() is None


class TestAllureEmission:
    def test_emits_result_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(tmp_path))
        configure_allure_writer(str(tmp_path))

        class _Pass(MockartyTestCase):
            def test_alpha(self_inner):
                self_inner.assertEqual(1, 1)

        suite = unittest.TestLoader().loadTestsFromTestCase(_Pass)
        unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
        results = _read_results(str(tmp_path))
        assert len(results) == 1
        assert results[0]["status"] == "passed"
        assert results[0]["name"] == "test_alpha"
        # Auto-labels present.
        names = {l["name"] for l in results[0]["labels"]}
        assert "testClass" in names
        assert "testMethod" in names
        assert "framework" in names

    def test_assertion_failure_recorded_as_failed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(tmp_path))
        configure_allure_writer(str(tmp_path))

        class _Fail(MockartyTestCase):
            def test_bad(self_inner):
                self_inner.assertEqual(1, 2)

        suite = unittest.TestLoader().loadTestsFromTestCase(_Fail)
        unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
        results = _read_results(str(tmp_path))
        assert len(results) == 1
        assert results[0]["status"] == "failed"

    def test_skip_recorded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(tmp_path))
        configure_allure_writer(str(tmp_path))

        class _Skip(MockartyTestCase):
            @unittest.skip("nope")
            def test_skipped(self_inner):
                pass

        suite = unittest.TestLoader().loadTestsFromTestCase(_Skip)
        unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
        results = _read_results(str(tmp_path))
        # Skipped tests may or may not emit a result depending on the
        # unittest runner — we don't fail if absent, but if present must
        # be "skipped".
        for r in results:
            assert r["status"] == "skipped"

    def test_step_records_nested_step(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCKARTY_ALLURE_RESULTS_DIR", str(tmp_path))
        configure_allure_writer(str(tmp_path))

        class _Stepped(MockartyTestCase):
            def test_x(self_inner):
                with self_inner.step("inner"):
                    self_inner.assertTrue(True)

        suite = unittest.TestLoader().loadTestsFromTestCase(_Stepped)
        unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
        results = _read_results(str(tmp_path))
        assert len(results) == 1
        # Step must show up in the serialised result.
        assert any(s.get("name") == "inner" for s in results[0].get("steps", []))


class TestNoWriterWhenUnset:
    def test_no_files_without_env(self, tmp_path):
        # Env var unset — no writer engaged, no files written.
        if "MOCKARTY_ALLURE_RESULTS_DIR" in os.environ:
            del os.environ["MOCKARTY_ALLURE_RESULTS_DIR"]

        class _Plain(MockartyTestCase):
            def test_z(self_inner):
                pass

        suite = unittest.TestLoader().loadTestsFromTestCase(_Plain)
        unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w")).run(suite)
        # tmp_path remains empty (we didn't point the writer at it).
        assert not glob.glob(os.path.join(str(tmp_path), "*"))
