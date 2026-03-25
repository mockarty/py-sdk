"""Contract testing examples.

Demonstrates:
  - Validating mocks against an OpenAPI spec
  - Verifying a provider against a contract
  - Checking spec compatibility
  - Validating payloads
  - Managing contract configs and results
  - Publishing and verifying pact contracts
  - Can-I-Deploy checks for deployment safety
  - Generating mocks from pact contracts
  - Detecting API drift
"""

from mockarty import ContractValidationRequest, MockartyClient

MOCKARTY_URL = "http://localhost:5770"
API_KEY = "your-api-key"

PETSTORE_SPEC_URL = "https://petstore3.swagger.io/api/v3/openapi.json"

INLINE_SPEC = """{
  "openapi": "3.0.0",
  "info": { "title": "Users API", "version": "1.0.0" },
  "paths": {
    "/api/users/{id}": {
      "get": {
        "parameters": [
          { "name": "id", "in": "path", "required": true, "schema": { "type": "string" } }
        ],
        "responses": {
          "200": {
            "description": "User found",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "required": ["id", "name", "email"],
                  "properties": {
                    "id": { "type": "string" },
                    "name": { "type": "string" },
                    "email": { "type": "string", "format": "email" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}"""


# ---------------------------------------------------------------------------
# Spec-based Validation
# ---------------------------------------------------------------------------

def validate_mocks_against_spec(client: MockartyClient) -> None:
    """Check if existing mocks conform to an API specification.

    This finds mocks whose routes match the spec paths and validates
    that their response payloads match the expected schema.
    """
    request = ContractValidationRequest(
        spec=INLINE_SPEC,
        namespace="sandbox",
    )
    result = client.contracts.validate_mocks(request)
    print(f"Mock validation: status={result.status}, violations={result.violations}")
    if result.details:
        for violation in result.details:
            print(f"  [{violation.severity}] {violation.path}: {violation.message}")


def validate_specific_mocks(client: MockartyClient) -> None:
    """Validate only specific mock IDs against a spec."""
    request = ContractValidationRequest(
        spec_url=PETSTORE_SPEC_URL,
        mock_ids=["user-get-by-id", "order-create-premium"],
    )
    result = client.contracts.validate_mocks(request)
    print(f"Targeted validation: status={result.status}")
    print(f"  Violations: {result.violations}")


def verify_provider(client: MockartyClient) -> None:
    """Verify a live provider against a contract spec.

    Sends real requests to the target_url and checks responses
    match the expected contract.
    """
    result = client.contracts.verify_provider({
        "specUrl": PETSTORE_SPEC_URL,
        "targetUrl": "http://localhost:5770",
    })
    print(f"Provider verification: status={result.status}")
    print(f"  Violations: {result.violations}")


def check_compatibility(client: MockartyClient) -> None:
    """Check backward compatibility between two spec versions."""
    result = client.contracts.check_compatibility({
        "spec": INLINE_SPEC,
        "specUrl": PETSTORE_SPEC_URL,
    })
    print(f"Compatibility check: status={result.status}")
    print(f"  Violations: {result.violations}")


def validate_payload(client: MockartyClient) -> None:
    """Validate a specific payload against a specification."""
    result = client.contracts.validate_payload({
        "spec": INLINE_SPEC,
        "payload": {
            "id": "usr-42",
            "name": "Alice",
            "email": "alice@example.com",
        },
    })
    print(f"Payload validation: status={result.status}")
    print(f"  Violations: {result.violations}")


# ---------------------------------------------------------------------------
# Config and Result Management
# ---------------------------------------------------------------------------

def manage_contract_configs(client: MockartyClient) -> None:
    """Create, list, and delete contract testing configurations."""
    # Create a config
    config = client.contracts.save_config({
        "name": "Users API Contract",
        "spec": INLINE_SPEC,
        "targetUrl": "http://localhost:5770",
        "schedule": "0 */6 * * *",  # Every 6 hours
    })
    print(f"Created contract config: {config.id} ({config.name})")

    # List configs
    configs = client.contracts.list_configs()
    print(f"Contract configs: {len(configs)}")
    for cfg in configs:
        print(f"  - {cfg.id}: {cfg.name}")

    # Delete the config
    if config.id:
        client.contracts.delete_config(config.id)
        print(f"Deleted config: {config.id}")


