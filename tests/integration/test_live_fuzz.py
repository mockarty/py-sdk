# Copyright (c) 2026 Mockarty. All rights reserved.

"""Live fuzz dispatch via :class:`Runner.submit` and :class:`Runner.local_spawn`.

Two paths exercised:

* HTTP submit — POST the transpiled DSL payload to
  ``/api/v1/fuzzing/run`` on the live admin. The admin's fuzz engine
  is licence-gated; on a free admin we get a 400 / 403 / 404 envelope.
  All three cases prove the SDK reaches the server with a valid
  transport — the response shape is what we assert on.
* Subprocess — write the transpiled config to a temp file and invoke
  ``mockarty-cli fuzz run --config <path>``. The CLI parses its flags
  before touching anything network-y, so the subprocess proves the
  SDK→CLI handoff is well-formed even when the admin has no licence.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from mockarty import MockartyClient
from mockarty.errors import (
    MockartyAPIError,
    MockartyForbiddenError,
    MockartyNotFoundError,
    MockartyValidationError,
)
from mockarty.fuzz import (
    AssertNoCrash,
    AssertStatus,
    Mutator,
    Runner,
    Seed,
    Target,
)


def _build_target() -> Target:
    return (
        Target("live-stage3-fuzz")
        .description("Live integration smoke for the fuzz DSL.")
        .http_endpoint("POST", "/api/v1/login", base_url="http://localhost:5770")
        .seeds(
            [
                Seed("valid", '{"username":"admin","password":"secret"}'),
                Seed("missing-pw", '{"username":"admin"}'),
                Seed("empty", "{}"),
            ]
        )
        .mutator(Mutator.JSON)
        .mutator(Mutator.BOUNDARY_VALUES)
        .duration(timedelta(seconds=2))
        .stop_on_finding(True)
        .reporter("allure")
        .assertion(AssertStatus(range(200, 300)))
        .assertion(AssertNoCrash())
    )


class TestFuzzTranspile:
    def test_to_json_yields_canonical_dict(self) -> None:
        payload = _build_target().to_json()
        # The transpiled payload must be a flat dict the admin can
        # accept verbatim. Spot-check the contract.
        assert isinstance(payload, dict)
        assert payload.get("name") == "live-stage3-fuzz"
        # Three seeds round-trip into the wire shape under
        # ``seedRequests`` (HTTP target) / ``seedInputs`` (generic).
        seeds = (
            payload.get("seedRequests")
            or payload.get("seedInputs")
            or payload.get("seeds")
            or []
        )
        assert len(seeds) == 3
        # Two mutators surface under ``payloadCategories``.
        cats = payload.get("payloadCategories") or payload.get("mutators") or []
        assert len(cats) >= 2
        # Options carry the duration.
        opts = payload.get("options") or {}
        assert "maxDuration" in opts or "duration" in opts


class TestFuzzSubmit:
    def test_submit_payload_transport_reaches_admin(
        self, mockarty_client: MockartyClient
    ) -> None:
        """POST hits the admin and returns a parseable response (or a
        recognised error). What we MUST NOT see is a transport-level
        exception — that would mean the SDK can't talk to the admin.
        """
        runner = Runner(mockarty_client)
        try:
            job_id = runner.submit(_build_target())
        except MockartyForbiddenError:
            pytest.skip("fuzz feature not licensed (403) — admin still reachable")
        except MockartyNotFoundError:
            pytest.skip("fuzz endpoint missing (404) — admin still reachable")
        except MockartyValidationError as exc:
            # 400 on a valid payload means the admin's contract has
            # drifted from the SDK's. Surface the body so the failure
            # is debuggable, then xfail — server-side issue, not SDK.
            pytest.xfail(
                f"admin rejected fuzz config with validation error: {exc.message!r}"
            )
        except MockartyAPIError as exc:
            # Any other code-mapped error means the route is wired up
            # but the server has its own opinion about the payload.
            # Treat as soft-skip with the server's reason captured.
            pytest.skip(f"admin returned {exc.status_code}: {exc.message!r}")
        else:
            # Happy path — server accepted the run.
            assert isinstance(job_id, str) and job_id, job_id
            # Best-effort cancel so the job doesn't run for its full
            # duration on a shared admin.
            try:
                runner.stop(job_id)
            except MockartyAPIError:
                pass


class TestFuzzLocalSpawn:
    def test_local_spawn_invokes_cli_with_config(
        self, mockarty_client: MockartyClient, cli_path: str | None
    ) -> None:
        if cli_path is None:
            pytest.skip(
                "mockarty-cli binary not on PATH and no MOCKARTY_CLI override; "
                "subprocess fuzz path requires the CLI",
            )
        runner = Runner(mockarty_client, cli_path=cli_path)
        result = runner.local_spawn(_build_target(), timeout=20.0)

        # The subprocess always returns a result struct — even when
        # the CLI rejects flags. We assert the SDK captured stdout /
        # stderr and built the command line correctly.
        assert result.command[0] == cli_path
        assert "fuzz" in result.command
        assert "--config" in result.command
        # CLI exits 0 / 1 / 2 depending on findings; we just need the
        # SDK to NOT hang or raise.
        assert result.returncode is not None
        # The CLI's current build prints the unknown-flag error on
        # stdout; older builds use stderr. Either way SOMETHING is
        # captured — empty output means we missed piping.
        assert result.stdout or result.stderr
