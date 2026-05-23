"""Unit tests for mockarty.protocols.telemetry."""

from __future__ import annotations

import threading

import pytest

from mockarty.protocols.telemetry import (
    AccumulatingRecorder,
    NopRecorder,
    Step,
    cap_preview,
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


# cap_preview tests — UTF-8 boundary handling identical to the Go SDK.

def test_cap_preview_zero_cap_returns_empty():
    assert cap_preview("hello", 0) == ""
    assert cap_preview(b"hello", -1) == ""


def test_cap_preview_none_returns_empty():
    assert cap_preview(None, 10) == ""


def test_cap_preview_cap_larger_than_body_returns_full():
    assert cap_preview("hello", 100) == "hello"
    assert cap_preview(b"hi", 100) == "hi"


def test_cap_preview_ascii_truncates_with_marker():
    out = cap_preview("0123456789ABCDEF", 5)  # 16 bytes
    assert out == "01234…(truncated 11B)"


def test_cap_preview_utf8_rounds_down_to_rune_boundary():
    # "Привет" — 6 Cyrillic chars × 2 bytes each = 12 bytes.
    # cap=5 lands in the middle of "и" (D0 B8); the fix rounds
    # down to byte 4 (start of "и") and emits "Пр" + marker.
    out = cap_preview("Привет", 5)
    assert out == "Пр…(truncated 8B)"
    # No replacement char in the preserved prefix.
    assert "�" not in out


def test_cap_preview_utf8_cut_exactly_on_boundary():
    # cap=4 = exactly between "р" and "и" — no rounding needed.
    assert cap_preview("Привет", 4) == "Пр…(truncated 8B)"


def test_cap_preview_accepts_bytes_str_and_objects():
    assert cap_preview(b"raw", 100) == "raw"
    assert cap_preview("str", 100) == "str"
    assert cap_preview(42, 100) == "42"
    assert cap_preview({"k": "v"}, 100).startswith("{")
