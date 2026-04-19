# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for Test Plans API (sync + async)."""

from __future__ import annotations

import io

import httpx
import pytest
import respx

from mockarty import (
    AdHocItem,
    AdHocRunResponse,
    AllureReport,
    AsyncMockartyClient,
    AsyncTestPlansAPI,
    CreateAdHocRunRequest,
    MockartyClient,
    PatchPlanRequest,
    PlanItemState,
    PlanNotFoundError,
    PreconditionFailedError,
    RunCancelledError,
    RunEvent,
    RunFailedError,
    Schedule,
    TestPlan,
    TestPlanItem,
    TestPlanRun,
    Webhook,
    WebhookDeliveryError,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def plan_payload() -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "numericId": 42,
        "namespace": "test-ns",
        "name": "Nightly Smoke",
        "items": [
            {
                "order": 0,
                "type": "functional",
                "refId": "coll-1",
                "name": "Smoke",
            }
        ],
    }


# ── CRUD ─────────────────────────────────────────────────────────────


class TestTestPlansCRUD:
    @respx.mock
    def test_create(self, client: MockartyClient, plan_payload: dict) -> None:
        respx.post("http://localhost:5770/api/v1/test-plans").mock(
            return_value=httpx.Response(201, json=plan_payload)
        )
        plan = TestPlan(
            namespace="test-ns",
            name="Nightly Smoke",
            items=[TestPlanItem(order=0, type="functional", resource_id="coll-1")],
        )
        created = client.test_plans.create(plan)
        assert isinstance(created, TestPlan)
        assert created.id == "11111111-1111-1111-1111-111111111111"
        assert created.numeric_id == 42
        assert created.items[0].resource_id == "coll-1"

    @respx.mock
    def test_get_by_uuid(self, client: MockartyClient, plan_payload: dict) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/11111111-1111-1111-1111-111111111111"
        ).mock(return_value=httpx.Response(200, json=plan_payload))

        plan = client.test_plans.get("11111111-1111-1111-1111-111111111111")
        assert plan.name == "Nightly Smoke"

    @respx.mock
    def test_get_strips_hash_prefix(
        self, client: MockartyClient, plan_payload: dict
    ) -> None:
        route = respx.get("http://localhost:5770/api/v1/test-plans/42").mock(
            return_value=httpx.Response(200, json=plan_payload)
        )
        plan = client.test_plans.get("#42")
        assert plan.numeric_id == 42
        assert route.called

    @respx.mock
    def test_get_not_found(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/test-plans/missing").mock(
            return_value=httpx.Response(
                404, json={"error": "plan not found", "code": "not_found"}
            )
        )
        with pytest.raises(PlanNotFoundError):
            client.test_plans.get("missing")

    def test_get_empty_id_rejected(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError):
            client.test_plans.get("")

    @respx.mock
    def test_update(self, client: MockartyClient, plan_payload: dict) -> None:
        respx.put(
            "http://localhost:5770/api/v1/test-plans/11111111-1111-1111-1111-111111111111"
        ).mock(return_value=httpx.Response(200, json=plan_payload))

        plan = TestPlan(
            namespace="test-ns",
            name="Updated",
            items=[TestPlanItem(order=0, type="functional", resource_id="coll-1")],
        )
        updated = client.test_plans.update(
            "11111111-1111-1111-1111-111111111111", plan
        )
        assert updated.id == "11111111-1111-1111-1111-111111111111"

    @respx.mock
    def test_delete(self, client: MockartyClient) -> None:
        route = respx.delete(
            "http://localhost:5770/api/v1/test-plans/11111111-1111-1111-1111-111111111111"
        ).mock(return_value=httpx.Response(204))
        client.test_plans.delete("11111111-1111-1111-1111-111111111111")
        assert route.called

    @respx.mock
    def test_list(self, client: MockartyClient, plan_payload: dict) -> None:
        respx.get("http://localhost:5770/api/v1/test-plans").mock(
            return_value=httpx.Response(
                200, json={"items": [plan_payload], "count": 1}
            )
        )
        plans = client.test_plans.list(limit=20)
        assert len(plans) == 1
        assert plans[0].name == "Nightly Smoke"


