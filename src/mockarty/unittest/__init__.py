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
import unittest
import warnings
from typing import Optional

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
        # Frame pop happens here so step() inside the test method still
        # sees the active CaseFrame. Result emission is deferred to
        # run() — by tearDown's call site the result object hasn't yet
        # recorded the test's failure on Python 3.11+ (the failure is
        # appended after tearDown returns), so we cannot observe the
        # correct status from here.
        #
        # We snapshot the frame before pop so the deferred emit in
        # run() still has the steps/attachments the test method pushed
        # onto it.
        try:
            self._mockarty_frame_snapshot = _ctx.current_case()
            _ctx.pop_case()
        finally:
            super().tearDown()

    # ── run override — emission point ───────────────────────────────────
    def run(self, result=None):  # noqa: D401 — unittest API
        # Capture the result object so we can inspect THIS test's
        # contribution to failures/errors after the run completes. Works
        # uniformly on Python 3.9 → 3.13+ because we rely on the public
        # ``TestResult`` API, not the private ``_outcome`` plumbing.
        own_result = result is None
        if result is None:
            result = self.defaultTestResult()
            startTestRun = getattr(result, "startTestRun", None)
            if startTestRun is not None:
                startTestRun()

        failures_before = len(result.failures)
        errors_before = len(result.errors)
        skipped_before = len(result.skipped)

        try:
            super().run(result)
        finally:
            self._mockarty_emit_result_from(
                result,
                failures_before=failures_before,
                errors_before=errors_before,
                skipped_before=skipped_before,
            )
            if own_result:
                stopTestRun = getattr(result, "stopTestRun", None)
                if stopTestRun is not None:
                    stopTestRun()
        return result

    # ── result emission ─────────────────────────────────────────────────
    def _mockarty_emit_result_from(
        self,
        result: unittest.TestResult,
        *,
        failures_before: int,
        errors_before: int,
        skipped_before: int,
    ) -> None:
        writer = _writer()
        if writer is None:
            return
        # The CaseFrame was popped in tearDown — re-derive the frame's
        # contents from the metadata we stashed during setUp. Anything
        # the test method pushed onto the frame (steps, attachments)
        # has already been folded into the popped CaseFrame, which we
        # captured before tearDown closed it. To preserve that we
        # peek the frame before pop in tearDown via a side-channel.
        case = getattr(self, "_mockarty_frame_snapshot", None)
        if case is None:
            return

        status = self._mockarty_status_from(
            result,
            failures_before=failures_before,
            errors_before=errors_before,
            skipped_before=skipped_before,
        )
        exc = self._mockarty_exc_from(
            result,
            failures_before=failures_before,
            errors_before=errors_before,
        )
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

    def _mockarty_status_from(
        self,
        result: unittest.TestResult,
        *,
        failures_before: int,
        errors_before: int,
        skipped_before: int,
    ) -> str:
        if len(result.failures) > failures_before:
            return STATUS_FAILED
        if len(result.errors) > errors_before:
            return STATUS_BROKEN
        if len(result.skipped) > skipped_before:
            return STATUS_SKIPPED
        return STATUS_PASSED

    def _mockarty_exc_from(
        self,
        result: unittest.TestResult,
        *,
        failures_before: int,
        errors_before: int,
    ) -> Optional[BaseException]:
        # TestResult stores (test, traceback_string) tuples — the raw
        # exception object isn't preserved. Surface a synthetic
        # AssertionError carrying the traceback so downstream renderers
        # have *something* to display; callers that want the original
        # exception should rely on the framework's own reporter.
        if len(result.failures) > failures_before:
            _tc, tb = result.failures[-1]
            return AssertionError(tb)
        if len(result.errors) > errors_before:
            _tc, tb = result.errors[-1]
            return Exception(tb)
        return None
