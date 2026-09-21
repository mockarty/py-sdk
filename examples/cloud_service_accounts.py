"""Inspect Cloud service-account capacity or an msa_ credential's identity."""

import os

from mockarty import MockartyClient

credential = os.environ.get("MOCKARTY_SERVICE_ACCOUNT_CREDENTIAL")
with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"],
                   api_key=credential or os.environ["MOCKARTY_API_KEY"]) as client:
    if credential:
        identity = client.cloud_service_account.self()
        print(identity["service_account"]["name"], len(identity["bindings"]))
    else:
        page = client.cloud_service_accounts.list(os.environ["MOCKARTY_SPACE_ID"])
        print(len(page["service_accounts"]), page["capacity"]["remaining"])
