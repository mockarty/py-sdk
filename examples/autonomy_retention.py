"""Configure namespace autonomous-run safety and evidence retention."""

from mockarty import MockartyClient


with MockartyClient(namespace="engineering") as client:
    client.namespace_settings.save_autonomy_settings(
        {
            "journalEventRetentionDays": 365,
            "journalPayloadRetentionDays": 30,
            "runWindowMinutes": 90,
        },
        request_id="safety-change-2026-08-25",
    )
