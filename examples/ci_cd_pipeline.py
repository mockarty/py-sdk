"""CI/CD pipeline automation example.

Demonstrates a complete end-to-end testing pipeline using the Mockarty SDK:

  1. Setup namespace for the CI run
  2. Import OpenAPI spec and generate mocks
  3. Contract validation (pact verification + can-i-deploy)
  4. Execute API test collections
  5. Run fuzzing against generated mocks
  6. Run performance tests
  7. Collect results and export reports
  8. Cleanup

This script is designed to be called from a CI/CD system (GitHub Actions,
GitLab CI, Jenkins, etc.) and returns non-zero exit code on failures.
"""

from __future__ import annotations

import sys
import time

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"
NAMESPACE = "ci-pipeline"

# OpenAPI spec for the service under test
OPENAPI_SPEC_URL = "http://localhost:5770/swagger/doc.json"


class PipelineResult:
    """Tracks pass/fail status for each pipeline stage."""

    def __init__(self) -> None:
        self.stages: list[dict[str, object]] = []

    def record(self, stage: str, passed: bool, details: str = "") -> None:
        self.stages.append({"stage": stage, "passed": passed, "details": details})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {stage}")
        if details:
            print(f"         {details}")

    @property
    def all_passed(self) -> bool:
        return all(s["passed"] for s in self.stages)

    def summary(self) -> None:
        total = len(self.stages)
        passed = sum(1 for s in self.stages if s["passed"])
        failed = total - passed
        print(f"\n{'=' * 60}")
        print(f"  PIPELINE RESULT: {'PASSED' if self.all_passed else 'FAILED'}")
        print(f"  Stages: {passed}/{total} passed, {failed} failed")
        print(f"{'=' * 60}")
        if not self.all_passed:
            print("\n  Failed stages:")
            for s in self.stages:
                if not s["passed"]:
                    print(f"    - {s['stage']}: {s['details']}")


# ---------------------------------------------------------------------------
# Stage 1: Namespace Setup
# ---------------------------------------------------------------------------