# ── Runs ─────────────────────────────────────────────────────────────


class TestTestPlansRuns:
    @respx.mock
    def test_run(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/test-plans/plan-1/run"
        ).mock(
            return_value=httpx.Response(
                202,
                json={"runId": "run-1", "planId": "plan-1", "status": "pending"},
            )
        )
        run = client.test_plans.run("plan-1")
        assert isinstance(run, TestPlanRun)
        assert run.id == "run-1"
        assert run.status == "pending"

    @respx.mock
    def test_run_with_subset_and_mode(self, client: MockartyClient) -> None:
        route = respx.post(
            "http://localhost:5770/api/v1/test-plans/plan-1/run"
        ).mock(
            return_value=httpx.Response(
                202, json={"runId": "r2", "planId": "plan-1", "status": "pending"}
            )
        )
        client.test_plans.run("plan-1", items=[0, 2], mode="parallel")
        import json as _json

        body = _json.loads(route.calls[0].request.content)
        assert body == {"items": [0, 2], "mode": "parallel"}

    @respx.mock
    def test_get_run(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/test-plans/runs/run-1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "run-1",
                    "planId": "plan-1",
                    "status": "completed",
                    "totalItems": 3,
                    "completedItems": 3,
                    "failedItems": 0,
                    "itemsState": [
                        {"order": 0, "type": "functional", "status": "passed"}
                    ],
                },
            )
        )
        run = client.test_plans.get_run("run-1")
        assert run.status == "completed"
        assert run.total_items == 3
        assert isinstance(run.items_state[0], PlanItemState)

    @respx.mock
    def test_wait_for_run_success(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/test-plans/runs/run-1").mock(
            return_value=httpx.Response(
                200,
                json={"id": "run-1", "status": "completed", "totalItems": 1},
            )
        )
        run = client.test_plans.wait_for_run("run-1", poll_interval=0.01)
        assert run.status == "completed"

    @respx.mock
    def test_wait_for_run_failed(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/test-plans/runs/run-1").mock(
            return_value=httpx.Response(
                200, json={"id": "run-1", "status": "failed"}
            )
        )
        with pytest.raises(RunFailedError):
            client.test_plans.wait_for_run("run-1", poll_interval=0.01)

    @respx.mock
    def test_wait_for_run_cancelled(self, client: MockartyClient) -> None:
        respx.get("http://localhost:5770/api/v1/test-plans/runs/run-1").mock(
            return_value=httpx.Response(
                200, json={"id": "run-1", "status": "cancelled"}
            )
        )
        with pytest.raises(RunCancelledError):
            client.test_plans.wait_for_run("run-1", poll_interval=0.01)

    @respx.mock
    def test_cancel_run(self, client: MockartyClient) -> None:
        route = respx.post(
            "http://localhost:5770/api/v1/test-plans/runs/run-1/cancel"
        ).mock(return_value=httpx.Response(202))
        client.test_plans.cancel_run("run-1")
        assert route.called

    @respx.mock
    def test_get_run_status(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/runs/run-1/status"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "running",
                    "totalItems": 3,
                    "completedItems": 1,
                    "failedItems": 0,
                },
            )
        )
        status = client.test_plans.get_run_status("run-1")
        assert status.status == "running"
        assert status.total_items == 3

    @respx.mock
    def test_list_runs(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/plan-1/runs"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "r1", "status": "completed"},
                        {"id": "r2", "status": "running"},
                    ],
                    "count": 2,
                },
            )
        )
        runs = client.test_plans.list_runs("plan-1")
        assert len(runs) == 2
        assert runs[0].id == "r1"

    @respx.mock
    def test_get_report(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/runs/run-1/report"
        ).mock(return_value=httpx.Response(200, json={"allure": True}))
        data = client.test_plans.get_report("run-1")
        assert b"allure" in data

    @respx.mock
    def test_download_report_zip(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/runs/run-1/report.zip"
        ).mock(return_value=httpx.Response(200, content=b"PK\x03\x04fake zip"))
        buf = io.BytesIO()
        client.test_plans.download_report_zip("run-1", buf)
        assert buf.getvalue().startswith(b"PK")

    @respx.mock
    def test_stream_run_parses_sse(self, client: MockartyClient) -> None:
        sse_body = (
            ": heartbeat\n"
            "event: run.started\n"
            'data: {"runId":"r1"}\n'
            "\n"
            "event: item.finished\n"
            'data: {"order":0,"status":"passed"}\n'
            "\n"
        )
        respx.get(
            "http://localhost:5770/api/v1/test-plans/runs/r1/stream"
        ).mock(
            return_value=httpx.Response(
                200,
                headers={"Content-Type": "text/event-stream"},
                content=sse_body.encode(),
            )
        )
        events = list(client.test_plans.stream_run("r1"))
        assert len(events) == 2
        assert events[0].kind == "run.started"
        assert events[0].data == {"runId": "r1"}
        assert events[1].kind == "item.finished"
        assert events[1].data["status"] == "passed"


