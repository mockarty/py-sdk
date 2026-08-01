# Copyright (c) 2026 Mockarty. All rights reserved.

"""Allure test-plan consumption (``ALLURE_TESTPLAN_PATH``).

Two layers:

* unit tests over :mod:`mockarty.testing.testplan` (parsing, validation,
  identity extraction);
* end-to-end ``pytester`` sessions proving the pytest plugin actually
  restricts execution — including the two failure modes that must never
  degrade into a silent full run (empty plan, broken plan).

The inner sessions run with ``-p no:allure_pytest`` so the assertions are
about OUR adapter; a dedicated test covers co-existence with a real
allure-pytest install.
"""

from __future__ import annotations

import json

import pytest

from mockarty.testing import testplan as tp

pytester = pytest.importorskip("_pytest.pytester")
pytest_plugins = ["pytester"]


def _write_plan(path, tests, version="1.0"):
    doc = {"tests": tests}
    if version is not None:
        doc["version"] = version
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


# ── unit: parsing + validation ──────────────────────────────────────────


def test_parse_plan_normalises_numeric_ids():
    plan = tp.parse_testplan(
        json.dumps({"version": "1.0", "tests": [{"id": 11111, "selector": "a.B.c"}]}),
        "/tmp/plan.json",
    )
    assert plan.version == "1.0"
    assert plan.entries == [tp.TestPlanEntry(id="11111", selector="a.B.c")]
    assert not plan.is_empty
    assert plan.matches(["11111"], [])
    assert plan.matches([], ["a.B.c"])
    assert not plan.matches(["9"], ["other"])


def test_parse_plan_accepts_id_only_and_selector_only():
    plan = tp.parse_testplan(
        json.dumps({"version": "1.0", "tests": [{"id": "7"}, {"selector": "x#y"}]}),
        "p",
    )
    assert plan.entries == [
        tp.TestPlanEntry(id="7", selector=None),
        tp.TestPlanEntry(id=None, selector="x#y"),
    ]


def test_parse_plan_empty_tests_is_valid_but_empty():
    plan = tp.parse_testplan(json.dumps({"version": "1.0", "tests": []}), "p")
    assert plan.is_empty
    assert not plan.matches(["anything"], ["anything"])


def test_parse_plan_unknown_version_still_parses():
    # Forward-compat: a future schema that still carries id/selector must
    # not become a silent full run, so we honour it rather than bail.
    plan = tp.parse_testplan(json.dumps({"version": "2.0", "tests": [{"id": "1"}]}), "p")
    assert plan.version == "2.0"
    assert plan.matches(["1"], [])


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "[]",
        json.dumps({"version": "1.0"}),  # no 'tests' key
        json.dumps({"version": "1.0", "tests": {}}),  # wrong type
        json.dumps({"version": "1.0", "tests": ["nope"]}),  # entry not object
        json.dumps({"version": "1.0", "tests": [{"name": "x"}]}),  # no id/selector
    ],
)
def test_parse_plan_rejects_broken_documents(raw):
    with pytest.raises(tp.TestPlanError):
        tp.parse_testplan(raw, "/tmp/plan.json")


def test_load_testplan_returns_none_without_env():
    assert tp.load_testplan(env={}) is None
    assert tp.load_testplan(env={tp.ENV_TESTPLAN_PATH: "   "}) is None


def test_load_testplan_mode_off_disables_consumption(tmp_path):
    path = _write_plan(tmp_path / "plan.json", [{"selector": "a"}])
    env = {tp.ENV_TESTPLAN_PATH: path, tp.ENV_TESTPLAN_MODE: "off"}
    assert tp.load_testplan(env=env) is None
    # Unknown mode values fall back to enforce — a typo must not silently
    # re-enable the full run.
    env[tp.ENV_TESTPLAN_MODE] = "enfroce"
    assert tp.load_testplan(env=env) is not None


def test_load_testplan_missing_file_is_an_error(tmp_path):
    env = {tp.ENV_TESTPLAN_PATH: str(tmp_path / "nope.json")}
    with pytest.raises(tp.TestPlanError) as excinfo:
        tp.load_testplan(env=env)
    assert "cannot read" in str(excinfo.value)


