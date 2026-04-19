# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for Advanced API resources: Generator, Fuzzing, Contracts, Recorder, Templates, Imports, TestRuns."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient
from mockarty.models.contract import ContractConfig, ContractValidationResult
from mockarty.models.fuzzing import FuzzingConfig, FuzzingResult, FuzzingRun, QuarantineEntry
from mockarty.models.generator import GeneratorPreview, GeneratorRequest, GeneratorResponse
from mockarty.models.imports import ImportResult
from mockarty.models.mock import Mock
from mockarty.models.recorder import RecorderEntry, RecorderSession
from mockarty.models.testrun import TestRun


# ── GeneratorAPI ─────────────────────────────────────────────────────


class TestGeneratorAPI:
    """Test mock generation from specifications."""

    @respx.mock
    def test_generate_openapi(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/generators/openapi").mock(
            return_value=httpx.Response(
                200,
                json={
                    "created": 3,
                    "mocks": [
                        {"id": "gen-1", "http": {"route": "/api/pets"}},
                        {"id": "gen-2", "http": {"route": "/api/pets/:id"}},
                        {"id": "gen-3", "http": {"route": "/api/users"}},
                    ],
                    "message": "Generated 3 mocks",
                },
            )
        )

        result = client.generator.generate_openapi(
            GeneratorRequest(url="https://petstore.swagger.io/v2/swagger.json")
        )
        assert isinstance(result, GeneratorResponse)
        assert result.created == 3
        assert len(result.mocks) == 3
        assert result.mocks[0].id == "gen-1"
        assert result.message == "Generated 3 mocks"

    @respx.mock
    def test_generate_openapi_from_dict(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/generators/openapi").mock(
            return_value=httpx.Response(
                200,
                json={"created": 1, "mocks": [{"id": "dict-gen"}]},
            )
        )

        result = client.generator.generate_openapi({"url": "https://example.com/spec"})
        assert result.created == 1

    @respx.mock
    def test_preview_openapi(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/generators/openapi/preview").mock(
            return_value=httpx.Response(
                200,
                json={
                    "mocks": [
                        {"id": "preview-1", "http": {"route": "/api/items"}},
                    ],
                    "count": 1,
                },
            )
        )

        preview = client.generator.preview_openapi(
            GeneratorRequest(spec='{"openapi": "3.0.0"}')
        )
        assert isinstance(preview, GeneratorPreview)
        assert preview.count == 1
        assert len(preview.mocks) == 1
        assert preview.mocks[0].id == "preview-1"

    @respx.mock
    def test_generate_graphql(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/generators/graphql").mock(
            return_value=httpx.Response(
                200,
                json={"created": 2, "mocks": [{"id": "gql-1"}, {"id": "gql-2"}]},
            )
        )

        result = client.generator.generate_graphql(
            {"graphqlUrl": "http://localhost:4000/graphql"}
        )
        assert result.created == 2
        assert len(result.mocks) == 2

    @respx.mock
    def test_generate_grpc(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/generators/grpc").mock(
            return_value=httpx.Response(
                200,
                json={"created": 1, "mocks": [{"id": "grpc-1"}]},
            )
        )

        result = client.generator.generate_grpc({"spec": "syntax = \"proto3\";"})
        assert result.created == 1

    @respx.mock
    def test_generate_soap(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/generators/soap").mock(
            return_value=httpx.Response(
                200,
                json={"created": 1, "mocks": [{"id": "soap-1"}]},
            )
        )

        result = client.generator.generate_soap({"url": "http://example.com/service?wsdl"})
        assert result.created == 1


# ── FuzzingAPI ───────────────────────────────────────────────────────


