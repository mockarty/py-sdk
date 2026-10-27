import asyncio
import json
import httpx
import pytest
import respx
from mockarty import MissionAnswerRequest, AsyncMockartyClient

RECEIPT = {"mission":{"id":"M1","namespace":"team-A","kind":"testing","goal":"verify","origin":"ui","status":"queued"},
           "control":{"id":"C1","missionId":"M1","idempotencyKey":"retry-A","action":"answer","phase":"committed","outcome":"applied"}}

@respx.mock
def test_captured_answer_wire(client):
    route=respx.post("http://localhost:5770/api/v1/missions/M1/answer").mock(return_value=httpx.Response(200,json=RECEIPT))
    request=MissionAnswerRequest(question_id="A",revision=2,generation=3,text="answer A",selected=["staging"],entity={"kind":"environment","id":"env-A","namespace":"team-A"},idempotency_key="retry-A")
    client.autonomous_missions.answer("M1",request)
    body=json.loads(route.calls.last.request.content)
    assert body=={"questionId":"A","revision":2,"generation":3,"text":"answer A","selected":["staging"],"entity":{"kind":"environment","id":"env-A","namespace":"team-A"},"idempotencyKey":"retry-A"}
    assert len(route.calls)==1

@pytest.mark.parametrize("fields",[
    {"text":"missing identity"},{"question_id":"A","text":"missing revision"},
    {"question_id":"A","revision":1,"generation":-1,"text":"negative"},
    {"question_id":"A","revision":1,"text":"typed","answer":"legacy"},
    {"question_id":"A","revision":1},
    {"question_id":"A","revision":1,"selected":["one"," one "]},
    {"question_id":"A","revision":1,"selected":[str(i) for i in range(33)]},
    {"question_id":"A","revision":1,"text":"я"*4001},
    {"question_id":"A","revision":1,"entity":{"kind":"environment"}},
    {"question_id":"A","revision":1.5,"text":"fraction"},
    {"question_id":"A","revision":True,"text":"boolean"},
])
def test_captured_answer_rejects_invalid(fields):
    with pytest.raises(ValueError): MissionAnswerRequest(**fields)

def test_legacy_and_unicode_boundary():
    assert MissionAnswerRequest(answer=" legacy ").answer=="legacy"
    assert MissionAnswerRequest(question_id="A",revision=1,text="я"*4000).text=="я"*4000


@respx.mock
def test_async_captured_answer_wire(base_url, api_key):
    route = respx.post(f"{base_url}/api/v1/missions/M1/answer").mock(return_value=httpx.Response(200, json=RECEIPT))
    async def run():
        async with AsyncMockartyClient(base_url=base_url, api_key=api_key, max_retries=0) as client:
            await client.autonomous_missions.answer("M1", MissionAnswerRequest(question_id="A", revision=2, text="answer A", idempotency_key="retry-A"))
    asyncio.run(run())
    assert json.loads(route.calls.last.request.content) == {"questionId":"A","revision":2,"text":"answer A","idempotencyKey":"retry-A"}


def test_mutated_answer_is_revalidated_before_network(client):
    request = MissionAnswerRequest(question_id="A", revision=1, text="answer A")
    request.revision = 0
    with pytest.raises(ValueError):
        client.autonomous_missions.answer("M1", request)