def test_load_testplan_directory_is_an_error(tmp_path):
    with pytest.raises(tp.TestPlanError):
        tp.load_testplan(env={tp.ENV_TESTPLAN_PATH: str(tmp_path)})


# ── unit: pytest item identity ──────────────────────────────────────────


class _FakeMark:
    def __init__(self, name, args=(), kwargs=None):
        self.name = name
        self.args = args
        self.kwargs = kwargs or {}


class _FakeItem:
    def __init__(self, nodeid, marks=(), originalname=None, obj=None):
        self.nodeid = nodeid
        self._marks = list(marks)
        self.originalname = originalname
        self.obj = obj

    def iter_markers(self, name=None):
        for m in self._marks:
            if name is None or m.name == name:
                yield m

    def get_closest_marker(self, name):
        for m in self._marks:
            if m.name == name:
                return m
        return None


def test_item_selectors_cover_nodeid_and_allure_full_name():
    item = _FakeItem("tests/auth/test_login.py::TestLogin::test_ok")
    sel = tp.item_selectors(item)
    assert "tests/auth/test_login.py::TestLogin::test_ok" in sel
    assert "tests.auth.test_login.TestLogin#test_ok" in sel
    # The dotted shape is what the Allure TestOps docs show for `selector`.
    assert "tests.auth.test_login.TestLogin.test_ok" in sel


def test_item_selectors_strip_parametrisation():
    item = _FakeItem("tests/test_x.py::test_p[case-1]", originalname="test_p")
    sel = tp.item_selectors(item)
    assert "tests/test_x.py::test_p[case-1]" in sel
    assert "tests/test_x.py::test_p" in sel


def test_item_allure_ids_reads_allure_label_and_mockarty_case():
    item = _FakeItem(
        "tests/test_x.py::test_a",
        marks=[
            _FakeMark("allure_label", ("777",), {"label_type": "ALLURE_ID"}),
            _FakeMark("mockarty_case", (), {"case_id": "CASE-9"}),
        ],
    )
    assert tp.item_allure_ids(item) == ["777", "CASE-9"]


def test_item_allure_ids_reads_as_id_label_and_decorator_attribute():
    class _Fn:
        __mockarty_case_id__ = "CASE-DEC"

    item = _FakeItem(
        "tests/test_x.py::test_a",
        marks=[_FakeMark("allure_label", ("42",), {"label_type": "AS_ID"})],
        obj=_Fn(),
    )
    assert tp.item_allure_ids(item) == ["42", "CASE-DEC"]


def test_select_items_partitions_by_plan():
    a = _FakeItem("tests/test_x.py::test_a")
    b = _FakeItem("tests/test_x.py::test_b")
    plan = tp.parse_testplan(
        json.dumps({"version": "1.0", "tests": [{"selector": "tests/test_x.py::test_a"}]}),
        "p",
    )
    selected, deselected = tp.select_items([a, b], plan)
    assert selected == [a]
    assert deselected == [b]


# ── e2e: the plugin actually restricts execution ────────────────────────

_SUITE = """
    import pytest

    def test_alpha():
        assert True

    @pytest.mark.allure_label("777", label_type="ALLURE_ID")
    def test_beta():
        assert True

    @pytest.mark.mockarty_case(case_id="CASE-9")
    def test_gamma():
        assert True
"""


def _mk_suite(pytester):
    pytester.makepyfile(test_suite=_SUITE)


def test_no_plan_runs_everything(pytester, monkeypatch):
    """Regression guard: without the env var nothing is filtered."""
    monkeypatch.delenv(tp.ENV_TESTPLAN_PATH, raising=False)
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    result.assert_outcomes(passed=3)


