# Copyright (c) 2026 Mockarty. All rights reserved.

"""Runtime context for Mockarty test framework.

Tracks the *currently bound* test-case run + plan run + steps stack via
:class:`contextvars.ContextVar`. ContextVar is thread-safe AND copies
across asyncio tasks, so the same primitive works for sync pytest, async
pytest, and concurrent.futures-driven parallel suites alike.

Decorators (:mod:`mockarty.testing.decorators`) and the
:func:`mockarty.testing.scenario` context manager push/pop frames here.
The plugin (:mod:`mockarty.testing.plugin`) reads the active frame to
emit reports / attachments after the test finishes.

Design notes:
    * Frames are dataclasses, intentionally simple — no behavior, only
      data the rest of the framework reads.
    * "No active frame" returns ``None`` everywhere — callers are
      expected to no-op, not raise. This keeps pytest hooks fail-soft so
      a misconfigured environment never blocks the test suite.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CaseFrame:
    """One frame on the case stack — one ``@test_case``-decorated test.

    Phase 2.6 fields (description / expected_result / custom_fields /
    claim_ownership) are Mockarty-only extensions; the pytest plugin
    forwards them to the server's ExternalRunRequest at the same names
    so the case row carries the SDK-author's intent instead of the
    legacy 'Auto-created by external-run upload' boilerplate.
    """

    case_id: Optional[str] = None
    case_name: Optional[str] = None
    plan_id: Optional[str] = None
    auto_create: bool = False
    description: Optional[str] = None
    expected_result: Optional[str] = None
    custom_fields: list[dict[str, Any]] = field(default_factory=list)
    claim_ownership: bool = False
    attachments: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepFrame:
    """One frame on the step stack — one ``@step``-decorated function or ``with step()`` block."""

    name: str
    started_ns: int = 0
    status: str = "passed"
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Internal: index of this step's snapshot inside the owning case's
    # ``steps`` list. Set on push, used by pop to update the right slot
    # under nested-step scenarios. -1 when the step has no parent case.
    _slot_index: int = -1


_case_stack: contextvars.ContextVar[Optional[list[CaseFrame]]] = contextvars.ContextVar(
    "mockarty_case_stack", default=None
)
_step_stack: contextvars.ContextVar[Optional[list[StepFrame]]] = contextvars.ContextVar(
    "mockarty_step_stack", default=None
)
# Snapshot of the most-recently-popped CaseFrame. Used by the pytest
# plugin's post-test hooks (Allure writer, external-runs upload) — by
# the time those hooks fire the decorator's finally has already popped
# the live stack, so the snapshot is the only access path. Reset by
# :func:`reset_for_test` between tests.
_last_case: contextvars.ContextVar[Optional[CaseFrame]] = contextvars.ContextVar(
    "mockarty_last_case", default=None
)


def push_case(frame: CaseFrame) -> None:
    """Push a case frame onto the stack for the current context."""
    stack = _case_stack.get()
    if stack is None:
        stack = []
        _case_stack.set(stack)
    stack.append(frame)


def pop_case() -> Optional[CaseFrame]:
    """Pop the top case frame, or return ``None`` when the stack is empty.

    The popped frame is captured in ``_last_case`` so post-test hooks
    (Allure writer, external-runs upload) can still access it after the
    decorator's ``finally`` has fired.
    """
    stack = _case_stack.get()
    if not stack:
        return None
    frame = stack.pop()
    _last_case.set(frame)
    return frame


def last_case() -> Optional[CaseFrame]:
    """Return the most-recently-popped case frame (None when reset)."""
    return _last_case.get()


def current_case() -> Optional[CaseFrame]:
    """Return the active case frame, or ``None`` outside any binding."""
    stack = _case_stack.get()
    if not stack:
        return None
    return stack[-1]


def push_step(frame: StepFrame) -> None:
    """Push a step frame; auto-attached to the current case if any.

    Records the slot index inside ``case.steps`` so the matching
    :func:`pop_step` updates the correct dict — nested steps would
    otherwise overwrite each other when popping outwards.
    """
    stack = _step_stack.get()
    if stack is None:
        stack = []
        _step_stack.set(stack)
    stack.append(frame)
    case = current_case()
    if case is not None:
        case.steps.append(_frame_to_dict(frame))
        frame._slot_index = len(case.steps) - 1


def pop_step() -> Optional[StepFrame]:
    """Pop the top step frame and finalise its dict in the case's steps list."""
    stack = _step_stack.get()
    if not stack:
        return None
    frame = stack.pop()
    case = current_case()
    if (
        case is not None
        and frame._slot_index >= 0
        and frame._slot_index < len(case.steps)
    ):
        case.steps[frame._slot_index] = _frame_to_dict(frame)
    return frame


def current_step() -> Optional[StepFrame]:
    """Return the active step frame, or ``None`` outside any step block."""
    stack = _step_stack.get()
    if not stack:
        return None
    return stack[-1]


def _frame_to_dict(frame: StepFrame) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": frame.name,
        "status": frame.status,
        "started_ns": frame.started_ns,
    }
    if frame.error:
        out["error"] = frame.error
    if frame.metadata:
        out["metadata"] = dict(frame.metadata)
    return out


def reset_for_test() -> None:
    """Clear case + step stacks. Called by the plugin between tests."""
    _case_stack.set(None)
    _step_stack.set(None)
    _last_case.set(None)
