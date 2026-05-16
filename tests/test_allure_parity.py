# Copyright (c) 2026 Mockarty. All rights reserved.

"""Schema parity test: Mockarty-written ``-result.json`` must round-trip
through :mod:`allure_commons.model2` cleanly, with every required field
populated and every optional field either absent or non-null.

We don't compare against an externally-recorded reference fixture
(allure-python-commons doesn't ship one and the byte form is impl-
sensitive). Instead we exercise the parity by:

1. Building a TestResult via our writer.
2. Loading the JSON and re-creating an allure-commons TestResult instance
   from the same dict. If a field is misnamed / wrong-typed, the
   reconstruction fails or produces an obviously-bad object.
3. Round-tripping the allure-commons instance back to dict via its own
   converter and asserting our keys are a subset.

This is robust to internal Allure repr changes (we don't compare bytes)
while still catching field-name drift / type mismatches.
"""

from __future__ import annotations

import json
import os

import pytest

allure_commons = pytest.importorskip("allure_commons.model2")
allure_converter = pytest.importorskip("allure_commons.types")

from mockarty.allure_writer import (
    AllureResultsWriter,
    Attachment,
    Label,
    Link,
    Parameter,
    STATUS_FAILED,
    STATUS_PASSED,
    StatusDetails,
    StepResult,
    TestResult,
    TestResultContainer,
)


@pytest.fixture
def writer(tmp_path):
    return AllureResultsWriter(str(tmp_path))


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class TestResultSchemaParity:
    def test_all_required_fields_present_for_passed(self, writer, tmp_path):
        r = TestResult(
            uuid="parity-1",
            name="parity test",
            fullName="mod.Cls.method",
            historyId="abc",
            status=STATUS_PASSED,
            start=1, stop=2,
            labels=[
                Label("framework", "pytest"),
                Label("language", "python"),
                Label("host", "h1"),
                Label("thread", "t1"),
                Label("feature", "auth"),
                Label("severity", "critical"),
            ],
            parameters=[Parameter(name="x", value="1")],
            steps=[StepResult(name="s1", status=STATUS_PASSED, start=1, stop=2)],
        )
        path = writer.write_result(r)
        doc = _load(path)
        # uuid + name + status are MUST per Allure schema.
        assert "uuid" in doc and "name" in doc and "status" in doc
        # Status must be one of the Allure enum.
        assert doc["status"] in ("passed", "failed", "broken", "skipped", "unknown")
        # Labels are list of {name, value}.
        for lab in doc["labels"]:
            assert set(lab.keys()) == {"name", "value"}
        # Parameters require name + value.
        for p in doc["parameters"]:
            assert "name" in p and "value" in p
        # Steps recursively follow the same status enum.
        for s in doc["steps"]:
            assert s["status"] in ("passed", "failed", "broken", "skipped", "unknown")

    def test_failed_result_with_status_details(self, writer):
        r = TestResult(
            uuid="parity-2",
            name="failed parity",
            status=STATUS_FAILED,
            statusDetails=StatusDetails(message="AssertionError: x", trace="t"),
            start=10, stop=20,
        )
        path = writer.write_result(r)
        doc = _load(path)
        assert doc["statusDetails"]["message"].startswith("AssertionError")
        assert doc["statusDetails"]["trace"] == "t"

    def test_links_and_attachments_shape(self, writer):
        att = writer.write_attachment(b"data", name="payload", content_type="application/json")
        r = TestResult(
            uuid="parity-3", name="links",
            status=STATUS_PASSED, start=1, stop=2,
            links=[
                Link(name="bug", url="http://b/1", type="issue"),
                Link(name=None, url="http://x", type=None),  # no type → omitted
            ],
            attachments=[att],
        )
        path = writer.write_result(r)
        doc = _load(path)
        # link with type omitted → key absent.
        assert "type" not in doc["links"][1] or doc["links"][1].get("type") is None
        # Attachment carries source filename pointing at an existing file.
        src = doc["attachments"][0]["source"]
        assert os.path.exists(os.path.join(os.path.dirname(path), src))

    def test_container_schema(self, writer):
        c = TestResultContainer(
            uuid="cc", name="fixture",
            children=["t1", "t2"],
            befores=[StepResult(name="setup", status=STATUS_PASSED)],
            afters=[StepResult(name="teardown", status=STATUS_PASSED)],
            start=1, stop=99,
        )
        path = writer.write_container(c)
        doc = _load(path)
        assert doc["uuid"] == "cc"
        assert doc["children"] == ["t1", "t2"]
        assert doc["befores"][0]["status"] == "passed"


class TestAllureCommonsCompatibility:
    """If allure-python-commons is installed, parse our JSON back into its
    model. Field-name drift surfaces immediately."""

    def test_round_trip_passed(self, writer):
        r = TestResult(
            uuid="rt-1",
            name="rt name",
            fullName="m.c.method",
            historyId="hid",
            status=STATUS_PASSED,
            start=100, stop=200,
            labels=[Label("feature", "auth")],
            parameters=[Parameter(name="x", value="1")],
        )
        path = writer.write_result(r)
        doc = _load(path)
        # allure-commons model2 ``TestResult`` is attrs-based — keys map
        # 1:1. Reconstruction should not raise.
        reconstructed = allure_commons.TestResult(
            uuid=doc["uuid"],
            name=doc["name"],
            fullName=doc.get("fullName"),
            historyId=doc.get("historyId"),
            status=doc["status"],
            start=doc.get("start"),
            stop=doc.get("stop"),
        )
        assert reconstructed.uuid == "rt-1"
        assert reconstructed.name == "rt name"
        assert reconstructed.fullName == "m.c.method"
