# Copyright (c) 2026 Mockarty. All rights reserved.

"""Offline tests for the LoadTest builder DSL → k6 script / perf-config.

These assert the EMITTED artefacts (script shape, options, perf-config dict)
without running anything. The local-run round-trip (config → perf engine →
requests > 0) is proven on the Go side in
``cmd/cli/cmd/perf_from_config_test.go``; here we verify the SDK produces a
config of exactly that shape.
"""

import json

from mockarty.builders import LoadTest


def test_basic_script_has_options_and_request():
    script = (
        LoadTest("smoke")
        .target("http://127.0.0.1:8080")
        .get("/health")
        .vus(5)
        .duration("30s")
        .to_k6_script()
    )
    assert "import http from 'k6/http'" in script
    assert "export const options" in script
    assert "export default function" in script
    assert "http.get(`${__ENV.BASE_URL}/health`)" in script
    # options encode the constant profile
    assert '"vus": 5' in script
    assert '"duration": "30s"' in script


def test_stages_take_priority_over_constant_vus():
    cfg = (
        LoadTest("ramp")
        .target("http://x")
        .get("/")
        .vus(99)  # ignored because stages present
        .stages([("10s", 20), ("30s", 20), ("5s", 0)])
        .to_perf_config()
    )
    assert cfg["stages"] == [
        {"duration": "10s", "target": 20},
        {"duration": "30s", "target": 20},
        {"duration": "5s", "target": 0},
    ]
    assert "vus" not in cfg  # stages win
    # script options also carry stages, not vus/duration
    script = cfg["script"]
    assert "stages" in script


def test_thresholds_collected():
    cfg = (
        LoadTest()
        .target("http://x")
        .threshold("http_req_duration", "p(95)<500")
        .threshold("http_req_duration", "p(99)<900")
        .threshold("http_req_failed", "rate<0.01")
        .to_perf_config()
    )
    assert cfg["thresholds"]["http_req_duration"] == ["p(95)<500", "p(99)<900"]
    assert cfg["thresholds"]["http_req_failed"] == ["rate<0.01"]


def test_post_body_json_content_type_and_serialization():
    script = (
        LoadTest()
        .target("http://api")
        .post("/cart", body={"sku": "abc", "qty": 2})
        .to_k6_script()
    )
    assert "http.post(`${__ENV.BASE_URL}/cart`" in script
    assert "application/json" in script
    # body is JSON-serialized into the script literal
    assert "sku" in script and "abc" in script


def test_env_exposed_and_base_url_defaulted():
    cfg = (
        LoadTest()
        .target("https://staging.example.com")
        .env(TOKEN="secret")
        .get("/")
        .to_perf_config()
    )
    assert cfg["environment"]["BASE_URL"] == "https://staging.example.com"
    assert cfg["environment"]["TOKEN"] == "secret"


def test_target_without_explicit_request_defaults_to_get_root():
    script = LoadTest().target("http://x").to_k6_script()
    assert "http.get(`${__ENV.BASE_URL}/`)" in script


def test_to_perf_config_is_valid_json_and_full_profile():
    profile = (
        LoadTest("checkout")
        .target("http://127.0.0.1:8080")
        .get("/health")
        .post("/order", body={"item": 1})
        .stages([("2s", 3)])
        .threshold("http_req_failed", "rate<0.1")
        .think_time(0.5)
    )
    raw = profile.to_json()
    parsed = json.loads(raw)  # must be valid JSON
    assert parsed["name"] == "checkout"
    assert parsed["script"].startswith("import http")
    assert parsed["stages"] == [{"duration": "2s", "target": 3}]
    assert parsed["thresholds"]["http_req_failed"] == ["rate<0.1"]
    assert "sleep(0.5)" in parsed["script"]


def test_rps_and_max_vus_flow_into_config_and_script():
    cfg = (
        LoadTest()
        .target("http://x")
        .get("/")
        .rps(100)
        .max_vus(50)
        .to_perf_config()
    )
    assert cfg["rps"] == 100
    assert cfg["maxVus"] == 50
    assert '"rps": 100' in cfg["script"]


def test_save_writes_file(tmp_path):
    p = tmp_path / "load.json"
    out = LoadTest("x").target("http://x").get("/").save(str(p))
    assert out == str(p)
    data = json.loads(p.read_text())
    assert data["name"] == "x"
    assert "script" in data
