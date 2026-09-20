"""Create a Cloud webhook and persist its one-time signing secret."""

import os

from mockarty import MockartyClient


with MockartyClient(base_url=os.environ["MOCKARTY_CLOUD_URL"], api_key=os.environ["MOCKARTY_CLOUD_TOKEN"]) as client:
    # Generate and save this UUID before the first attempt; reuse it after a
    # timeout or process restart. It can replay the one-time secret for an
    # authorized caller, so keep it private.
    request_id = os.environ["MOCKARTY_WEBHOOK_REQUEST_ID"]
    credential = client.cloud_webhooks.create(
        os.environ["MOCKARTY_WORKSPACE_ID"],
        "Build events",
        "https://hooks.example.com/mockarty",
        ["instance.created", "instance.running"],
        idempotency_key=request_id,
    )
    # Persist this one-time value in your secret manager; list calls never return it.
    print(credential["webhook"]["id"], credential["secret"])
