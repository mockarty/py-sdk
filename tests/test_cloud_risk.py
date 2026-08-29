from __future__ import annotations

import httpx
import respx

from mockarty.client import MockartyClient


@respx.mock
def test_cloud_risk_case_and_release_contract() -> None:
    listing = respx.get("https://cloud.test/api/v1/cloud/operator/risk/cases", params={"status": "open", "limit": "25"}).mock(
        return_value=httpx.Response(200, json={"cases": [{"id": "case-1", "status": "open"}]})
    )
    detail = respx.get("https://cloud.test/api/v1/cloud/operator/risk/cases/case-1").mock(
        return_value=httpx.Response(200, json={"case": {"id": "case-1"}, "events": [], "enforcements": []})
    )
    release = respx.post("https://cloud.test/api/v1/cloud/operator/risk/cases/case-1/enforcements/enf-1/release").mock(
        return_value=httpx.Response(200, json={"enforcement": {"id": "enf-1", "status": "released", "revision": 3}})
    )
    client = MockartyClient(base_url="https://cloud.test", max_retries=0)
    assert client.cloud_risk.list_cases(status="open", limit=25)[0]["id"] == "case-1"
    assert client.cloud_risk.get_case("case-1")["case"]["id"] == "case-1"
    assert client.cloud_risk.release_enforcement("case-1", "enf-1", revision=2, reason="customer verified")["enforcement"]["status"] == "released"
    assert listing.called and detail.called
    assert release.calls.last.request.content == b'{"revision":2,"reason":"customer verified"}'
    assert release.calls.last.request.headers["Idempotency-Key"].startswith("risk-release:")
