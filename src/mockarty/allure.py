# Copyright (c) 2026 Mockarty. All rights reserved.

"""``mockarty.allure`` — drop-in alias for the ``allure`` package.

Why this module exists
----------------------

Per the SDK strategic pivot (SDK_FRAMEWORK_PLAN rev 3, §2 + §8.1) Mockarty
SDK promises **zero-refactor migration** from Allure-based test suites.
Three usage patterns must work simultaneously:

1.  **Pure Allure** — user has ``allure-pytest`` installed and writes::

        import allure
        @allure.feature("auth")
        def test_login():
            with allure.step("submit form"):
                ...

    Their existing code is untouched. Our listener (registered by the
    pytest plugin) hooks into ``allure_commons.plugin_manager`` and
    mirrors every step / attach / label into a Mockarty case frame,
    which then flows to the admin server as a TCM external-run.

2.  **Mixed** — same suite combines ``@allure.feature(...)`` with
    ``@mockarty.testing.test_case(...)``. Both report sinks receive
    every step.

3.  **Pure Mockarty** — user writes::

        from mockarty.testing import step, test_case
        @test_case("CASE-1")
        def test_login():
            with step("submit form"):
                ...

    Works without ``allure-pytest`` installed at all (no-op mirror).

This file provides option 4: import ``mockarty.allure`` as if it were
``allure``. The surface mirrors the actual ``allure`` package symbol-for-
symbol — when ``allure-pytest`` is installed we re-export its real
implementations (so users get the original behaviour PLUS our mirror);
when it isn't, we stub each decorator to a no-op so the user's code
still type-checks and runs.

Example::

    import mockarty.allure as allure   # drop-in
    @allure.feature("auth")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_login():
        with allure.step("submit form"):
            allure.attach("hello", name="hint", attachment_type=allure.attachment_type.TEXT)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator

# ── Discovery ───────────────────────────────────────────────────────────

try:  # pragma: no cover — runtime detection
    import allure as _real_allure  # type: ignore[import-not-found]

    _ALLURE_AVAILABLE = True
except Exception:  # pragma: no cover
    _real_allure = None  # type: ignore[assignment]
    _ALLURE_AVAILABLE = False


def is_real_allure_available() -> bool:
    """True iff the user has ``allure-pytest`` (or ``allure-commons``) installed."""
    return _ALLURE_AVAILABLE


# ── Re-exports / stubs ──────────────────────────────────────────────────

if _ALLURE_AVAILABLE:
    # Direct re-export keeps signatures + dynamic surface identical.
    step = _real_allure.step  # type: ignore[attr-defined]
    attach = _real_allure.attach  # type: ignore[attr-defined]
    title = _real_allure.title  # type: ignore[attr-defined]
    description = _real_allure.description  # type: ignore[attr-defined]
    description_html = _real_allure.description_html  # type: ignore[attr-defined]
    label = _real_allure.label  # type: ignore[attr-defined]
    severity = _real_allure.severity  # type: ignore[attr-defined]
    epic = _real_allure.epic  # type: ignore[attr-defined]
    feature = _real_allure.feature  # type: ignore[attr-defined]
    story = _real_allure.story  # type: ignore[attr-defined]
    suite = _real_allure.suite  # type: ignore[attr-defined]
    parent_suite = _real_allure.parent_suite  # type: ignore[attr-defined]
    sub_suite = _real_allure.sub_suite  # type: ignore[attr-defined]
    tag = _real_allure.tag  # type: ignore[attr-defined]
    id = _real_allure.id  # type: ignore[attr-defined,assignment]  # noqa: A001
    link = _real_allure.link  # type: ignore[attr-defined]
    issue = _real_allure.issue  # type: ignore[attr-defined]
    testcase = _real_allure.testcase  # type: ignore[attr-defined]
    dynamic = _real_allure.dynamic  # type: ignore[attr-defined]
    manual = _real_allure.manual  # type: ignore[attr-defined]
    attachment_type = _real_allure.attachment_type  # type: ignore[attr-defined]
    severity_level = _real_allure.severity_level  # type: ignore[attr-defined]
    parameter_mode = _real_allure.parameter_mode  # type: ignore[attr-defined]
    global_attach = _real_allure.global_attach  # type: ignore[attr-defined]
    global_error = _real_allure.global_error  # type: ignore[attr-defined]
else:  # pragma: no cover — allure not installed → stub everything

    def _noop_decorator(*_a: Any, **_kw: Any) -> Callable[[Callable], Callable]:
        def _wrap(fn: Callable) -> Callable:
            return fn

        return _wrap

    @contextmanager
    def _noop_cm(*_a: Any, **_kw: Any) -> Iterator[None]:
        yield

    class _StepShim:
        def __call__(self, title: str) -> Any:
            return _noop_cm()

    class _AttachShim:
        def __call__(self, *_a: Any, **_kw: Any) -> None:
            return None

        def file(self, *_a: Any, **_kw: Any) -> None:
            return None

    class _DynamicShim:
        def __getattr__(self, _name: str) -> Callable[..., None]:
            def _noop(*_a: Any, **_kw: Any) -> None:
                return None

            return _noop

    step = _StepShim()  # type: ignore[assignment]
    attach = _AttachShim()  # type: ignore[assignment]
    global_attach = _AttachShim()  # type: ignore[assignment]
    global_error = lambda *a, **kw: None  # type: ignore[assignment]  # noqa: E731
    title = _noop_decorator  # type: ignore[assignment]
    description = _noop_decorator  # type: ignore[assignment]
    description_html = _noop_decorator  # type: ignore[assignment]
    label = _noop_decorator  # type: ignore[assignment]
    severity = _noop_decorator  # type: ignore[assignment]
    epic = _noop_decorator  # type: ignore[assignment]
    feature = _noop_decorator  # type: ignore[assignment]
    story = _noop_decorator  # type: ignore[assignment]
    suite = _noop_decorator  # type: ignore[assignment]
    parent_suite = _noop_decorator  # type: ignore[assignment]
    sub_suite = _noop_decorator  # type: ignore[assignment]
    tag = _noop_decorator  # type: ignore[assignment]
    id = _noop_decorator  # type: ignore[assignment]  # noqa: A001
    link = _noop_decorator  # type: ignore[assignment]
    issue = _noop_decorator  # type: ignore[assignment]
    testcase = _noop_decorator  # type: ignore[assignment]
    manual = _noop_decorator  # type: ignore[assignment]
    dynamic = _DynamicShim()  # type: ignore[assignment]
    attachment_type = type("AttachmentType", (), {})  # type: ignore[assignment]
    severity_level = type(
        "SeverityLevel",
        (),
        {
            "BLOCKER": "blocker",
            "CRITICAL": "critical",
            "NORMAL": "normal",
            "MINOR": "minor",
            "TRIVIAL": "trivial",
        },
    )  # type: ignore[assignment]
    parameter_mode = type("ParameterMode", (), {})  # type: ignore[assignment]


__all__ = [
    "attach",
    "attachment_type",
    "description",
    "description_html",
    "dynamic",
    "epic",
    "feature",
    "global_attach",
    "global_error",
    "id",
    "install_allure_shim",
    "is_real_allure_available",
    "issue",
    "label",
    "link",
    "manual",
    "parameter_mode",
    "parent_suite",
    "severity",
    "severity_level",
    "step",
    "story",
    "sub_suite",
    "suite",
    "tag",
    "testcase",
    "title",
]


# ── Optional sys.modules shim ───────────────────────────────────────────


def install_allure_shim() -> bool:
    """Register ``mockarty.allure`` as ``sys.modules["allure"]``.

    OPT-IN aggressive integration: after calling this, *any* ``import
    allure`` in user code resolves to this module. Only useful when
    ``allure-pytest`` is NOT installed and the user wants existing
    Allure code to keep working as a no-op. Guarded by the env var
    ``MOCKARTY_ALLURE_SHIM=on`` so it never engages by surprise.

    Returns True when the shim was installed (or already in place),
    False when ``allure-pytest`` is genuinely installed (we yield to
    the real package) or the env var disagrees.
    """
    import os
    import sys

    if (os.environ.get("MOCKARTY_ALLURE_SHIM") or "").lower() not in (
        "1",
        "on",
        "true",
        "yes",
    ):
        return False
    if _ALLURE_AVAILABLE:
        # Real allure-pytest is installed — don't shadow it.
        return False
    if "allure" in sys.modules and sys.modules["allure"] is not _self_module():
        return True  # someone already provided a stub
    sys.modules["allure"] = _self_module()
    return True


def _self_module():  # pragma: no cover — trivial accessor
    import sys

    return sys.modules[__name__]
