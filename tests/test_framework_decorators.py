# Copyright (c) 2026 Mockarty. All rights reserved.

"""Unit tests for the Mockarty test framework primitives.

Coverage:
    * Context stack semantics (push/pop, nesting, reset)
    * @test_case decorator (args validation, sync + async, frame state)
    * @step decorator + context manager (nesting, error capture, sync + async)
    * @attach_report marker propagation
    * mockarty.attach() — registers on active frame, no-op without frame
    * scenario() context manager (mock tracking, frame lifecycle)

The tests do NOT spin up a real Mockarty server — they exercise framework
state machinery only. Plugin upload behaviour is covered by a separate
integration test that mocks the SDK client surface.
"""

from __future__ import annotations

import asyncio
import pytest

# Aliases prefixed with `mk_` so pytest's `test_*` collection rule doesn't
# pick up the decorator factories themselves as test functions.
from mockarty.testing import attach as mk_attach
from mockarty.testing import attach_report as mk_attach_report
from mockarty.testing import context as ctx
from mockarty.testing import plan as mk_plan
from mockarty.testing import scenario as mk_scenario
from mockarty.testing import step as mk_step
from mockarty.testing import test_case as mk_test_case
from mockarty.testing.decorators import (
    declared_plan as _declared_plan,
    is_attach_report as _is_attach_report,
)


def setup_function(_):
    """Ensure each test starts with clean stacks."""
    ctx.reset_for_test()


# ── @test_case ──────────────────────────────────────────────────────────


def test_test_case_pushes_and_pops_frame():
    @mk_test_case("CASE-1")
    def fn():
        frame = ctx.current_case()
        assert frame is not None
        assert frame.case_id == "CASE-1"

    assert ctx.current_case() is None
    fn()
    assert ctx.current_case() is None


def test_test_case_with_auto_create_requires_name():
    with pytest.raises(ValueError, match="name="):
        @mk_test_case(auto_create=True)
        def _fn():
            pass


def test_test_case_requires_either_id_or_auto_create():
    with pytest.raises(ValueError, match="case_id"):
        @mk_test_case()
        def _fn():
            pass


def test_test_case_async_pushes_during_await():
    seen = {}

    @mk_test_case("CASE-ASYNC")
    async def fn():
        await asyncio.sleep(0)
        frame = ctx.current_case()
        seen["case_id"] = frame.case_id if frame else None

    asyncio.run(fn())
    assert seen["case_id"] == "CASE-ASYNC"
    assert ctx.current_case() is None


def test_test_case_plan_propagates_to_frame():
    @mk_test_case("CASE-1", plan="PLAN-42")
    def fn():
        frame = ctx.current_case()
        assert frame.plan_id == "PLAN-42"

    fn()


def test_test_case_metadata_isolated_per_call():
    @mk_test_case("CASE-1", metadata={"k": "v"})
    def fn():
        frame = ctx.current_case()
        frame.metadata["mutated"] = True
        return frame.metadata

    a = fn()
    b = fn()
    # Each invocation gets its own frame copy — mutating one doesn't bleed.
    assert "mutated" in a
    assert "mutated" in b
    assert a is not b


# ── @step / with mk_step() ────────────────────────────────────────────────


def test_step_as_context_manager_records_passed():
    @mk_test_case("CASE-1")
    def fn():
        with mk_step("login form"):
            pass
        return list(ctx.current_case().steps)

    steps = fn()
    assert len(steps) == 1
    assert steps[0]["name"] == "login form"
    assert steps[0]["status"] == "passed"


def test_step_captures_exception_status():
    @mk_test_case("CASE-1")
    def fn():
        seen_steps_at_exit = None
        try:
            with mk_step("risky"):
                raise RuntimeError("boom")
        except RuntimeError:
            seen_steps_at_exit = list(ctx.current_case().steps)
        return seen_steps_at_exit

    steps = fn()
    assert steps is not None
    assert len(steps) == 1
    assert steps[0]["status"] == "failed"
    assert "boom" in steps[0]["error"]


