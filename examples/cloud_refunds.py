import os

from mockarty import MockartyClient


client = MockartyClient(os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"])
resolution = client.cloud_refunds.resolve_refund(
    os.environ["REFUND_OPERATION_ID"],
    action="retry",
    reason_code="provider_recovery_retry",
    generation=4,
    idempotency_key="refund-resolution:example-1",
)
print(resolution["refund"]["operation_id"], resolution["refund"]["status"])