class TestFuzzingAPI:
    """Test fuzzing configuration and execution."""

    @respx.mock
    def test_create_config(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/configs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "fuzz-cfg-1",
                    "name": "Pet API Fuzz",
                    "targetBaseUrl": "http://localhost:8080",
                    "strategy": "smart",
                },
            )
        )

        config = client.fuzzing.create_config(
            FuzzingConfig(
                name="Pet API Fuzz",
                target_base_url="http://localhost:8080",
                strategy="smart",
            )
        )
        assert isinstance(config, FuzzingConfig)
        assert config.id == "fuzz-cfg-1"
        assert config.target_base_url == "http://localhost:8080"
        assert config.strategy == "smart"

    @respx.mock
    def test_list_configs_array(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/configs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "cfg-1", "name": "Config A"},
                    {"id": "cfg-2", "name": "Config B"},
                ],
            )
        )

        configs = client.fuzzing.list_configs()
        assert len(configs) == 2
        assert configs[0].id == "cfg-1"

    @respx.mock
    def test_list_configs_envelope(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/configs").mock(
            return_value=httpx.Response(
                200,
                json={"configs": [{"id": "cfg-1"}]},
            )
        )

        configs = client.fuzzing.list_configs()
        assert len(configs) == 1

    @respx.mock
    def test_get_config(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/configs/cfg-1").mock(
            return_value=httpx.Response(
                200, json={"id": "cfg-1", "name": "My Config"}
            )
        )

        config = client.fuzzing.get_config("cfg-1")
        assert config.id == "cfg-1"
        assert config.name == "My Config"

    @respx.mock
    def test_update_config(self, client: MockartyClient) -> None:
        respx.put("http://localhost:5770/api/v1/fuzzing/configs/cfg-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "cfg-1", "name": "Updated Config", "targetBaseUrl": "http://new-target:8080"},
            )
        )

        config = client.fuzzing.update_config("cfg-1", {"name": "Updated Config"})
        assert isinstance(config, FuzzingConfig)
        assert config.name == "Updated Config"

    @respx.mock
    def test_delete_config(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/fuzzing/configs/cfg-1").mock(
            return_value=httpx.Response(200)
        )
        client.fuzzing.delete_config("cfg-1")
        assert route.called

    @respx.mock
    def test_start_fuzzing(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/run").mock(
            return_value=httpx.Response(
                200, json={"id": "run-1", "status": "running"}
            )
        )

        run = client.fuzzing.start({"targetBaseUrl": "http://localhost:8080"})
        assert isinstance(run, FuzzingRun)
        assert run.id == "run-1"
        assert run.status == "running"

    @respx.mock
    def test_stop_fuzzing(self, client: MockartyClient) -> None:
        route = respx.post("http://localhost:5770/api/v1/fuzzing/run/run-1/stop").mock(
            return_value=httpx.Response(200)
        )
        client.fuzzing.stop("run-1")
        assert route.called

    @respx.mock
    def test_list_results(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/results").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "res-1",
                        "configId": "cfg-1",
                        "status": "completed",
                        "totalRequests": 5000,
                        "totalFindings": 3,
                    }
                ],
            )
        )

        results = client.fuzzing.list_results()
        assert len(results) == 1
        assert isinstance(results[0], FuzzingResult)
        assert results[0].total_requests == 5000
        assert results[0].total_findings == 3

    @respx.mock
    def test_get_result(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/results/res-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "res-1",
                    "configId": "cfg-1",
                    "status": "completed",
                    "startedAt": "2023-11-14T22:13:20Z",
                    "completedAt": "2023-11-14T22:18:20Z",
                },
            )
        )

        result = client.fuzzing.get_result("res-1")
        assert result.config_id == "cfg-1"
        assert result.started_at == "2023-11-14T22:13:20Z"
        assert result.completed_at == "2023-11-14T22:18:20Z"

    @respx.mock
    def test_delete_result(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/fuzzing/results/res-1").mock(
            return_value=httpx.Response(200)
        )
        client.fuzzing.delete_result("res-1")
        assert route.called

    @respx.mock
    def test_get_schedule(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/schedules/sched-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "sched-1", "name": "Nightly Fuzz", "cronExpression": "0 2 * * *", "enabled": True},
            )
        )

        schedule = client.fuzzing.get_schedule("sched-1")
        assert schedule["id"] == "sched-1"
        assert schedule["name"] == "Nightly Fuzz"

    @respx.mock
    def test_export_findings_returns_bytes(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/findings/export").mock(
            return_value=httpx.Response(200, content=b'[{"id":"f-1"}]')
        )

        data = client.fuzzing.export_findings({"format": "json"})
        assert isinstance(data, bytes)
        assert b"f-1" in data

    # ── Batch finding operations ──────────────────────────────────────

    @respx.mock
    def test_batch_manual_triage(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/findings/batch-manual-triage").mock(
            return_value=httpx.Response(200, json={"updated": 3})
        )

        result = client.fuzzing.batch_manual_triage(
            ["f-1", "f-2", "f-3"],
            status="false_positive",
            note="All benign",
        )
        assert result["updated"] == 3

    @respx.mock
    def test_batch_manual_triage_without_note(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/findings/batch-manual-triage").mock(
            return_value=httpx.Response(200, json={"updated": 2})
        )

        result = client.fuzzing.batch_manual_triage(
            ["f-1", "f-2"], status="confirmed"
        )
        assert result["updated"] == 2

    @respx.mock
    def test_batch_delete_findings(self, client: MockartyClient) -> None:
        respx.delete("http://localhost:5770/api/v1/fuzzing/findings/batch").mock(
            return_value=httpx.Response(200, json={"deleted": 2})
        )

        result = client.fuzzing.batch_delete_findings(["f-1", "f-2"])
        assert result["deleted"] == 2

    # ── Quarantine ────────────────────────────────────────────────────

    @respx.mock
    def test_list_quarantine(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/quarantine").mock(
            return_value=httpx.Response(
                200,
                json={
                    "entries": [
                        {
                            "id": "q-1",
                            "fingerprint": "injection|POST /users|<script>",
                            "category": "injection",
                            "endpointPattern": "POST /users",
                            "title": "XSS false positive",
                            "reason": "Sanitized by middleware",
                            "createdAt": "2023-11-14T22:13:20Z",
                        }
                    ],
                    "total": 1,
                },
            )
        )

        entries, total = client.fuzzing.list_quarantine(limit=10, offset=0)
        assert total == 1
        assert len(entries) == 1
        assert isinstance(entries[0], QuarantineEntry)
        assert entries[0].id == "q-1"
        assert entries[0].fingerprint == "injection|POST /users|<script>"
        assert entries[0].endpoint_pattern == "POST /users"

    @respx.mock
    def test_create_quarantine(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/quarantine").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "q-new",
                    "fingerprint": "sqli|GET /search|1 OR 1=1",
                    "category": "sqli",
                    "reason": "Parameterized queries prevent injection",
                },
            )
        )

        entry = client.fuzzing.create_quarantine({
            "fingerprint": "sqli|GET /search|1 OR 1=1",
            "category": "sqli",
            "reason": "Parameterized queries prevent injection",
        })
        assert isinstance(entry, QuarantineEntry)
        assert entry.id == "q-new"

    @respx.mock
    def test_delete_quarantine(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/fuzzing/quarantine/q-1").mock(
            return_value=httpx.Response(200)
        )
        client.fuzzing.delete_quarantine("q-1")
        assert route.called

    @respx.mock
    def test_batch_delete_quarantine(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/quarantine/batch-delete").mock(
            return_value=httpx.Response(200, json={"deleted": 3})
        )

        result = client.fuzzing.batch_delete_quarantine(["q-1", "q-2", "q-3"])
        assert result["deleted"] == 3

    @respx.mock
    def test_quarantine_finding(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/quarantine/from-finding").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "q-from-f",
                    "fingerprint": "xss|POST /api|<img onerror>",
                    "reason": "False positive",
                },
            )
        )

        entry = client.fuzzing.quarantine_finding("f-123", reason="False positive")
        assert isinstance(entry, QuarantineEntry)
        assert entry.id == "q-from-f"
        assert entry.reason == "False positive"

    @respx.mock
    def test_batch_quarantine_findings(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/fuzzing/quarantine/from-findings").mock(
            return_value=httpx.Response(
                200,
                json={"created": 2, "triaged": 2, "failed": 0},
            )
        )

        result = client.fuzzing.batch_quarantine_findings(
            ["f-1", "f-2"], reason="Bulk quarantine"
        )
        assert result["created"] == 2
        assert result["triaged"] == 2
        assert result["failed"] == 0


