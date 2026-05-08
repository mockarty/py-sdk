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

from mockarty.testing import context as _ctx
from mockarty.testing import decorators as _dec
from mockarty.testing.fixtures import mock_cleanup, mockarty_client


# Re-export fixtures so users can ``from mockarty.testing import plugin as _``
# and rely on the entry-point loader to surface the fixtures.
__all__ = ["mockarty_client", "mock_cleanup"]


def pytest_configure(config: pytest.Config) -> None:
    """Register markers so ``--strict-markers`` doesn't reject them."""
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
    case = _ctx.current_case()
    if case is None:
        # No active case binding — reset stacks to be safe and exit.
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
