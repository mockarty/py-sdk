"""Create a Cloud webhook and persist its one-time signing secret."""

import os

from mockarty import MockartyClient


with MockartyClient(base_url=os.environ["MOCKARTY_CLOUD_URL"], api_key=os.environ["MOCKARTY_CLOUD_TOKEN"]) as client:
    credential = client.cloud_webhooks.create(
        os.environ["MOCKARTY_WORKSPACE_ID"],
        "Build events",
        "https://hooks.example.com/mockarty",
        ["instance.created", "instance.running"],
    )
    # Persist this one-time value in your secret manager; list calls never return it.
    print(credential["webhook"]["id"], credential["secret"])
