import httpx
import respx

from mockarty import MockartyClient


@respx.mock
def test_page_analyzer_lifecycle_uses_all_existing_routes(client: MockartyClient) -> None:
    base = "http://localhost:5770/api/v1/page-analyzer"
    routes = [
        respx.get(f"{base}/configs").mock(return_value=httpx.Response(200, json={"configs": []})),
        respx.post(f"{base}/configs").mock(return_value=httpx.Response(200, json={})),
        respx.put(f"{base}/configs/cfg-1").mock(return_value=httpx.Response(200, json={})),
        respx.delete(f"{base}/configs/cfg-1").mock(return_value=httpx.Response(200, json={"success": True})),
        respx.post(f"{base}/run").mock(return_value=httpx.Response(200, json={"resultId": "res-1", "status": "pending"})),
        respx.get(f"{base}/results").mock(return_value=httpx.Response(200, json={"results": [], "limit": 25, "offset": 5})),
        respx.get(f"{base}/results/res-1").mock(return_value=httpx.Response(200, json={})),
        respx.delete(f"{base}/results/res-1").mock(return_value=httpx.Response(200, json={"success": True})),
        respx.post(f"{base}/results/res-1/ai-analyze").mock(return_value=httpx.Response(200, json={"analysis": "ok"})),
    ]

    client.page_analyzer.list_configs()
    client.page_analyzer.save_config({"name": "home", "targetUrl": "https://example.com"})
    client.page_analyzer.update_config("cfg-1", {"name": "home", "targetUrl": "https://example.com"})
    client.page_analyzer.delete_config("cfg-1")
    client.page_analyzer.run({"targetUrl": "https://example.com"})
    client.page_analyzer.list_results(limit=25, offset=5)
    client.page_analyzer.get_result("res-1")
    client.page_analyzer.delete_result("res-1")
    client.page_analyzer.analyze_with_ai("res-1")

    assert all(route.called for route in routes)
    assert all(route.calls.last.request.url.params["namespace"] == "test-ns" for route in routes)
