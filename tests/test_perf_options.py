# Copyright (c) 2026 Mockarty. All rights reserved.

"""Saved performance config model wire-contract tests."""

import json

import pytest

from mockarty.models.common import AbortCriterion, PerfConfig, PerfOptions, PerfStage


def test_saved_perf_config_serializes_metrics_push_inside_options():
    """A saved perf config must retain live-metrics targets in its options envelope."""
    config = PerfConfig(
        name="checkout soak",
        script="export default function () {}",
        options=PerfOptions(
            vus=12,
            duration="2m",
            metrics_push=["prometheus:https://metrics.example/push"],
            metrics_push_interval="10s",
            stages=[PerfStage(duration="30s", target=12)],
        ),
    )

    payload = config.model_dump(by_alias=True, exclude_none=True)

    assert payload["options"]["metricsPush"] == ["prometheus:https://metrics.example/push"]
    assert payload["options"]["metricsPushInterval"] == "10s"
    assert payload["options"]["stages"] == [{"duration": "30s", "target": 12}]


def test_get_model_put_preserves_future_fields_and_canonicalizes_max_vus():
    """New-server fields survive a typed saved-config GET -> PUT round trip."""
    response = {
        "id": "cfg-1",
        "collectionId": "col-1",
        "parentId": "folder-1",
        "namespace": "payments",
        "userId": "user-1",
        "name": "nightly",
        "script": "export default function () {}",
        "sortOrder": 4,
        "isFolder": False,
        "environment": {"region": "eu", "attempt": 2},
        "createdAt": "2026-08-22T10:00:00Z",
        "updatedAt": "2026-08-22T11:00:00Z",
        "futureConfig": {"keep": True},
        "options": {
            "maxVus": 17,
            "futureOption": {"keep": True},
            "stages": [{"duration": "30s"}],
            "abortCriteria": [{"metric": "http_req_failed"}],
        },
    }

    config = PerfConfig.model_validate(response)
    assert config.collection_id == "col-1"
    assert config.parent_id == "folder-1"
    assert config.user_id == "user-1"
    assert config.options is not None
    assert config.options.max_vus == 17
    assert config.options.stages == [PerfStage(duration="30s", target=0)]
    assert config.options.abort_criteria[0].enabled is False

    payload = config.model_dump(by_alias=True, exclude_none=True)
    assert payload["collectionId"] == "col-1"
    assert payload["userId"] == "user-1"
    assert payload["sortOrder"] == 4
    assert payload["isFolder"] is False
    assert payload["futureConfig"] == {"keep": True}
    assert payload["options"]["maxVUs"] == 17
    assert "maxVus" not in payload["options"]
    assert payload["options"]["futureOption"] == {"keep": True}


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ({"maxVUs": 23, "maxVus": 7}, 23),
        ({"maxVus": 7, "maxVUs": 23}, 23),
        ({"maxVUs": None, "maxVus": 7}, None),
        ({"maxVus": 7, "maxVUs": None}, None),
    ],
)
def test_canonical_max_vus_wins_regardless_of_order_or_null(wire, expected):
    options = PerfOptions.model_validate(wire)

    assert options.max_vus == expected
    payload = options.model_dump(by_alias=True, exclude_none=True)
    assert "maxVus" not in payload
    if expected is None:
        assert "maxVUs" not in payload
    else:
        assert payload["maxVUs"] == expected


def test_mutable_extras_cannot_inject_typed_names_or_aliases():
    config = PerfConfig(
        name="typed-name",
        options=PerfOptions(
            stages=[PerfStage(duration="30s")],
            abort_criteria=[AbortCriterion(metric="http_req_failed")],
        ),
    )
    config.__pydantic_extra__ = {
        "name": "injected-name",
        "parentId": "injected-parent",
        "parent_id": "injected-parent-by-name",
        "PARENTID": "case-injected-parent",
    }
    config.options.__pydantic_extra__ = {
        "metricsPush": ["injected"],
        "metrics_push": ["injected-by-name"],
        "maxVUs": 91,
        "maxVus": 92,
        "max_vus": 93,
        "MAXVUS": 94,
    }
    config.options.stages[0].__pydantic_extra__ = {
        "duration": "injected-duration",
        "targetRPS": 99,
        "target_rps": 98,
    }
    config.options.abort_criteria[0].__pydantic_extra__ = {"enabled": True}

    payload = config.model_dump(by_alias=True, exclude_none=True)

    assert payload["name"] == "typed-name"
    assert "parentId" not in payload
    assert "parent_id" not in payload
    assert "PARENTID" not in payload
    for protected in ("metricsPush", "metrics_push", "maxVUs", "maxVus", "max_vus", "MAXVUS"):
        assert protected not in payload["options"]
    stage = payload["options"]["stages"][0]
    assert stage["duration"] == "30s"
    assert "targetRPS" not in stage
    assert "target_rps" not in stage
    assert payload["options"]["abortCriteria"][0]["enabled"] is False

    json_payload = json.loads(config.model_dump_json(by_alias=True, exclude_none=True))
    assert json_payload == payload


def test_unknown_null_survives_while_typed_optional_none_is_omitted_recursively():
    config = PerfConfig.model_validate(
        {
            "name": "nightly",
            "futureConfigNull": None,
            "options": {
                "duration": None,
                "futureOptionNull": None,
                "stages": [{"duration": "30s", "targetRPS": None, "futureStageNull": None}],
                "abortCriteria": [{"metric": "http_req_failed", "name": None, "futureCriterionNull": None}],
            },
        }
    )

    payload = config.model_dump(by_alias=True, exclude_none=True)

    assert payload["futureConfigNull"] is None
    assert "duration" not in payload["options"]
    assert payload["options"]["futureOptionNull"] is None
    assert "targetRPS" not in payload["options"]["stages"][0]
    assert payload["options"]["stages"][0]["futureStageNull"] is None
    assert "name" not in payload["options"]["abortCriteria"][0]
    assert payload["options"]["abortCriteria"][0]["futureCriterionNull"] is None
