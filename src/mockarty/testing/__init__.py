# Copyright (c) 2026 Mockarty. All rights reserved.

"""Mockarty test framework — pytest plugin + decorators + scenario DSL.

Public surface (the Allure-but-better story):

    Decorators / context managers
        - test_case(case_id=..., name=..., plan=..., auto_create=...)
        - step("...")             — decorator OR context manager
        - attach_report           — opt-in: upload outcome + attachments after the test
        - plan("plan-id")         — declare owning Test Plan
        - attach(name, body, ...) — register a small artifact for upload

    DSL
        - scenario("name", client=...)  — context manager for ad-hoc scenarios

    Fixtures (pytest-injected)
        - mockarty_client         — auto-closes after the test
        - mock_cleanup            — auto-deletes mocks created via the fixture

    Plugin
        - The pytest plugin is auto-loaded via the ``pytest11`` entry
          point declared in ``pyproject.toml``. After ``pip install
          mockarty`` you get the fixtures + decorators ready out of the
          box; no ``conftest.py`` boilerplate needed.

Example::

    from mockarty.testing import test_case, step, attach_report, attach

    @test_case("CASE-LOGIN-1", plan="qa-smoke")
    @attach_report
    def test_login(mockarty_client):
        with step("seed mock"):
            ...
        with step("login flow"):
            response = my_app.login(...)
            attach("response.json", response.text, content_type="application/json")
            assert response.status_code == 200
"""

from mockarty.testing.decorators import (
    attach,
    attach_report,
    plan,
    step,
    test_case,
)
from mockarty.testing.fixtures import mock_cleanup, mockarty_client
from mockarty.testing.scenario import Scenario, scenario

__all__ = [
    "Scenario",
    "attach",
    "attach_report",
    "mock_cleanup",
    "mockarty_client",
    "plan",
    "scenario",
    "step",
    "test_case",
]
