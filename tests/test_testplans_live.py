# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live wire-parity smoke test for TestPlansAPI CRUD against a running admin.

Drives create -> get (by UUID and by numericId) -> list -> update -> delete ->
gone entirely through the SDK, verifying the TestPlan + TestPlanItem envelope
round-trips (items, executionMode, the server-assigned numericId). Uses a
single `sleep` item so the plan is valid without provisioning any backing
resource — sleep items carry no refId requirement server-side. Test Plans are
the flagship CI/CD orchestration surface, so the wire shape must not drift.
Gated by MOCKARTY_LIVE_TOKEN (same convention as test_flow_runs_live.py); skips
offline.
"""

from __future__ import annotations

import os
import time

import pytest

from mockarty import MockartyClient, TestPlan, TestPlanItem

LIVE_TOKEN = os.environ.get("MOCKARTY_LIVE_TOKEN")
LIVE_URL = os.environ.get("MOCKARTY_LIVE_URL", "http://127.0.0.1:5770")

# sleep items reference no backing entity; the server accepts a nil refId for
# them (Item.Validate skips the refId-required check when type == "sleep").
_NIL_UUID = "00000000-0000-0000-0000-000000000000"


def _sleep_item(order: int = 1) -> TestPlanItem:
    return TestPlanItem(
        order=order,
        type="sleep",
        resource_id=_NIL_UUID,
        name="wait",
        delay_after_ms=50,
    )


@pytest.mark.skipif(
    not LIVE_TOKEN,
    reason="set MOCKARTY_LIVE_TOKEN to a fresh API key to run the live smoke test",
)
def test_testplan_crud_live():
    client = MockartyClient(
        base_url=LIVE_URL,
        api_key=LIVE_TOKEN,
        namespace="sandbox",
    )

    name = f"py-sdk-plan-{int(time.time() * 1000)}"
    plan = TestPlan(namespace="sandbox", name=name, items=[_sleep_item()])

    try:
        created = client.test_plans.create(plan)
    except Exception as exc:  # license gating is correct behaviour, skip
        msg = str(exc)
        if any(s in msg for s in ("not licensed", "feature_not_licensed", "limit", "trial")):
            pytest.skip(f"test-plans feature unavailable (license): {exc}")
        raise

    assert created.id, f"create returned no id: {created!r}"
    assert created.name == name, f"create returned name={created.name!r}, want {name!r}"
    assert created.numeric_id, f"create did not assign a numericId: {created!r}"
    assert created.items and len(created.items) == 1, (
        f"items did not round-trip on create: {created.items!r}"
    )
    assert created.items[0].type == "sleep", f"item type drift: {created.items[0].type!r}"
    plan_id = created.id

    deleted = False
    try:
        # get by UUID id
        by_id = client.test_plans.get(plan_id)
        assert by_id.id == plan_id, f"get(id) returned id={by_id.id!r}, want {plan_id!r}"

        # get by numericId (the user-facing CI handle) resolves to the same plan
        by_numeric = client.test_plans.get(str(created.numeric_id))
        assert by_numeric.id == plan_id, (
            f"get(numericId={created.numeric_id}) returned id={by_numeric.id!r}, want {plan_id!r}"
        )

        # list includes the created plan
        plans = client.test_plans.list()
        assert any(p.id == plan_id for p in plans), (
            f"list() did not include {plan_id!r} (count={len(plans)})"
        )

        # update mutates the name and the item's delay, and round-trips.
        # NOTE: we keep a single sleep item — multiple sleep items would all
        # carry a nil refId and the server synthesises their itemUid from
        # refId, colliding under DAG mode ("duplicate itemUid"). The SDK's
        # TestPlanItem model exposes no item_uid field to disambiguate, so a
        # multi-sleep plan isn't expressible via the SDK today. Plans built
        # from real resources (distinct refId UUIDs) are unaffected.
        changed_item = _sleep_item(1)
        changed_item.delay_after_ms = 120
        updated = client.test_plans.update(
            plan_id,
            TestPlan(
                namespace="sandbox",
                name=name + "-updated",
                items=[changed_item],
            ),
        )
        assert updated.name == name + "-updated", (
            f"update did not persist name: {updated.name!r}"
        )
        assert updated.items and updated.items[0].delay_after_ms == 120, (
            f"update did not persist the changed delay: {updated.items!r}"
        )
    finally:
        client.test_plans.delete(plan_id)
        deleted = True

    if deleted:
        remaining = client.test_plans.list()
        assert not any(p.id == plan_id for p in remaining), (
            f"test plan {plan_id!r} still listed after delete"
        )