def test_plan_selector_runs_only_listed_test(pytester, tmp_path, monkeypatch):
    path = _write_plan(tmp_path / "plan.json", [{"selector": "test_suite.py::test_alpha"}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    # No -q: the header line is where an active plan is announced.
    result = pytester.runpytest_inprocess("-p", "no:allure_pytest")
    result.assert_outcomes(passed=1, deselected=2)
    result.stdout.fnmatch_lines(
        [
            "*Allure test plan active*1 entries*",
            "*3 items / 2 deselected / 1 selected*",
        ]
    )


def test_plan_id_matches_allure_id_label(pytester, tmp_path, monkeypatch):
    path = _write_plan(tmp_path / "plan.json", [{"id": 777}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    result.assert_outcomes(passed=1, deselected=2)


def test_plan_id_matches_mockarty_case_marker(pytester, tmp_path, monkeypatch):
    path = _write_plan(tmp_path / "plan.json", [{"id": "CASE-9"}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    result.assert_outcomes(passed=1, deselected=2)


def test_plan_dotted_selector_matches(pytester, tmp_path, monkeypatch):
    """The shape the Allure TestOps docs use: package.Class.method."""
    path = _write_plan(tmp_path / "plan.json", [{"selector": "test_suite.test_alpha"}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    result.assert_outcomes(passed=1, deselected=2)


def test_empty_plan_runs_nothing_and_says_so(pytester, tmp_path, monkeypatch):
    """The headline bug: an empty plan must NOT read as 'everything passed'."""
    path = _write_plan(tmp_path / "plan.json", [])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    result.assert_outcomes(passed=0, failed=0, deselected=3)
    # Exit code 5 = "no tests ran" — never 0.
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result.stdout.fnmatch_lines(["*test plan*is EMPTY*NOT a pass*"])


def test_plan_matching_nothing_is_reported(pytester, tmp_path, monkeypatch):
    path = _write_plan(tmp_path / "plan.json", [{"selector": "nope::nothing"}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result.stdout.fnmatch_lines(["*NONE matched*"])


def test_broken_plan_is_a_usage_error_not_a_full_run(pytester, tmp_path, monkeypatch):
    path = tmp_path / "plan.json"
    path.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, str(path))
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    # Exit code 4 = usage error, and the session dies before collection —
    # so there is not even an outcome summary, let alone a green one.
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "passed" not in result.stdout.str()
    assert "not valid JSON" in result.stderr.str() + result.stdout.str()


def test_missing_plan_file_is_a_usage_error(pytester, tmp_path, monkeypatch):
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, str(tmp_path / "absent.json"))
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "passed" not in result.stdout.str()
    assert "cannot read the test plan" in result.stderr.str() + result.stdout.str()


def test_mode_off_restores_the_full_run(pytester, tmp_path, monkeypatch):
    path = _write_plan(tmp_path / "plan.json", [{"selector": "test_suite.py::test_alpha"}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    monkeypatch.setenv(tp.ENV_TESTPLAN_MODE, "off")
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q", "-p", "no:allure_pytest")
    result.assert_outcomes(passed=3)


def test_plan_intersects_with_keyword_filter(pytester, tmp_path, monkeypatch):
    """The plan is an ADDITIONAL filter, not a replacement for -k/-m."""
    path = _write_plan(
        tmp_path / "plan.json",
        [{"selector": "test_suite.py::test_alpha"}, {"selector": "test_suite.py::test_beta"}],
    )
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    _mk_suite(pytester)
    # -k selects {beta, gamma}, the plan selects {alpha, beta} → only beta.
    result = pytester.runpytest_inprocess(
        "-q", "-p", "no:allure_pytest", "-k", "beta or gamma"
    )
    result.assert_outcomes(passed=1, deselected=2)


def test_coexists_with_real_allure_pytest(pytester, tmp_path, monkeypatch):
    """With allure-pytest installed both adapters read the same plan.

    An allure-style selector is understood by both, so the intersection is
    exactly the selected test (and not, e.g., zero).
    """
    pytest.importorskip("allure_pytest")
    path = _write_plan(tmp_path / "plan.json", [{"selector": "test_suite#test_alpha"}])
    monkeypatch.setenv(tp.ENV_TESTPLAN_PATH, path)
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")
    _mk_suite(pytester)
    result = pytester.runpytest_inprocess("-q")
    result.assert_outcomes(passed=1, deselected=2)
