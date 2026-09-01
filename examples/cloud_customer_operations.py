"""Read customer loyalty and operator support projections."""

import os

from mockarty import MockartyClient


with MockartyClient(
    base_url=os.environ["MOCKARTY_BASE_URL"],
    api_key=os.environ["MOCKARTY_API_KEY"],
) as client:
    space_id = os.environ["MOCKARTY_CLOUD_SPACE_ID"]
    print(client.cloud_customer.list_loyalty_redemptions(space_id, limit=25))
    print(client.cloud_operations.list_support_cases(status="open", limit=50))
