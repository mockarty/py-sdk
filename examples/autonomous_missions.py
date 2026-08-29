"""Submit and supervise one bounded goal-first autonomous mission."""

import os
from mockarty import (
    MissionCancelRequest,
    MissionStartRequest,
    MockartyClient,
)


with MockartyClient(
    base_url=os.environ.get("MOCKARTY_BASE_URL"),
    api_key=os.environ.get("MOCKARTY_API_KEY"),
    namespace=os.environ.get("MOCKARTY_NAMESPACE", "sandbox"),
) as client:
    product_id = os.environ.get("MOCKARTY_PRODUCT_ID", "")
    settings = client.autonomous_missions.get_effective_settings(product_id=product_id)
    started = client.autonomous_missions.start(
        MissionStartRequest(
            goal="Take the checkout release to production quality and provide evidence",
            product_id=product_id,
            autonomy="auto",
            budget_tokens_total=100_000,
            expected_settings_digest=settings.settings_digest,
        )
    )
    print("mission:", started.mission.id, started.mission.status, "created:", started.created)
    if os.environ.get("MOCKARTY_EXAMPLE_CANCEL") == "1":
        cancelled = client.autonomous_missions.cancel(
            started.mission.id,
            MissionCancelRequest(
                reason="example run no longer needed",
                idempotency_key="autonomous-missions-example-cancel",
            ),
        )
        print("cancel receipt:", cancelled.control.id, cancelled.control.outcome, cancelled.control.reason)
        for binding in cancelled.execution_bindings:
            print("child:", binding.external_id, binding.kind, binding.state)
