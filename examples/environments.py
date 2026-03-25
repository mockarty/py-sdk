"""API Tester environment management examples.

Demonstrates:
  - Creating environments with variables
  - Listing and inspecting environments
  - Updating environment variables
  - Activating environments for test execution
  - Switching between environments (dev, staging, production)
  - Deleting environments
"""

from mockarty import MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"


def create_development_environment(client: MockartyClient) -> str:
    """Create a development environment with common variables.

    Environments store variables used in API Tester collections.
    Variables can reference base URLs, auth tokens, database
    names, and other configuration values.
    """
    env = client.environments.create({
        "name": "Development",
        "description": "Local development environment",
        "variables": {
            "baseUrl": "http://localhost:5770",
            "apiVersion": "v2",
            "authToken": "dev-token-abc123",
            "dbName": "mockarty_dev",
            "logLevel": "debug",
            "timeout": "30s",
        },
    })
    env_id = env.get("id", "unknown")
    print(f"Created environment: {env_id} ({env.get('name')})")
    print(f"  Variables: {list(env.get('variables', {}).keys())}")
    return env_id


def create_staging_environment(client: MockartyClient) -> str:
    """Create a staging environment that mirrors production settings."""
    env = client.environments.create({
        "name": "Staging",
        "description": "Pre-production staging environment",
        "variables": {
            "baseUrl": "https://staging.api.example.com",
            "apiVersion": "v2",
            "authToken": "staging-token-xyz789",
            "dbName": "mockarty_staging",
            "logLevel": "info",
            "timeout": "10s",
        },
    })
    env_id = env.get("id", "unknown")
    print(f"Created environment: {env_id} ({env.get('name')})")
    return env_id


def create_production_environment(client: MockartyClient) -> str:
    """Create a production environment with restricted settings."""
    env = client.environments.create({
        "name": "Production",
        "description": "Production environment -- use with caution",
        "variables": {
            "baseUrl": "https://api.example.com",
            "apiVersion": "v2",
            "authToken": "prod-token-REDACTED",
            "dbName": "mockarty_prod",
            "logLevel": "warn",
            "timeout": "5s",
            "rateLimitRps": "100",
        },
    })
    env_id = env.get("id", "unknown")
    print(f"Created environment: {env_id} ({env.get('name')})")
    return env_id


def list_environments(client: MockartyClient) -> None:
    """List all available environments."""
    envs = client.environments.list()
    print(f"Environments ({len(envs)}):")
    for env in envs:
        active = " [ACTIVE]" if env.get("active") else ""
        print(f"  - {env.get('id')}: {env.get('name')}{active}")
        if env.get("description"):
            print(f"    {env['description']}")


def get_environment_details(client: MockartyClient, env_id: str) -> None:
    """Get detailed information about an environment."""
    env = client.environments.get(env_id)
    print(f"Environment: {env.get('name')}")
    print(f"  ID:          {env.get('id')}")
    print(f"  Description: {env.get('description')}")
    print(f"  Active:      {env.get('active')}")
    print(f"  Variables:")
    for key, value in env.get("variables", {}).items():
        print(f"    {key}: {value}")


def get_active_environment(client: MockartyClient) -> None:
    """Get the currently active environment."""
    env = client.environments.get_active()
    print(f"Active environment: {env.get('name')} ({env.get('id')})")
    print(f"  Base URL: {env.get('variables', {}).get('baseUrl')}")


def update_environment(client: MockartyClient, env_id: str) -> None:
    """Update environment variables.

    Common use cases:
      - Rotating auth tokens
      - Changing API versions
      - Adjusting timeouts or rate limits
    """
    updated = client.environments.update(env_id, {
        "name": "Development (Updated)",
        "variables": {
            "baseUrl": "http://localhost:5770",
            "apiVersion": "v3",
            "authToken": "dev-token-refreshed-456",
            "dbName": "mockarty_dev",
            "logLevel": "debug",
            "timeout": "60s",
            "newFeatureFlag": "enabled",
        },
    })
    print(f"Updated environment: {updated.get('name')}")
    print(f"  API version: {updated.get('variables', {}).get('apiVersion')}")
    print(f"  New flag:    {updated.get('variables', {}).get('newFeatureFlag')}")


def activate_environment(client: MockartyClient, env_id: str) -> None:
    """Activate an environment for API Tester execution.

    When an environment is active, all API Tester requests use its
    variables for template interpolation (e.g., {{baseUrl}}/api/users).
    Only one environment can be active at a time.
    """
    client.environments.activate(env_id)
    print(f"Activated environment: {env_id}")

    # Verify it is now active
    active = client.environments.get_active()
    print(f"  Confirmed active: {active.get('name')}")


def switch_environments_workflow(client: MockartyClient) -> None:
    """Demonstrate switching between environments for different test scenarios.

    A typical workflow:
      1. Run tests against development
      2. Switch to staging and run the same tests
      3. Compare results
    """
    dev_env = client.environments.create({
        "name": "Switch Demo - Dev",
        "variables": {"baseUrl": "http://localhost:5770", "env": "dev"},
    })
    staging_env = client.environments.create({
        "name": "Switch Demo - Staging",
        "variables": {"baseUrl": "https://staging.api.example.com", "env": "staging"},
    })

    dev_id = dev_env.get("id")
    staging_id = staging_env.get("id")

    # Activate dev and run tests
    client.environments.activate(dev_id)
    active = client.environments.get_active()
    print(f"Running tests against: {active.get('name')} ({active.get('variables', {}).get('baseUrl')})")

    # Switch to staging and run same tests
    client.environments.activate(staging_id)
    active = client.environments.get_active()
    print(f"Switched to: {active.get('name')} ({active.get('variables', {}).get('baseUrl')})")

    # Cleanup
    client.environments.delete(dev_id)
    client.environments.delete(staging_id)
    print("Switch demo environments cleaned up")


def cleanup_environments(
    client: MockartyClient, env_ids: list[str]
) -> None:
    """Delete environments by IDs."""
    for env_id in env_ids:
        try:
            client.environments.delete(env_id)
            print(f"Deleted environment: {env_id}")
        except Exception as e:
            print(f"Failed to delete {env_id}: {e}")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Create Environments ===")
        dev_id = create_development_environment(client)
        staging_id = create_staging_environment(client)
        prod_id = create_production_environment(client)
        print()

        print("=== List Environments ===")
        list_environments(client)
        print()

        print("=== Get Details ===")
        get_environment_details(client, dev_id)
        print()

        print("=== Update Environment ===")
        update_environment(client, dev_id)
        print()

        print("=== Activate Environment ===")
        activate_environment(client, staging_id)
        print()
        get_active_environment(client)
        print()

        print("=== Switch Environments ===")
        switch_environments_workflow(client)
        print()

        print("=== Cleanup ===")
        cleanup_environments(client, [dev_id, staging_id, prod_id])
        print()

        print("Environments example complete.")


if __name__ == "__main__":
    main()