# ── ContractAPI ──────────────────────────────────────────────────────


class TestContractAPI:
    """Test contract testing operations."""

    @respx.mock
    def test_validate_mocks(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/contract/validate-mocks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "val-1",
                    "status": "failed",
                    "violations": 2,
                    "details": [
                        {
                            "path": "/api/users",
                            "message": "Missing required field 'email'",
                            "severity": "error",
                        },
                        {
                            "path": "/api/users/:id",
                            "message": "Wrong status code",
                            "severity": "warning",
                            "expected": "200",
                            "actual": "201",
                        },
                    ],
                },
            )
        )

        result = client.contracts.validate_mocks({
            "specUrl": "https://example.com/spec.yaml",
            "namespace": "default",
        })
        assert isinstance(result, ContractValidationResult)
        assert result.status == "failed"
        assert result.violations == 2
        assert len(result.details) == 2
        assert result.details[0].path == "/api/users"
        assert result.details[1].expected == "200"

    @respx.mock
    def test_verify_provider(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/contract/verify-provider").mock(
            return_value=httpx.Response(
                200,
                json={"id": "val-2", "status": "passed", "violations": 0},
            )
        )

        result = client.contracts.verify_provider({
            "targetUrl": "http://localhost:8080",
            "specUrl": "https://example.com/spec.yaml",
        })
        assert result.status == "passed"
        assert result.violations == 0

    @respx.mock
    def test_list_configs(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/contract/configs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "c-1", "name": "Config A"},
                    {"id": "c-2", "name": "Config B"},
                ],
            )
        )

        configs = client.contracts.list_configs()
        assert len(configs) == 2
        assert configs[0].name == "Config A"

    @respx.mock
    def test_save_config(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/contract/configs").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "c-1",
                    "name": "User API Contract",
                    "targetUrl": "http://localhost:8080",
                },
            )
        )

        config = client.contracts.save_config(
            ContractConfig(
                name="User API Contract",
                target_url="http://localhost:8080",
            )
        )
        assert isinstance(config, ContractConfig)
        assert config.id == "c-1"

    @respx.mock
    def test_delete_config(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/contract/configs/c-1").mock(
            return_value=httpx.Response(200)
        )
        client.contracts.delete_config("c-1")
        assert route.called

    @respx.mock
    def test_list_results(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/contract/results").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "res-1", "configId": "c-1", "status": "passed"},
                    {"id": "res-2", "configId": "c-1", "status": "failed"},
                ],
            )
        )

        results = client.contracts.list_results()
        assert len(results) == 2
        assert results[0].status == "passed"
        assert results[1].status == "failed"

    @respx.mock
    def test_get_result(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/contract/results/res-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "res-1", "configId": "c-1", "status": "passed"},
            )
        )

        result = client.contracts.get_result("res-1")
        assert result.id == "res-1"


