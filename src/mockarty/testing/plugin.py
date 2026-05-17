# Copyright (c) 2026 Mockarty. All rights reserved.

"""pytest plugin: ties decorators + scenario into the runner lifecycle.

What it does:
    * After each test that bound a TCM case (via ``@test_case`` or ``with scenario()``):
        - If ``@attach_report`` is on the test, upload the outcome (passed/
          failed/skipped + duration), captured stdout/stderr, and any
          attachments registered via ``mockarty.attach``.
        - Otherwise, only ensure the context stack is reset.
    * On collection: warn (don't fail) when ``@test_case(auto_create=True)``
      is used but ``MOCKARTY_API_KEY`` / a fixture is missing — the user
      gets a clear hint instead of a cryptic 401 mid-suite.

Fail-soft policy:
    * Any HTTP error during upload is logged via :mod:`warnings` and
      swallowed. Tests must never fail because reporting failed.
    * When no Mockarty client is reachable (no fixture, no env config),
      the plugin is effectively a no-op.

Activation:
    * Auto-loaded via the ``pytest11`` entry point declared in
      ``pyproject.toml``; users don't need to add anything to
      ``conftest.py`` after ``pip install mockarty``.
"""

from __future__ import annotations

import os
import warnings
from typing import Any, Optional

import pytest

from mockarty.testing import allure_interop as _allure_mirror
from mockarty.testing import context as _ctx
from mockarty.testing import decorators as _dec
from mockarty.testing.fixtures import mock_cleanup, mockarty_client

# Native Allure-2 writer — engages when MOCKARTY_ALLURE_RESULTS_DIR is set,
# regardless of whether allure-pytest is installed. Lets users emit Allure
# artifacts from pure-Mockarty tests without taking on the allure-pytest
# dependency.
try:
    from mockarty import allure_writer as _allure_writer  # type: ignore
except Exception:  # pragma: no cover — defensive
    _allure_writer = None  # type: ignore[assignment]


# Re-export fixtures so users can ``from mockarty.testing import plugin as _``
# and rely on the entry-point loader to surface the fixtures.
__all__ = ["mockarty_client", "mock_cleanup"]


# Sentinel attribute on the test fn marking an implicit (mirror-driven)
# case frame so the post-test hook can clean it up without confusing it
# with an explicit ``@test_case``-bound frame.
_IMPLICIT_CASE_FLAG = "_mockarty_implicit_allure_case"


