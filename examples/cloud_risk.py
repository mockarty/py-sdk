import os

from mockarty import MockartyClient


client = MockartyClient(os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"])
for case in client.cloud_risk.list_cases(status="open", limit=50):
    print(case["id"], case["decision"], case["reason_code"])

# release_enforcement derives a stable idempotency key for safe exact retries.
