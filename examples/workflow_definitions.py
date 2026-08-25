"""Create, resolve, and publish one immutable Workflow Definition version."""

import os

from mockarty import MockartyClient


namespace = os.getenv("MOCKARTY_NAMESPACE", "sandbox")
definition = {
    "contractVersion": "mockarty.workflow/v1",
    "namespace": namespace,
    "id": "release-check",
    "version": "1.0.0",
    "status": "draft",
    "entryNode": "inspect",
    "nodes": [
        {
            "id": "inspect",
            "capability": {"key": "mission.inspect", "version": "1.0.0"},
        }
    ],
    "transitions": [],
}

with MockartyClient(
    base_url=os.getenv("MOCKARTY_URL", "http://127.0.0.1:5770"),
    api_key=os.environ["MOCKARTY_API_TOKEN"],
    namespace=namespace,
) as client:
    created = client.workflow_definitions.create_draft(definition)
    dry_run = client.workflow_definitions.dry_run(
        definition["id"], definition["version"], created["revision"]
    )
    if not dry_run["ready"]:
        raise RuntimeError(f"workflow is blocked: {dry_run['blockers']}")
    published = client.workflow_definitions.publish(
        definition["id"], definition["version"], created["revision"]
    )
    print(f"published {published['definition']['id']}@{published['definition']['version']}")
