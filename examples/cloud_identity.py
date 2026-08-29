import os

from mockarty import MockartyClient

with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"]) as client:
    for identity in client.cloud_identity.list():
        print(identity["provider"])
