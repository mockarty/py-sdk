"""Search and review reusable AutoTester experience."""

from mockarty import MockartyClient

with MockartyClient() as client:
    for item in client.experience.search(query="payment retry", limit=5).results:
        print(item.kind, item.text, item.source)
    for candidate in client.experience.list_review(state="candidate", limit=20).items:
        print("review", candidate.state, candidate.id, candidate.version, candidate.source)
