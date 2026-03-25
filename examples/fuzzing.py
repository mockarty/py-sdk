"""Fuzzing operations examples.

Demonstrates:
  - Creating and managing fuzzing configurations
  - Starting, monitoring, and stopping fuzzing runs
  - Quick fuzz for ad-hoc testing
  - Viewing and managing fuzzing results
  - Findings: listing, triaging, analyzing with AI, replaying
  - Batch operations on findings
  - Exporting findings for reporting
  - Importing targets from cURL, OpenAPI, collections, recorder, mocks
  - Scheduling recurring fuzzing runs
  - Fuzzing summary dashboard
"""

from mockarty import FuzzingConfig, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


# ---------------------------------------------------------------------------
# Configuration Management
# ---------------------------------------------------------------------------

def create_fuzzing_config(client: MockartyClient) -> str:
    """Create a fuzzing configuration targeting an API.

    Fuzzing configs define:
      - target_url: the API endpoint to fuzz
      - spec_url or spec: OpenAPI spec for understanding valid inputs
      - duration: how long to run (e.g., "5m", "1h")
      - workers: number of concurrent workers
    """
    config = FuzzingConfig(
        name="User API Fuzzing",
        target_url="http://localhost:5770/api/users",
        spec_url="http://localhost:5770/swagger/doc.json",
        duration="5m",
        workers=4,
    )
    created = client.fuzzing.create_config(config)
    print(f"Created fuzzing config: {created.id} ({created.name})")
    return created.id


def create_config_from_spec_string(client: MockartyClient) -> str:
    """Create a fuzzing config with an inline OpenAPI spec."""
    config = FuzzingConfig(
        name="Inline Spec Fuzzing",
        target_url="http://localhost:5770/api/products",
        spec="""{
            "openapi": "3.0.0",
            "info": {"title": "Products", "version": "1.0"},
            "paths": {
                "/api/products": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "price": {"type": "number"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }""",
        duration="2m",
        workers=2,
    )
    created = client.fuzzing.create_config(config)
    print(f"Created inline fuzzing config: {created.id}")
    return created.id


def list_fuzzing_configs(client: MockartyClient) -> None:
    """List all saved fuzzing configurations."""
    configs = client.fuzzing.list_configs()
    print(f"Found {len(configs)} fuzzing configs:")
    for cfg in configs:
        print(f"  - {cfg.id}: {cfg.name} (target={cfg.target_url})")


# ---------------------------------------------------------------------------
# Run Management
# ---------------------------------------------------------------------------

def start_and_manage_run(client: MockartyClient, config_id: str) -> None:
    """Start a fuzzing run and demonstrate lifecycle management."""
    config = client.fuzzing.get_config(config_id)
    print(f"Starting fuzzing: {config.name}")

    run = client.fuzzing.start(config)
    print(f"Fuzzing run started: {run.id} (status={run.status})")

    # In a real scenario you would poll or wait for completion.
    # For demonstration, we stop it immediately.
    print(f"Stopping run: {run.id}")
    client.fuzzing.stop(run.id)
    print("Run stopped.")


def quick_fuzz_endpoint(client: MockartyClient) -> None:
    """Run a quick ad-hoc fuzz test without creating a saved config.

    Quick fuzz is ideal for one-off security checks or smoke testing
    a specific endpoint before going deeper.
    """
    result = client.fuzzing.quick_fuzz({
        "targetUrl": "http://localhost:5770/api/products",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": {"name": "Test Product", "price": 19.99},
        "duration": "30s",
        "workers": 2,
    })
    print(f"Quick fuzz result: {result.get('status')}")
    print(f"  Requests sent: {result.get('totalRequests')}")
    print(f"  Findings:      {result.get('findings')}")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def view_fuzzing_results(client: MockartyClient) -> None:
    """View results from completed fuzzing runs."""
    results = client.fuzzing.list_results()
    print(f"Found {len(results)} fuzzing results:")
    for result in results[:5]:
        print(f"  - {result.id}:")
        print(f"    Status:          {result.status}")
        print(f"    Total requests:  {result.total_requests}")
        print(f"    Findings:        {result.findings}")


def view_result_details(client: MockartyClient, result_id: str) -> None:
    """Get detailed results for a specific fuzzing run."""
    result = client.fuzzing.get_result(result_id)
    print(f"Fuzzing result: {result.id}")
    print(f"  Status:         {result.status}")
    print(f"  Total requests: {result.total_requests}")
    print(f"  Findings:       {result.findings}")
    print(f"  Started:        {result.started_at}")
    print(f"  Finished:       {result.finished_at}")


