"""A Test IT style pytest case reports to Mockarty after changing its import."""

from __future__ import annotations

from types import SimpleNamespace
import base64
import json

import httpx
import pytest

from mockarty.api.external_runs import ExternalRunsAPI
from mockarty.testing import plugin

pytest_plugins = ["pytester"]


def test_testit_pytest_case_reports_step_attachment_and_external_id(pytester, monkeypatch):
    requests: list[tuple[str, dict]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(201, json={"run_id": "run-1"})

    http = httpx.Client(base_url="https://mockarty.example", transport=httpx.MockTransport(handle))
    client = SimpleNamespace(external_runs=ExternalRunsAPI(http, "quality"))
    monkeypatch.setattr(plugin, "_resolve_client", lambda item: client)
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")
    (pytester.path / "evidence.png").write_bytes(b"\x89PNG\r\n")
    pytester.makepyfile(
        """
        from pathlib import Path
        import mockarty.testit as testit

        @testit.displayName("Login flow")
        @testit.externalId("legacy-login-42")
        def test_login():
            with testit.step("Submit credentials"):
                testit.addAttachments("hello", is_text=True, name="trace.txt")
                testit.addAttachments(str(Path(__file__).with_name("evidence.png")))
                assert True
        """
    )
    result = pytester.runpytest_inprocess("-q", "--testit")
    result.assert_outcomes(passed=1)
    http.close()
    assert len(requests) == 1
    path, report = requests[0]
    assert path == "/api/v1/namespaces/quality/tcm/external-runs"
    assert report["externalId"] == "legacy-login-42"
    assert report["caseName"] == "Login flow"
    assert report["testDisplayName"] == "Login flow"
    assert report["autoCreate"] is True
    assert report["status"] == "passed"
    assert report["steps"][0]["name"] == "Submit credentials"
    assert [(a["name"], a["contentType"], base64.b64decode(a["bodyB64"])) for a in report["attachments"]] == [
        ("trace.txt", "text/plain; charset=utf-8", b"hello"),
        ("evidence.png", "image/png", b"\x89PNG\r\n"),
    ]


def test_compat_client_uses_requested_namespace(monkeypatch):
    captured = {}

    def construct(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MOCKARTY_BASE_URL", "https://mockarty.example")
    monkeypatch.setenv("MOCKARTY_API_KEY", "sample-key")
    monkeypatch.setenv("MOCKARTY_NAMESPACE", "quality")
    monkeypatch.setattr("mockarty.client.MockartyClient", construct)
    assert plugin._resolve_client(SimpleNamespace(funcargs={})) is not None
    assert captured["namespace"] == "quality"


def test_file_attachment_requires_existing_path(tmp_path):
    import mockarty.testit as testit

    with pytest.raises(FileNotFoundError):
        testit.addAttachments(str(tmp_path / "missing.png"))


def test_file_attachment_rejects_above_inline_limit(tmp_path):
    import mockarty.testit as testit

    oversized = tmp_path / "oversized.bin"
    oversized.write_bytes(b"x" * (256 * 1024 + 1))
    with pytest.raises(ValueError, match="256 KiB"):
        testit.addAttachments(str(oversized))


def test_testit_mode_fails_when_no_mockarty_destination(pytester, monkeypatch):
    monkeypatch.delenv("MOCKARTY_BASE_URL", raising=False)
    monkeypatch.delenv("MOCKARTY_API_KEY", raising=False)
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")
    pytester.makepyfile("def test_example():\n    assert True\n")
    result = pytester.runpytest_inprocess("-q", "--testit")
    result.assert_outcomes(failed=1)


def test_testit_mode_fails_safely_when_upload_rejected(pytester, monkeypatch):
    def reject(**_kwargs):
        raise RuntimeError("secret-token")

    client = SimpleNamespace(external_runs=SimpleNamespace(report=reject))
    monkeypatch.setattr(plugin, "_resolve_client", lambda item: client)
    monkeypatch.setenv("MOCKARTY_ALLURE_MIRROR", "off")
    pytester.makepyfile("def test_example():\n    assert True\n")
    result = pytester.runpytest_inprocess("-q", "--testit")
    result.assert_outcomes(failed=1)
    assert "RuntimeError" in result.stdout.str()
    assert "secret-token" not in result.stdout.str()
