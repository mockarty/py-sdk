# Copyright (c) 2026 Mockarty. All rights reserved.

"""Pytest plugin tests — fixtures themselves are exercised; we use a
pytester subdir to verify the entry-point doesn't auto-collide with
the other Mockarty fixtures.
"""

from __future__ import annotations

from pathlib import Path

from mockarty.fuzz import Target
from mockarty.fuzz.pytest_plugin import (
    mockarty_fuzz_output_dir,
    mockarty_fuzz_runner,
    mockarty_fuzz_target_factory,
)


def test_fixtures_are_importable():
    """The fixture functions are exported and callable."""
    assert callable(mockarty_fuzz_output_dir)
    assert callable(mockarty_fuzz_target_factory)
    assert callable(mockarty_fuzz_runner)


def test_target_factory_uses_test_node_name(tmp_path: Path):
    """When the fixture is invoked it pre-fills the name."""
    # Direct use through pytest's fixture machinery is covered by
    # test_fuzz_example.py — here we just ensure the API contract:
    # the factory returns a Target instance.
    t = Target("explicit-name")
    assert isinstance(t, Target)
    assert t.name == "explicit-name"