# ── RecorderAPI ──────────────────────────────────────────────────────


class TestRecorderAPI:
    """Test traffic recording operations."""

    @respx.mock
    def test_create_session(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/recorder/start").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "sess-1",
                    "name": "User API Recording",
                    "targetUrl": "http://localhost:8080",
                    "status": "recording",
                },
            )
        )

        session = client.recorder.create(
            RecorderSession(name="User API Recording", target_url="http://localhost:8080")
        )
        assert isinstance(session, RecorderSession)
        assert session.id == "sess-1"
        assert session.status == "recording"

    @respx.mock
    def test_list_sessions(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/recorder/sessions").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "sess-1", "status": "recording"},
                    {"id": "sess-2", "status": "stopped"},
                ],
            )
        )

        sessions = client.recorder.list()
        assert len(sessions) == 2
        assert sessions[0].status == "recording"

    @respx.mock
    def test_get_session(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/recorder/sess-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "sess-1", "name": "My Session", "entryCount": 42},
            )
        )

        session = client.recorder.get("sess-1")
        assert session.entry_count == 42

    @respx.mock
    def test_stop_session(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/recorder/sess-1/stop").mock(
            return_value=httpx.Response(
                200, json={"id": "sess-1", "status": "stopped"}
            )
        )

        session = client.recorder.stop("sess-1")
        assert session.status == "stopped"

    @respx.mock
    def test_delete_session(self, client: MockartyClient) -> None:
        route = respx.delete(
            "http://localhost:5770/api/v1/recorder/sess-1"
        ).mock(return_value=httpx.Response(200))
        client.recorder.delete("sess-1")
        assert route.called

    @respx.mock
    def test_get_entries(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/recorder/sess-1/entries"
        ).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "e-1",
                        "method": "GET",
                        "path": "/api/users",
                        "statusCode": 200,
                        "duration": 45,
                    },
                    {
                        "id": "e-2",
                        "method": "POST",
                        "path": "/api/users",
                        "statusCode": 201,
                        "duration": 120,
                    },
                ],
            )
        )

        entries = client.recorder.entries("sess-1")
        assert len(entries) == 2
        assert isinstance(entries[0], RecorderEntry)
        assert entries[0].method == "GET"
        assert entries[0].status_code == 200
        assert entries[1].duration == 120

    @respx.mock
    def test_generate_mocks(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/recorder/sess-1/mocks"
        ).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "rec-mock-1", "http": {"route": "/api/users", "httpMethod": "GET"}},
                    {"id": "rec-mock-2", "http": {"route": "/api/users", "httpMethod": "POST"}},
                ],
            )
        )

        mocks = client.recorder.generate_mocks("sess-1")
        assert len(mocks) == 2
        assert isinstance(mocks[0], Mock)
        assert mocks[0].id == "rec-mock-1"

    @respx.mock
    def test_replay_session_passes_options(self, client: MockartyClient) -> None:
        # Capture the request body so we can assert the options dict was
        # forwarded as-is to the server.
        captured: dict[str, object] = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            import json as _json
            captured.update(_json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "sessionId": "sess-1",
                    "totalEntries": 3,
                    "matched": 2,
                    "mismatched": 0,
                    "failed": 1,
                    "skipped": 0,
                    "results": [],
                },
            )

        respx.post("http://localhost:5770/api/v1/recorder/sess-1/replay").mock(
            side_effect=_handler
        )

        summary = client.recorder.replay_session(
            "sess-1",
            options={
                "targetUrl": "http://staging.example.com",
                "concurrency": 5,
                "timeoutMs": 5000,
                "entryIds": ["e-1", "e-2"],
            },
        )
        assert summary["matched"] == 2
        assert summary["failed"] == 1
        assert captured["targetUrl"] == "http://staging.example.com"
        assert captured["concurrency"] == 5
        assert captured["entryIds"] == ["e-1", "e-2"]

    @respx.mock
    def test_replay_session_nil_options_sends_empty_object(
        self, client: MockartyClient
    ) -> None:
        # When called without options the SDK still sends an object body so
        # the server's JSON decoder doesn't see a null payload.
        captured: dict[str, object] = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            import json as _json
            captured.update(_json.loads(request.content))
            return httpx.Response(
                200, json={"sessionId": "sess-1", "totalEntries": 0}
            )

        respx.post("http://localhost:5770/api/v1/recorder/sess-1/replay").mock(
            side_effect=_handler
        )
        summary = client.recorder.replay_session("sess-1")
        assert summary["totalEntries"] == 0
        # captured is empty dict, but the body itself was a JSON object
        assert captured == {}

    @respx.mock
    def test_correlate_session(self, client: MockartyClient) -> None:
        captured: dict[str, object] = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            import json as _json
            captured.update(_json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "sessionId": "sess-1",
                    "totalEntries": 4,
                    "correlations": [
                        {
                            "value": "tok-abc-1234",
                            "valueType": "token",
                            "confidence": 0.95,
                            "source": {
                                "entryId": "e-1",
                                "section": "response.body.json",
                            },
                            "targets": [
                                {
                                    "entryId": "e-2",
                                    "section": "request.header",
                                },
                            ],
                        },
                    ],
                },
            )

        respx.post(
            "http://localhost:5770/api/v1/recorder/sess-1/correlate"
        ).mock(side_effect=_handler)

        report = client.recorder.correlate_session(
            "sess-1",
            options={
                "minValueLength": 8,
                "excludeNumeric": True,
            },
        )
        assert report["totalEntries"] == 4
        assert len(report["correlations"]) == 1
        assert report["correlations"][0]["valueType"] == "token"
        assert captured["minValueLength"] == 8
        assert captured["excludeNumeric"] is True

    @respx.mock
    def test_correlate_session_server_error(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/recorder/sess-1/correlate"
        ).mock(
            return_value=httpx.Response(400, json={"error": "minValueLength out of range"})
        )
        with pytest.raises(Exception):
            client.recorder.correlate_session(
                "sess-1", options={"minValueLength": 99999}
            )