def view_contract_results(client: MockartyClient) -> None:
    """View historical contract testing results."""
    results = client.contracts.list_results()
    print(f"Contract results: {len(results)}")
    for result in results[:5]:
        print(f"  - {result.id}: status={result.status}, violations={result.violations}")


# ---------------------------------------------------------------------------
# Pact Contract Testing
# ---------------------------------------------------------------------------

def publish_and_verify_pact(client: MockartyClient) -> None:
    """Publish a pact contract and verify the provider against it.

    Pact contracts define consumer-driven expectations:
      - consumer: the service consuming the API
      - provider: the service providing the API
      - interactions: expected request/response pairs

    This is the core consumer-driven contract testing workflow.
    """
    # Publish a pact contract from the consumer side
    pact = client.contracts.publish_pact({
        "consumer": "order-service",
        "provider": "user-service",
        "version": "2.1.0",
        "interactions": [
            {
                "description": "a request for user by ID",
                "request": {
                    "method": "GET",
                    "path": "/api/users/usr-42",
                    "headers": {"Accept": "application/json"},
                },
                "response": {
                    "status": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "id": "usr-42",
                        "name": "Alice",
                        "email": "alice@example.com",
                    },
                },
            },
            {
                "description": "a request for a non-existent user",
                "request": {
                    "method": "GET",
                    "path": "/api/users/usr-999",
                },
                "response": {
                    "status": 404,
                    "body": {"error": "user not found"},
                },
            },
        ],
    })
    pact_id = pact.get("id", "unknown")
    print(f"Published pact contract: {pact_id}")
    print(f"  Consumer: {pact.get('consumer')}")
    print(f"  Provider: {pact.get('provider')}")

    # Verify the provider fulfills the pact
    verification = client.contracts.verify_pact({
        "pactId": pact_id,
        "providerBaseUrl": "http://localhost:5770",
        "providerVersion": "3.0.1",
    })
    print(f"Pact verification result: {verification.get('status')}")
    if verification.get("failures"):
        for failure in verification["failures"]:
            print(f"  FAIL: {failure.get('description')}: {failure.get('message')}")
    else:
        print("  All interactions verified successfully")

    return pact_id


def can_i_deploy_check(client: MockartyClient) -> None:
    """Check whether a service version can be safely deployed.

    Can-I-Deploy queries the verification matrix to determine if
    all consumer/provider pairs are compatible at their specified versions.
    This is typically called in a CI/CD pipeline before deployment.
    """
    result = client.contracts.can_i_deploy({
        "service": "order-service",
        "version": "2.1.0",
        "environment": "production",
    })
    deployable = result.get("deployable", False)
    print(f"Can I deploy? {'YES' if deployable else 'NO'}")
    if result.get("reason"):
        print(f"  Reason: {result['reason']}")
    if result.get("verifications"):
        for v in result["verifications"]:
            print(f"  - {v.get('consumer')} <-> {v.get('provider')}: {v.get('status')}")


def generate_mocks_from_pact(client: MockartyClient, pact_id: str) -> None:
    """Generate mock definitions from a published pact contract.

    This creates HTTP mocks that match the pact interactions,
    allowing the consumer to test against mocks while the
    provider is being developed.
    """
    mocks = client.contracts.generate_mocks_from_pact(pact_id)
    print(f"Generated {len(mocks)} mocks from pact '{pact_id}':")
    for mock in mocks:
        if mock.http:
            print(f"  - {mock.id}: {mock.http.http_method} {mock.http.route}")
        else:
            print(f"  - {mock.id}")


def list_pacts_and_verifications(client: MockartyClient) -> None:
    """List all published pacts and their verification history."""
    pacts = client.contracts.list_pacts()
    print(f"Published pacts ({len(pacts)}):")
    for p in pacts:
        print(f"  - {p.get('id')}: {p.get('consumer')} -> {p.get('provider')} "
              f"v{p.get('version')}")

    verifications = client.contracts.list_verifications()
    print(f"Verification history ({len(verifications)}):")
    for v in verifications[:5]:
        print(f"  - {v.get('id')}: provider={v.get('provider')} "
              f"status={v.get('status')}")


