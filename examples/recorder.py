"""Traffic recording examples.

Demonstrates:
  - Creating and managing recording sessions
  - Listing sessions and viewing recorded entries
  - Stopping sessions and generating mocks from traffic
  - Recorder configurations: save, list, export, delete
  - CA certificate management for HTTPS recording
  - Entry annotation and replay
  - Traffic modifications
  - Port allocation status
"""

from mockarty import MockartyClient, RecorderSession

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


# ---------------------------------------------------------------------------
# Session Lifecycle
# ---------------------------------------------------------------------------

def create_recording_session(client: MockartyClient) -> str:
    """Start a new traffic recording session.

    The recorder acts as a proxy -- traffic sent through Mockarty
    on the configured target URL is captured as recorded entries.
    """
    session = RecorderSession(
        name="API Traffic Recording",
        target_url="https://api.example.com",
    )
    created = client.recorder.create(session)
    print(f"Created recording session: {created.id}")
    print(f"  Name:       {created.name}")
    print(f"  Target:     {created.target_url}")
    print(f"  Status:     {created.status}")
    return created.id


def list_sessions(client: MockartyClient) -> None:
    """List all recording sessions."""
    sessions = client.recorder.list()
    print(f"Recording sessions ({len(sessions)}):")
    for s in sessions:
        print(f"  - {s.id}: {s.name} (status={s.status}, entries={s.entry_count})")


def get_session_details(client: MockartyClient, session_id: str) -> None:
    """Get details about a specific recording session."""
    session = client.recorder.get(session_id)
    print(f"Session: {session.name}")
    print(f"  ID:          {session.id}")
    print(f"  Target URL:  {session.target_url}")
    print(f"  Status:      {session.status}")
    print(f"  Entries:     {session.entry_count}")
    print(f"  Created:     {session.created_at}")


def stop_recording(client: MockartyClient, session_id: str) -> None:
    """Stop a recording session."""
    session = client.recorder.stop(session_id)
    print(f"Stopped session: {session.id} (status={session.status})")


def view_recorded_entries(client: MockartyClient, session_id: str) -> None:
    """View the requests captured during a recording session."""
    entries = client.recorder.entries(session_id)
    print(f"Recorded entries ({len(entries)}):")
    for entry in entries[:10]:
        print(f"  {entry.method} {entry.path} -> {entry.status_code} ({entry.duration}ms)")


def generate_mocks_from_traffic(client: MockartyClient, session_id: str) -> None:
    """Generate mock definitions from recorded traffic.

    This analyzes the recorded request/response pairs and creates
    corresponding mocks automatically.
    """
    mocks = client.recorder.generate_mocks(session_id)
    print(f"Generated {len(mocks)} mocks from recorded traffic:")
    for mock in mocks[:5]:
        if mock.http:
            print(f"  - {mock.id}: {mock.http.http_method} {mock.http.route}")
        elif mock.grpc:
            print(f"  - {mock.id}: gRPC {mock.grpc.service}/{mock.grpc.method}")
        else:
            print(f"  - {mock.id}")


def delete_session(client: MockartyClient, session_id: str) -> None:
    """Delete a recording session and its entries."""
    client.recorder.delete(session_id)
    print(f"Deleted session: {session_id}")


# ---------------------------------------------------------------------------
# Recorder Configurations
# ---------------------------------------------------------------------------

def manage_recorder_configs(client: MockartyClient) -> None:
    """Save, list, export, and delete recorder configurations.

    Configurations store reusable recording setups including
    target URL, filters, header rules, and body transformations.
    """
    # Save a configuration
    config = client.recorder.save_config({
        "name": "Production API Recorder",
        "targetUrl": "https://api.production.example.com",
        "filters": {
            "includePaths": ["/api/v2/*"],
            "excludePaths": ["/api/v2/health", "/api/v2/metrics"],
            "methods": ["GET", "POST", "PUT"],
        },
        "headerRules": {
            "remove": ["Authorization", "Cookie"],
            "add": {"X-Recorded": "true"},
        },
        "bodyTransformations": {
            "maskFields": ["password", "ssn", "creditCard"],
        },
    })
    config_id = config.get("id", "unknown")
    print(f"Saved recorder config: {config_id} ({config.get('name')})")

    # List all configurations
    configs = client.recorder.list_configs()
    print(f"Recorder configs ({len(configs)}):")
    for cfg in configs:
        print(f"  - {cfg.get('id')}: {cfg.get('name')} (target={cfg.get('targetUrl')})")

    # Export a configuration as a file
    exported = client.recorder.export_config(config_id)
    print(f"Exported config {config_id}: {len(exported)} bytes")

    # Delete the configuration
    client.recorder.delete_config(config_id)
    print(f"Deleted config: {config_id}")


# ---------------------------------------------------------------------------
# CA Certificate Management
# ---------------------------------------------------------------------------

def manage_ca_certificate(client: MockartyClient) -> None:
    """Manage the CA certificate for HTTPS traffic recording.

    To record HTTPS traffic, the recorder needs a CA certificate
    that clients trust. This section shows how to:
      - Check if a CA certificate exists
      - Generate a new CA certificate
      - Download the CA certificate for client installation
    """
    # Check current CA status
    status = client.recorder.get_ca_status()
    print(f"CA certificate status: {status.get('status')}")
    print(f"  Generated:  {status.get('generatedAt')}")
    print(f"  Expires:    {status.get('expiresAt')}")
    print(f"  Installed:  {status.get('installed')}")

    if status.get("status") != "active":
        # Generate a new CA certificate
        result = client.recorder.generate_ca()
        print(f"Generated new CA: {result.get('status')}")

    # Download the CA certificate for installation on clients
    ca_cert = client.recorder.download_ca()
    print(f"Downloaded CA certificate: {len(ca_cert)} bytes")
    # In production, you would save this to a file:
    # with open("mockarty-ca.pem", "wb") as f:
    #     f.write(ca_cert)


