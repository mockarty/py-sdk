import os

from mockarty import MockartyClient


client = MockartyClient(os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"])
# The API token needs the exact operator:commerce:write scope.
refunds = client.cloud_refunds.list_refunds()
selected = next(refund for refund in refunds
                if refund["operation_id"] == os.environ["REFUND_OPERATION_ID"])
resolution = client.cloud_refunds.resolve_refund(
    selected["operation_id"],
    action="retry",
    reason_code="provider_recovery_retry",
    generation=selected["generation"],
    idempotency_key=os.environ["REFUND_IDEMPOTENCY_KEY"],
)
print(resolution["refund"]["operation_id"], resolution["refund"]["status"])
