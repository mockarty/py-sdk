"""Unit tests for mockarty.protocols.telemetry."""

from __future__ import annotations

import threading

import pytest

from mockarty.protocols.telemetry import (
    AccumulatingRecorder,
    NopRecorder,
    Step,
    new_step_key,
)


def test_nop_recorder_drops_step():
    rec = NopRecorder()
    rec.record(Step(key="k", name="n"))  # must not raise


def test_accumulating_recorder_buffers_steps():
    rec = AccumulatingRecorder()
    assert len(rec) == 0
    rec.record(Step(key="k1", name="n1"))
    rec.record(Step(key="k2", name="n2", status="failed"))
    assert len(rec) == 2
    payloads = rec.steps()
    assert payloads[0]["stepKey"] == "k1"
    assert payloads[0]["status"] == "passed"
    assert payloads[1]["status"] == "failed"


def test_accumulating_recorder_clear():
    rec = AccumulatingRecorder()
    rec.record(Step(key="k", name="n"))
    rec.clear()
    assert len(rec) == 0
    assert rec.steps() == []


def test_accumulating_recorder_raw_steps_returns_copy():
    rec = AccumulatingRecorder()
    rec.record(Step(key="k", name="n"))
    raw = rec.raw_steps()
    raw.append(Step(key="x", name="x"))  # mutating the copy must not affect rec
    assert len(rec) == 1


def test_accumulating_recorder_is_thread_safe():
    rec = AccumulatingRecorder()
    barrier = threading.Barrier(8)

    def worker(idx: int) -> None:
        barrier.wait()
        for i in range(100):
            rec.record(Step(key=f"k-{idx}-{i}", name="n"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(rec) == 800


def test_step_to_payload_empty_fields_omitted():
    payload = Step(key="k", name="n").to_payload()
    assert payload == {"stepKey": "k", "name": "n", "status": "passed"}


def test_step_to_payload_status_defaults_to_passed():
    payload = Step(key="k", name="n", status="").to_payload()
    assert payload["status"] == "passed"


def test_step_to_payload_duration_derived_from_timestamps():
    s = Step(key="k", name="n", started_at=1000.0, finished_at=1000.250)
    payload = s.to_payload()
    assert payload["durationMs"] == 250


def test_step_to_payload_includes_parameters_and_extras():
    s = Step(
        key="k",
        name="n",
        parameters={"http_status": "200", "operation": "GetUser"},
        message="ok",
        stack_trace="line 1\nline 2",
        parent_key="parent#1",
    )
    p = s.to_payload()
    assert p["parameters"] == {"http_status": "200", "operation": "GetUser"}
    assert p["message"] == "ok"
    assert p["stackTrace"] == "line 1\nline 2"
    assert p["parentKey"] == "parent#1"


def test_step_to_payload_explicit_duration_wins_over_derived():
    s = Step(
        key="k", name="n",
        started_at=1000.0, finished_at=1000.250,
        duration_ms=999,
    )
    assert s.to_payload()["durationMs"] == 999


def test_new_step_key_format():
    assert new_step_key("topic/op", 42) == "topic/op#42"


@pytest.mark.parametrize("name,seq", [("", 0), ("x", 1), ("a/b/c#extra", 7)])
def test_new_step_key_is_stable(name: str, seq: int):
    assert new_step_key(name, seq) == f"{name}#{seq}"
