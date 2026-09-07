import os

from mockarty import MockartyClient


namespace = os.environ["MOCKARTY_NAMESPACE"]
descriptor = {
    "namespace": namespace,
    "contractVersion": "mockarty.connection/v1",
    "id": "gitlab-prod",
    "kind": "gitlab",
    "endpoint": "https://gitlab.example.com/api/v4",
    "targetPolicy": {
        "schemes": ["https"],
        "hosts": ["gitlab.example.com"],
        "ports": [443],
        "pathPrefixes": ["/api/v4"],
    },
    "secretRefs": [{"storeId": "team-vault", "key": "gitlab-token", "version": 3}],
    "allowedOperationIds": ["gitlab.pipeline.observe"],
}

with MockartyClient(
    base_url=os.environ["MOCKARTY_BASE_URL"],
    api_key=os.environ["MOCKARTY_API_KEY"],
    namespace=namespace,
) as client:
    snapshot = client.connections.create(descriptor)
    print(f"connection revision {snapshot['descriptor']['revision']}: {snapshot['digest']}")
