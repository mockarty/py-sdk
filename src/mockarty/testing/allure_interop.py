# Copyright (c) 2026 Mockarty. All rights reserved.

"""Optional Allure interop.

When ``allure-pytest`` is installed in the user's project, every Mockarty
step is mirrored into an Allure step automatically, and every Mockarty
attachment is duplicated into the Allure report. This way users keep a
single source of truth in their tests (Mockarty decorators) and still
get a rich Allure report locally if they prefer it.

When Allure is NOT installed this module raises :class:`ImportError` at
import time, which the decorators module catches — Mockarty stepping
still works, just without the Allure mirror.
"""

from __future__ import annotations

# Re-export the bits we use, raising ImportError when allure-pytest is
# absent. The decorators module wraps this import in try/except so the
# absence is silent for end users.
from allure import attach as _allure_attach  # type: ignore[import-not-found]  # noqa: F401
from allure import step as _allure_step  # type: ignore[import-not-found]  # noqa: F401


def step(name: str):
    """Open an Allure step with ``name``."""
    return _allure_step(name)


def attach(body: bytes, *, name: str, content_type: str) -> None:
    """Mirror an attachment into the Allure report."""
    _allure_attach(body, name=name, attachment_type=content_type)
