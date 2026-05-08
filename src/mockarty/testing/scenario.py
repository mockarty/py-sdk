# Copyright (c) 2026 Mockarty. All rights reserved.

"""High-level scenario context manager.

Usage::

    from mockarty import MockartyClient
    from mockarty.testing import scenario, step

    with MockartyClient() as client:
        with scenario("E2E login", client=client) as s:
            with step("seed mock"):
                s.mock(MockBuilder.http("/auth/login", "POST")
                       .respond(200, body={"token": "abc"})
                       .build())
            with step("call under test"):
                response = my_app.login(username="...", password="...")
                assert response.status_code == 200

The scenario:
    * Tracks any mocks created via ``s.mock()`` and deletes them on exit
      (matches :func:`mockarty.testing.fixtures.mock_cleanup` semantics).
    * Mirrors the case lifecycle from :func:`mockarty.testing.decorators.test_case`
      so :func:`mockarty.testing.decorators.attach` and ``with step()``
      work inside.
    * Captures the final pass/fail outcome so the plugin can ship it as a
      synthetic case run when an active fixture / client is provided.

Scenarios are intentionally simple — heavy entity orchestration belongs
in TCM cases proper. The DSL exists to give users a single ``with`` block
that ties seed mocks + assertions + reporting together inside any test
runner (pytest, unittest, plain script).
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Optional

from mockarty.testing import context as _ctx


class Scenario(AbstractContextManager["Scenario"]):
    """Active scenario binding. Use :func:`scenario` to construct."""

    def __init__(
        self,
        name: str,
        *,
        client: Any = None,
        case_id: Optional[str] = None,
        plan: Optional[str] = None,
        auto_create_case: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("scenario(name=...) requires a non-empty name")
        self.name = name
        self.client = client
        self.case_id = case_id
        self.plan = plan
        self.auto_create_case = auto_create_case
        self.metadata = dict(metadata) if metadata else {}
        self._created_mock_ids: list[str] = []
        self._frame: Optional[_ctx.CaseFrame] = None

    def __enter__(self) -> "Scenario":
        self._frame = _ctx.CaseFrame(
            case_id=self.case_id,
            case_name=self.name,
            plan_id=self.plan,
            auto_create=self.auto_create_case if self.case_id is None else False,
            metadata=dict(self.metadata),
        )
        _ctx.push_case(self._frame)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Tear down ad-hoc mocks first — they are the only side-effect the
        # scenario itself owns. The plugin is responsible for case-run
        # finalisation; we just pop the frame.
        if self.client is not None:
            for mock_id in self._created_mock_ids:
                try:
                    self.client.mocks.delete(mock_id)
                except Exception:
                    # Don't shadow the test failure if cleanup blows up.
                    pass
        _ctx.pop_case()
        self._frame = None

    # ── Mock seeding ──────────────────────────────────────────────────

    def mock(self, mock_or_builder: Any) -> Any:
        """Create a mock and track it for auto-cleanup on scenario exit.

        Accepts either a :class:`mockarty.models.mock.Mock` or anything
        that has a ``.build()`` method (e.g. a builder). Returns the
        created mock as the SDK does.
        """
        if self.client is None:
            raise RuntimeError(
                "scenario.mock() requires the scenario to be initialised with client="
            )
        if hasattr(mock_or_builder, "build"):
            mock_or_builder = mock_or_builder.build()
        result = self.client.mocks.create(mock_or_builder)
        # SDK convention: result.mock holds the created object.
        created = getattr(result, "mock", result)
        if getattr(created, "id", None):
            self._created_mock_ids.append(created.id)
        return created

    # ── Metadata helpers ──────────────────────────────────────────────

    def set_metadata(self, **kwargs: Any) -> None:
        """Merge kv pairs into the current case-frame metadata."""
        if self._frame is not None:
            self._frame.metadata.update(kwargs)


def scenario(
    name: str,
    *,
    client: Any = None,
    case_id: Optional[str] = None,
    plan: Optional[str] = None,
    auto_create_case: bool = True,
    metadata: Optional[dict[str, Any]] = None,
) -> Scenario:
    """Construct a scenario context manager.

    See module docstring for usage.
    """
    return Scenario(
        name,
        client=client,
        case_id=case_id,
        plan=plan,
        auto_create_case=auto_create_case,
        metadata=metadata,
    )
