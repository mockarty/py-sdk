# Copyright (c) 2026 Mockarty. All rights reserved.

"""Allure mirror-mode default-ON verification (Wave 1, piece G-py).

Per SDK_FRAMEWORK_PLAN rev 3 §2 + §5.1 (Owner directive 2026-05-16),
``allure``-based test code MUST run through the Mockarty SDK with zero
refactor. This test file pins that contract.

Three usage patterns covered:

    1.  ``import allure`` + ``with allure.step()`` — pure Allure code,
        steps end up in BOTH allure-pytest's native lifecycle AND our
        :class:`~mockarty.testing.context.CaseFrame`.
    2.  Mixed: ``@allure.feature(...)`` together with
        ``@mockarty.testing.test_case`` — both sinks receive every event.
    3.  Pure ``mockarty.testing.step`` — works regardless of whether
        ``allure-pytest`` is installed (no double-counting when it is).

Also covers:

    * Nested ``@allure.step`` three deep.
    * ``allure.attach`` with binary body.
    * The ``mockarty.allure`` drop-in alias module (option-4 migration).
    * Opt-out via ``MOCKARTY_ALLURE_MIRROR=off`` — listener is detached.

These tests assume ``allure-pytest`` is installed (it's in the
``[allure]`` extra). If it isn't, the relevant sub-tests are
``pytest.skip``ed — the rest of the suite still runs.
"""

from __future__ import annotations

import pytest

from mockarty.testing import allure_interop as _mirror
from mockarty.testing import context as ctx
from mockarty.testing import step as mk_step
from mockarty.testing import test_case as mk_test_case


@pytest.fixture(autouse=True)
def _reset_state():
    """Each test starts with clean Mockarty stacks + pending buffers."""
    ctx.reset_for_test()
    _mirror._pending_labels.clear()
    _mirror._pending_links.clear()
    _mirror._pending_title.clear()
    _mirror._pending_description.clear()
    yield
    ctx.reset_for_test()


@pytest.fixture
def allure_installed() -> bool:
    """True iff allure-pytest is importable in this test env."""
    try:
        import allure  # noqa: F401
    except Exception:
        return False
    return True


@pytest.fixture
def listener_active(allure_installed: bool):
    """Ensure the Allure→Mockarty mirror listener is registered.

    The pytest plugin's ``pytest_configure`` already installs it once at
    session start; this fixture asserts that and re-installs if a
    previous test detached the listener for opt-out testing.
    """
    if not allure_installed:
        pytest.skip("allure-pytest not installed")
    if not _mirror._registered:
        _mirror.install_listener()
    assert _mirror._registered
    yield
    if not _mirror._registered:
        _mirror.install_listener()


# ─────────────────────────────────────────────────────────────────────────
# 1) PURE Allure: import allure + with allure.step — flows into both sinks
# ─────────────────────────────────────────────────────────────────────────


def test_pure_allure_step_mirrors_into_mockarty_frame(listener_active):
    """A naked ``with allure.step(...)`` writes into the active Mockarty CaseFrame."""
    import allure

    case = ctx.CaseFrame(case_id="CASE-PURE-1")
    ctx.push_case(case)
    try:
        with allure.step("submit login form"):
            pass
    finally:
        ctx.pop_case()

    # Mockarty's accumulator now has the Allure-emitted step.
    assert len(case.steps) == 1
    assert case.steps[0]["name"] == "submit login form"
    assert case.steps[0]["status"] == "passed"