def test_step_nesting():
    @mk_test_case("CASE-1")
    def fn():
        with mk_step("outer"):
            with mk_step("inner"):
                pass
        return list(ctx.current_case().steps)

    steps = fn()
    # Both steps recorded on the case in the order they were *opened*.
    assert [s["name"] for s in steps] == ["outer", "inner"]


def test_step_decorator_form():
    @mk_test_case("CASE-1")
    def fn():
        @mk_step("decorated step")
        def inner():
            pass

        inner()
        return list(ctx.current_case().steps)

    steps = fn()
    assert steps[0]["name"] == "decorated step"


def test_step_requires_nonempty_name():
    with pytest.raises(ValueError):
        mk_step("")
    with pytest.raises(ValueError):
        mk_step("   ")


def test_step_works_outside_case_frame():
    # A bare `with mk_step(...)` outside a case frame should not raise.
    # The step is recorded on the step stack; since no case is active,
    # the framework has nothing to attach it to. This is the fail-soft path.
    with mk_step("orphan"):
        pass
    # No exception, no case frame mutation.
    assert ctx.current_case() is None


def test_step_does_not_leak_frame_when_allure_cm_raises_on_enter(monkeypatch):
    """Regression: an Allure-mirror failure in ``__enter__`` must not
    leave the Mockarty step frame dangling on the step stack — the user
    sees the swallowed exception (best-effort mirror) and the frame is
    cleaned up symmetrically with the no-mirror case.
    """
    from mockarty.testing import allure_interop as _allure

    class _BrokenCM:
        def __enter__(self):
            raise RuntimeError("allure CM blew up")

        def __exit__(self, *_):  # pragma: no cover — never reached
            return False

    # Swap allure_interop.step out for the duration of this test.
    monkeypatch.setattr(_allure, "step", lambda _name: _BrokenCM())

    with mk_step("guarded"):
        # Even though the Allure CM failed on __enter__, the Mockarty
        # step frame must be present mid-block (the fail-soft path
        # keeps Mockarty's own bookkeeping alive).
        assert ctx.current_step() is not None
        assert ctx.current_step().name == "guarded"

    # After exiting, the step stack is empty — no leak.
    assert ctx.current_step() is None


def test_step_pops_frame_even_when_allure_cm_raises_on_exit(monkeypatch):
    """Regression: an Allure-mirror failure in ``__exit__`` must not
    leave the Mockarty step frame on the stack either — the pop runs
    in a try/finally so the mirror's exception is swallowed but the
    bookkeeping still happens.
    """
    from mockarty.testing import allure_interop as _allure

    class _CrashOnExit:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            raise RuntimeError("allure exit blew up")

    monkeypatch.setattr(_allure, "step", lambda _name: _CrashOnExit())

    with mk_step("guarded"):
        assert ctx.current_step() is not None

    assert ctx.current_step() is None


# ── @attach_report + @plan ─────────────────────────────────────────────


def test_attach_report_marks_function():
    @mk_attach_report
    def fn():
        return 1

    assert _is_attach_report(fn) is True


def test_plan_decorator_records_id():
    @mk_plan("PLAN-7")
    def fn():
        return 1

    assert _declared_plan(fn) == "PLAN-7"


def test_plan_rejects_empty_id():
    with pytest.raises(ValueError):
        mk_plan("")


# ── mockarty.attach() ──────────────────────────────────────────────────


def test_attach_registers_on_active_frame():
    @mk_test_case("CASE-1")
    def fn():
        mk_attach("hello", "world", content_type="text/plain")
        return list(ctx.current_case().attachments)

    atts = fn()
    assert len(atts) == 1
    assert atts[0]["name"] == "hello"
    assert atts[0]["body"] == b"world"
    assert atts[0]["content_type"].startswith("text/plain")


def test_attach_silent_outside_frame():
    # No active case: attach() must no-op rather than blow up.
    mk_attach("orphan", b"x")  # no exception expected


