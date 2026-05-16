# Copyright (c) 2026 Mockarty. All rights reserved.

"""Tests for ``mockarty.pact.types`` — spec-version coercion + models."""

from __future__ import annotations

import pytest

from mockarty.pact.types import (
    Interaction,
    Metadata,
    Pact,
    Pacticipant,
    PactSpecification,
    PluginEntry,
    ProviderState,
    RequestPart,
    ResponsePart,
    SpecVersion,
    coerce_spec_version,
    freeze_headers,
)


class TestCoerceSpecVersion:
    @pytest.mark.parametrize(
        "value",
        ["V3", "v3", "3", "3.0", "3.0.0", SpecVersion.V3],
    )
    def test_v3_forms(self, value):
        assert coerce_spec_version(value) is SpecVersion.V3

    @pytest.mark.parametrize(
        "value",
        ["V4", "v4", "4", "4.0", "4.0.0", SpecVersion.V4],
    )
    def test_v4_forms(self, value):
        assert coerce_spec_version(value) is SpecVersion.V4

    @pytest.mark.parametrize("value", ["", "1.0.0", "v5", "abc", "V3.5"])
    def test_invalid_raises(self, value):
        with pytest.raises(ValueError):
            coerce_spec_version(value)


def test_pact_model_roundtrip():
    p = Pact(
        consumer=Pacticipant(name="A"),
        provider=Pacticipant(name="B"),
        interactions=[
            Interaction(
                description="hello",
                provider_states=[ProviderState(name="state", params={"k": 1})],
                request=RequestPart(method="GET", path="/x"),
                response=ResponsePart(status=204),
            ),
        ],
        metadata=Metadata(
            pactSpecification=PactSpecification(version="4.0"),
        ),
    )
    raw = p.model_dump(mode="json", by_alias=True)
    assert raw["interactions"][0]["request"]["method"] == "GET"
    assert raw["metadata"]["pactSpecification"]["version"] == "4.0"

    again = Pact.model_validate(raw)
    assert again == p


def test_freeze_headers_handles_none_and_mixed_types():
    assert freeze_headers(None) == {}
    assert freeze_headers({}) == {}
    out = freeze_headers({"X-A": 1, "X-B": "two"})
    assert out == {"X-A": "1", "X-B": "two"}


def test_plugin_entry_defaults():
    p = PluginEntry(name="protobuf")
    assert p.version == ""
    assert p.configuration == {}
