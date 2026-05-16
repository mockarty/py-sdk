# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mockarty adapter for the stdlib :mod:`unittest` runner.

Usage::

    from mockarty.unittest import MockartyTestCase

    class TestLogin(MockartyTestCase):
        case_id = "CASE-LOGIN-1"  # optional

        def test_submit(self):
            with self.step("submit form"):
                self.assertEqual(200, 200)

Drop-in: subclass :class:`MockartyTestCase` instead of
``unittest.TestCase``. Every test method opens a Mockarty
:class:`~mockarty.testing.context.CaseFrame`; when
``MOCKARTY_ALLURE_RESULTS_DIR`` is set, the adapter additionally writes
an Allure-2 result file per test.

The mixin is fail-soft: any error inside the adapter is logged via
``warnings`` and the test continues. Setup / teardown failures are
recorded as ``broken`` (Allure semantics) rather than ``failed``.
"""

from __future__ import annotations

import os
import sys
import unittest
import warnings
from typing import Any, Optional

from mockarty.allure_writer import (
    AllureResultsWriter,
    STATUS_BROKEN,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    case_frame_to_result,
    now_ms,
)
from mockarty.testing import context as _ctx
from mockarty.testing.decorators import step as _step

__all__ = ["MockartyTestCase", "configure_allure_writer"]


_writer_cache: dict[str, AllureResultsWriter] = {}


def _writer() -> Optional[AllureResultsWriter]:
    out = os.environ.get("MOCKARTY_ALLURE_RESULTS_DIR")
    if not out:
        return None
    w = _writer_cache.get(out)
    if w is None:
        w = AllureResultsWriter(out)
        _writer_cache[out] = w
    return w


def configure_allure_writer(directory: str) -> AllureResultsWriter:
    """Programmatic override for the writer's output dir (tests / CI).

    Equivalent to setting ``MOCKARTY_ALLURE_RESULTS_DIR`` before import,
    but accessible at runtime — useful when the directory is computed
    from a build artifact path.
    """
    w = AllureResultsWriter(directory)
    _writer_cache[directory] = w
    return w


class MockartyTestCase(unittest.TestCase):
    """``unittest.TestCase`` with Mockarty + Allure capture wired in."""

    #: Optional class-level TCM case id used as a default when the
    #: subclass doesn't override per-method.
    case_id: Optional[str] = None
    plan_id: Optional[str] = None

    # ── helpers ─────────────────────────────────────────────────────────
    def step(self, name: str):
        """Open a Mockarty step; works as context manager."""
        return _step(name)

    # ── lifecycle ───────────────────────────────────────────────────────
    def setUp(self) -> None:  # noqa: D401 — unittest API
        super().setUp()
        cls = type(self)
        method_name = self._testMethodName
        frame = _ctx.CaseFrame(
            case_id=cls.case_id,
            case_name=f"{cls.__name__}.{method_name}",
            plan_id=cls.plan_id,
            auto_create=cls.case_id is None,
            metadata={
                "_allure_title": method_name,
                "_unittest_class": cls.__name__,
                "_unittest_module": cls.__module__,
            },
        )
        _ctx.push_case(frame)
        self._mockarty_started = now_ms()

    def tearDown(self) -> None:  # noqa: D401 — unittest API
        try:
            self._mockarty_emit_result()
        finally:
            _ctx.pop_case()
            super().tearDown()

    # ── result emission ─────────────────────────────────────────────────
    def _mockarty_emit_result(self) -> None:
        writer = _writer()
        if writer is None:
            return
        case = _ctx.current_case()
        if case is None:
            return
        # Determine status from unittest's outcome machinery. The
        # private ``_outcome`` attr is the cleanest cross-version way to
        # detect failures + errors without overriding ``run`` entirely.
        status = self._mockarty_status()
        exc = self._mockarty_exc_info()
        try:
            tr = case_frame_to_result(
                case,
                name=self._testMethodName,
                framework="unittest",
                test_class=type(self).__name__,
                test_method=self._testMethodName,
                package=type(self).__module__,
                start_ms=getattr(self, "_mockarty_started", now_ms()),
                stop_ms=now_ms(),
                status=status,
                exc=exc,
                writer=writer,
            )
            writer.write_result(tr)
        except Exception as exc2:  # pragma: no cover — best-effort
            warnings.warn(
                f"mockarty.unittest: failed to write Allure result: {exc2}",
                RuntimeWarning,
                stacklevel=2,
            )

    def _mockarty_status(self) -> str:
        outcome = getattr(self, "_outcome", None)
        if outcome is None:
            return STATUS_PASSED
        if getattr(outcome, "skipped", None):
            return STATUS_SKIPPED
        errors = getattr(outcome, "errors", []) or []
        # outcome.errors is list of (testcase, exc_info-or-None); a non-None
        # exc_info means the test raised.
        for _tc, exc_info in errors:
            if exc_info is None:
                continue
            etype, _evalue, _tb = exc_info
            if etype is None:
                continue
            if issubclass(etype, AssertionError):
                return STATUS_FAILED
            if issubclass(etype, unittest.SkipTest):
                return STATUS_SKIPPED
            return STATUS_BROKEN
        # pytest-style attribute ``result.failures``/``errors`` is more
        # common but ``_outcome`` covers the canonical path.
        return STATUS_PASSED

    def _mockarty_exc_info(self) -> Optional[BaseException]:
        outcome = getattr(self, "_outcome", None)
        if outcome is None:
            return None
        errors = getattr(outcome, "errors", []) or []
        for _tc, exc_info in errors:
            if not exc_info:
                continue
            etype, evalue, _tb = exc_info
            if etype is not None and evalue is not None:
                return evalue
        return None