# ── Schedules ────────────────────────────────────────────────────────


class TestSchedules:
    @respx.mock
    def test_add(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/test-plans/plan-1/schedules"
        ).mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "sch-1",
                    "planId": "plan-1",
                    "kind": "cron",
                    "cronExpr": "0 2 * * *",
                    "enabled": True,
                },
            )
        )
        sch = client.test_plans.add_schedule(
            "plan-1",
            Schedule(kind="cron", cron_expr="0 2 * * *"),
        )
        assert sch.id == "sch-1"
        assert sch.cron_expr == "0 2 * * *"

    @respx.mock
    def test_list(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/plan-1/schedules"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {"id": "sch-1", "kind": "cron", "cronExpr": "0 2 * * *"}
                    ],
                    "count": 1,
                },
            )
        )
        schedules = client.test_plans.list_schedules("plan-1")
        assert len(schedules) == 1

    @respx.mock
    def test_update(self, client: MockartyClient) -> None:
        respx.patch(
            "http://localhost:5770/api/v1/test-plans/plan-1/schedules/sch-1"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"id": "sch-1", "kind": "cron", "enabled": False},
            )
        )
        sch = client.test_plans.update_schedule(
            "plan-1", "sch-1", Schedule(kind="cron", enabled=False)
        )
        assert sch.enabled is False

    @respx.mock
    def test_delete(self, client: MockartyClient) -> None:
        route = respx.delete(
            "http://localhost:5770/api/v1/test-plans/plan-1/schedules/sch-1"
        ).mock(return_value=httpx.Response(204))
        client.test_plans.delete_schedule("plan-1", "sch-1")
        assert route.called


# ── Webhooks ─────────────────────────────────────────────────────────


class TestWebhooks:
    @respx.mock
    def test_add(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/test-plans/plan-1/webhooks"
        ).mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "wh-1",
                    "url": "https://ci.example.com/hook",
                    "events": ["run.completed"],
                    "enabled": True,
                },
            )
        )
        wh = client.test_plans.add_webhook(
            "plan-1",
            Webhook(
                url="https://ci.example.com/hook",
                events=["run.completed"],
                secret="s3cr3t",
            ),
        )
        assert wh.id == "wh-1"

    @respx.mock
    def test_list(self, client: MockartyClient) -> None:
        respx.get(
            "http://localhost:5770/api/v1/test-plans/plan-1/webhooks"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "wh-1",
                            "url": "https://x/hook",
                            "events": ["run.completed"],
                        }
                    ],
                    "count": 1,
                },
            )
        )
        hooks = client.test_plans.list_webhooks("plan-1")
        assert len(hooks) == 1

    @respx.mock
    def test_test_webhook_success(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/test-plans/plan-1/webhooks/wh-1/test"
        ).mock(
            return_value=httpx.Response(200, json={"success": True, "status": 200})
        )
        client.test_plans.test_webhook("plan-1", "wh-1")

    @respx.mock
    def test_test_webhook_failure(self, client: MockartyClient) -> None:
        respx.post(
            "http://localhost:5770/api/v1/test-plans/plan-1/webhooks/wh-1/test"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"success": False, "status": 500, "error": "timeout"},
            )
        )
        with pytest.raises(WebhookDeliveryError):
            client.test_plans.test_webhook("plan-1", "wh-1")

    @respx.mock
    def test_delete_webhook(self, client: MockartyClient) -> None:
        route = respx.delete(
            "http://localhost:5770/api/v1/test-plans/plan-1/webhooks/wh-1"
        ).mock(return_value=httpx.Response(204))
        client.test_plans.delete_webhook("plan-1", "wh-1")
        assert route.called


