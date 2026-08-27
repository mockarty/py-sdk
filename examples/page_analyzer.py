"""Start an HTTP-level Page Analyzer run."""

from mockarty import MockartyClient


with MockartyClient() as client:
    run = client.page_analyzer.run({
        "targetUrl": "https://example.com",
        "options": {"checkResources": True, "followRedirects": True},
    })
    print(run["resultId"], run["status"])
