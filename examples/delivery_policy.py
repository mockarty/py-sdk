# Copyright (c) 2026 Mockarty. All rights reserved.

import os

from mockarty import MockartyClient


with MockartyClient(base_url=os.getenv("MOCKARTY_BASE_URL"), api_key=os.getenv("MOCKARTY_API_KEY")) as client:
    environment = client.delivery_policy.create(
        {
            "id": "staging",
            "projectId": "payments",
            "class": "staging",
            "profile": "standard",
            "auditId": "change-123",
            "evidenceId": "review-123",
        },
        idempotency_key="payments-staging-v1",
    )
    print(environment["id"], environment["revision"], environment["etag"])
