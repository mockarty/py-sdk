"""Search and record reusable AutoTester experience."""

from mockarty import MockartyClient

with MockartyClient() as client:
    for item in client.experience.search(query="payment retry", limit=5).results:
        print(item.kind, item.text, item.source)
