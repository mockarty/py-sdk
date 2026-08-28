"""Create a Shared SaaS project through Mockarty Cloud."""

import os

from mockarty import MockartyClient

with MockartyClient(base_url=os.environ["MOCKARTY_BASE_URL"], api_key=os.environ["MOCKARTY_API_KEY"]) as client:
    project = client.cloud_shared_projects.create(os.environ["MOCKARTY_SPACE_ID"], "SDK example", {"version": 1})
    print(project["id"], project["revision"])