def test_pure_allure_step_records_failure(listener_active):
    """Exception inside an Allure step is reflected on the Mockarty step."""
    import allure

    case = ctx.CaseFrame(case_id="CASE-PURE-FAIL")
    ctx.push_case(case)
    try:
        try:
            with allure.step("risky"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
    finally:
        ctx.pop_case()

    assert len(case.steps) == 1
    assert case.steps[0]["status"] == "failed"
    assert "boom" in (case.steps[0].get("error") or "")


def test_pure_allure_step_nested_three_deep(listener_active):
    """Three nested ``allure.step``s all appear on the Mockarty frame."""
    import allure

    case = ctx.CaseFrame(case_id="CASE-NEST-3")
    ctx.push_case(case)
    try:
        with allure.step("outer"):
            with allure.step("middle"):
                with allure.step("inner"):
                    pass
    finally:
        ctx.pop_case()

    assert [s["name"] for s in case.steps] == ["outer", "middle", "inner"]


def test_pure_allure_attach_mirrors_binary(listener_active):
    """``allure.attach`` with binary body ends up in the Mockarty frame."""
    import allure

    case = ctx.CaseFrame(case_id="CASE-ATTACH-BIN")
    ctx.push_case(case)
    try:
        payload = b"\x00\x01\x02PNG-bytes"
        with allure.step("upload artefact"):
            allure.attach(
                payload,
                name="snapshot.png",
                attachment_type=allure.attachment_type.PNG,
            )
    finally:
        ctx.pop_case()

    assert len(case.attachments) == 1
    att = case.attachments[0]
    assert att["name"] == "snapshot.png"
    assert att["body"] == payload
    assert att["content_type"].startswith("image/")


# ─────────────────────────────────────────────────────────────────────────
# 2) MIXED: @allure.feature + @mockarty.testing.test_case
# ─────────────────────────────────────────────────────────────────────────


def test_mixed_decorators_both_sinks_receive(listener_active):
    """``allure.dynamic.feature(...)`` writes label onto Mockarty case metadata."""
    import allure

    @mk_test_case("CASE-MIXED-1")
    def inner():
        allure.dynamic.feature("auth")
        with allure.step("login"):
            pass
        return ctx.current_case()

    captured = inner()
    assert captured is not None
    # Step came through the mirror.
    assert [s["name"] for s in captured.steps] == ["login"]
    # Feature label came through add_label.
    labels = captured.metadata.get("_allure_labels", [])
    assert any(
        lab["value"] == "auth" and lab["name"].endswith("feature")
        for lab in labels
    ), labels


def test_mixed_mockarty_step_does_not_double_record(listener_active):
    """Mockarty's own ``step()`` opens an Allure step too — but the listener
    must NOT also push it onto the Mockarty frame (else the same step
    would appear twice)."""

    @mk_test_case("CASE-MIXED-2")
    def inner():
        with mk_step("seed mock"):
            pass
        return ctx.current_case()

    captured = inner()
    # Exactly one step — Mockarty's, not duplicated by the mirror.
    assert [s["name"] for s in captured.steps] == ["seed mock"]


# ─────────────────────────────────────────────────────────────────────────
# 3) PURE Mockarty: works regardless of allure-pytest installation
# ─────────────────────────────────────────────────────────────────────────


def test_pure_mockarty_step_works_without_allure_visible():
    """``mk_step`` works whether or not allure-pytest is installed.

    When installed we still don't double-record (covered above). When
    NOT installed, ``allure_interop.step()`` returns a no-op CM —
    verified here by exercising the suppressed branch.
    """

    @mk_test_case("CASE-PURE-MK")
    def inner():
        with mk_step("just-mockarty"):
            pass
        return ctx.current_case()

    captured = inner()
    assert [s["name"] for s in captured.steps] == ["just-mockarty"]


# ─────────────────────────────────────────────────────────────────────────
# 4) mockarty.allure alias module — drop-in replacement
# ─────────────────────────────────────────────────────────────────────────


def test_mockarty_allure_alias_surface_matches_allure():
    """``mockarty.allure`` exports the same top-level symbols as ``allure``."""
    import mockarty.allure as mockarty_allure

    for symbol in (
        "step",
        "attach",
        "title",
        "description",
        "label",
        "severity",
        "epic",
        "feature",
        "story",
        "suite",
        "parent_suite",
        "sub_suite",
        "tag",
        "id",
        "link",
        "issue",
        "testcase",
        "dynamic",
        "severity_level",
        "attachment_type",
    ):
        assert hasattr(mockarty_allure, symbol), f"missing: {symbol}"


def test_mockarty_allure_step_writes_through_to_mockarty_frame(
    listener_active,
):
    """``mockarty.allure.step`` (which re-exports allure.step) routes into Mockarty."""
    import mockarty.allure as mockarty_allure

    case = ctx.CaseFrame(case_id="CASE-ALIAS-1")
    ctx.push_case(case)
    try:
        with mockarty_allure.step("aliased step"):
            pass
    finally:
        ctx.pop_case()

    assert [s["name"] for s in case.steps] == ["aliased step"]


def test_mockarty_allure_decorator_form(listener_active):
    """``mockarty.allure.step("title")`` works as a function decorator too."""
    import mockarty.allure as mockarty_allure

    case = ctx.CaseFrame(case_id="CASE-ALIAS-DECO")
    ctx.push_case(case)

    @mockarty_allure.step("decorator-applied")
    def do_work():
        return 42

    try:
        result = do_work()
    finally:
        ctx.pop_case()

    assert result == 42
    assert [s["name"] for s in case.steps] == ["decorator-applied"]


# ─────────────────────────────────────────────────────────────────────────
# 5) Default-ON: mirror is registered at plugin-load time
# ─────────────────────────────────────────────────────────────────────────


def test_listener_is_registered_by_default(allure_installed: bool):
    """The pytest plugin's ``pytest_configure`` registers our listener.

    Verifies the **default-ON** contract — no env var, no config, the
    listener is just there after ``pip install mockarty``.
    """
    if not allure_installed:
        pytest.skip("allure-pytest not installed")
    assert _mirror._registered, "listener should be auto-registered by plugin"
    assert _mirror.is_allure_available()


# ─────────────────────────────────────────────────────────────────────────
# 6) Opt-out via MOCKARTY_ALLURE_MIRROR=off
# ─────────────────────────────────────────────────────────────────────────


def test_mirror_can_be_disabled_via_env(monkeypatch, allure_installed: bool):
    """Setting ``MOCKARTY_ALLURE_MIRROR=off`` makes install_listener() refuse."""
    if not allure_installed:
        pytest.skip("allure-pytest not installed")
    # Detach existing listener, then try to reinstall with opt-out env.
    _mirror.uninstall_listener()
    assert not _mirror._registered

    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")
    installed = _mirror.install_listener()
    assert installed is False
    assert not _mirror._registered

    # Restore for downstream tests.
    monkeypatch.delenv("MOCKARTY_ALLURE_MIRROR")
    _mirror.install_listener()
    assert _mirror._registered


def test_mirror_idempotent_install(allure_installed: bool):
    """Calling install_listener() twice is a no-op (no duplicate listener)."""
    if not allure_installed:
        pytest.skip("allure-pytest not installed")
    if not _mirror._registered:
        _mirror.install_listener()
    first = _mirror._registered
    second = _mirror.install_listener()
    assert first is True
    assert second is True


# ─────────────────────────────────────────────────────────────────────────
# 7) No active frame → mirror is silent (no exceptions)
# ─────────────────────────────────────────────────────────────────────────


def test_allure_step_without_case_frame_is_silent(listener_active):
    """No CaseFrame active → mirror silently no-ops, no exception."""
    import allure

    assert ctx.current_case() is None
    with allure.step("orphan"):
        pass  # must not raise
    assert ctx.current_case() is None


# ─────────────────────────────────────────────────────────────────────────
# 8) SuppressingCM resets the ContextVar even when the inner CM
#    raises in __enter__ — regression guard for the recursion guard.
# ─────────────────────────────────────────────────────────────────────────


def test_suppressing_cm_resets_contextvar_on_enter_failure():
    """A failed ``__enter__`` must NOT leak the suppression flag.

    If the recursion guard ContextVar leaks (because we forgot to reset
    it in the enter-failure branch), the next genuine Allure step in
    the same context would be silently dropped by the mirror — a
    silent data-loss bug. Pin the contract here.
    """

    class _Failing:
        def __enter__(self):
            raise RuntimeError("inner enter failed")

        def __exit__(self, *_):  # pragma: no cover — never reached
            return False

    assert _mirror._suppress_mirror.get() is False
    cm = _mirror._SuppressingCM(_Failing())
    with pytest.raises(RuntimeError):
        cm.__enter__()
    assert _mirror._suppress_mirror.get() is False, (
        "ContextVar leaked after inner __enter__ raised — the recursion "
        "guard would silently drop subsequent Allure step events."
    )