# ── TemplateAPI ──────────────────────────────────────────────────────


class TestTemplateAPI:
    """Test template file management."""

    @respx.mock
    def test_list_templates(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/templates").mock(
            return_value=httpx.Response(
                200,
                json={
                    "templates": ["user_response.json", "error_response.json"],
                    "namespace": "sandbox",
                    "total": 2,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )

        templates = client.templates.list()
        assert templates == ["user_response.json", "error_response.json"]

    @respx.mock
    def test_list_templates_bare_list(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/templates").mock(
            return_value=httpx.Response(200, json=["a.json", "b.json"])
        )
        assert client.templates.list() == ["a.json", "b.json"]

    @respx.mock
    def test_get_template(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/templates/user_response.json").mock(
            return_value=httpx.Response(
                200,
                content=b'{"name": "$.fake.FirstName"}',
                headers={"content-type": "application/json"},
            )
        )

        content = client.templates.get("user_response.json")
        assert b"$.fake.FirstName" in content

    @respx.mock
    def test_upload_template(self, client: MockartyClient) -> None:
        route = respx.post(
            "http://localhost:5770/api/v1/templates/new_template.json"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": "Template uploaded successfully",
                    "fileName": "new_template.json",
                    "namespace": "sandbox",
                },
            )
        )

        client.templates.upload("new_template.json", '{"key": "value"}')
        assert route.called
        assert route.calls[0].request.content == b'{"key": "value"}'

    @respx.mock
    def test_delete_template(self, client: MockartyClient) -> None:
        route = respx.delete(
            "http://localhost:5770/api/v1/templates/old_template.json"
        ).mock(return_value=httpx.Response(200))
        client.templates.delete("old_template.json")
        assert route.called


