"""Read a committed Cloud entitlement projection for one Space."""

import os

from mockarty import MockartyClient


with MockartyClient(
    base_url=os.environ["MOCKARTY_CLOUD_URL"],
    api_key=os.environ["MOCKARTY_CLOUD_TOKEN"],
) as client:
    projection = client.cloud_entitlements.get(os.environ["MOCKARTY_SPACE_ID"])
    # This projection is unsigned inspection data, not an offline licence.
    print(projection["snapshot"]["plan"], projection["revision"])