def test_attach_rejects_empty_name():
    @mk_test_case("CASE-1")
    def fn():
        with pytest.raises(ValueError):
            mk_attach("", b"x")

    fn()


# ── scenario() ─────────────────────────────────────────────────────────


def test_scenario_pushes_and_pops_case_frame():
    assert ctx.current_case() is None
    with mk_scenario("login flow"):
        f = ctx.current_case()
        assert f is not None
        assert f.case_name == "login flow"
        assert f.auto_create is True
    assert ctx.current_case() is None


def test_scenario_records_pinned_case_id():
    with mk_scenario("login flow", case_id="CASE-9"):
        f = ctx.current_case()
        assert f.case_id == "CASE-9"
        assert f.auto_create is False  # pinned id wins over auto_create default


def test_scenario_metadata_helper():
    with mk_scenario("flow") as s:
        s.set_metadata(env="staging", build="42")
        f = ctx.current_case()
        assert f.metadata == {"env": "staging", "build": "42"}


def test_scenario_attach_delegates_to_attach_function(monkeypatch):
    """Scenario.attach must invoke mockarty.testing.attach so payloads land
    on the active case frame. Covers the UX papercut where users expected
    s.attach(...) but had to fall back to the free function."""
    seen: list[tuple] = []
    from mockarty.testing import decorators as _decorators

    monkeypatch.setattr(
        _decorators,
        "attach",
        lambda name, body, *, content_type="text/plain": seen.append(
            (name, body, content_type)
        ),
    )
    with mk_scenario("flow") as s:
        s.attach("note", "payload", content_type="text/plain")
    assert seen == [("note", "payload", "text/plain")]


def test_case_alias_equals_test_case():
    """Public ``case`` alias must be the same callable as ``test_case`` —
    exists only to dodge pytest's auto-collection of identifiers prefixed
    with ``test_``."""
    from mockarty.testing import case as mk_case
    from mockarty.testing import test_case as mk_test_case_direct

    assert mk_case is mk_test_case_direct
    # And the alias must be usable as a decorator with the same signature.
    @mk_case("CASE-ALIAS-1")
    def _demo():  # pragma: no cover — body is irrelevant
        pass


def test_scenario_mock_requires_client():
    with mk_scenario("flow") as s:
        with pytest.raises(RuntimeError, match="client="):
            s.mock(object())


class _StubMockResult:
    def __init__(self, mock_id):
        self.mock = type("M", (), {"id": mock_id})


class _StubClient:
    def __init__(self):
        self.created = []
        self.deleted = []

        class _Mocks:
            def __init__(self, parent):
                self.parent = parent

            def create(self, mock):
                mid = f"m-{len(self.parent.created)}"
                self.parent.created.append(mid)
                return _StubMockResult(mid)

            def delete(self, mock_id):
                self.parent.deleted.append(mock_id)

        self.mocks = _Mocks(self)


def test_scenario_tracks_and_cleans_mocks():
    client = _StubClient()
    with mk_scenario("flow", client=client) as s:
        s.mock({"some": "mock"})
        s.mock({"another": "mock"})
        assert client.created == ["m-0", "m-1"]
        assert client.deleted == []
    assert client.deleted == ["m-0", "m-1"]


def test_scenario_cleanup_runs_even_on_exception():
    client = _StubClient()
    with pytest.raises(RuntimeError, match="from inside"):
        with mk_scenario("flow", client=client) as s:
            s.mock({"any": "mock"})
            raise RuntimeError("from inside")
    # Cleanup must still have run.
    assert client.deleted == ["m-0"]


# ── reset_for_test ─────────────────────────────────────────────────────


def test_reset_clears_stacks():
    ctx.push_case(ctx.CaseFrame(case_id="X"))
    ctx.push_step(ctx.StepFrame(name="s"))
    assert ctx.current_case() is not None
    assert ctx.current_step() is not None
    ctx.reset_for_test()
    assert ctx.current_case() is None
    assert ctx.current_step() is None