# ---------------------------------------------------------------------------
# Entry Annotation and Replay
# ---------------------------------------------------------------------------

def annotate_and_replay_entries(client: MockartyClient, session_id: str) -> None:
    """Annotate recorded entries with metadata and replay them.

    Annotations help categorize entries for later analysis:
      - tag entries by feature area
      - mark entries as important or problematic
      - add notes about expected behavior

    Replay sends the recorded request again to verify the target
    still behaves the same way.
    """
    entries = client.recorder.entries(session_id)
    if not entries:
        print("No entries to annotate or replay.")
        return

    # Annotate the first entry
    entry = entries[0]
    annotated = client.recorder.annotate_entry(
        session_id,
        entry.id,
        {
            "tags": ["critical-path", "authentication"],
            "notes": "Login flow entry point -- verify token format",
            "importance": "high",
        },
    )
    print(f"Annotated entry {entry.id}:")
    print(f"  Tags:  {annotated.get('tags')}")
    print(f"  Notes: {annotated.get('notes')}")

    # Replay the entry to verify behavior
    replay_result = client.recorder.replay_entry(session_id, entry.id)
    print(f"Replay result for entry {entry.id}:")
    print(f"  Status code: {replay_result.get('statusCode')}")
    print(f"  Duration:    {replay_result.get('duration')}ms")
    print(f"  Matches original: {replay_result.get('matchesOriginal')}")


# ---------------------------------------------------------------------------
# Traffic Modifications
# ---------------------------------------------------------------------------

def manage_traffic_modifications(client: MockartyClient, session_id: str) -> None:
    """Configure traffic modifications for a recording session.

    Modifications allow the recorder to transform traffic in-flight:
      - Add or remove headers
      - Rewrite URLs
      - Mask sensitive data in bodies
      - Add artificial latency
    """
    # Get current modifications
    mods = client.recorder.get_modifications(session_id)
    print(f"Current modifications: {mods}")

    # Update modifications
    updated = client.recorder.update_modifications(session_id, {
        "headerRules": {
            "add": {"X-Test-Environment": "staging"},
            "remove": ["Authorization"],
        },
        "bodyRules": {
            "maskFields": ["password", "token"],
            "maskValue": "***REDACTED***",
        },
        "urlRewrite": {
            "from": "/api/v1/",
            "to": "/api/v2/",
        },
        "latencyMs": 100,
    })
    print(f"Updated modifications: {updated}")


# ---------------------------------------------------------------------------
# Port Status
# ---------------------------------------------------------------------------

def check_recorder_ports(client: MockartyClient) -> None:
    """Check recorder port allocation status.

    Each recording session uses a dedicated port for proxying traffic.
    This endpoint shows which ports are in use and available.
    """
    ports = client.recorder.get_ports()
    print(f"Recorder ports:")
    print(f"  Available range: {ports.get('rangeStart')}-{ports.get('rangeEnd')}")
    print(f"  In use:          {ports.get('inUse')}")
    print(f"  Available:       {ports.get('available')}")


# ---------------------------------------------------------------------------
# Full Workflow
# ---------------------------------------------------------------------------

def full_recording_workflow(client: MockartyClient) -> None:
    """Complete recording workflow: record, inspect, annotate, generate, cleanup."""
    # 1. Start recording
    session = RecorderSession(
        name="Full Workflow Demo",
        target_url="https://jsonplaceholder.typicode.com",
    )
    created = client.recorder.create(session)
    session_id = created.id
    print(f"1. Started recording: {session_id}")

    # 2. Send traffic through Mockarty to the target URL
    print("2. Send traffic through Mockarty to record it...")

    # 3. Stop recording
    client.recorder.stop(session_id)
    print("3. Recording stopped")

    # 4. View entries
    entries = client.recorder.entries(session_id)
    print(f"4. Captured {len(entries)} entries")

    # 5. Annotate entries
    if entries:
        client.recorder.annotate_entry(
            session_id,
            entries[0].id,
            {"tags": ["demo"], "notes": "First captured request"},
        )
        print("5. Annotated first entry")

        # 6. Replay entry
        client.recorder.replay_entry(session_id, entries[0].id)
        print("6. Replayed first entry")
    else:
        print("5-6. Skipped (no entries)")

    # 7. Generate mocks
    mocks = client.recorder.generate_mocks(session_id)
    print(f"7. Generated {len(mocks)} mocks")

    # 8. Cleanup
    client.recorder.delete(session_id)
    print("8. Session deleted")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Sessions ===")
        list_sessions(client)
        print()

        print("=== Recorder Configs ===")
        manage_recorder_configs(client)
        print()

        print("=== CA Certificate ===")
        manage_ca_certificate(client)
        print()

        print("=== Port Status ===")
        check_recorder_ports(client)
        print()

        print("=== Full Workflow ===")
        full_recording_workflow(client)
        print()

        print("Recorder example complete.")


if __name__ == "__main__":
    main()
