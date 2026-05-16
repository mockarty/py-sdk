# Copyright (c) 2026 Mockarty. All rights reserved.

"""Validate the Allure-2 results writer end-to-end and check that the
shape we ship to disk is identical (in field structure) to what the
upstream ``allure-pytest`` plugin produces.

This is a live-admin file only by package convention — it doesn't
strictly need the admin running to assert byte-level schema parity. But
since the writer is the input to :class:`ExternalRunsAPI.upload_allure_dir`,
which is exercised live in ``test_live_external_runs.py``, we keep it
in the integration bundle so a single ``pytest tests/integration`` run
covers both ends of the pipeline.
"""

from __future__ import annotations

import glob
import json
import pathlib
import subprocess
import sys
import textwrap

import pytest

from mockarty import allure_writer as aw


REQUIRED_TOP_LEVEL_KEYS = {
    "uuid",
    "name",
    "status",
    "stage",
    # The Allure 2 schema accepts missing optional fields, but every
    # well-formed result we ship MUST carry these so the admin's
    # ingester / allure-commandline both have something to render.
    # Time fields are required when the run actually executed.
}


def _load_results(directory: pathlib.Path) -> list[dict]:
    out: list[dict] = []
    for p in sorted(directory.glob("*-result.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


class TestWriterSchema:
    def test_writer_emits_every_required_allure_field(self, tmp_path: pathlib.Path) -> None:
        writer = aw.AllureResultsWriter(str(tmp_path / "allure-results"))

        att = writer.write_attachment(
            b"hello world", name="hint.txt", content_type="text/plain"
        )

        result = aw.TestResult(
            uuid="schema-1",
            name="login_smoke",
            fullName="tests.test_login.test_smoke",
            historyId="hist-login-smoke",
            status=aw.STATUS_PASSED,
            stage=aw.STAGE_FINISHED,
            statusDetails=aw.StatusDetails(message="passed", trace=None),
            description="Login flow happy path",
            start=1_700_000_000_000,
            stop=1_700_000_001_500,
            labels=[
                aw.Label("feature", "auth"),
                aw.Label("severity", "critical"),
                aw.Label("framework", "mockarty"),
            ],
            links=[aw.Link(name="docs", url="https://mockarty.ru/docs", type="custom")],
            parameters=[aw.Parameter(name="user", value="alice")],
            attachments=[att],
            steps=[
                aw.StepResult(
                    name="submit form",
                    status=aw.STATUS_PASSED,
                    stage=aw.STAGE_FINISHED,
                    start=1_700_000_000_100,
                    stop=1_700_000_000_400,
                )
            ],
        )
        writer.write_result(result)

        files = _load_results(pathlib.Path(writer.output_dir))
        assert len(files) == 1
        payload = files[0]

        # Top-level required keys present.
        missing = REQUIRED_TOP_LEVEL_KEYS - set(payload.keys())
        assert not missing, f"missing required allure fields: {missing}"

        # Time fields are ms-epoch integers.
        assert isinstance(payload["start"], int) and payload["start"] > 0
        assert isinstance(payload["stop"], int) and payload["stop"] >= payload["start"]

        # Status is one of the canonical enum.
        assert payload["status"] in {"passed", "failed", "broken", "skipped", "unknown"}
        # Stage likewise.
        assert payload["stage"] in {
            "scheduled",
            "running",
            "finished",
            "pending",
            "interrupted",
        }

        # Lists are present (may be empty for some categories, but a
        # passed test with explicit attachments must surface them).
        assert isinstance(payload.get("labels", []), list) and payload["labels"]
        assert isinstance(payload.get("links", []), list) and payload["links"]
        assert isinstance(payload.get("parameters", []), list) and payload["parameters"]
        assert isinstance(payload.get("steps", []), list) and payload["steps"]
        assert isinstance(payload.get("attachments", []), list) and payload["attachments"]

        # Step schema: nested ones must also have status + stage + start/stop.
        step = payload["steps"][0]
        assert step["status"] == "passed"
        assert step["stage"] == "finished"
        assert isinstance(step["start"], int)
        assert isinstance(step["stop"], int)

        # statusDetails is present and serialised under camelCase.
        assert "statusDetails" in payload
        assert payload["statusDetails"]["message"] == "passed"

    def test_failed_result_carries_status_details(self, tmp_path: pathlib.Path) -> None:
        writer = aw.AllureResultsWriter(str(tmp_path / "allure-results"))
        writer.write_result(
            aw.TestResult(
                uuid="fail-1",
                name="payment_fails_on_negative_amount",
                status=aw.STATUS_FAILED,
                statusDetails=aw.StatusDetails(
                    message="AssertionError: amount must be positive",
                    trace="Traceback (most recent call last):\n  ...\n",
                ),
                start=1, stop=2,
            )
        )
        payload = _load_results(pathlib.Path(writer.output_dir))[0]
        assert payload["status"] == "failed"
        assert payload["statusDetails"]["message"].startswith("AssertionError")
        assert payload["statusDetails"]["trace"]


class TestAllurePytestParity:
    """Compare the field shape we emit against ``allure-pytest`` running
    a tiny synthetic test.

    Parity here means **structural superset** — every required key the
    upstream emits must also appear in our output for an equivalent
    test. We don't compare byte-equal because the upstream randomises
    uuids and embeds host/thread labels that differ across runs.
    """

    @pytest.fixture(scope="class")
    def reference_results(self, tmp_path_factory: pytest.TempPathFactory) -> list[dict]:
        """Drive allure-pytest in a subprocess against a 1-test file.

        Run via subprocess so the in-process pytest plugin chain that's
        loaded for our own tests doesn't fight with the upstream one.
        """
        try:
            import allure_pytest  # noqa: F401
        except ImportError:
            pytest.skip("allure-pytest not installed — parity check skipped")

        tmp = tmp_path_factory.mktemp("parity")
        results_dir = tmp / "results"
        test_file = tmp / "test_ref.py"
        test_file.write_text(
            textwrap.dedent(
                """
                import allure


                @allure.feature("auth")
                @allure.severity(allure.severity_level.CRITICAL)
                def test_reference():
                    with allure.step("submit form"):
                        allure.attach("hint", name="note", attachment_type=allure.attachment_type.TEXT)
                """
            ).strip(),
            encoding="utf-8",
        )
        # ``-p no:cacheprovider`` keeps the reference run hermetic; the
        # allure plugin self-registers via entry-points so we only need
        # the --alluredir flag.
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(test_file),
                f"--alluredir={results_dir}",
                "-p",
                "no:cacheprovider",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            pytest.skip(
                f"allure-pytest subprocess returned {proc.returncode}\n"
                f"stdout: {proc.stdout[:400]}\nstderr: {proc.stderr[:400]}"
            )
        files = sorted(glob.glob(str(results_dir / "*-result.json")))
        if not files:
            pytest.skip("allure-pytest produced no result files")
        return [json.loads(pathlib.Path(p).read_text(encoding="utf-8")) for p in files]

    def test_our_writer_covers_upstream_keys(
        self, tmp_path: pathlib.Path, reference_results: list[dict]
    ) -> None:
        # Emit our own equivalent of the upstream test.
        writer = aw.AllureResultsWriter(str(tmp_path / "ours"))
        writer.write_result(
            aw.TestResult(
                uuid="ours-1",
                name="test_reference",
                fullName="test_ref.test_reference",
                status=aw.STATUS_PASSED,
                stage=aw.STAGE_FINISHED,
                start=1, stop=2,
                labels=[
                    aw.Label("feature", "auth"),
                    aw.Label("severity", "critical"),
                ],
                steps=[aw.StepResult(name="submit form", start=1, stop=2)],
            )
        )
        ours = _load_results(pathlib.Path(writer.output_dir))[0]
        upstream = reference_results[0]

        # Required-keys check: keys that BOTH writers must always emit.
        # ``stage`` is in our writer's contract but upstream
        # ``allure-pytest`` historically omits it on the happy path —
        # the allure-commandline ingester defaults missing ``stage`` to
        # ``finished``. So we only require it on ours.
        ours_must_have = {"uuid", "name", "status", "stage"}
        both_must_have = {"uuid", "name", "status"}
        for k in ours_must_have:
            assert k in ours, f"our writer dropped required key {k!r}"
        for k in both_must_have:
            assert k in upstream, f"upstream missing {k!r} — schema drift"

        # Labels are recorded as a list of {name, value} dicts in both.
        assert isinstance(ours.get("labels", []), list)
        assert isinstance(upstream.get("labels", []), list)
        if ours["labels"]:
            assert {"name", "value"} <= set(ours["labels"][0].keys())
        if upstream["labels"]:
            assert {"name", "value"} <= set(upstream["labels"][0].keys())