# ── Async API ────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAsyncTestPlansAPI:
    async def test_create(self, plan_payload: dict) -> None:
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace="test-ns",
            max_retries=0,
        ) as c:
            assert isinstance(c.test_plans, AsyncTestPlansAPI)
            with respx.mock(base_url="http://localhost:5770") as router:
                router.post("/api/v1/test-plans").mock(
                    return_value=httpx.Response(201, json=plan_payload)
                )
                created = await c.test_plans.create(
                    TestPlan(
                        namespace="test-ns",
                        name="Nightly",
                        items=[
                            TestPlanItem(
                                order=0, type="functional", resource_id="coll-1"
                            )
                        ],
                    )
                )
                assert created.id == "11111111-1111-1111-1111-111111111111"

    async def test_stream_run_async(self) -> None:
        sse_body = (
            "event: run.started\n"
            'data: {"runId":"r1"}\n'
            "\n"
            "event: run.completed\n"
            'data: {"status":"completed"}\n'
            "\n"
        )
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace="test-ns",
            max_retries=0,
        ) as c:
            with respx.mock(base_url="http://localhost:5770") as router:
                router.get("/api/v1/test-plans/runs/r1/stream").mock(
                    return_value=httpx.Response(
                        200,
                        headers={"Content-Type": "text/event-stream"},
                        content=sse_body.encode(),
                    )
                )
                events: list[RunEvent] = []
                async for ev in c.test_plans.stream_run("r1"):
                    events.append(ev)
                assert [e.kind for e in events] == [
                    "run.started",
                    "run.completed",
                ]

    async def test_wait_for_run_failed(self) -> None:
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace="test-ns",
            max_retries=0,
        ) as c:
            with respx.mock(base_url="http://localhost:5770") as router:
                router.get("/api/v1/test-plans/runs/r1").mock(
                    return_value=httpx.Response(
                        200, json={"id": "r1", "status": "failed"}
                    )
                )
                with pytest.raises(RunFailedError):
                    await c.test_plans.wait_for_run("r1", poll_interval=0.01)


# ── TP-6b: namespace-scoped endpoints ───────────────────────────────
#
# These tests cover the four endpoints added in the TP-6b milestone:
#   - PATCH  /namespaces/:ns/test-plans/:id   (If-Match, 412 handling)
#   - POST   /namespaces/:ns/test-runs/ad-hoc
#   - GET    /namespaces/:ns/test-plans/:id/runs/:runId/report
#   - GET    /namespaces/:ns/test-plans/:id/runs/:runId/report.zip


_NS = "test-ns"
_PATCH_URL = f"http://localhost:5770/api/v1/namespaces/{_NS}/test-plans/plan-1"
_ADHOC_URL = f"http://localhost:5770/api/v1/namespaces/{_NS}/test-runs/ad-hoc"
_REPORT_URL = (
    f"http://localhost:5770/api/v1/namespaces/{_NS}/test-plans/plan-1/runs/run-1/report"
)
_REPORT_ZIP_URL = (
    f"http://localhost:5770/api/v1/namespaces/{_NS}/test-plans/plan-1/runs/run-1/report.zip"
)


