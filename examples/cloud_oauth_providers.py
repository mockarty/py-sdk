"""Configure a Cloud cabinet OAuth provider without sending a raw secret."""

from mockarty import MockartyClient

with MockartyClient() as client:
    provider = client.cloud_oauth_providers.update(
        "github",
        client_id="your-github-client-id",
        client_secret_ref="env://CLOUD_API_PROVIDER_SECRET_OAUTH_GITHUB",
        expected_revision=0,
        enabled=True,
        idempotency_key="configure-github-1",
    )
    print(provider["provider"], provider["config_revision"], provider["secret_configured"])