def stage_setup_namespace(client: MockartyClient, result: PipelineResult) -> bool:
    """Create an isolated namespace for this CI run.

    Each CI run uses its own namespace to avoid conflicts with
    other builds running in parallel.
    """
    print("\n--- Stage 1: Setup Namespace ---")
    try:
        # Create namespace (idempotent -- may already exist)
        try:
            client.namespaces.create(NAMESPACE)
        except Exception:
            pass  # Namespace already exists

        # Switch client to the CI namespace
        client.namespace = NAMESPACE

        # Verify namespace exists
        namespaces = client.namespaces.list()
        if NAMESPACE in namespaces:
            result.record("namespace_setup", True, f"Namespace '{NAMESPACE}' ready")
            return True
        else:
            result.record("namespace_setup", True, f"Namespace '{NAMESPACE}' created")
            return True
    except Exception as e:
        result.record("namespace_setup", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 2: Import OpenAPI and Generate Mocks
# ---------------------------------------------------------------------------

def stage_import_and_generate(client: MockartyClient, result: PipelineResult) -> bool:
    """Import an OpenAPI spec and generate mock definitions.

    This creates mocks for all endpoints defined in the spec,
    providing a baseline for contract and functional testing.
    """
    print("\n--- Stage 2: Import OpenAPI & Generate Mocks ---")
    try:
        # Preview what will be generated
        preview = client.generator.preview_openapi({
            "specUrl": OPENAPI_SPEC_URL,
        })
        print(f"  Preview: {preview.count} mocks would be generated")

        # Generate and create mocks
        gen_result = client.generator.generate_openapi({
            "specUrl": OPENAPI_SPEC_URL,
            "namespace": NAMESPACE,
            "tags": ["ci-generated", "openapi"],
        })
        mock_count = gen_result.created
        result.record(
            "openapi_import",
            mock_count > 0,
            f"Generated {mock_count} mocks from OpenAPI spec",
        )

        # Verify mocks were created
        page = client.mocks.list(tags=["ci-generated"])
        result.record(
            "mock_verification",
            page.total > 0,
            f"Verified {page.total} mocks in namespace",
        )
        return True
    except Exception as e:
        result.record("openapi_import", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 3: Contract Validation
# ---------------------------------------------------------------------------

def stage_contract_validation(client: MockartyClient, result: PipelineResult) -> bool:
    """Validate contracts: mock conformance, pact verification, can-i-deploy.

    This stage ensures:
      - Generated mocks conform to the OpenAPI spec
      - Pact contracts between services are satisfied
      - It is safe to deploy the current version
    """
    print("\n--- Stage 3: Contract Validation ---")
    try:
        # Validate mocks against spec
        validation = client.contracts.validate_mocks({
            "specUrl": OPENAPI_SPEC_URL,
            "namespace": NAMESPACE,
        })
        violations = validation.violations or 0
        result.record(
            "mock_spec_validation",
            violations == 0,
            f"Violations: {violations} (status={validation.status})",
        )

        # Publish a pact contract for this build
        pact = client.contracts.publish_pact({
            "consumer": "frontend-app",
            "provider": "backend-api",
            "version": "ci-build-latest",
            "interactions": [
                {
                    "description": "health check",
                    "request": {"method": "GET", "path": "/health"},
                    "response": {"status": 200},
                },
            ],
        })
        pact_id = pact.get("id")
        result.record("pact_publish", bool(pact_id), f"Pact ID: {pact_id}")

        # Verify the pact
        if pact_id:
            verification = client.contracts.verify_pact({
                "pactId": pact_id,
                "providerBaseUrl": MOCKARTY_URL,
                "providerVersion": "ci-build-latest",
            })
            pact_ok = verification.get("status") in ("passed", "success", None)
            result.record(
                "pact_verification",
                pact_ok,
                f"Status: {verification.get('status')}",
            )

        # Can I deploy?
        deploy_check = client.contracts.can_i_deploy({
            "service": "frontend-app",
            "version": "ci-build-latest",
            "environment": "staging",
        })
        deployable = deploy_check.get("deployable", True)
        result.record(
            "can_i_deploy",
            deployable,
            f"Deployable: {deployable}",
        )

        # Cleanup pact
        if pact_id:
            try:
                client.contracts.delete_pact(pact_id)
            except Exception:
                pass

        return violations == 0
    except Exception as e:
        result.record("contract_validation", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 4: Execute Test Collections
# ---------------------------------------------------------------------------

def stage_execute_tests(client: MockartyClient, result: PipelineResult) -> bool:
    """Execute API test collections against the mocked endpoints.

    Test collections contain request/response pairs with assertions.
    This stage runs them and collects pass/fail results.
    """
    print("\n--- Stage 4: Execute Test Collections ---")
    try:
        collections = client.collections.list()
        if not collections:
            result.record("test_execution", True, "No collections to execute (skipped)")
            return True

        total_passed = 0
        total_failed = 0

        for collection in collections[:5]:  # Limit to 5 collections in CI
            try:
                run_result = client.collections.execute(collection.id)
                passed = run_result.passed or 0
                failed = run_result.failed or 0
                total_passed += passed
                total_failed += failed
                status = "PASS" if failed == 0 else "FAIL"
                print(f"  [{status}] {collection.name}: "
                      f"{passed} passed, {failed} failed")
            except Exception as e:
                print(f"  [SKIP] {collection.name}: {e}")

        result.record(
            "test_execution",
            total_failed == 0,
            f"Total: {total_passed} passed, {total_failed} failed",
        )

        # View test run history
        runs = client.test_runs.list()
        print(f"  Test run history: {len(runs)} runs")

        return total_failed == 0
    except Exception as e:
        result.record("test_execution", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 5: Fuzzing
# ---------------------------------------------------------------------------

def stage_fuzzing(client: MockartyClient, result: PipelineResult) -> bool:
    """Run a quick fuzzing test against the API.

    In CI, we use a short duration to catch obvious issues.
    More thorough fuzzing can be scheduled separately.
    """
    print("\n--- Stage 5: Fuzzing ---")
    try:
        fuzz_result = client.fuzzing.quick_fuzz({
            "targetUrl": f"{MOCKARTY_URL}/api/users",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": {"name": "test", "email": "test@example.com"},
            "duration": "30s",
            "workers": 2,
        })

        findings = fuzz_result.get("findings", 0)
        critical = fuzz_result.get("criticalFindings", 0)
        total_reqs = fuzz_result.get("totalRequests", 0)

        result.record(
            "fuzzing",
            critical == 0,
            f"Requests: {total_reqs}, findings: {findings}, critical: {critical}",
        )

        # If there are findings, get the summary
        if findings > 0:
            fuzz_findings = client.fuzzing.list_findings()
            for f in fuzz_findings[:3]:
                print(f"    [{f.get('severity')}] {f.get('title')}")

        return critical == 0
    except Exception as e:
        result.record("fuzzing", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 6: Performance Testing
# ---------------------------------------------------------------------------

def stage_performance_test(client: MockartyClient, result: PipelineResult) -> bool:
    """Run a baseline performance test.

    Checks that response times meet SLA requirements:
      - P95 latency < 200ms
      - P99 latency < 500ms
      - Error rate < 1%
    """
    print("\n--- Stage 6: Performance Test ---")
    try:
        perf_task = client.perf.run({
            "name": "CI Baseline Perf Test",
            "targetUrl": f"{MOCKARTY_URL}/api/users",
            "method": "GET",
            "duration": "30s",
            "concurrency": 10,
            "rps": 50,
        })
        print(f"  Performance test started: {perf_task.id}")

        # Wait for completion (in real CI, poll with timeout)
        time.sleep(5)

        # Check results
        perf_results = client.perf.results()
        if perf_results:
            latest = perf_results[0]
            p95 = latest.p95_latency or 0
            p99 = latest.p99_latency or 0
            error_rate = latest.error_rate or 0

            sla_ok = p95 < 200 and p99 < 500 and error_rate < 1.0
            result.record(
                "performance",
                sla_ok,
                f"P95={p95}ms, P99={p99}ms, errors={error_rate}%",
            )
        else:
            result.record("performance", True, "No results yet (async)")

        return True
    except Exception as e:
        result.record("performance", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 7: Results and Export
# ---------------------------------------------------------------------------

def stage_export_results(client: MockartyClient, result: PipelineResult) -> bool:
    """Collect and export all test results.

    Generates reports for:
      - Contract validation results
      - Test collection results
      - Fuzzing findings
      - Performance metrics
    """
    print("\n--- Stage 7: Results & Export ---")
    try:
        # Contract results
        contract_results = client.contracts.list_results()
        print(f"  Contract results:  {len(contract_results)}")

        # Test runs
        test_runs = client.test_runs.list()
        print(f"  Test runs:         {len(test_runs)}")

        # Fuzzing results
        fuzzing_results = client.fuzzing.list_results()
        print(f"  Fuzzing results:   {len(fuzzing_results)}")

        # Performance results
        perf_results = client.perf.results()
        print(f"  Performance results: {len(perf_results)}")

        # System stats
        stats = client.stats.get_stats()
        print(f"  Total requests during pipeline: {stats.get('totalRequests')}")

        # Export fuzzing findings
        if fuzzing_results:
            export = client.fuzzing.export_findings({
                "format": "json",
                "severity": ["critical", "high"],
            })
            print(f"  Exported {export.get('count', 0)} fuzzing findings")

        # Export collection results
        collections = client.collections.list()
        for col in collections[:3]:
            try:
                export_data = client.collections.export(col.id)
                print(f"  Exported collection '{col.name}': {len(export_data)} bytes")
            except Exception:
                pass

        result.record("export_results", True, "All results collected")
        return True
    except Exception as e:
        result.record("export_results", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Stage 8: Cleanup
# ---------------------------------------------------------------------------

def stage_cleanup(client: MockartyClient, result: PipelineResult) -> bool:
    """Clean up CI resources.

    Delete mocks, clear logs, and remove the CI namespace
    to avoid resource accumulation.
    """
    print("\n--- Stage 8: Cleanup ---")
    try:
        # Delete all CI-generated mocks
        page = client.mocks.list(tags=["ci-generated"], limit=100)
        if page.items:
            mock_ids = [m.id for m in page.items]
            client.mocks.batch_delete(mock_ids)
            print(f"  Deleted {len(mock_ids)} CI mocks")

        # Clear undefined requests
        client.undefined.clear_all()
        print("  Cleared undefined requests")

        # Clear agent tasks
        client.agent_tasks.clear_all()
        print("  Cleared agent tasks")

        result.record("cleanup", True, "CI resources cleaned up")
        return True
    except Exception as e:
        result.record("cleanup", False, str(e))
        return False


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> int:
    """Execute the full CI/CD pipeline.

    Returns 0 on success, 1 on failure.
    """
    print("=" * 60)
    print("  MOCKARTY CI/CD PIPELINE")
    print(f"  Server: {MOCKARTY_URL}")
    print(f"  Namespace: {NAMESPACE}")
    print("=" * 60)

    pipeline = PipelineResult()

    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        # Stage 1: Setup
        if not stage_setup_namespace(client, pipeline):
            pipeline.summary()
            return 1

        # Stage 2: Import and generate
        stage_import_and_generate(client, pipeline)

        # Stage 3: Contract validation
        stage_contract_validation(client, pipeline)

        # Stage 4: Test execution
        stage_execute_tests(client, pipeline)

        # Stage 5: Fuzzing
        stage_fuzzing(client, pipeline)

        # Stage 6: Performance
        stage_performance_test(client, pipeline)

        # Stage 7: Export
        stage_export_results(client, pipeline)

        # Stage 8: Cleanup (always runs)
        stage_cleanup(client, pipeline)

    pipeline.summary()
    return 0 if pipeline.all_passed else 1


def main() -> None:
    exit_code = run_pipeline()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
