# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mockarty adapter for the `behave <https://behave.readthedocs.io/>`_ BDD runner.

Drop these hooks into your ``features/environment.py``::

    from mockarty.behave import install_hooks
    install_hooks(globals())

After install, every behave scenario produces a Mockarty ``CaseFrame``
plus (when configured) an Allure-2 result on disk.

Configuration via env vars:
    * ``MOCKARTY_ALLURE_RESULTS_DIR`` — output directory for
      ``allure-results``. When unset, no native files are written; the
      Mockarty case frame is still produced so an ExternalRunsAPI upload
      stays possible.
    * ``MOCKARTY_FRAMEWORK`` — overrides the framework label (default
      ``behave``).

The adapter is fail-soft: any error inside a hook is logged via
``warnings`` and never blocks behave's own lifecycle.
"""

from __future__ import annotations

import os
import time
import warnings
from typing import Any, Optional

from mockarty.allure_writer import (
    AllureResultsWriter,
    Label,
    Parameter,
    STAGE_FINISHED,
    STATUS_BROKEN,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    StepResult,
    case_frame_to_result,
    now_ms,
)
from mockarty.testing import context as _ctx

__all__ = [
    "before_all",
    "before_feature",
    "before_scenario",
    "after_scenario",
    "after_feature",
    "after_all",
    "install_hooks",
]


def _writer() -> Optional[AllureResultsWriter]:
    out = os.environ.get("MOCKARTY_ALLURE_RESULTS_DIR")
    if not out:
        return None
    return AllureResultsWriter(out)


_state: dict[str, Any] = {"writer": None, "scenario_start": {}, "step_starts": {}}


def before_all(context: Any) -> None:
    _state["writer"] = _writer()


def before_feature(context: Any, feature: Any) -> None:
    # Track feature → Allure parentSuite label.
    setattr(context, "_mockarty_feature_name", getattr(feature, "name", ""))


def before_scenario(context: Any, scenario: Any) -> None:
    frame = _ctx.CaseFrame(
        case_name=getattr(scenario, "name", "scenario"),
        auto_create=True,
        metadata={
            "_allure_title": getattr(scenario, "name", "scenario"),
            "_allure_labels": _scenario_labels(context, scenario),
        },
    )
    _ctx.push_case(frame)
    _state["scenario_start"][id(scenario)] = now_ms()


def _scenario_labels(context: Any, scenario: Any) -> list[dict[str, str]]:
    labels: list[dict[str, str]] = []
    feature_name = getattr(context, "_mockarty_feature_name", None)
    if feature_name:
        labels.append({"name": "parentSuite", "value": str(feature_name)})
    if hasattr(scenario, "tags"):
        for tag in scenario.tags or []:
            labels.append({"name": "tag", "value": str(tag)})
    return labels


def after_scenario(context: Any, scenario: Any) -> None:
    case = _ctx.current_case()
    if case is None:
        return
    try:
        start = _state["scenario_start"].pop(id(scenario), now_ms())
        stop = now_ms()
        status = _behave_status(getattr(scenario, "status", "passed"))
        # Pull behave step rows into Mockarty case.steps if not already there.
        if not case.steps and hasattr(scenario, "steps"):
            for st in scenario.steps:
                case.steps.append(
                    {
                        "name": f"{st.keyword.strip()} {st.name}",
                        "status": _behave_step_status(getattr(st, "status", "passed")),
                        "error": _step_error_text(st),
                    }
                )

        writer = _state.get("writer")
        if writer is not None:
            try:
                tr = case_frame_to_result(
                    case,
                    name=getattr(scenario, "name", "scenario"),
                    framework="behave",
                    start_ms=start,
                    stop_ms=stop,
                    status=status,
                    writer=writer,
                    full_name=_full_name(context, scenario),
                )
                writer.write_result(tr)
            except Exception as exc:  # pragma: no cover — defensive
                warnings.warn(
                    f"mockarty.behave: failed to write Allure result: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
    finally:
        _ctx.pop_case()


def after_feature(context: Any, feature: Any) -> None:
    # Reserved for future container emission.
    return None


def after_all(context: Any) -> None:
    _ctx.reset_for_test()


def _behave_status(status: Any) -> str:
    s = getattr(status, "name", None) or str(status)
    s = s.lower()
    if s == "passed":
        return STATUS_PASSED
    if s == "failed":
        return STATUS_FAILED
    if s in ("skipped", "untested"):
        return STATUS_SKIPPED
    if s == "undefined":
        return STATUS_BROKEN
    return STATUS_FAILED


def _behave_step_status(status: Any) -> str:
    return _behave_status(status)


def _step_error_text(step: Any) -> Optional[str]:
    err = getattr(step, "error_message", None) or getattr(step, "exception", None)
    return str(err) if err else None


def _full_name(context: Any, scenario: Any) -> str:
    feat = getattr(context, "_mockarty_feature_name", "") or ""
    name = getattr(scenario, "name", "scenario")
    return f"{feat}::{name}" if feat else name


def install_hooks(namespace: dict[str, Any]) -> None:
    """Patch a behave ``environment.py`` namespace with the adapter hooks.

    If the user already defined a hook, we *chain*: our hook runs first,
    then theirs. This way authors can keep their existing logic and
    still get Mockarty/Allure capture.
    """
    for hook_name in (
        "before_all",
        "before_feature",
        "before_scenario",
        "after_scenario",
        "after_feature",
        "after_all",
    ):
        existing = namespace.get(hook_name)
        ours = globals()[hook_name]
        if existing is None:
            namespace[hook_name] = ours
        else:
            namespace[hook_name] = _chain(ours, existing)


def _chain(first: Any, second: Any) -> Any:
    def chained(*args: Any, **kwargs: Any) -> None:
        try:
            first(*args, **kwargs)
        except Exception as exc:  # pragma: no cover — defensive
            warnings.warn(
                f"mockarty.behave: adapter hook raised: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
        second(*args, **kwargs)

    return chained
