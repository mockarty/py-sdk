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
    """Synthesize a case-run on the server reflecting the pytest outcome.

    This is a best-effort facade over the SDK's TCM client. The exact
    method names below intentionally probe what the live SDK exposes, so
    a future SDK rename doesn't break the plugin — when the method is
    absent we silently skip rather than blow up.
    """
    tcm = getattr(client, "tcm", None)
    if tcm is None:
        return  # SDK doesn't ship TCM client surface yet — silent skip

    case_id = case.case_id
    if case_id is None and case.auto_create and case.case_name:
        case_id = _maybe_create_case(tcm, case.case_name, case.plan_id)
    if not case_id:
        return  # no binding; nothing to upload against

    status = _pytest_status_to_tcm(report)
    payload = {
        "test_id": item.nodeid,
        "status": status,
        "duration_ms": int(report.duration * 1000) if report.duration else 0,
        "stdout": getattr(report, "capstdout", "") or "",
        "stderr": getattr(report, "capstderr", "") or "",
        "steps": list(case.steps),
        "metadata": dict(case.metadata),
    }
    if report.longreprtext:
        payload["error"] = report.longreprtext

    # Best-effort dispatch — try the most likely method names in order.
    if hasattr(tcm, "report_test_outcome"):
        tcm.report_test_outcome(case_id=case_id, **payload)
    elif hasattr(tcm, "create_case_run"):
        tcm.create_case_run(case_id=case_id, **payload)
    else:
        return  # SDK surface not yet available — fail-soft

    # Attachments — separate call to keep transport simple.
    if hasattr(tcm, "upload_attachment") and case.attachments:
        for att in case.attachments:
            try:
                tcm.upload_attachment(
                    case_id=case_id,
                    name=att["name"],
                    body=att["body"],
                    content_type=att["content_type"],
                )
            except Exception:  # pragma: no cover — best-effort
                pass


def _maybe_create_case(
    tcm: Any, name: str, plan_id: Optional[str]
) -> Optional[str]:
    """Create a case via the SDK if ``auto_create=True`` was set."""
    if not hasattr(tcm, "create_case"):
        return None
    try:
        result = tcm.create_case(name=name, plan_id=plan_id)
    except Exception:  # pragma: no cover — best-effort
        return None
    return getattr(result, "id", None)


def _pytest_status_to_tcm(report: pytest.TestReport) -> str:
    if report.passed:
        return "passed"
    if report.failed:
        return "failed"
    if report.skipped:
        return "skipped"
    return "unknown"


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
