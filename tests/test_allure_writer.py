# Copyright (c) 2026 Mockarty. All rights reserved.

"""Unit tests for :mod:`mockarty.allure_writer`.

These tests cover byte-accurate Allure-2 schema fidelity:

* TestResult serialisation: required + optional fields, drops Nones,
  preserves empty collections as omitted (matches Allure's own writer).
* Attachment persistence: filename uniqueness, MIME type derivation,
  extension override.
* Status helpers: worst-of-children bubble-up, exception → StatusDetails.
* Label helpers: auto-detected machine labels (host/thread/framework).
* Link expansion: ALLURE_*_LINK_PATTERN env var.
* History id: stable across runs, varies with non-excluded parameters.
* Concurrent writes from multiple threads — no filename collisions.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from mockarty import allure_writer as aw
from mockarty.allure_writer import (
    AllureResultsWriter,
    Attachment,
    Label,
    Link,
    Parameter,
    STATUS_BROKEN,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    STATUS_UNKNOWN,
    StatusDetails,
    StepResult,
    TestResult,
    TestResultContainer,
    auto_labels,
    case_frame_to_result,
    expand_link,
    format_exception,
    make_full_name,
    make_history_id,
    normalize_status,
    now_ms,
    worst_status,
)
from mockarty.testing import context as _ctx


def _read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── Schema fidelity ─────────────────────────────────────────────────────


class TestSerialisationSchema:
    def test_minimal_result_required_fields_only(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        r = TestResult(uuid="u1", name="t", status=STATUS_PASSED)
        path = w.write_result(r)
        doc = _read(path)
        assert doc["uuid"] == "u1"
        assert doc["name"] == "t"
        assert doc["status"] == STATUS_PASSED
        assert doc["stage"] == "finished"
        # None-valued optional fields must be absent (Allure rejects nulls).
        assert "statusDetails" not in doc
        assert "description" not in doc
        # Empty collections must be omitted (Allure parser tolerance varies).
        assert "labels" not in doc
        assert "steps" not in doc

    def test_full_result_serialisation_matches_schema(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        att = w.write_attachment(b"hello", name="log", content_type="text/plain")
        r = TestResult(
            uuid="u2",
            name="full",
            fullName="m.cls.method",
            historyId="abc",
            testCaseId="CASE-1",
            status=STATUS_FAILED,
            stage="finished",
            statusDetails=StatusDetails(message="boom", trace="trace"),
            description="markdown desc",
            descriptionHtml="<b>html</b>",
            start=1000,
            stop=2000,
            labels=[Label("feature", "auth")],
            links=[Link(name="bug", url="http://b/1", type="issue")],
            parameters=[Parameter(name="x", value="1")],
            attachments=[att],
            steps=[
                StepResult(name="step1", status=STATUS_PASSED, start=1100, stop=1500)
            ],
        )
        path = w.write_result(r)
        doc = _read(path)
        # Verify every required field present + correctly typed.
        assert doc["statusDetails"] == {"message": "boom", "trace": "trace"}
        assert doc["labels"] == [{"name": "feature", "value": "auth"}]
        assert doc["links"][0]["type"] == "issue"
        assert doc["parameters"][0] == {"name": "x", "value": "1"}
        assert doc["attachments"][0]["source"].endswith(".txt")
        assert doc["steps"][0]["name"] == "step1"
        assert doc["start"] == 1000 and doc["stop"] == 2000

    def test_container_serialisation(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        c = TestResultContainer(
            uuid="c1", name="fixture", children=["u1", "u2"],
            befores=[StepResult(name="setup", status=STATUS_PASSED)],
            afters=[StepResult(name="teardown", status=STATUS_PASSED)],
            start=10, stop=20,
        )
        path = w.write_container(c)
        doc = _read(path)
        assert doc["children"] == ["u1", "u2"]
        assert doc["befores"][0]["name"] == "setup"
        assert doc["afters"][0]["name"] == "teardown"


# ── Attachments ─────────────────────────────────────────────────────────


class TestAttachments:
    def test_str_body_encoded_utf8(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        a = w.write_attachment("café", name="note")
        assert a.type == "text/plain"
        with open(os.path.join(str(tmp_path), a.source), "rb") as fh:
            assert fh.read().decode("utf-8") == "café"

    def test_bytes_body_default_octet_stream(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        a = w.write_attachment(b"\x00\xff", name="bin")
        assert a.type == "application/octet-stream"

    def test_filename_unique_under_concurrency(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        names = set()
        lock = threading.Lock()

        def go(i):
            a = w.write_attachment(f"body-{i}".encode(), name=f"n{i}", content_type="text/plain")
            with lock:
                names.add(a.source)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(go, range(64)))
        assert len(names) == 64

    def test_extension_override(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        a = w.write_attachment(b"{}", name="x", content_type="application/json", extension="json")
        assert a.source.endswith(".json")


# ── Status helpers ──────────────────────────────────────────────────────


class TestStatusHelpers:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("passed", STATUS_PASSED),
            ("ok", STATUS_PASSED),
            ("PASS", STATUS_PASSED),
            ("failed", STATUS_FAILED),
            ("fail", STATUS_FAILED),
            ("error", STATUS_BROKEN),
            ("BROKEN", STATUS_BROKEN),
            ("skipped", STATUS_SKIPPED),
            ("skip", STATUS_SKIPPED),
            ("unknown", STATUS_UNKNOWN),
            (None, STATUS_UNKNOWN),
        ],
    )
    def test_normalize_status(self, raw, expected):
        assert normalize_status(raw) == expected

    def test_worst_status_bubbling(self):
        assert worst_status([STATUS_PASSED, STATUS_FAILED, STATUS_BROKEN]) == STATUS_BROKEN
        assert worst_status([STATUS_PASSED, STATUS_FAILED]) == STATUS_FAILED
        assert worst_status([STATUS_PASSED, STATUS_SKIPPED]) == STATUS_SKIPPED
        assert worst_status([]) == STATUS_PASSED
        assert worst_status([STATUS_PASSED, STATUS_PASSED]) == STATUS_PASSED

    def test_format_exception_captures_message_and_trace(self):
        try:
            raise ValueError("boom!")
        except ValueError as e:
            sd = format_exception(e)
        assert sd is not None
        assert sd.message == "ValueError: boom!"
        assert "ValueError" in (sd.trace or "")

    def test_format_exception_none_returns_none(self):
        assert format_exception(None) is None


# ── History id ──────────────────────────────────────────────────────────


class TestHistoryId:
    def test_stable_across_runs(self):
        ps = [Parameter(name="x", value="1"), Parameter(name="y", value="2")]
        a = make_history_id("m.c.method", ps)
        b = make_history_id("m.c.method", ps)
        assert a == b
        assert len(a) == 32  # md5 hex

    def test_excluded_parameter_does_not_affect_history(self):
        with_excl = [
            Parameter(name="x", value="1"),
            Parameter(name="trace", value="123abc", excluded=True),
        ]
        without_excl = [Parameter(name="x", value="1")]
        assert make_history_id("m.c.method", with_excl) == make_history_id(
            "m.c.method", without_excl
        )

    def test_parameter_change_changes_history(self):
        a = make_history_id("m.c.method", [Parameter(name="x", value="1")])
        b = make_history_id("m.c.method", [Parameter(name="x", value="2")])
        assert a != b


# ── Auto-labels ─────────────────────────────────────────────────────────


class TestAutoLabels:
    def test_machine_labels_present(self):
        labs = auto_labels(framework="pytest", test_class="C", test_method="m")
        names = {l.name for l in labs}
        assert "language" in names
        assert "framework" in names
        assert "host" in names
        assert "thread" in names
        assert "testClass" in names
        assert "testMethod" in names

    def test_no_class_no_method_still_works(self):
        labs = auto_labels()
        names = {l.name for l in labs}
        assert "language" in names
        assert "testClass" not in names


# ── Link expansion ──────────────────────────────────────────────────────


class TestLinkExpansion:
    def test_absolute_url_unchanged(self, monkeypatch):
        monkeypatch.setenv("ALLURE_ISSUE_LINK_PATTERN", "https://j/{}")
        link = expand_link(Link(name=None, url="https://existing/u", type="issue"))
        assert link.url == "https://existing/u"

    def test_issue_pattern_applies(self, monkeypatch):
        monkeypatch.setenv("ALLURE_ISSUE_LINK_PATTERN", "https://jira.io/{}")
        link = expand_link(Link(name=None, url="BUG-1", type="issue"))
        assert link.url == "https://jira.io/BUG-1"

    def test_tms_pattern_applies(self, monkeypatch):
        monkeypatch.setenv("ALLURE_TMS_LINK_PATTERN", "https://tms/{}")
        link = expand_link(Link(name=None, url="TC-7", type="tms"))
        assert link.url == "https://tms/TC-7"

    def test_no_pattern_returns_as_is(self, monkeypatch):
        monkeypatch.delenv("ALLURE_LINK_PATTERN", raising=False)
        link = expand_link(Link(name=None, url="x", type="custom"))
        assert link.url == "x"


# ── make_full_name ──────────────────────────────────────────────────────


class TestFullName:
    def test_all_parts(self):
        assert make_full_name("m", "C", "test_x") == "m.C.test_x"

    def test_skip_none_parts(self):
        assert make_full_name(None, None, "test_x") == "test_x"
        assert make_full_name("m", None, "test_x") == "m.test_x"


# ── CaseFrame → TestResult ──────────────────────────────────────────────


class TestCaseFrameConversion:
    def test_minimal_case(self, tmp_path):
        case = _ctx.CaseFrame(case_name="t", auto_create=True)
        case.steps.append({"name": "s1", "status": "passed", "started_ns": 0})
        r = case_frame_to_result(case, name="t", framework="pytest")
        assert r.name == "t"
        assert r.status == STATUS_PASSED
        assert len(r.steps) == 1
        assert r.steps[0].status == STATUS_PASSED

    def test_failed_step_bubbles_to_failed_result(self, tmp_path):
        case = _ctx.CaseFrame(case_name="t", auto_create=True)
        case.steps.append({"name": "s1", "status": "failed", "error": "boom"})
        r = case_frame_to_result(case, name="t", framework="pytest")
        assert r.status == STATUS_FAILED

    def test_attachments_persisted_with_writer(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        case = _ctx.CaseFrame(case_name="t", auto_create=True)
        case.attachments.append(
            {"name": "log", "body": b"hello", "content_type": "text/plain"}
        )
        r = case_frame_to_result(case, name="t", framework="pytest", writer=w)
        assert len(r.attachments) == 1
        path = os.path.join(str(tmp_path), r.attachments[0].source)
        assert os.path.exists(path)
        with open(path, "rb") as fh:
            assert fh.read() == b"hello"

    def test_allure_metadata_labels_links_preserved(self):
        case = _ctx.CaseFrame(case_name="t", auto_create=True)
        case.metadata["_allure_labels"] = [
            {"name": "feature", "value": "auth"},
            {"name": "tag", "value": "smoke"},
        ]
        case.metadata["_allure_links"] = [
            {"name": "spec", "url": "http://x", "type": "tms"},
        ]
        case.metadata["_allure_parameters"] = [
            {"name": "env", "value": "stage"}
        ]
        r = case_frame_to_result(case, name="t", framework="pytest")
        label_names = {l.name for l in r.labels}
        assert "feature" in label_names
        assert "tag" in label_names
        assert len(r.links) == 1
        assert any(p.name == "env" for p in r.parameters)


# ── Concurrent result writes (xdist simulation) ─────────────────────────


class TestConcurrentWrites:
    def test_64_parallel_results_no_collision(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))

        def go(i):
            r = TestResult(uuid=f"u{i}-{threading.get_ident()}", name=f"t{i}", status=STATUS_PASSED)
            w.write_result(r)

        with ThreadPoolExecutor(max_workers=16) as ex:
            list(ex.map(go, range(64)))
        results = [f for f in os.listdir(str(tmp_path)) if f.endswith("-result.json")]
        assert len(results) == 64


# ── Environment/categories/executor ─────────────────────────────────────


class TestSidecarFiles:
    def test_environment_properties(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        path = w.write_environment({"BUILD": "42", "BRANCH": "main"})
        with open(path, "r", encoding="utf-8") as fh:
            data = fh.read()
        # Sorted by key.
        assert "BRANCH=main" in data
        assert "BUILD=42" in data
        # Order is sorted alphabetically.
        assert data.index("BRANCH") < data.index("BUILD")

    def test_environment_newlines_neutralised(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        path = w.write_environment({"X": "line1\nline2"})
        with open(path, "r", encoding="utf-8") as fh:
            data = fh.read()
        assert "line1 line2" in data
        assert data.count("\n") == 1  # only the trailing newline

    def test_categories_json(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        path = w.write_categories(
            [{"name": "Flaky", "matchedStatuses": ["broken"]}]
        )
        doc = _read(path)
        assert doc[0]["name"] == "Flaky"

    def test_executor_json(self, tmp_path):
        w = AllureResultsWriter(str(tmp_path))
        path = w.write_executor({"name": "GitHub Actions", "buildOrder": 12})
        doc = _read(path)
        assert doc["buildOrder"] == 12


# ── Time helpers ────────────────────────────────────────────────────────


def test_now_ms_returns_milliseconds():
    a = now_ms()
    assert a > 1_700_000_000_000  # past 2023-11
    assert a < 100_000_000_000_000


# ── Stage / status enum sanity ──────────────────────────────────────────


def test_canonical_label_set_includes_expected():
    assert "feature" in aw.CANONICAL_LABELS
    assert "epic" in aw.CANONICAL_LABELS
    assert "severity" in aw.CANONICAL_LABELS
    assert "host" in aw.CANONICAL_LABELS


def test_status_unknown_constant_exposed():
    assert aw.STATUS_UNKNOWN == "unknown"