# ── ImportAPI ────────────────────────────────────────────────────────


class TestImportAPI:
    """Test collection import operations."""

    @respx.mock
    def test_import_postman(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/api-tester/import/postman").mock(
            return_value=httpx.Response(
                200,
                json={
                    "collectionId": "col-1",
                    "name": "Postman Collection",
                    "imported": 15,
                    "message": "Imported 15 requests",
                },
            )
        )

        result = client.imports.postman({"info": {"name": "My Collection"}, "item": []})
        assert isinstance(result, ImportResult)
        assert result.collection_id == "col-1"
        assert result.imported == 15
        assert result.name == "Postman Collection"

    @respx.mock
    def test_import_insomnia(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/api-tester/import/insomnia").mock(
            return_value=httpx.Response(
                200,
                json={"collectionId": "col-2", "name": "Insomnia", "imported": 8},
            )
        )

        result = client.imports.insomnia({"resources": []})
        assert result.imported == 8

    @respx.mock
    def test_import_har(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/api-tester/import/har").mock(
            return_value=httpx.Response(
                200,
                json={"collectionId": "col-3", "name": "HAR Import", "imported": 20},
            )
        )

        result = client.imports.har({"log": {"entries": []}})
        assert result.imported == 20

    @respx.mock
    def test_import_curl(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/api-tester/import/curl").mock(
            return_value=httpx.Response(
                200,
                json={"collectionId": "col-4", "name": "cURL Import", "imported": 2},
            )
        )

        result = client.imports.curl([
            "curl -X GET http://example.com/api/users",
            "curl -X POST http://example.com/api/users -d '{}'",
        ])
        assert result.imported == 2


# ── TestRunAPI ───────────────────────────────────────────────────────