def pytest_configure(config: pytest.Config) -> None:
    """Register markers + activate the Allure→Mockarty mirror (default-ON)."""
    config.addinivalue_line(
        "markers",
        "mockarty_case(case_id=None, name=None, plan=None, auto_create=False): "
        "marker form of @mockarty.test_case, in case decorator-based binding "
        "doesn't fit a particular suite layout.",
    )
    config.addinivalue_line(
        "markers",
        "mockarty_attach_report: marker form of @mockarty.attach_report.",
    )
    # Mirror-mode is DEFAULT-ON per Owner directive (SDK_FRAMEWORK_PLAN
    # rev 3, §2 + §5.1, 2026-05-16). Set MOCKARTY_ALLURE_MIRROR=off to
    # opt out (recognised inside install_listener()).
    try:
        _allure_mirror.install_listener()
    except Exception as exc:  # pragma: no cover — defensive
        warnings.warn(
            f"mockarty: failed to install Allure mirror: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
    # Optional aggressive ``sys.modules["allure"]`` shim — only when
    # the user explicitly opts in via MOCKARTY_ALLURE_SHIM=on AND the
    # real allure package is missing. See mockarty.allure for details.
    try:
        from mockarty.allure import install_allure_shim

        install_allure_shim()
    except Exception:  # pragma: no cover — best-effort
        pass


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Lift ``@pytest.mark.mockarty_case``/``mockarty_attach_report`` markers
    onto the underlying function so the post-test hook can read them
    uniformly."""
    for item in items:
        if not isinstance(item, pytest.Function):
            continue
        case_marker = item.get_closest_marker("mockarty_case")
        if case_marker is not None:
            kwargs = dict(case_marker.kwargs)
            if case_marker.args:
                # First positional arg is treated as case_id, mirroring the
                # decorator's signature.
                kwargs.setdefault("case_id", case_marker.args[0])
            # Apply by wrapping the function exactly as the decorator does.
            item.obj = _dec.test_case(**kwargs)(item.obj)
        if item.get_closest_marker("mockarty_attach_report") is not None:
            item.obj = _dec.attach_report(item.obj)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item):
    """Open an implicit Mockarty case frame for pure-Allure tests.

    Mirror-mode (Allure → Mockarty) needs an active case frame to write
    into; without one the Allure listener silently drops events. When
    the user's test has any Allure markers/decorators but no
    ``@mockarty.testing.test_case`` binding, we open a synthetic
    ``CaseFrame`` here so their pure-Allure code still produces a
    Mockarty case run. The post-test hook tears it down.

    Heuristic: presence of an ``allure_*`` marker, ``pytestmark`` list,
    or a function attribute set by ``@allure.label/feature/...``
    indicates the user wants Allure semantics. We can also just open
    the frame unconditionally — empty case frames are no-ops on
    upload — but that wastes ContextVar churn for non-Allure suites.

    Mirror is best-effort: any failure here MUST NOT block the test.
    """
    yield
    if not _allure_mirror.is_allure_available():
        return
    if not _allure_mirror.is_mirror_active():  # listener opted out / not installed
        return
    if not isinstance(item, pytest.Function):
        return
    # If the user already has an explicit Mockarty case binding (via
    # @test_case or @mockarty_case marker), don't open a duplicate.
    if _ctx.current_case() is not None:
        return
    if not _has_allure_signal(item):
        return
    frame = _ctx.CaseFrame(
        case_name=item.name,
        auto_create=True,
        metadata={"_implicit_allure_mirror": True},
    )
    _ctx.push_case(frame)
    # Drain any decorator-time labels/links/title that Allure emitted
    # while collecting this test.
    try:
        _allure_mirror.flush_pending_to_frame(frame)
    except Exception:  # pragma: no cover — best-effort
        pass
    setattr(item, _IMPLICIT_CASE_FLAG, True)


def _has_allure_signal(item: pytest.Function) -> bool:
    """True iff the test or its module appears to use Allure decorators."""
    # Function-level: any marker starts with 'allure_' (pytest marker
    # form) OR the function carries Allure label-set attributes.
    for marker in item.iter_markers():
        if marker.name.startswith("allure_"):
            return True
    fn = item.obj
    if any(
        getattr(fn, attr, None) is not None
        for attr in ("__allure_display_name__", "__allure_labels__")
    ):
        return True
    # Pending decorator buffers — Allure decorators ran during collection
    # for THIS test (we can't easily distinguish per-test from the
    # buffer, but module-level allure decorators trigger pending state
    # too, so we conservatively trip on any pending).
    if (
        _allure_mirror._pending_labels
        or _allure_mirror._pending_links
        or _allure_mirror._pending_title
        or _allure_mirror._pending_description
    ):
        return True
    return False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    """After-each-phase hook. We only act on the 'call' phase (the test
    body), not setup/teardown, so the upload happens once per test."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return

    if not isinstance(item, pytest.Function):
        return

    fn = item.obj
    # ``current_case()`` is None by the time this hook fires because the
    # decorator's ``finally:`` block has already popped. ``last_case()``
    # gives us the snapshot of the just-popped frame.
    case = _ctx.current_case() or _ctx.last_case()

    # Native Allure-2 writer: emit a result file for every test, including
    # implicit (mirror-driven) ones, so a user who set MOCKARTY_ALLURE_RESULTS_DIR
    # gets full coverage. Best-effort — never blocks the test outcome.
    if case is not None:
        _emit_native_allure(item, report, case)

    if case is None:
        # No active case binding — reset stacks to be safe and exit.
        _ctx.reset_for_test()
        return

    # Implicit (mirror-driven) frame: pop it so the next test starts
    # clean. We DO NOT upload these by default — uploading every
    # Allure-touched test would surprise users who haven't opted into
    # ``@attach_report``. The frame existed solely so the mirror had a
    # place to write events.
    if getattr(item, _IMPLICIT_CASE_FLAG, False):
        _ctx.reset_for_test()
        return

    # Only upload when explicitly requested.
    if not _dec.is_attach_report(fn):
        _ctx.reset_for_test()
        return

    client = _resolve_client(item)
    if client is None:
        # Fail-soft: no client available, skip upload silently. We emit a
        # one-time warning per session so users notice if they expected
        # uploads but configured something incorrectly.
        _warn_once_no_client()
        _ctx.reset_for_test()
        return

    try:
        _upload_case_outcome(client, item, report, case)
    except Exception as exc:  # pragma: no cover — best-effort
        warnings.warn(
            f"mockarty: failed to upload test outcome for {item.nodeid}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
    finally:
        _ctx.reset_for_test()


def _resolve_client(item: pytest.Item) -> Optional[Any]:
    """Find a MockartyClient: fixture instance > env-configured ad-hoc."""
    # 1) Look for a `mockarty_client` fixture on the item.
    fixt = getattr(item, "funcargs", {}).get("mockarty_client")
    if fixt is not None:
        return fixt

    # 2) Try to construct an ad-hoc client from env. Defer the import to
    # keep the plugin import-cost low for users without env config.
    base_url = os.environ.get("MOCKARTY_BASE_URL")
    api_key = os.environ.get("MOCKARTY_API_KEY")
    if not base_url:
        return None
    try:
        from mockarty.client import MockartyClient

        return MockartyClient(base_url=base_url, api_key=api_key)
    except Exception:  # pragma: no cover
        return None


def _upload_case_outcome(
    client: Any,
    item: pytest.Function,
    report: pytest.TestReport,
    case: _ctx.CaseFrame,
) -> None:
    """POST a synthetic case run reflecting the pytest outcome.

    Goes through ``client.external_runs.report(...)`` which hits
    ``/api/v1/namespaces/:ns/tcm/external-runs``. The endpoint owns
    case resolution (UUID > name > auto-create) so the plugin only
    needs to hand it the bound frame's identifiers + the captured
    pytest data.

    Best-effort: any error here is swallowed by the caller. Tests must
    never fail because the upload failed.
    """
    runs_api = getattr(client, "external_runs", None)
    if runs_api is None:
        return  # SDK predates external_runs — silent skip
    if case.case_id is None and not case.auto_create:
        return  # no binding to upload against

    steps = [
        {
            "name": s.get("name", ""),
            "status": _pytest_step_status(s.get("status", "passed")),
            "error": s.get("error"),
            "metadata": s.get("metadata"),
        }
        for s in case.steps
    ]

    attachments = [
        {
            "name": a["name"],
            "body": a["body"],
            "contentType": a.get("content_type", "application/octet-stream"),
        }
        for a in case.attachments
    ]

    runs_api.report(
        status=_pytest_status_to_external(report),
        case_id=case.case_id,
        case_name=case.case_name,
        plan_id=case.plan_id,
        auto_create=case.auto_create,
        framework="pytest",
        framework_version=pytest.__version__,
        external_id=item.nodeid,
        test_display_name=item.name,
        duration_ms=int(report.duration * 1000) if report.duration else 0,
        error=report.longreprtext if report.longreprtext else None,
        stdout=getattr(report, "capstdout", "") or None,
        stderr=getattr(report, "capstderr", "") or None,
        metadata=dict(case.metadata) if case.metadata else None,
        steps=steps if steps else None,
        attachments=attachments if attachments else None,
    )


def _pytest_status_to_external(report: pytest.TestReport) -> str:
    """Map a pytest report.outcome to the external-run status enum."""
    if report.passed:
        return "passed"
    if report.failed:
        return "failed"
    if report.skipped:
        return "skipped"
    # pytest's "unknown" rarely surfaces in practice, but the server
    # rejects anything outside the enum so map it to failed.
    return "failed"


def _pytest_step_status(s: str) -> str:
    """Coerce a step's recorded status into the wire enum."""
    if s in ("passed", "failed", "skipped", "broken"):
        return s
    return "failed"


_warned_no_client = False
_native_writer = None  # type: Optional[Any]
_native_writer_dir: Optional[str] = None


def _resolve_native_writer() -> Optional[Any]:
    """Return a session-shared AllureResultsWriter when configured.

    Engages only when ``MOCKARTY_ALLURE_RESULTS_DIR`` is set. The writer
    itself is internally thread/process-safe so a single instance is
    reused by every test in the session.
    """
    global _native_writer, _native_writer_dir
    target = os.environ.get("MOCKARTY_ALLURE_RESULTS_DIR")
    if not target or _allure_writer is None:
        return None
    if _native_writer is None or _native_writer_dir != target:
        _native_writer = _allure_writer.AllureResultsWriter(target)
        _native_writer_dir = target
    return _native_writer


def _emit_native_allure(
    item: pytest.Function,
    report: pytest.TestReport,
    case: _ctx.CaseFrame,
) -> None:
    """Convert the case frame to an Allure TestResult and persist it."""
    writer = _resolve_native_writer()
    if writer is None:
        return
    try:
        # Wall-clock start derived from now() minus pytest duration.
        # report.duration is in seconds; convert to ms epoch window.
        stop_ms = _allure_writer.now_ms()
        start_ms = stop_ms - int((report.duration or 0) * 1000)
        # Pull parametrize values off pytest's ``callspec`` if present —
        # makes parameterised iterations distinguishable in the report.
        params = []
        callspec = getattr(item, "callspec", None)
        if callspec is not None:
            for pname, pval in (getattr(callspec, "params", {}) or {}).items():
                try:
                    params.append(
                        _allure_writer.Parameter(name=str(pname), value=repr(pval))
                    )
                except Exception:  # pragma: no cover — defensive
                    continue
        status = _pytest_report_to_allure_status(report)
        result = _allure_writer.case_frame_to_result(
            case,
            name=item.name,
            full_name=item.nodeid,
            framework="pytest",
            parameters=params,
            test_class=_class_name_of(item),
            test_method=item.originalname or item.name,
            package=item.module.__name__ if item.module else None,
            start_ms=start_ms,
            stop_ms=stop_ms,
            status=status,
            exc=call_excinfo_value(report),
            writer=writer,
            description=(item.function.__doc__ or None),
        )
        writer.write_result(result)
    except Exception as exc:  # pragma: no cover — best-effort
        warnings.warn(
            f"mockarty: native Allure writer failed for {item.nodeid}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )


def _pytest_report_to_allure_status(report: pytest.TestReport) -> str:
    if report.passed:
        return _allure_writer.STATUS_PASSED
    if report.skipped:
        return _allure_writer.STATUS_SKIPPED
    # Failures from assertions = "failed"; everything else (collection
    # errors, fixture explosions) = "broken".
    longrepr = getattr(report, "longrepr", None)
    text = ""
    try:
        text = str(longrepr) if longrepr is not None else ""
    except Exception:  # pragma: no cover
        text = ""
    if "AssertionError" in text:
        return _allure_writer.STATUS_FAILED
    return (
        _allure_writer.STATUS_FAILED if report.failed else _allure_writer.STATUS_BROKEN
    )


def call_excinfo_value(report: pytest.TestReport) -> Optional[BaseException]:
    """Best-effort: surface the original exception value from the report."""
    excinfo = getattr(report, "longrepr", None)
    val = getattr(excinfo, "value", None)
    return val if isinstance(val, BaseException) else None


def _class_name_of(item: pytest.Function) -> Optional[str]:
    cls = getattr(item, "cls", None)
    return cls.__name__ if cls is not None else None


def _warn_once_no_client() -> None:
    global _warned_no_client
    if _warned_no_client:
        return
    _warned_no_client = True
    warnings.warn(
        "mockarty: @attach_report is set but no MockartyClient is reachable "
        "(no `mockarty_client` fixture, MOCKARTY_BASE_URL unset). "
        "Test outcomes are not being uploaded. Set MOCKARTY_BASE_URL and "
        "MOCKARTY_API_KEY, or pass `mockarty_client` as a test argument.",
        RuntimeWarning,
        stacklevel=2,
    )