class TestPatch:
    @respx.mock
    def test_patch_with_explicit_etag(
        self, client: MockartyClient, plan_payload: dict
    ) -> None:
        """An explicit If-Match is forwarded verbatim and skips the pre-fetch."""
        updated = {**plan_payload, "name": "Renamed"}
        route = respx.patch(_PATCH_URL).mock(
            return_value=httpx.Response(200, json=updated)
        )
        plan = client.test_plans.patch(
            "plan-1",
            PatchPlanRequest(name="Renamed"),
            if_match='"1700000000000"',
        )
        assert plan.name == "Renamed"
        assert route.called
        req = route.calls[0].request
        assert req.headers["If-Match"] == '"1700000000000"'
        import json as _json

        body = _json.loads(req.content)
        assert body == {"name": "Renamed"}

    @respx.mock
    def test_patch_auto_fetches_etag(
        self, client: MockartyClient, plan_payload: dict
    ) -> None:
        """When if_match is omitted the SDK performs a GET to derive it."""
        with_updated = {**plan_payload, "updatedAt": "2026-01-01T00:00:00Z"}
        respx.get(
            "http://localhost:5770/api/v1/test-plans/plan-1"
        ).mock(return_value=httpx.Response(200, json=with_updated))
        route = respx.patch(_PATCH_URL).mock(
            return_value=httpx.Response(200, json=with_updated)
        )
        plan = client.test_plans.patch(
            "plan-1", PatchPlanRequest(description="Updated")
        )
        assert plan.id == "11111111-1111-1111-1111-111111111111"
        assert route.called
        assert route.calls[0].request.headers["If-Match"].startswith('"')

    @respx.mock
    def test_patch_precondition_failed(self, client: MockartyClient) -> None:
        respx.patch(_PATCH_URL).mock(
            return_value=httpx.Response(
                412,
                json={
                    "error": "If-Match does not match",
                    "code": "precondition_failed",
                },
                headers={"X-Request-Id": "req-123"},
            )
        )
        with pytest.raises(PreconditionFailedError) as exc:
            client.test_plans.patch(
                "plan-1",
                PatchPlanRequest(name="X"),
                if_match='"stale"',
            )
        # Exposes the server's correlation id so callers can log/report it.
        assert exc.value.request_id == "req-123"
        assert "If-Match" in exc.value.message

    def test_patch_requires_at_least_one_field(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError):
            client.test_plans.patch("plan-1", PatchPlanRequest(), if_match='"1"')

    def test_patch_rejects_empty_plan_ref(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError):
            client.test_plans.patch(
                "", PatchPlanRequest(name="x"), if_match='"1"'
            )

    @respx.mock
    def test_patch_overrides_namespace(
        self, client: MockartyClient, plan_payload: dict
    ) -> None:
        """Explicit ``namespace=`` overrides the client default in the path."""
        alt_url = (
            "http://localhost:5770/api/v1/namespaces/tenant-b/test-plans/plan-1"
        )
        respx.patch(alt_url).mock(
            return_value=httpx.Response(200, json=plan_payload)
        )
        client.test_plans.patch(
            "plan-1",
            PatchPlanRequest(enabled=False),
            if_match='"1"',
            namespace="tenant-b",
        )


class TestAdHocRun:
    @respx.mock
    def test_create_ad_hoc_run(self, client: MockartyClient) -> None:
        respx.post(_ADHOC_URL).mock(
            return_value=httpx.Response(
                202,
                json={
                    "run_id": "run-1",
                    "plan_id": "plan-1",
                    "status": "pending",
                    "adhoc": True,
                    "_links": {"self": "/api/v1/test-plans/runs/run-1"},
                },
            )
        )
        resp = client.test_plans.create_ad_hoc_run(
            CreateAdHocRunRequest(
                name="demo",
                items=[AdHocItem(type="functional", ref_id="coll-1", order=0)],
            )
        )
        assert isinstance(resp, AdHocRunResponse)
        assert resp.run_id == "run-1"
        assert resp.plan_id == "plan-1"
        assert resp.adhoc is True
        assert resp.links and "self" in resp.links

    def test_create_ad_hoc_run_requires_items(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError):
            client.test_plans.create_ad_hoc_run(CreateAdHocRunRequest(items=[]))