class TestTestRunAPI:
    """Test test run history operations."""

    @respx.mock
    def test_list_runs(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/api-tester/test-runs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "run-1",
                        "collectionId": "col-1",
                        "status": "passed",
                        "totalTests": 10,
                        "passedTests": 10,
                        "failedTests": 0,
                        "duration": 5000,
                    },
                    {
                        "id": "run-2",
                        "collectionId": "col-1",
                        "status": "failed",
                        "totalTests": 10,
                        "passedTests": 8,
                        "failedTests": 2,
                        "duration": 4500,
                    },
                ],
            )
        )

        runs = client.test_runs.list()
        assert len(runs) == 2
        assert isinstance(runs[0], TestRun)
        assert runs[0].status == "passed"
        assert runs[0].total_tests == 10
        assert runs[1].failed_tests == 2

    @respx.mock
    def test_list_runs_envelope(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/api-tester/test-runs").mock(
            return_value=httpx.Response(
                200, json={"runs": [{"id": "run-1", "status": "passed"}]}
            )
        )

        runs = client.test_runs.list()
        assert len(runs) == 1

    @respx.mock
    def test_list_runs_mode_filter(self, client: MockartyClient) -> None:
        """Migration 033: mode + referenceId filters hit the unified feed."""
        route = respx.get(
            "http://localhost:5770/api/v1/api-tester/test-runs"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "runs": [
                        {
                            "id": "fuzz-run-1",
                            "mode": "fuzz",
                            "referenceId": "cfg-42",
                            "status": "running",
                        }
                    ]
                },
            )
        )

        runs = client.test_runs.list(mode="fuzz", reference_id="cfg-42", limit=25)
        assert len(runs) == 1
        assert runs[0].mode == "fuzz"
        assert runs[0].reference_id == "cfg-42"

        # The query params must be forwarded to the server
        assert route.called
        url = route.calls[-1].request.url
        assert url.params.get("mode") == "fuzz"
        assert url.params.get("referenceId") == "cfg-42"
        assert url.params.get("limit") == "25"

    @respx.mock
    def test_list_by_mode_wrapper(self, client: MockartyClient) -> None:
        """list_by_mode delegates to list with the mode argument."""
        route = respx.get(
            "http://localhost:5770/api/v1/api-tester/test-runs"
        ).mock(
            return_value=httpx.Response(200, json={"runs": []})
        )

        client.test_runs.list_by_mode("chaos")
        assert route.called
        assert route.calls[-1].request.url.params.get("mode") == "chaos"

    @respx.mock
    def test_get_run(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/api-tester/test-runs/run-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "run-1",
                    "collectionId": "col-1",
                    "status": "passed",
                    "startedAt": "2023-11-14T22:13:20Z",
                    "completedAt": "2023-11-14T22:13:25Z",
                    "environment": "staging",
                },
            )
        )

        run = client.test_runs.get("run-1")
        assert run.id == "run-1"
        assert run.collection_id == "col-1"
        assert run.started_at == "2023-11-14T22:13:20Z"
        assert run.environment == "staging"

    @respx.mock
    def test_delete_run(self, client: MockartyClient) -> None:
        route = respx.delete("http://localhost:5770/api/v1/api-tester/test-runs/run-1").mock(
            return_value=httpx.Response(200)
        )
        client.test_runs.delete("run-1")
        assert route.called

    @respx.mock
    def test_list_by_collection(self, client: MockartyClient) -> None:
        # Backend has no per-collection test-runs endpoint; SDK filters client-side
        # over the full list returned by /api-tester/test-runs.
        respx.get("http://localhost:5770/api/v1/api-tester/test-runs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "run-1", "collectionId": "col-1", "status": "passed"},
                    {"id": "run-2", "collectionId": "col-1", "status": "failed"},
                    {"id": "run-3", "collectionId": "col-2", "status": "passed"},
                ],
            )
        )

        runs = client.test_runs.list_by_collection("col-1")
        assert len(runs) == 2
        assert all(r.collection_id == "col-1" for r in runs)

    @respx.mock
    def test_list_active(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/test-runs/active").mock(
            return_value=httpx.Response(
                200,
                json={
                    "runs": [
                        {"id": "00000000-0000-0000-0000-000000000001", "status": "running"},
                        {"id": "00000000-0000-0000-0000-000000000002", "status": "pending"},
                    ]
                },
            )
        )

        runs = client.test_runs.list_active()
        assert len(runs) == 2
        assert runs[0].status == "running"


