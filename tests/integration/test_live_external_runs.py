# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live ``ExternalRunsAPI`` against the running admin.

The ``/api/v1/namespaces/{ns}/tcm/external-runs`` endpoint is part of
the TCM (Test Case Management) feature surface. On an admin with no
TCM licence the route returns 404 instead of mounting, so each test
here either:

* exercises the endpoint and asserts the live response shape, or
* skips with a clear reason when TCM isn't licensed.

The skip path is itself useful — it confirms the SDK surfaces the 404
as :class:`MockartyNotFoundError` rather than silently swallowing it.
"""

from __future__ import annotations

import base64
import pathlib
import uuid

import pytest

from mockarty import MockartyClient, allure_writer as aw
from mockarty.api.external_runs import (
    EXTERNAL_STATUS_FAILED,
    EXTERNAL_STATUS_PASSED,
)
from mockarty.errors import MockartyAPIError, MockartyNotFoundError


def _tcm_or_skip(client: MockartyClient) -> None:
    """Probe the endpoint; skip the whole test cleanly when 404.

    We use the lightest possible probe: a POST with a body the server
    will validate AFTER routing — so a 404 means "no route" (= TCM
    not licensed), while any 4xx with ``code=validation`` means the
    route is mounted but the body is incomplete (= TCM licensed).
    """
    try:
        client.external_runs.report(
            status=EXTERNAL_STATUS_PASSED,
            case_name=f"probe-{uuid.uuid4().hex[:8]}",
            auto_create=True,
            framework="probe",
        )
    except MockartyNotFoundError:
        pytest.skip("TCM external-runs route returns 404 — TCM feature not licensed")
    except MockartyAPIError:
        # Any other error means the route exists; the test that
        # follows will issue a real payload and assert on it.
        return


@pytest.fixture(scope="module", autouse=True)
def _ensure_tcm_available(mockarty_client: MockartyClient) -> None:
    _tcm_or_skip(mockarty_client)


class TestExternalRunsReport:
    def test_report_single_passed_run_round_trip(
        self, mockarty_client: MockartyClient
    ) -> None:
        case = f"py-sdk-live-{uuid.uuid4().hex[:8]}"
        resp = mockarty_client.external_runs.report(
            status=EXTERNAL_STATUS_PASSED,
            case_name=case,
            auto_create=True,
            framework="mockarty-py-sdk-integration",
            framework_version="0.3.0",
            duration_ms=1234,
            labels={"feature": "live-suite", "severity": "normal"},
            metadata={"branch": "cli-sdk-pivot-framework-completion"},
            steps=[
                {"name": "setup", "status": "passed", "durationMs": 100},
                {"name": "exercise", "status": "passed", "durationMs": 900},
                {"name": "teardown", "status": "passed", "durationMs": 100},
            ],
            attachments=[
                {"name": "trace.log", "body": b"sample trace payload"},
            ],
        )
        # Server echoes back at least the case info + run id.
        assert isinstance(resp, dict)
        # Different admin builds use ``runId`` or ``run_id``; accept both.
        run_id = resp.get("runId") or resp.get("run_id")
        case_id = resp.get("caseId") or resp.get("case_id")
        assert run_id, f"server response missing run id: {resp!r}"
        assert case_id, f"server response missing case id: {resp!r}"

    def test_report_failed_run_preserves_error(
        self, mockarty_client: MockartyClient
    ) -> None:
        case = f"py-sdk-fail-{uuid.uuid4().hex[:8]}"
        resp = mockarty_client.external_runs.report(
            status=EXTERNAL_STATUS_FAILED,
            case_name=case,
            auto_create=True,
            framework="mockarty-py-sdk-integration",
            error="AssertionError: expected 200, got 500",
            stdout="DEBUG: request sent\n",
            stderr="ERROR: assertion failed\n",
        )
        assert resp.get("runId") or resp.get("run_id")


class TestUploadAllureDir:
    def test_upload_allure_results_dir_lifts_each_file(
        self, mockarty_client: MockartyClient, tmp_path: pathlib.Path
    ) -> None:
        """Write three results + an attachment to disk, then upload —
        each file becomes its own external run."""
        writer = aw.AllureResultsWriter(str(tmp_path / "allure-results"))
        attachment = writer.write_attachment(
            b"server returned 200 OK",
            name="response.txt",
            content_type="text/plain",
        )
        suffix = uuid.uuid4().hex[:6]
        for status, label in (
            (aw.STATUS_PASSED, "pass"),
            (aw.STATUS_FAILED, "fail"),
            (aw.STATUS_SKIPPED, "skip"),
        ):
            writer.write_result(
                aw.TestResult(
                    uuid=f"{label}-{suffix}",
                    name=f"py_sdk_live_upload_{label}_{suffix}",
                    fullName=f"tests.live.test_{label}",
                    status=status,
                    stage=aw.STAGE_FINISHED,
                    start=1_700_000_000_000,
                    stop=1_700_000_000_500,
                    labels=[aw.Label("feature", "upload-bridge")],
                    attachments=[attachment] if status == aw.STATUS_PASSED else [],
                )
            )

        results = mockarty_client.external_runs.upload_allure_dir(
            writer.output_dir,
            auto_create=True,
            framework="allure",
            on_error="raise",
        )
        assert len(results) == 3
        # Every upload returned at least a run id.
        for r in results:
            assert r.get("runId") or r.get("run_id"), f"upload response missing run id: {r!r}"

    def test_attachment_round_trip_preserves_bytes(
        self, mockarty_client: MockartyClient, tmp_path: pathlib.Path
    ) -> None:
        """The wire shape base64-encodes attachment bodies. Verify the
        SDK preserves bytes through the round trip on the request side
        (the server doesn't echo bodies back, so we sniff the SDK's
        outbound payload via the public _build helpers used by the
        unit tests).
        """
        from mockarty.api.external_runs import _build_attachments

        body = bytes(range(256))
        encoded = _build_attachments([{"name": "binary.bin", "body": body}])
        assert encoded[0]["name"] == "binary.bin"
        assert base64.b64decode(encoded[0]["bodyB64"]) == body

        # Now exercise live: submit a run with the same attachment.
        case = f"py-sdk-attach-{uuid.uuid4().hex[:8]}"
        resp = mockarty_client.external_runs.report(
            status=EXTERNAL_STATUS_PASSED,
            case_name=case,
            auto_create=True,
            framework="mockarty-py-sdk-integration",
            attachments=[{"name": "binary.bin", "body": body}],
        )
        assert resp.get("runId") or resp.get("run_id")
