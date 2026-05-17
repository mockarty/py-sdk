# Copyright (c) 2026 Mockarty. All rights reserved.

"""Decorators and context managers for binding tests to Mockarty entities.

Public surface:
    * :func:`test_case` — decorator binding a test to a TCM case (existing or auto-create).
    * :func:`step` — decorator OR context manager opening a step under the current case.
    * :func:`attach_report` — decorator marking a test for auto-upload of attachments + outcome.
    * :func:`plan` — decorator declaring the owning Test Plan; consumed by the plugin.

All decorators are **fail-soft**: when invoked outside a Mockarty-aware test
session (no fixture, no server) they no-op and return the wrapped function
unchanged. This lets users keep the decorators in code that runs in both
local-only and Mockarty-connected modes.

Allure interop: when the user has ``allure-pytest`` installed every step is
mirrored into ``allure.step()`` automatically — see :mod:`mockarty.testing.allure_interop`.
"""

from __future__ import annotations

import functools
import inspect
import time
from typing import Any, Callable, Optional, TypeVar

from mockarty.testing import context as _ctx

# Try to find allure-pytest's `step` decorator. Best-effort: when missing,
# we still emit Mockarty steps; allure mirroring just doesn't happen.
try:  # pragma: no cover — runtime detection
    from mockarty.testing import allure_interop as _allure
except ImportError:  # pragma: no cover
    _allure = None  # type: ignore[assignment]


F = TypeVar("F", bound=Callable[..., Any])


# ── @test_case ──────────────────────────────────────────────────────────