def view_fuzzing_summary(client: MockartyClient) -> None:
    """Get a high-level summary of all fuzzing activity.

    The summary includes total runs, findings by severity,
    top vulnerable endpoints, and trend data.
    """
    summary = client.fuzzing.get_summary()
    print("Fuzzing summary:")
    print(f"  Total runs:     {summary.get('totalRuns')}")
    print(f"  Total findings: {summary.get('totalFindings')}")
    print(f"  Critical:       {summary.get('criticalFindings')}")
    print(f"  High:           {summary.get('highFindings')}")


# ---------------------------------------------------------------------------
# Findings Management
# ---------------------------------------------------------------------------

def list_and_inspect_findings(client: MockartyClient) -> None:
    """List all fuzzing findings and inspect details.

    Findings are individual issues discovered during fuzzing --
    unexpected status codes, crashes, timeouts, etc.
    """
    findings = client.fuzzing.list_findings()
    print(f"Fuzzing findings ({len(findings)}):")
    for f in findings[:10]:
        print(f"  - {f.get('id')}: [{f.get('severity')}] {f.get('title')}")
        print(f"    Endpoint: {f.get('method')} {f.get('path')}")
        print(f"    Status:   {f.get('status')}")

    # Get details for a specific finding
    if findings:
        detail = client.fuzzing.get_finding(findings[0]["id"])
        print(f"\nFinding detail: {detail.get('id')}")
        print(f"  Title:    {detail.get('title')}")
        print(f"  Severity: {detail.get('severity')}")
        print(f"  Request:  {detail.get('request')}")
        print(f"  Response: {detail.get('response')}")


def triage_findings(client: MockartyClient) -> None:
    """Triage fuzzing findings by setting status and adding notes.

    Triage statuses typically include:
      - new: freshly discovered (default)
      - confirmed: verified as a real issue
      - false_positive: not a real issue
      - fixed: resolved in code
      - ignored: acknowledged but not actionable
    """
    findings = client.fuzzing.list_findings()
    if not findings:
        print("No findings to triage.")
        return

    # Triage individual finding
    finding_id = findings[0]["id"]
    triaged = client.fuzzing.triage_finding(
        finding_id,
        status="confirmed",
        notes="Validated: the endpoint does not handle null values in 'name' field.",
    )
    print(f"Triaged finding {finding_id}: status={triaged.get('status')}")

    # Mark another as false positive
    if len(findings) > 1:
        fp_id = findings[1]["id"]
        client.fuzzing.triage_finding(
            fp_id,
            status="false_positive",
            notes="Expected 400 response for malformed input -- working as designed.",
        )
        print(f"Marked {fp_id} as false_positive")


def analyze_findings_with_ai(client: MockartyClient) -> None:
    """Use AI to analyze fuzzing findings for root cause and remediation.

    AI analysis examines the request/response pair, identifies the
    likely vulnerability type, and suggests fixes.
    """
    findings = client.fuzzing.list_findings()
    if not findings:
        print("No findings to analyze.")
        return

    # Analyze a single finding
    finding_id = findings[0]["id"]
    analysis = client.fuzzing.analyze_finding(finding_id)
    print(f"AI analysis for {finding_id}:")
    print(f"  Category:   {analysis.get('category')}")
    print(f"  Root cause: {analysis.get('rootCause')}")
    print(f"  Suggestion: {analysis.get('suggestion')}")
    print(f"  Severity:   {analysis.get('severity')}")

    # Batch analyze multiple findings at once
    if len(findings) >= 3:
        ids = [f["id"] for f in findings[:3]]
        batch_result = client.fuzzing.batch_analyze(ids)
        print(f"\nBatch analysis of {len(ids)} findings:")
        for item in batch_result.get("results", []):
            print(f"  - {item.get('findingId')}: {item.get('category')}")


def replay_finding(client: MockartyClient) -> None:
    """Replay a fuzzing finding to verify it is still reproducible.

    After fixing a bug, replay the original request to confirm
    the issue is resolved.
    """
    findings = client.fuzzing.list_findings()
    if not findings:
        print("No findings to replay.")
        return

    finding_id = findings[0]["id"]
    result = client.fuzzing.replay_finding(finding_id)
    print(f"Replay result for {finding_id}:")
    print(f"  Status code: {result.get('statusCode')}")
    print(f"  Still fails: {result.get('stillFails')}")
    print(f"  Response:    {result.get('response')}")


def batch_triage_findings(client: MockartyClient) -> None:
    """Batch triage multiple findings at once.

    Useful for bulk-dismissing false positives or confirming
    a set of related findings.
    """
    findings = client.fuzzing.list_findings()
    if len(findings) < 2:
        print("Need at least 2 findings for batch triage.")
        return

    ids = [f["id"] for f in findings[:3]]
    result = client.fuzzing.batch_triage(ids, status="confirmed")
    print(f"Batch triaged {len(ids)} findings as 'confirmed'")
    print(f"  Updated: {result.get('updated')}")


