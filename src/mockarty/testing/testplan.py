# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Allure test-plan consumption — the ``ALLURE_TESTPLAN_PATH`` contract.

Allure TestOps (and Mockarty's own ``mockarty-cli allure rerun-failed`` /
``allure selection-plan``) drive *selective execution* by writing a
``testplan.json`` and exporting ``ALLURE_TESTPLAN_PATH``. The adapter is
expected to read that file and run **only** the listed tests.

File format (schema ``version: "1.0"``)::

    {
      "version": "1.0",
      "tests": [
        {"id": 11111, "selector": "my.company.SimpleTest.simpleTestOne"}
      ]
    }

``id`` is the Allure id (the ``@allure.id`` / ``@AllureId`` value, carried on
results as the ``ALLURE_ID`` / ``AS_ID`` label); ``selector`` is a full-name
style unique identifier of the test. At least one of the two must be present
on every entry; a test is selected when **either** matches.

Behaviour of this implementation (deliberately stricter than the reference
adapters, which silently fall back to a full run):

===============================  ==================================================
State                            Result
===============================  ==================================================
env var unset / empty            no filtering — normal, unfiltered run
``MOCKARTY_TESTPLAN_MODE=off``   no filtering, even when the path is set
plan with N entries              only matching tests run
plan with ``"tests": []``        **nothing runs**, reported explicitly
file missing/unreadable/broken   **error** — never a silent full run
``tests`` key absent or not a
list, or an entry with neither
``id`` nor ``selector``          **error** — the plan cannot select anything
===============================  ==================================================

The "silent full run" cases are the whole reason this module is strict: a
user who asks to re-run 3 failed tests must never get 3000 executed tests
and a green tick.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

__all__ = [
    "ENV_TESTPLAN_MODE",
    "ENV_TESTPLAN_PATH",
    "MODE_ENFORCE",
    "MODE_OFF",
    "SUPPORTED_VERSION",
    "TestPlan",
    "TestPlanEntry",
    "TestPlanError",
    "item_allure_ids",
    "item_selectors",
    "load_testplan",
    "parse_testplan",
    "select_items",
    "testplan_mode",
]

#: Path to the plan file. Canonical Allure TestOps contract — same spelling
#: in the Go and Java SDKs.
ENV_TESTPLAN_PATH = "ALLURE_TESTPLAN_PATH"

#: Escape hatch: ``off`` ignores the plan entirely (full run). Same spelling
#: in the Go and Java SDKs.
ENV_TESTPLAN_MODE = "MOCKARTY_TESTPLAN_MODE"

MODE_ENFORCE = "enforce"
MODE_OFF = "off"

#: The only schema version Allure TestOps emits today.
SUPPORTED_VERSION = "1.0"


class TestPlanError(Exception):
    """A test plan was requested but could not be honoured.

    Raised for a missing / unreadable / malformed plan. Never raised for
    "no plan configured" — that is a normal unfiltered run.
    """


@dataclass(frozen=True)
class TestPlanEntry:
    """One ``tests[]`` entry. At least one of the two fields is non-empty."""

    id: Optional[str] = None
    selector: Optional[str] = None


@dataclass
class TestPlan:
    """A parsed, validated ``testplan.json``."""

    path: str
    version: str
    entries: list[TestPlanEntry] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True when the plan selects nothing (``"tests": []``)."""
        return not self.entries

    def matches(self, ids: Iterable[str], selectors: Iterable[str]) -> bool:
        """True when any entry matches one of the test's ids or selectors."""
        id_set = {str(i) for i in ids if str(i)}
        selector_set = {str(s) for s in selectors if str(s)}
        for entry in self.entries:
            if entry.id is not None and entry.id in id_set:
                return True
            if entry.selector is not None and entry.selector in selector_set:
                return True
        return False


def testplan_mode(env: Optional[Mapping[str, str]] = None) -> str:
    """Resolve :data:`ENV_TESTPLAN_MODE`; unknown values fall back to enforce.

    Falling back to ``enforce`` (rather than erroring) is deliberate: a typo
    in the opt-out must not turn into "ran everything", which is the exact
    failure this module exists to prevent.
    """
    source = os.environ if env is None else env
    raw = (source.get(ENV_TESTPLAN_MODE) or "").strip().lower()
    if raw in ("off", "false", "0", "no", "disabled"):
        return MODE_OFF
    return MODE_ENFORCE


