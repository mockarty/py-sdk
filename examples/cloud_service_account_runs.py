"""Dispatch one Shared run with an msa_ credential."""

from datetime import datetime, timedelta, timezone
import os

from mockarty import MockartyClient

with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"],
                   api_key=os.environ["MOCKARTY_SERVICE_ACCOUNT_CREDENTIAL"]) as client:
    run = client.cloud_service_account.dispatch_run(
        os.environ["MOCKARTY_SPACE_ID"],
        deadline=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        capability="execute", run_class="batch", project_id=os.environ["MOCKARTY_PROJECT_ID"],
        payload={"suite": "smoke"}, idempotency_key=os.environ["MOCKARTY_IDEMPOTENCY_KEY"],
    )
    print(run["id"], run["state"], run["revision"])
