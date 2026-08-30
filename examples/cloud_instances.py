"""Create a Managed contour without printing its one-time credential."""

import os

from mockarty import MockartyClient


with MockartyClient(base_url=os.environ["MOCKARTY_CLOUD_URL"], api_key=os.environ["MOCKARTY_CLOUD_TOKEN"]) as client:
    result = client.cloud_instances.create(os.environ["MOCKARTY_CLOUD_SPACE_ID"], "Managed beta", "example-create-1")
    bootstrap = result.get("bootstrap", {})
    # Persist bootstrap["password"] in a secret manager; never log it.
    print(result["instance"]["id"], "bootstrap available:", bootstrap.get("available", False))