def export_findings_report(client: MockartyClient) -> None:
    """Export fuzzing findings for external reporting or compliance.

    Exports can be filtered by severity, status, or date range.
    """
    result = client.fuzzing.export_findings({
        "format": "json",
        "severity": ["critical", "high"],
        "status": ["confirmed", "new"],
    })
    print(f"Exported findings: {result.get('count')} items")
    print(f"  Format:   {result.get('format')}")
    print(f"  Download: {result.get('downloadUrl')}")


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

def import_targets(client: MockartyClient) -> None:
    """Import fuzzing targets from various sources.

    Targets can be imported from:
      - cURL commands (paste from browser DevTools)
      - OpenAPI specifications
      - API Tester collections
      - Recorder sessions
      - Existing mocks
    """
    # Import from a cURL command
    curl_result = client.fuzzing.import_from_curl({
        "curl": "curl -X POST http://localhost:5770/api/orders "
                "-H 'Content-Type: application/json' "
                "-d '{\"item\": \"widget\", \"quantity\": 5}'",
    })
    print(f"Imported from cURL: {curl_result.get('configId')}")

    # Import from an OpenAPI spec
    openapi_result = client.fuzzing.import_from_openapi({
        "specUrl": "http://localhost:5770/swagger/doc.json",
        "paths": ["/api/users", "/api/products"],
    })
    print(f"Imported from OpenAPI: {openapi_result.get('count')} endpoints")

    # Import from a recorder session
    recorder_result = client.fuzzing.import_from_recorder({
        "sessionId": "rec-session-123",
    })
    print(f"Imported from recorder: {recorder_result.get('count')} endpoints")

    # Import from existing mocks
    mock_result = client.fuzzing.import_from_mock({
        "mockIds": ["user-get-by-id", "order-create"],
    })
    print(f"Imported from mocks: {mock_result.get('count')} endpoints")

    # Import from a collection
    collection_result = client.fuzzing.import_from_collection({
        "collectionId": "col-api-tests",
    })
    print(f"Imported from collection: {collection_result.get('count')} endpoints")


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

def manage_fuzzing_schedules(client: MockartyClient) -> None:
    """Create and manage recurring fuzzing schedules.

    Schedules allow fuzzing to run automatically on a cron-like basis,
    catching regressions early in the development cycle.
    """
    # Create a schedule for nightly fuzzing
    schedule = client.fuzzing.create_schedule({
        "name": "Nightly API Fuzz",
        "configId": "fuzz-config-users",
        "cron": "0 2 * * *",  # Every day at 2 AM
        "enabled": True,
        "notifyOnFindings": True,
    })
    schedule_id = schedule.get("id", "unknown")
    print(f"Created schedule: {schedule_id} ({schedule.get('name')})")

    # List all schedules
    schedules = client.fuzzing.list_schedules()
    print(f"Fuzzing schedules ({len(schedules)}):")
    for s in schedules:
        status = "enabled" if s.get("enabled") else "disabled"
        print(f"  - {s.get('id')}: {s.get('name')} [{status}] cron={s.get('cron')}")

    # Update a schedule (e.g., change to weekly)
    updated = client.fuzzing.update_schedule(schedule_id, {
        "name": "Weekly API Fuzz",
        "cron": "0 2 * * 1",  # Every Monday at 2 AM
        "enabled": True,
    })
    print(f"Updated schedule: {updated.get('name')} cron={updated.get('cron')}")

    # Delete the schedule
    client.fuzzing.delete_schedule(schedule_id)
    print(f"Deleted schedule: {schedule_id}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_configs(client: MockartyClient, config_ids: list[str]) -> None:
    """Delete fuzzing configurations."""
    for config_id in config_ids:
        try:
            client.fuzzing.delete_config(config_id)
            print(f"Deleted config: {config_id}")
        except Exception as e:
            print(f"Failed to delete {config_id}: {e}")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Configuration Management ===")
        config_id_1 = create_fuzzing_config(client)
        config_id_2 = create_config_from_spec_string(client)
        list_fuzzing_configs(client)
        print()

        print("=== Quick Fuzz ===")
        quick_fuzz_endpoint(client)
        print()

        print("=== Results ===")
        view_fuzzing_results(client)
        view_fuzzing_summary(client)
        print()

        print("=== Findings ===")
        list_and_inspect_findings(client)
        print()
        triage_findings(client)
        print()
        analyze_findings_with_ai(client)
        print()
        replay_finding(client)
        print()
        batch_triage_findings(client)
        print()
        export_findings_report(client)
        print()

        print("=== Imports ===")
        import_targets(client)
        print()

        print("=== Schedules ===")
        manage_fuzzing_schedules(client)
        print()

        # Start a run (uncomment to actually run)
        # start_and_manage_run(client, config_id_1)

        # Cleanup
        cleanup_configs(client, [config_id_1, config_id_2])
        print("\nFuzzing example complete.")


if __name__ == "__main__":
    main()