# ---------------------------------------------------------------------------
# API Drift Detection
# ---------------------------------------------------------------------------

def detect_api_drift(client: MockartyClient) -> None:
    """Detect drift between an API spec and the actual implementation.

    Drift detection compares the spec definition with live responses
    to find undocumented fields, missing endpoints, or schema mismatches.
    """
    result = client.contracts.detect_drift({
        "specUrl": PETSTORE_SPEC_URL,
        "targetUrl": "http://localhost:5770",
        "sampleSize": 10,
    })
    drift_found = result.get("driftDetected", False)
    print(f"API drift detected: {drift_found}")
    if result.get("differences"):
        for diff in result["differences"]:
            print(f"  [{diff.get('type')}] {diff.get('path')}: {diff.get('message')}")


# ---------------------------------------------------------------------------
# Full Pact Workflow
# ---------------------------------------------------------------------------

def full_pact_workflow(client: MockartyClient) -> None:
    """Complete pact contract testing workflow.

    1. Consumer publishes a pact contract
    2. Provider verifies it fulfills the contract
    3. Check if it is safe to deploy
    4. Generate mocks for consumer testing
    5. Clean up
    """
    print("--- Step 1: Publish pact ---")
    pact = client.contracts.publish_pact({
        "consumer": "checkout-service",
        "provider": "inventory-service",
        "version": "1.0.0",
        "interactions": [
            {
                "description": "check product stock",
                "request": {
                    "method": "GET",
                    "path": "/api/inventory/prod-100",
                },
                "response": {
                    "status": 200,
                    "body": {
                        "productId": "prod-100",
                        "inStock": True,
                        "quantity": 42,
                    },
                },
            },
        ],
    })
    pact_id = pact.get("id", "unknown")
    print(f"  Pact published: {pact_id}")

    print("\n--- Step 2: Verify provider ---")
    verification = client.contracts.verify_pact({
        "pactId": pact_id,
        "providerBaseUrl": "http://localhost:5770",
        "providerVersion": "2.0.0",
    })
    print(f"  Verification: {verification.get('status')}")

    print("\n--- Step 3: Can I deploy? ---")
    deploy = client.contracts.can_i_deploy({
        "service": "checkout-service",
        "version": "1.0.0",
        "environment": "staging",
    })
    print(f"  Deployable: {deploy.get('deployable')}")

    print("\n--- Step 4: Generate mocks ---")
    mocks = client.contracts.generate_mocks_from_pact(pact_id)
    print(f"  Generated {len(mocks)} mocks")

    print("\n--- Step 5: Cleanup ---")
    client.contracts.delete_pact(pact_id)
    print(f"  Pact {pact_id} deleted")


def main() -> None:
    with MockartyClient(base_url=MOCKARTY_URL, api_key=API_KEY) as client:
        print("=== Spec-based Validation ===")
        validate_mocks_against_spec(client)
        print()
        validate_payload(client)
        print()

        print("=== Config Management ===")
        manage_contract_configs(client)
        print()

        print("=== Contract Results ===")
        view_contract_results(client)
        print()

        print("=== Pact Contracts ===")
        pact_id = publish_and_verify_pact(client)
        print()
        can_i_deploy_check(client)
        print()

        if pact_id:
            generate_mocks_from_pact(client, pact_id)
            print()

        list_pacts_and_verifications(client)
        print()

        print("=== API Drift Detection ===")
        detect_api_drift(client)
        print()

        print("=== Full Pact Workflow ===")
        full_pact_workflow(client)
        print()

        # Cleanup remaining pacts
        if pact_id:
            try:
                client.contracts.delete_pact(pact_id)
            except Exception:
                pass

        # Uncomment for live provider verification:
        # verify_provider(client)
        # check_compatibility(client)
        # validate_specific_mocks(client)

        print("Contract testing example complete.")


if __name__ == "__main__":
    main()
