"""Namespace settings management examples.

Demonstrates:
  - Managing namespace users and roles
  - Configuring cleanup policies
  - Setting up webhooks for namespace events
  - Team collaboration workflow
"""

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"
NAMESPACE = "sandbox"


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

def manage_namespace_users(client: MockartyClient) -> None:
    """Manage users within a namespace.

    Each namespace can have its own set of users with assigned roles:
      - admin: full access (create, edit, delete mocks, manage users)
      - editor: can create and edit mocks, but not manage users
      - viewer: read-only access to mocks and logs
    """
    # Add users with different roles
    admin_result = client.namespace_settings.add_user(
        NAMESPACE, user_id="user-alice-001", role="admin"
    )
    print(f"Added admin: {admin_result.get('userId')} (role={admin_result.get('role')})")

    editor_result = client.namespace_settings.add_user(
        NAMESPACE, user_id="user-bob-002", role="editor"
    )
    print(f"Added editor: {editor_result.get('userId')} (role={editor_result.get('role')})")

    viewer_result = client.namespace_settings.add_user(
        NAMESPACE, user_id="user-charlie-003", role="viewer"
    )
    print(f"Added viewer: {viewer_result.get('userId')} (role={viewer_result.get('role')})")


def list_namespace_users(client: MockartyClient) -> None:
    """List all users in a namespace."""
    users = client.namespace_settings.list_users(NAMESPACE)
    print(f"Namespace '{NAMESPACE}' users ({len(users)}):")
    for user in users:
        print(f"  - {user.get('userId')}: role={user.get('role')}, "
              f"added={user.get('addedAt')}")


def update_user_role(client: MockartyClient) -> None:
    """Update a user's role in the namespace.

    Common scenarios:
      - Promote a viewer to editor when they join the team
      - Demote an admin when they change teams
      - Grant temporary admin access for maintenance
    """
    result = client.namespace_settings.update_user_role(
        NAMESPACE, user_id="user-bob-002", role="admin"
    )
    print(f"Updated role: {result.get('userId')} -> {result.get('role')}")


def remove_user(client: MockartyClient) -> None:
    """Remove a user from a namespace."""
    client.namespace_settings.remove_user(NAMESPACE, user_id="user-charlie-003")
    print("Removed user: user-charlie-003")


# ---------------------------------------------------------------------------
# Cleanup Policies
# ---------------------------------------------------------------------------

def manage_cleanup_policy(client: MockartyClient) -> None:
    """Configure automatic cleanup policies for a namespace.

    Cleanup policies prevent stale data from accumulating:
      - Mock logs: delete request logs older than N days
      - Unused mocks: flag or delete mocks not hit in N days
      - Fuzzing results: retain only the last N results
      - Undefined requests: auto-clear after N days
    """
    # Get current policy
    current = client.namespace_settings.get_cleanup_policy(NAMESPACE)
    print(f"Current cleanup policy for '{NAMESPACE}':")
    print(f"  Logs retention: {current.get('logsRetentionDays')} days")
    print(f"  Max results:    {current.get('maxFuzzingResults')}")

    # Update the policy
    updated = client.namespace_settings.update_cleanup_policy(NAMESPACE, {
        "logsRetentionDays": 30,
        "unusedMockThresholdDays": 90,
        "maxFuzzingResults": 100,
        "maxPerfResults": 50,
        "undefinedRequestRetentionDays": 7,
        "autoCleanupEnabled": True,
        "cleanupSchedule": "0 3 * * *",  # Daily at 3 AM
    })
    print(f"Updated cleanup policy:")
    print(f"  Logs retention:    {updated.get('logsRetentionDays')} days")
    print(f"  Unused threshold:  {updated.get('unusedMockThresholdDays')} days")
    print(f"  Max fuzzing:       {updated.get('maxFuzzingResults')}")
    print(f"  Auto-cleanup:      {updated.get('autoCleanupEnabled')}")
    print(f"  Schedule:          {updated.get('cleanupSchedule')}")


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