def parse_testplan(raw: Any, path: str) -> TestPlan:
    """Parse + validate plan bytes/str. Raises :class:`TestPlanError`."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TestPlanError(
                f"{ENV_TESTPLAN_PATH}={path}: not valid UTF-8 ({exc})"
            ) from exc
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise TestPlanError(
            f"{ENV_TESTPLAN_PATH}={path}: not valid JSON ({exc}). "
            "Refusing to run the full suite — fix the plan or unset "
            f"{ENV_TESTPLAN_PATH}."
        ) from exc
    if not isinstance(doc, dict):
        raise TestPlanError(
            f"{ENV_TESTPLAN_PATH}={path}: expected a JSON object with a "
            f"'tests' array, got {type(doc).__name__}."
        )

    version = doc.get("version")
    version = "" if version is None else str(version)

    tests = doc.get("tests")
    if tests is None:
        raise TestPlanError(
            f"{ENV_TESTPLAN_PATH}={path}: the plan has no 'tests' array. "
            "An Allure test plan without 'tests' cannot select anything; "
            "refusing to silently run the whole suite."
        )
    if not isinstance(tests, list):
        raise TestPlanError(
            f"{ENV_TESTPLAN_PATH}={path}: 'tests' must be an array, got "
            f"{type(tests).__name__}."
        )

    entries: list[TestPlanEntry] = []
    for index, item in enumerate(tests):
        if not isinstance(item, dict):
            raise TestPlanError(
                f"{ENV_TESTPLAN_PATH}={path}: tests[{index}] must be an "
                f"object with 'id' and/or 'selector', got "
                f"{type(item).__name__}."
            )
        entry_id = _clean(item.get("id"))
        selector = _clean(item.get("selector"))
        if entry_id is None and selector is None:
            raise TestPlanError(
                f"{ENV_TESTPLAN_PATH}={path}: tests[{index}] has neither "
                "'id' nor 'selector' — it can never match a test."
            )
        entries.append(TestPlanEntry(id=entry_id, selector=selector))

    return TestPlan(path=path, version=version, entries=entries)


def _clean(value: Any) -> Optional[str]:
    """Normalise a plan field to a non-empty string (ids may be numbers)."""
    if value is None:
        return None
    if isinstance(value, bool):  # guard: True would stringify to "True"
        return None
    text = str(value).strip()
    return text or None


def load_testplan(env: Optional[Mapping[str, str]] = None) -> Optional[TestPlan]:
    """Load the plan named by :data:`ENV_TESTPLAN_PATH`.

    Returns ``None`` when no plan is configured (or the mode is ``off``) —
    the caller then runs unfiltered. Raises :class:`TestPlanError` when a
    plan IS configured but cannot be read or parsed.
    """
    source = os.environ if env is None else env
    path = (source.get(ENV_TESTPLAN_PATH) or "").strip()
    if not path:
        return None
    if testplan_mode(source) == MODE_OFF:
        return None
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise TestPlanError(
            f"{ENV_TESTPLAN_PATH}={path}: cannot read the test plan ({exc}). "
            "Refusing to run the full suite — a selective run that silently "
            "becomes a full run is worse than a failed one."
        ) from exc
    return parse_testplan(raw, path)


# ── pytest item identity ────────────────────────────────────────────────
#
# A pytest item can be addressed by several equivalent strings depending on
# which tool produced the plan. We compute every plausible form and let the
# plan match any of them (the reference adapters do the same: allure-java
# matches uniqueId OR fullName).

#: Marker label types that carry an Allure id.
_ID_LABEL_TYPES = frozenset({"ALLURE_ID", "AS_ID", "ID", "ALLUREID"})


def item_allure_ids(item: Any) -> list[str]:
    """Every Allure id this test can be addressed by.

    Sources, in order:

    * ``@allure.id("123")`` / ``@pytest.mark.allure_label("123",
      label_type="ALLURE_ID")`` — how TestOps ids arrive in a pytest suite;
    * ``@pytest.mark.mockarty_case(case_id="CASE-1")`` and the equivalent
      ``@mockarty.testing.test_case("CASE-1")`` decorator, so a Mockarty-
      native suite is addressable by its TCM case id too.
    """
    ids: list[str] = []

    def add(value: Any) -> None:
        text = _clean(value)
        if text and text not in ids:
            ids.append(text)

    iter_markers = getattr(item, "iter_markers", None)
    if callable(iter_markers):
        try:
            markers = list(iter_markers(name="allure_label"))
        except TypeError:  # pragma: no cover — exotic item shims
            markers = []
        for mark in markers:
            label_type = str(getattr(mark, "kwargs", {}).get("label_type", "")).upper()
            if label_type in _ID_LABEL_TYPES:
                for arg in getattr(mark, "args", ()) or ():
                    add(arg)

    closest = getattr(item, "get_closest_marker", None)
    if callable(closest):
        case_marker = closest("mockarty_case")
        if case_marker is not None:
            kwargs = getattr(case_marker, "kwargs", {}) or {}
            add(kwargs.get("case_id"))
            args = getattr(case_marker, "args", ()) or ()
            if args:
                add(args[0])

    add(getattr(getattr(item, "obj", None), "__mockarty_case_id__", None))
    return ids


def item_selectors(item: Any) -> list[str]:
    """Every selector string this test can be addressed by.

    Covers the four shapes a plan realistically carries:

    * ``item.nodeid`` — what the Mockarty adapter reports as ``fullName``,
      so it is what Mockarty's own ``rerun-failed`` plan contains;
    * the nodeid with the parametrisation suffix stripped, so a plan that
      names the test function re-runs all of its parameter cases;
    * ``allure-pytest``'s ``package.Class#test`` full name (asked from the
      real allure-pytest when installed, so it is byte-exact);
    * the fully dot-separated ``package.Class.test``, which is the shape
      the Allure TestOps docs show for ``selector``.
    """
    selectors: list[str] = []

    def add(value: Any) -> None:
        text = _clean(value)
        if text and text not in selectors:
            selectors.append(text)

    nodeid = getattr(item, "nodeid", "") or ""
    add(nodeid)
    if "[" in nodeid:
        add(nodeid.split("[", 1)[0])

    try:  # byte-exact compatibility when the user has allure-pytest
        from allure_pytest.utils import allure_full_name  # type: ignore

        add(allure_full_name(item))
    except Exception:  # pragma: no cover — allure-pytest absent or changed
        pass

    package, classes, test = _split_nodeid(nodeid, item)
    if test:
        class_part = ("." + ".".join(classes)) if classes else ""
        if package:
            add(f"{package}{class_part}#{test}")
            add(f"{package}{class_part}.{test}")
        if classes:
            add(f"{'.'.join(classes)}#{test}")
            add(f"{'.'.join(classes)}.{test}")
        add(test)
    return selectors


def _split_nodeid(nodeid: str, item: Any) -> tuple[str, list[str], str]:
    """Split ``path/to/mod.py::Class::test[p]`` → (package, classes, test).

    Mirrors ``allure_pytest.utils.parse_nodeid`` closely enough that the
    resulting ``package.Class#test`` equals allure-pytest's ``fullName``
    for the common layouts, without depending on allure-pytest internals.
    """
    if not nodeid:
        return "", [], ""
    parts = nodeid.split("::")
    path = parts[0]
    if path.endswith(".py"):
        path = path[: -len(".py")]
    package = path.replace(os.sep, ".").replace("/", ".").strip(".")
    tail = parts[1:]
    if not tail:
        return package, [], ""
    test = tail[-1]
    if "[" in test:
        test = test.split("[", 1)[0]
    # pytest keeps the un-parametrised name on Function items.
    original = getattr(item, "originalname", None)
    if original:
        test = str(original)
    return package, [p for p in tail[:-1] if p], test


def select_items(items: Sequence[Any], plan: TestPlan) -> tuple[list[Any], list[Any]]:
    """Partition collected items into (selected, deselected) per the plan."""
    selected: list[Any] = []
    deselected: list[Any] = []
    for item in items:
        if plan.matches(item_allure_ids(item), item_selectors(item)):
            selected.append(item)
        else:
            deselected.append(item)
    return selected, deselected
