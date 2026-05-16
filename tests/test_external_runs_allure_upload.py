# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for :meth:`ExternalRunsAPI.upload_allure_dir`.

Validates the Allure-results → external-run wire-shape translator by
mocking the HTTP transport via respx and asserting:

* Every ``*-result.json`` triggers a POST.
* Attachment bodies are read off disk and base64-encoded.
* status mapping (``broken`` → ``failed`` on the wire).
* Labels propagated as a flat dict.
* missing directory → FileNotFoundError.
* on_error='warn' continues; on_error='raise' propagates.
"""

from __future__ import annotations

import base64
import json
import os

import httpx
import pytest
import respx

from mockarty import allure_writer as aw
from mockarty.client import MockartyClient


@pytest.fixture
def writer(tmp_path):
    return aw.AllureResultsWriter(str(tmp_path / "allure-results"))


@pytest.fixture
def client():
    return MockartyClient(base_url="http://test", api_key="x", namespace="default")


class TestUploadAllureDir:
    def test_uploads_each_result(self, writer, client, tmp_path):
        att = writer.write_attachment(b"payload", name="log", content_type="text/plain")
        for i, status in enumerate(["passed", "failed", "broken", "skipped"]):
            r = aw.TestResult(
                uuid=f"u{i}",
                name=f"test_{status}",
                fullName=f"m.c.test_{status}",
                status=status,
                start=1000 + i, stop=2000 + i,
                labels=[aw.Label("feature", "auth")],
                attachments=[att] if status == "passed" else [],
            )
            writer.write_result(r)
        with respx.mock(base_url="http://test") as router:
            route = router.post("/api/v1/namespaces/default/tcm/external-runs").mock(
                return_value=httpx.Response(200, json={"runId": "rid"})
            )
            out = client.external_runs.upload_allure_dir(writer.output_dir)
        assert len(out) == 4
        assert route.call_count == 4
        # Inspect one payload — broken should be mapped to failed for the wire.
        bodies = [json.loads(c.request.content) for c in route.calls]
        statuses = [b["status"] for b in bodies]
        assert "failed" in statuses
        assert "broken" not in statuses  # mapped away
        # Attachment is included for the passed test only.
        passed_payload = next(b for b in bodies if b["status"] == "passed")
        assert "attachments" in passed_payload
        decoded = base64.b64decode(passed_payload["attachments"][0]["bodyB64"])
        assert decoded == b"payload"

    def test_missing_dir_raises(self, client):
        with pytest.raises(FileNotFoundError):
            client.external_runs.upload_allure_dir("/nonexistent/path/xyz")

    def test_corrupted_result_warn_continues(self, writer, client, tmp_path):
        # Valid result + corrupted result.
        writer.write_result(aw.TestResult(uuid="ok", name="ok", status="passed"))
        bad_path = os.path.join(writer.output_dir, "broken-result.json")
        with open(bad_path, "w") as fh:
            fh.write("{not valid json")
        with respx.mock(base_url="http://test") as router:
            router.post("/api/v1/namespaces/default/tcm/external-runs").mock(
                return_value=httpx.Response(200, json={})
            )
            with pytest.warns(RuntimeWarning):
                out = client.external_runs.upload_allure_dir(writer.output_dir, on_error="warn")
        # The good one still uploaded.
        assert len(out) == 1

    def test_corrupted_result_raise_propagates(self, writer, client):
        bad_path = os.path.join(writer.output_dir, "broken-result.json")
        os.makedirs(writer.output_dir, exist_ok=True)
        with open(bad_path, "w") as fh:
            fh.write("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            client.external_runs.upload_allure_dir(writer.output_dir, on_error="raise")

    def test_labels_propagate(self, writer, client):
        r = aw.TestResult(
            uuid="u1", name="t", status="passed",
            labels=[aw.Label("feature", "auth"), aw.Label("severity", "critical")],
        )
        writer.write_result(r)
        with respx.mock(base_url="http://test") as router:
            route = router.post("/api/v1/namespaces/default/tcm/external-runs").mock(
                return_value=httpx.Response(200, json={})
            )
            client.external_runs.upload_allure_dir(writer.output_dir)
        body = json.loads(route.calls[0].request.content)
        assert body["labels"]["feature"] == "auth"
        assert body["labels"]["severity"] == "critical"
