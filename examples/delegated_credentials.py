# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Issue a project-scoped delegated credential, hand it to a CI job, rotate and revoke it.

Run against a live Mockarty admin node::

    MOCKARTY_BASE_URL=http://127.0.0.1:5770 \
    MOCKARTY_API_KEY=mk_... \
    python examples/delegated_credentials.py

The point of the example is the difference from an API key: an API key's
namespace is a DEFAULT its holder can change, and it carries no expiry of its
own. A delegated credential freezes both, and the holder — the CI job in this
story — has no path to widen either.
"""

import os
from datetime import datetime, timedelta, timezone

from mockarty import (
    DELEGATED_ACTION_VOCABULARY,
    DelegatedCredentialCreateRequest,
    MockartyClient,
)

with MockartyClient(
    base_url=os.environ["MOCKARTY_BASE_URL"],
    api_key=os.environ["MOCKARTY_API_KEY"],
) as client:
    api = client.delegated_credentials

    issued = api.create(
        DelegatedCredentialCreateRequest(
            name="ci-reader",
            description="nightly regression job — read-only, one namespace, 30 days",
            namespaces=["staging"],
            # Narrow the actions explicitly. Omit to grant the full vocabulary
            # (read, write, delete), which is how the server reads an empty list.
            allowed_actions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )

    # Shown ONCE. Store it in the CI secret store: the row keeps only a bcrypt
    # hash and a sha256 index, so the bearer cannot be read back. Lost it?
    # Rotate.
    print(f"issued {issued.credential.id} ({issued.credential.token_prefix})")
    print(f"  frozen scope: namespaces={issued.credential.namespaces} "
          f"actions={issued.credential.allowed_actions} "
          f"expires={issued.credential.expires_at.isoformat()}")
    print(f"  hand this to the job: {issued.token}")
    print(f"  the full action vocabulary is: {', '.join(DELEGATED_ACTION_VOCABULARY)}")

    # The issuer can see what it issued — and so can a delegated credential, for
    # the credentials IT minted, but never for its issuer's.
    page = api.list()
    print(f"\n{page.count} credential(s) visible to this caller")
    for cred in page.credentials:
        state = "revoked" if cred.is_revoked else ("expired" if cred.is_expired() else "active")
        print(f"  {cred.id} {cred.name:<18} {state} {cred.namespaces} -> {cred.expires_at.isoformat()}")

    # The leaked-secret path. Rotation issues a fresh bearer and leaves the
    # scope EXACTLY as it was: a live credential's authority is never edited,
    # because a silent widening would leave no new credential to audit.
    rotated = api.rotate(issued.credential.id)
    assert rotated.credential.namespaces == issued.credential.namespaces, "rotation must not change the scope"
    print(f"\nrotated — the previous token stopped working immediately:\n  {rotated.token}")

    # Revocation is terminal: there is no un-revoke, because "temporarily
    # revoked" is exactly the window a shared credential should not have.
    # Revoking twice is a no-op rather than an error.
    api.revoke(issued.credential.id)
    api.revoke(issued.credential.id)
    print(f"\nrevoked {issued.credential.id} (idempotent)")

    print("\nthe held token can act only in its frozen namespaces, "
          "only with its frozen actions, only until its expiry")