class TestRunReport:
    @respx.mock
    def test_get_run_report_json(self, client: MockartyClient) -> None:
        respx.get(_REPORT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "runId": "run-1",
                    "planId": "plan-1",
                    "status": "completed",
                    "items": [],
                    "summary": {"passed": 3, "failed": 0},
                    "labels": {"env": "ci"},
                },
            )
        )
        report = client.test_plans.get_run_report("plan-1", "run-1")
        assert isinstance(report, AllureReport)
        assert report.run_id == "run-1"
        assert report.status == "completed"
        assert report.summary == {"passed": 3, "failed": 0}
        # Raw bytes are always preserved for forward compatibility.
        assert report.raw is not None
        assert b"runId" in report.raw

    def test_get_run_report_rejects_empty_run(self, client: MockartyClient) -> None:
        with pytest.raises(ValueError):
            client.test_plans.get_run_report("plan-1", "")

    @respx.mock
    def test_get_run_report_zip(self, client: MockartyClient) -> None:
        respx.get(_REPORT_ZIP_URL).mock(
            return_value=httpx.Response(200, content=b"PK\x03\x04binary")
        )
        buf = io.BytesIO()
        client.test_plans.get_run_report_zip("plan-1", "run-1", buf)
        assert buf.getvalue().startswith(b"PK")


@pytest.mark.asyncio
class TestAsyncNamespaceScoped:
    async def test_patch_async_precondition_failed(self) -> None:
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace=_NS,
            max_retries=0,
        ) as c:
            with respx.mock(base_url="http://localhost:5770") as router:
                router.patch(f"/api/v1/namespaces/{_NS}/test-plans/plan-1").mock(
                    return_value=httpx.Response(
                        412,
                        json={"error": "etag mismatch", "code": "precondition_failed"},
                    )
                )
                with pytest.raises(PreconditionFailedError):
                    await c.test_plans.patch(
                        "plan-1",
                        PatchPlanRequest(name="async"),
                        if_match='"stale"',
                    )

    async def test_create_ad_hoc_run_async(self) -> None:
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace=_NS,
            max_retries=0,
        ) as c:
            with respx.mock(base_url="http://localhost:5770") as router:
                router.post(f"/api/v1/namespaces/{_NS}/test-runs/ad-hoc").mock(
                    return_value=httpx.Response(
                        202,
                        json={
                            "run_id": "r-async",
                            "plan_id": "p-async",
                            "status": "pending",
                            "adhoc": True,
                        },
                    )
                )
                resp = await c.test_plans.create_ad_hoc_run(
                    CreateAdHocRunRequest(
                        items=[
                            AdHocItem(type="chaos", ref_id="exp-1", order=0)
                        ]
                    )
                )
                assert resp.run_id == "r-async"

    async def test_get_run_report_async(self) -> None:
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace=_NS,
            max_retries=0,
        ) as c:
            with respx.mock(base_url="http://localhost:5770") as router:
                router.get(
                    f"/api/v1/namespaces/{_NS}/test-plans/plan-1/runs/run-1/report"
                ).mock(
                    return_value=httpx.Response(
                        200,
                        json={"runId": "run-1", "status": "completed"},
                    )
                )
                rep = await c.test_plans.get_run_report("plan-1", "run-1")
                assert rep.status == "completed"

    async def test_get_run_report_zip_async(self) -> None:
        async with AsyncMockartyClient(
            base_url="http://localhost:5770",
            api_key="mk_test",
            namespace=_NS,
            max_retries=0,
        ) as c:
            with respx.mock(base_url="http://localhost:5770") as router:
                router.get(
                    f"/api/v1/namespaces/{_NS}/test-plans/plan-1"
                    "/runs/run-1/report.zip"
                ).mock(return_value=httpx.Response(200, content=b"PK\x03\x04zip"))
                buf = io.BytesIO()
                await c.test_plans.get_run_report_zip("plan-1", "run-1", buf)
                assert buf.getvalue().startswith(b"PK")