def manage_webhooks(client: MockartyClient) -> None:
    """Configure webhooks for namespace events.

    Webhooks notify external systems when events occur:
      - mock.created: a new mock was created
      - mock.deleted: a mock was deleted
      - test.completed: a test run finished
      - fuzzing.completed: a fuzzing run finished
      - contract.violation: a contract violation was detected
      - undefined.detected: an unmatched request was logged
    """
    # Create a webhook for test completions
    test_webhook = client.namespace_settings.create_webhook(NAMESPACE, {
        "name": "CI/CD Notifications",
        "url": "https://ci.example.com/webhooks/mockarty",
        "events": ["test.completed", "fuzzing.completed", "contract.violation"],
        "headers": {
            "Authorization": "Bearer webhook-secret-token",
            "X-Source": "mockarty",
        },
        "enabled": True,
    })
    test_webhook_id = test_webhook.get("id", "unknown")
    print(f"Created webhook: {test_webhook_id} ({test_webhook.get('name')})")
    print(f"  URL:    {test_webhook.get('url')}")
    print(f"  Events: {test_webhook.get('events')}")

    # Create a webhook for Slack notifications on undefined requests
    slack_webhook = client.namespace_settings.create_webhook(NAMESPACE, {
        "name": "Slack - Missing Mocks",
        "url": "https://hooks.slack.com/services/T00/B00/xxxx",
        "events": ["undefined.detected"],
        "enabled": True,
    })
    slack_webhook_id = slack_webhook.get("id", "unknown")
    print(f"Created webhook: {slack_webhook_id} ({slack_webhook.get('name')})")

    # List all webhooks
    webhooks = client.namespace_settings.list_webhooks(NAMESPACE)
    print(f"\nNamespace webhooks ({len(webhooks)}):")
    for wh in webhooks:
        status = "enabled" if wh.get("enabled") else "disabled"
        print(f"  - {wh.get('id')}: {wh.get('name')} [{status}]")
        print(f"    URL: {wh.get('url')}")
        print(f"    Events: {wh.get('events')}")

    # Delete webhooks
    client.namespace_settings.delete_webhook(NAMESPACE, test_webhook_id)
    client.namespace_settings.delete_webhook(NAMESPACE, slack_webhook_id)
    print(f"\nDeleted webhooks: {test_webhook_id}, {slack_webhook_id}")


# ---------------------------------------------------------------------------
# Team Collaboration Workflow
# ---------------------------------------------------------------------------

def team_setup_workflow(client: MockartyClient) -> None:
    """Set up a namespace for team collaboration.

    Complete setup workflow:
      1. Add team members with appropriate roles
      2. Configure cleanup policies
      3. Set up webhooks for CI/CD integration
    """
    ns = "team-backend"

    # Try to create namespace (may already exist)
    try:
        client.namespaces.create(ns)
        print(f"Created namespace: {ns}")
    except Exception:
        print(f"Namespace '{ns}' already exists")

    # 1. Add team members
    print("\n--- Adding team members ---")
    team = [
        ("lead-dev-001", "admin"),
        ("senior-dev-002", "editor"),
        ("junior-dev-003", "editor"),
        ("qa-engineer-004", "editor"),
        ("product-manager-005", "viewer"),
    ]
    for user_id, role in team:
        try:
            client.namespace_settings.add_user(ns, user_id, role)
            print(f"  Added {user_id} as {role}")
        except Exception as e:
            print(f"  {user_id}: {e}")

    # 2. Configure cleanup
    print("\n--- Configuring cleanup ---")
    client.namespace_settings.update_cleanup_policy(ns, {
        "logsRetentionDays": 14,
        "unusedMockThresholdDays": 60,
        "maxFuzzingResults": 200,
        "autoCleanupEnabled": True,
        "cleanupSchedule": "0 4 * * 0",  # Sundays at 4 AM
    })
    print("  Cleanup policy configured (14-day logs, 60-day unused threshold)")

    # 3. Set up webhook
    print("\n--- Setting up webhook ---")
    wh = client.namespace_settings.create_webhook(ns, {
        "name": "Team Notifications",
        "url": "https://hooks.example.com/team-backend",
        "events": ["test.completed", "contract.violation"],
        "enabled": True,
    })
    print(f"  Webhook created: {wh.get('id')}")

    # Cleanup demo data
    print("\n--- Cleanup ---")
    for user_id, _ in team:
        try:
            client.namespace_settings.remove_user(ns, user_id)
        except Exception:
            pass
    try:
        client.namespace_settings.delete_webhook(ns, wh.get("id"))
    except Exception:
        pass
    print("  Demo data cleaned up")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== User Management ===")
        manage_namespace_users(client)
        print()
        list_namespace_users(client)
        print()
        update_user_role(client)
        print()
        remove_user(client)
        print()

        print("=== Cleanup Policies ===")
        manage_cleanup_policy(client)
        print()

        print("=== Webhooks ===")
        manage_webhooks(client)
        print()

        print("=== Team Setup Workflow ===")
        team_setup_workflow(client)
        print()

        # Final cleanup of demo users
        try:
            client.namespace_settings.remove_user(NAMESPACE, "user-alice-001")
            client.namespace_settings.remove_user(NAMESPACE, "user-bob-002")
        except Exception:
            pass

        print("Namespace settings example complete.")


if __name__ == "__main__":
    main()
