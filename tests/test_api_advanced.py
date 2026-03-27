# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for Advanced API resources: Generator, Fuzzing, Contracts, Recorder, Templates, Imports, TestRuns."""

from __future__ import annotations

import httpx
import pytest
import respx

from mockarty import MockartyClient
from mockarty.models.contract import ContractConfig, ContractValidationResult
from mockarty.models.fuzzing import FuzzingConfig, FuzzingResult, FuzzingRun
from mockarty.models.generator import GeneratorPreview, GeneratorRequest, GeneratorResponse
from mockarty.models.imports import ImportResult
from mockarty.models.mock import Mock
from mockarty.models.recorder import RecorderEntry, RecorderSession
from mockarty.models.templates import TemplateFile
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
                    "targetUrl": "http://localhost:8080",
                    "duration": "5m",
                    "workers": 4,
                },
            )
        )

        config = client.fuzzing.create_config(
            FuzzingConfig(
                name="Pet API Fuzz",
                target_url="http://localhost:8080",
                duration="5m",
                workers=4,
            )
        )
        assert isinstance(config, FuzzingConfig)
        assert config.id == "fuzz-cfg-1"
        assert config.target_url == "http://localhost:8080"
        assert config.workers == 4

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

        run = client.fuzzing.start({"targetUrl": "http://localhost:8080"})
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
                        "findings": 3,
                    }
                ],
            )
        )

        results = client.fuzzing.list_results()
        assert len(results) == 1
        assert isinstance(results[0], FuzzingResult)
        assert results[0].total_requests == 5000
        assert results[0].findings == 3

    @respx.mock
    def test_get_result(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/fuzzing/results/res-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "res-1",
                    "configId": "cfg-1",
                    "status": "completed",
                    "startedAt": 1700000000,
                    "finishedAt": 1700000300,
                },
            )
        )

        result = client.fuzzing.get_result("res-1")
        assert result.config_id == "cfg-1"
        assert result.started_at == 1700000000
        assert result.finished_at == 1700000300


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


# ── TemplateAPI ──────────────────────────────────────────────────────


class TestTemplateAPI:
    """Test template file management."""

    @respx.mock
    def test_list_templates(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/templates").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"name": "user_response.json", "size": 256, "updatedAt": 1700000000},
                    {"name": "error_response.json", "size": 128, "updatedAt": 1700000100},
                ],
            )
        )

        templates = client.templates.list()
        assert len(templates) == 2
        assert isinstance(templates[0], TemplateFile)
        assert templates[0].name == "user_response.json"
        assert templates[0].size == 256
        assert templates[0].updated_at == 1700000000

    @respx.mock
    def test_list_templates_envelope(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/templates").mock(
            return_value=httpx.Response(
                200,
                json={"templates": [{"name": "tmpl.json"}]},
            )
        )

        templates = client.templates.list()
        assert len(templates) == 1

    @respx.mock
    def test_get_template(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/templates/user_response.json").mock(
            return_value=httpx.Response(
                200, json={"content": '{"name": "$.fake.FirstName"}'}
            )
        )

        content = client.templates.get("user_response.json")
        assert '$.fake.FirstName' in content

    @respx.mock
    def test_create_template(self, client: MockartyClient) -> None:
        respx.post("http://localhost:5770/api/v1/templates").mock(
            return_value=httpx.Response(
                200,
                json={"name": "new_template.json", "size": 64, "updatedAt": 1700000200},
            )
        )

        template = client.templates.create("new_template.json", '{"key": "value"}')
        assert isinstance(template, TemplateFile)
        assert template.name == "new_template.json"

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
    def test_get_run(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/api-tester/test-runs/run-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "run-1",
                    "collectionId": "col-1",
                    "status": "passed",
                    "startedAt": 1700000000,
                    "finishedAt": 1700000005,
                    "environment": "staging",
                },
            )
        )

        run = client.test_runs.get("run-1")
        assert run.id == "run-1"
        assert run.collection_id == "col-1"
        assert run.started_at == 1700000000
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
        respx.get("http://localhost:5770/api/v1/api-tester/collections/col-1/test-runs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "run-1", "collectionId": "col-1", "status": "passed"},
                    {"id": "run-2", "collectionId": "col-1", "status": "failed"},
                ],
            )
        )

        runs = client.test_runs.list_by_collection("col-1")
        assert len(runs) == 2
        assert all(r.collection_id == "col-1" for r in runs)


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
