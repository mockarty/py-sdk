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

@pytest.mark.parametrize("key",["id","selector"])
@pytest.mark.parametrize("value",[0,False,None,[],{}])
def test_selector_present_values_require_strings(key,value):
    data=json.loads(base64.urlsafe_b64decode(envelope()+"="*((-len(envelope()))%4)))
    data["items"][0]["selector"][key]=value
    raw=base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    with pytest.raises(ValueError):load_ci_job_context(raw)

def test_selected_directory_filters_before_media(monkeypatch,respx_mock,tmp_path):
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    (tmp_path/"selected-result.json").write_text(json.dumps(dict(uuid="selected",fullName="suite.test",name="case",status="passed")))
    (tmp_path/"outsider-result.json").write_text(json.dumps(dict(uuid="other",fullName="other.test",name="other",status="passed",attachments=[dict(name="missing",source="absent.txt")])))
    route=respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs").respond(200,json={})
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        out=client.external_runs.upload_allure_dir(str(tmp_path),namespace="qa")
    assert len(out)==1 and len(route.calls)==1

def test_selected_directory_duplicates_before_http(monkeypatch,respx_mock,tmp_path):
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    for name in ("a-result.json","b-result.json"):
        (tmp_path/name).write_text(json.dumps(dict(uuid="selected",fullName="suite.test",name="case",status="passed")))
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        with pytest.raises(ValueError):client.external_runs.upload_allure_dir(str(tmp_path))
    assert not respx_mock.calls


def test_selected_directory_all_media_preflight(monkeypatch,respx_mock,tmp_path):
    data=json.loads(base64.urlsafe_b64decode(envelope()+"="*((-len(envelope()))%4)))
    second=dict(data["items"][0],itemUid="22222222-2222-4222-8222-222222222222",selector={"id":"second","selector":"suite.second"})
    data["items"].append(second)
    raw=base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",raw)
    (tmp_path/"a-result.json").write_text(json.dumps(dict(uuid="selected",fullName="suite.test",name="first",status="passed")))
    (tmp_path/"b-result.json").write_text(json.dumps(dict(uuid="second",fullName="suite.second",name="second",status="passed",attachments=[dict(name="secret",source="secret.txt")])))
    (tmp_path/"secret.txt").write_text(data["token"])
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        with pytest.raises(ValueError):client.external_runs.upload_allure_dir(str(tmp_path),namespace="qa")
    assert not respx_mock.calls


@pytest.mark.parametrize("kind",["status","step","inline"])
def test_selected_batch_body_preflight(monkeypatch,respx_mock,kind):
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    good=dict(externalId="selected",fullName="suite.test",status="passed")
    bad=dict(good)
    if kind=="status":bad["status"]="invalid"
    if kind=="step":bad["steps"]=[dict(name=" ",status="passed")]
    if kind=="inline":bad["attachments"]=[dict(name="large",bodyB64=base64.b64encode(bytes((256<<10)+1)).decode())]
    respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs/batch").respond(200,json={})
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        with pytest.raises(ValueError):client.external_runs.report_batch([good,bad])
    assert not respx_mock.calls


@pytest.mark.parametrize("version",[True,False])
def test_selected_batch_boolean_schema(monkeypatch,respx_mock,version):
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    good=dict(externalId="selected",fullName="suite.test",status="passed")
    respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs/batch").respond(200,json={})
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        with pytest.raises(ValueError):client.external_runs.report_batch([good,dict(good,schemaVersion=version)])
    assert not respx_mock.calls

@pytest.mark.parametrize("count",[1000,1001])
def test_selected_batch_step_limit(monkeypatch,respx_mock,count):
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    good=dict(externalId="selected",fullName="suite.test",status="passed")
    bad=dict(good,steps=[dict(name="step",status="passed") for _ in range(count)])
    respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs/batch").respond(200,json={})
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:
        if count==1000:client.external_runs.report_batch([good,bad])
        else:
            with pytest.raises(ValueError):client.external_runs.report_batch([good,bad])
    assert len(respx_mock.calls)==(1 if count==1000 else 0)


def test_selected_exact_inline_limit(monkeypatch,respx_mock):
    monkeypatch.setenv("MOCKARTY_CI_CONTEXT",envelope())
    body=dict(externalId="selected",fullName="suite.test",status="passed",attachments=[dict(name=str(i),bodyB64=base64.b64encode(bytes(256<<10)).decode()) for i in range(4)])
    body["metadata"]={"bodyB64":"customer notes","nested":{"bodyB64":body["attachments"][0]["bodyB64"]}}
    respx_mock.post("http://fixture.test/api/v1/namespaces/qa/tcm/external-runs/batch").respond(200,json={})
    with MockartyClient(base_url="http://fixture.test",namespace="qa") as client:client.external_runs.report_batch([body])
    assert len(respx_mock.calls)==1
    outgoing=json.loads(respx_mock.calls[0].request.content)["runs"][0]
    assert outgoing["attachments"]==body["attachments"]
    assert load_ci_job_context(envelope()).callback.token not in json.dumps(outgoing["metadata"])
    assert outgoing["metadata"]["bodyB64"]=="customer notes"