# ── Client property access ───────────────────────────────────────────


class TestAdvancedClientProperties:
    """Verify advanced API properties are accessible on the client."""

    def test_generator_property(self, client: MockartyClient) -> None:
        from mockarty.api.generator import GeneratorAPI
        assert isinstance(client.generator, GeneratorAPI)

    def test_fuzzing_property(self, client: MockartyClient) -> None:
        from mockarty.api.fuzzing import FuzzingAPI
        assert isinstance(client.fuzzing, FuzzingAPI)

    def test_contracts_property(self, client: MockartyClient) -> None:
        from mockarty.api.contracts import ContractAPI
        assert isinstance(client.contracts, ContractAPI)

    def test_recorder_property(self, client: MockartyClient) -> None:
        from mockarty.api.recorder import RecorderAPI
        assert isinstance(client.recorder, RecorderAPI)

    def test_templates_property(self, client: MockartyClient) -> None:
        from mockarty.api.templates import TemplateAPI
        assert isinstance(client.templates, TemplateAPI)

    def test_imports_property(self, client: MockartyClient) -> None:
        from mockarty.api.imports import ImportAPI
        assert isinstance(client.imports, ImportAPI)

    def test_test_runs_property(self, client: MockartyClient) -> None:
        from mockarty.api.testruns import TestRunAPI
        assert isinstance(client.test_runs, TestRunAPI)

    def test_tags_property(self, client: MockartyClient) -> None:
        from mockarty.api.tags import TagAPI
        assert isinstance(client.tags, TagAPI)

    def test_folders_property(self, client: MockartyClient) -> None:
        from mockarty.api.folders import FolderAPI
        assert isinstance(client.folders, FolderAPI)

    def test_undefined_property(self, client: MockartyClient) -> None:
        from mockarty.api.undefined import UndefinedAPI
        assert isinstance(client.undefined, UndefinedAPI)

    def test_stats_property(self, client: MockartyClient) -> None:
        from mockarty.api.stats import StatsAPI
        assert isinstance(client.stats, StatsAPI)

    def test_agent_tasks_property(self, client: MockartyClient) -> None:
        from mockarty.api.agent_tasks import AgentTaskAPI
        assert isinstance(client.agent_tasks, AgentTaskAPI)

    def test_namespace_settings_property(self, client: MockartyClient) -> None:
        from mockarty.api.namespace_settings import NamespaceSettingsAPI
        assert isinstance(client.namespace_settings, NamespaceSettingsAPI)

    def test_proxy_property(self, client: MockartyClient) -> None:
        from mockarty.api.proxy import ProxyAPI
        assert isinstance(client.proxy, ProxyAPI)

    def test_environments_property(self, client: MockartyClient) -> None:
        from mockarty.api.environments import EnvironmentAPI
        assert isinstance(client.environments, EnvironmentAPI)

    def test_properties_are_lazy_cached(self, client: MockartyClient) -> None:
        """Properties return the same instance on repeated access."""
        assert client.generator is client.generator
        assert client.fuzzing is client.fuzzing
        assert client.contracts is client.contracts
        assert client.recorder is client.recorder
        assert client.templates is client.templates
        assert client.imports is client.imports
        assert client.test_runs is client.test_runs
        assert client.tags is client.tags
        assert client.folders is client.folders
        assert client.undefined is client.undefined
        assert client.stats is client.stats
        assert client.agent_tasks is client.agent_tasks
        assert client.proxy is client.proxy
        assert client.environments is client.environments

    def test_namespace_change_resets_caches(self, client: MockartyClient) -> None:
        """Changing namespace invalidates all cached API instances."""
        gen1 = client.generator
        fuzz1 = client.fuzzing
        tags1 = client.tags

        client.namespace = "new-ns"

        assert client.generator is not gen1
        assert client.fuzzing is not fuzz1
        assert client.tags is not tags1