def test_case(
    case_id: Optional[str] = None,
    *,
    name: Optional[str] = None,
    plan: Optional[str] = None,
    auto_create: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> Callable[[F], F]:
    """Bind a test function to a Mockarty TCM case.

    Examples::

        @mockarty.test_case("CASE-LOGIN-1")
        def test_login(mockarty_client): ...

        @mockarty.test_case(name="login flow", auto_create=True, plan="qa-smoke")
        def test_login_auto(mockarty_client): ...

    Args:
        case_id: existing TCM case id to bind against. Mutually exclusive
            with ``auto_create=True``.
        name: human-readable case name. Required with ``auto_create=True``.
        plan: owning Test Plan id (numeric or uuid). Optional — used by the
            plugin to associate the test with a plan run.
        auto_create: when True, the plugin creates the case in TCM if it
            doesn't exist yet. The created case id is reported in the test
            log so subsequent runs can pin it via ``case_id=``.
        metadata: free-form dict attached to the case frame; surfaces in
            attachments / reports.

    Returns:
        A decorator that pushes a :class:`mockarty.testing.context.CaseFrame`
        for the duration of the test, then pops it.
    """
    if not case_id and not auto_create:
        raise ValueError(
            "mockarty.test_case() requires either case_id= or auto_create=True"
        )
    if auto_create and not name:
        raise ValueError("mockarty.test_case(auto_create=True) requires name=")

    def decorator(fn: F) -> F:
        meta = dict(metadata) if metadata else {}

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                frame = _ctx.CaseFrame(
                    case_id=case_id,
                    case_name=name,
                    plan_id=plan,
                    auto_create=auto_create,
                    metadata=dict(meta),
                )
                _ctx.push_case(frame)
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _ctx.pop_case()

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            frame = _ctx.CaseFrame(
                case_id=case_id,
                case_name=name,
                plan_id=plan,
                auto_create=auto_create,
                metadata=dict(meta),
            )
            _ctx.push_case(frame)
            try:
                return fn(*args, **kwargs)
            finally:
                _ctx.pop_case()

        return wrapper  # type: ignore[return-value]

    return decorator


# ── @step / with step(...) ──────────────────────────────────────────────


def step(name: str) -> Any:
    """Mark a function or block as a TCM step.

    Two equivalent usages::

        # Decorator (function-level step):
        @mockarty.step("login form submit")
        def login(client, ...): ...

        # Context manager (block-level step):
        with mockarty.step("verify response"):
            assert resp.status == 200

    Steps nest: the inner step is recorded after the outer one. When
    ``allure-pytest`` is installed each Mockarty step is mirrored into
    Allure automatically — keeping a single source of truth in your code.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("mockarty.step() requires a non-empty name")
    return _StepDecoratorOrCtx(name)


class _StepDecoratorOrCtx:
    """Dual-purpose helper: works as decorator AND context manager."""

    def __init__(self, name: str) -> None:
        self.name = name

    # context-manager protocol
    def __enter__(self) -> "_StepDecoratorOrCtx":
        self._frame = _ctx.StepFrame(name=self.name, started_ns=time.monotonic_ns())
        _ctx.push_step(self._frame)
        # Allure mirror is best-effort: if its CM blows up at __enter__
        # we must NOT leave the Mockarty step frame dangling on the
        # stack. Pop it back out and re-raise so the surrounding test
        # sees the original error.
        self._allure_cm = None
        if _allure is not None:
            try:
                cm = _allure.step(self.name)
                cm.__enter__()
                self._allure_cm = cm
            except Exception:  # pragma: no cover — best-effort mirror
                # Mirror failed — keep Mockarty step alive, don't crash
                # the user's test on an Allure plumbing hiccup.
                self._allure_cm = None
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Any,
    ) -> None:
        frame = _ctx.current_step()
        if frame is not None and exc_type is not None:
            frame.status = "failed"
            frame.error = f"{exc_type.__name__}: {exc}"
        # Pop Mockarty step first, then attempt Allure CM teardown —
        # never let an Allure exit error mask a user exception.
        try:
            _ctx.pop_step()
        finally:
            cm = self._allure_cm
            if cm is not None:
                self._allure_cm = None
                try:
                    cm.__exit__(exc_type, exc, tb)
                except Exception:  # pragma: no cover — best-effort mirror
                    pass

    # decorator protocol
    def __call__(self, fn: F) -> F:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _StepDecoratorOrCtx(self.name):
                    return await fn(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with _StepDecoratorOrCtx(self.name):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]


# ── @attach_report ──────────────────────────────────────────────────────


def attach_report(fn: F) -> F:
    """Mark a test for auto-upload of its outcome + captured artifacts.

    The plugin's ``pytest_runtest_makereport`` hook reads this marker and,
    after the test completes, uploads:

      * the test outcome (passed / failed / skipped + duration)
      * captured stdout / stderr
      * any explicit attachments registered via :func:`mockarty.attach`

    to the bound TCM case run on the configured Mockarty server.

    The marker is fail-soft: when no Mockarty client / no bound case is
    detected, the upload is silently skipped (the test still passes).
    """
    setattr(fn, "_mockarty_attach_report", True)
    return fn


def is_attach_report(fn: Callable[..., Any]) -> bool:
    """Plugin helper: True if ``fn`` was decorated with :func:`attach_report`."""
    return bool(getattr(fn, "_mockarty_attach_report", False))


# ── attach() — explicit artifact upload ─────────────────────────────────


def attach(
    name: str,
    body: bytes | str,
    *,
    content_type: str = "application/octet-stream",
) -> None:
    """Register an attachment on the active case frame.

    Body is held in memory until the plugin uploads it after the test.
    Heavy artifacts (multi-MB) should be deferred to per-step file uploads
    via the SDK directly — this helper is for small artifacts (logs,
    response snippets, screenshots).
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("mockarty.attach() requires a non-empty name")
    if isinstance(body, str):
        body = body.encode("utf-8")
        if content_type == "application/octet-stream":
            content_type = "text/plain; charset=utf-8"
    case = _ctx.current_case()
    if case is None:
        return  # silently no-op — fail-soft outside a binding
    case.attachments.append(
        {"name": name, "body": body, "content_type": content_type}
    )
    if _allure is not None:
        try:
            _allure.attach(body, name=name, content_type=content_type)
        except Exception:  # pragma: no cover — best-effort mirror
            pass


# ── @plan declaration ───────────────────────────────────────────────────


def plan(plan_id: str) -> Callable[[F], F]:
    """Declare the owning Test Plan for a test.

    Equivalent to passing ``plan=`` to :func:`test_case`, but composable
    independently — handy when the same case decorator is reused across
    multiple plans.
    """
    if not plan_id:
        raise ValueError("mockarty.plan() requires a non-empty plan id")

    def decorator(fn: F) -> F:
        setattr(fn, "_mockarty_plan_id", plan_id)
        return fn

    return decorator


def declared_plan(fn: Callable[..., Any]) -> Optional[str]:
    """Plugin helper: read the @plan declaration off a function."""
    pid = getattr(fn, "_mockarty_plan_id", None)
    return pid if isinstance(pid, str) else None


# Re-export `step` factory + class so users can ``isinstance(x, mockarty.step)``-style
# checks if they want to (rare). The decorator/context-manager pair is the
# normal entry point.
__all__ = [
    "attach",
    "attach_report",
    "declared_plan",
    "is_attach_report",
    "plan",
    "step",
    "test_case",
]
