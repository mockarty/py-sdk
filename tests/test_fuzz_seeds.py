# Copyright (c) 2026 Mockarty. All rights reserved.

"""Seed builder tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from mockarty.fuzz import Seed


def test_seed_requires_name():
    with pytest.raises(ValueError):
        Seed("", "x")


def test_seed_accepts_string_payload():
    s = Seed("a", "body")
    assert s.payload == "body"


def test_seed_accepts_bytes_payload_round_trips_latin1():
    raw = bytes(range(256))
    s = Seed("a", raw)
    assert s.payload.encode("latin-1") == raw


def test_seed_bytes_helper():
    s = Seed.bytes("a", b"\x00\xff")
    assert len(s.payload) == 2


def test_seed_from_file(tmp_path: Path):
    p = tmp_path / "login.json"
    p.write_text('{"u": 1}', encoding="utf-8")
    s = Seed.from_file(p)
    assert s.name == "login"
    assert s.payload == '{"u": 1}'


def test_seed_from_file_with_explicit_name(tmp_path: Path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"\x01\x02")
    s = Seed.from_file(p, name="custom", content_type="application/octet-stream")
    assert s.name == "custom"
    assert s.content_type == "application/octet-stream"


def test_seed_to_request_uses_defaults_when_missing():
    s = Seed("a", "body")
    req = s.to_request(
        default_method="POST",
        default_url="https://api",
        default_path="/login",
        default_content_type="application/json",
    )
    assert req.method == "POST"
    assert req.url == "https://api"
    assert req.path == "/login"
    assert req.content_type == "application/json"
    assert req.body == "body"
    assert req.id == "a"


def test_seed_to_request_explicit_fields_override_defaults():
    s = Seed(
        "a",
        "body",
        method="DELETE",
        url="https://override",
        path="/other",
        content_type="text/plain",
        headers={"X": "1"},
        query_params={"q": "v"},
    )
    req = s.to_request(
        default_method="GET",
        default_url="https://api",
        default_path="/default",
    )
    assert req.method == "DELETE"
    assert req.url == "https://override"
    assert req.path == "/other"
    assert req.content_type == "text/plain"
    assert req.headers == {"X": "1"}
    assert req.query_params == {"q": "v"}


def test_seed_equality_and_hash():
    a = Seed("x", "p")
    b = Seed("x", "p")
    c = Seed("x", "q")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert a != "not-a-seed"
    # ensure it's set-friendly
    assert len({a, b, c}) == 2


def test_seed_repr_truncates_long_payload():
    s = Seed("x", "a" * 100)
    r = repr(s)
    assert r.startswith("Seed(name='x'")
    assert "..." in r


def test_seed_repr_handles_newlines():
    s = Seed("x", "a\nb")
    r = repr(s)
    assert "\\n" in r


def test_seed_unicode_payload():
    s = Seed("u", "Привет 🎉")
    req = s.to_request()
    assert req.body == "Привет 🎉"
