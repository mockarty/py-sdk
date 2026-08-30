import os

from mockarty import MockartyClient


with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"], namespace=os.environ["MOCKARTY_NAMESPACE"]) as client:
    page = client.effect_reconciliation.list_queue(limit=20)
    print(f"unresolved effects: {len(page['items'])}")
