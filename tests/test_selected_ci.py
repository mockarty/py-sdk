import base64
import json
import pytest
from mockarty import MockartyClient
from mockarty.ci_job_context import load_ci_job_context
ID="11111111-1111-4111-8111-111111111111"
def envelope():
    item=dict(itemUid=ID,caseId=ID,versionId=ID,groupId=ID,attemptId=ID,jobConfigId=ID,selector={"id":"selected","selector":"suite.test"})
    data=dict(format="mockarty.native-ci-job/v1",namespace="qa",token=base64.urlsafe_b64encode(bytes(32)).decode().rstrip("="),items=[item],launchId=ID,groupId=ID,attemptId=ID,invocationId=ID)
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
def test_selected_report_and_metadata(monkeypatch,respx_mock):
    raw=envelope();monkeypatch.setenv("MOCKARTY_CI_CONTEXT",raw)
    route=respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs").respond(200,json={})
    meta={"environment":{"MOCKARTY_CI_CONTEXT":raw,"safe":"kept"},"stdout":raw}
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        client.external_runs.report(status="passed",auto_create=True,external_id="selected",full_name="suite.test",metadata=meta)
    body=json.loads(route.calls[0].request.content)
    assert body["caseId"]==ID and body["ciContext"]["itemUid"]==ID and not body["autoCreate"]
    assert raw not in json.dumps(body["metadata"]) and "MOCKARTY_CI_CONTEXT" not in json.dumps(body["metadata"])
    assert meta["environment"]["MOCKARTY_CI_CONTEXT"]==raw
@pytest.mark.parametrize("kind",["unknown","foreign","attachment","malformed"])
def test_refusal_before_http(monkeypatch,respx_mock,kind):
    raw=envelope();ns="qa";kwargs={"external_id":"selected","full_name":"suite.test"}
    if kind=="unknown":kwargs["external_id"]="unknown"
    if kind=="foreign":ns="foreign"
    if kind=="attachment":kwargs["attachments"]=[{"name":"log","body":raw}]
    if kind=="malformed":raw="private-invalid-context"
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",raw)
    with MockartyClient(base_url="http://fixture.test",namespace=ns) as client:
        with pytest.raises(ValueError) as err:client.external_runs.report(status="passed",case_name="ordinary",**kwargs)
    assert raw not in str(err.value) and not respx_mock.calls
def test_completion_one_post(respx_mock):
    job=load_ci_job_context(envelope());assert job.callback.token not in repr(job) and job.callback.token not in repr(job.callback)
    route=respx_mock.post(f"http://fixture.test/api/v1/namespaces/qa/tcm/ci-launches/{ID}/groups/{ID}/complete").respond(503,json={"error":"unavailable"})
    with MockartyClient(base_url="http://fixture.test",namespace="qa",max_retries=3) as client:
        with pytest.raises(Exception):client.external_runs.complete_group(job.callback,"failed")
    assert len(route.calls)==1 and json.loads(route.calls[0].request.content)["callback"]["itemUid"]=="00000000-0000-0000-0000-000000000000"
@pytest.mark.asyncio
async def test_async_selected(monkeypatch,respx_mock):
    from mockarty import AsyncMockartyClient
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    r=respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs").respond(200,json={})
    c=respx_mock.post(f"http://fixture.test/api/v1/namespaces/qa/tcm/ci-launches/{ID}/groups/{ID}/complete").respond(200,json={})
    async with AsyncMockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        await client.external_runs.report(status="passed",case_name="ordinary",external_id="selected",full_name="suite.test")
        await client.external_runs.complete_group(load_ci_job_context(envelope()).callback,"passed")
    assert json.loads(r.calls[0].request.content)["caseId"]==ID and len(c.calls)==1
@pytest.mark.parametrize("raw",["","a"*((1<<20)+1),"e30","e30="])
def test_invalid(raw):
    with pytest.raises(ValueError):load_ci_job_context(raw)
def test_framework_environment_never_persists_capability(tmp_path):
    from mockarty.allure_writer import AllureResultsWriter
    env={"MOCKARTY_CI_CONTEXT":"private-envelope","alias":"prefix-private-envelope","safe":"kept"}
    path=AllureResultsWriter(tmp_path).write_environment(env)
    text=open(path).read()
    assert "private-envelope" not in text and "MOCKARTY_CI_CONTEXT" not in text and "safe=kept" in text
    assert env["alias"]=="prefix-private-envelope"
