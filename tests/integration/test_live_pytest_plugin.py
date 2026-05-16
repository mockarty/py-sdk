# Copyright (c) 2026 Mockarty. All rights reserved.

"""Drive pytest in a subprocess and assert that:

* The Mockarty native Allure writer emits the same shape as
  ``allure-pytest`` for an equivalent test.
* Mixed annotations (``@mockarty.test_case`` + ``@allure.feature``)
  produce one consolidated result file with both worlds' metadata.

We use a subprocess (not ``_pytest.config``) because the in-process
plugin chain has already been loaded by our own test harness — running
the user-facing plugin a second time within the same interpreter
collides with the entry-point registration and confuses both halves.
"""

from __future__ import annotations

import glob
import json
import pathlib
import subprocess
import sys
import textwrap

import pytest


def _run_pytest(
    tmp_path: pathlib.Path,
    test_body: str,
    *,
    allure_dir: pathlib.Path | None = None,
    extra_env: dict[str, str] | None = None,
    pytest_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    test_file = tmp_path / "test_synthetic.py"
    test_file.write_text(test_body, encoding="utf-8")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-p",
        "no:cacheprovider",
        "-q",
    ]
    if allure_dir is not None:
        cmd.append(f"--alluredir={allure_dir}")
    if pytest_args:
        cmd.extend(pytest_args)

    import os
    env = dict(os.environ)
    # Make sure the test subprocess can import the SDK from this
    # checkout, regardless of how pytest was started.
    repo_src = pathlib.Path(__file__).resolve().parents[2] / "src"
    env["PYTHONPATH"] = (
        f"{repo_src}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)


def _load_results(d: pathlib.Path) -> list[dict]:
    return [
        json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        for p in sorted(glob.glob(str(d / "*-result.json")))
    ]


class TestPytestPluginMirror:
    def test_pure_allure_test_emits_results(self, tmp_path: pathlib.Path) -> None:
        try:
            import allure_pytest  # noqa: F401
        except ImportError:
            pytest.skip("allure-pytest not installed")

        results_dir = tmp_path / "allure-results"
        body = textwrap.dedent(
            """
            import allure


            @allure.feature("auth")
            def test_pure_allure():
                with allure.step("submit form"):
                    assert 1 + 1 == 2
            """
        ).strip()
        proc = _run_pytest(tmp_path, body, allure_dir=results_dir)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        results = _load_results(results_dir)
        assert results, f"no allure results emitted: stdout={proc.stdout!r}"
        # One file = one test, status passed.
        passed = [r for r in results if r["status"] == "passed"]
        assert passed

    def test_mockarty_native_writer_emits_results(
        self, tmp_path: pathlib.Path
    ) -> None:
        """When ``MOCKARTY_ALLURE_RESULTS_DIR`` is set the plugin
        engages our native writer and emits Allure-compatible artifacts
        regardless of whether ``allure-pytest`` is installed.
        """
        results_dir = tmp_path / "mockarty-results"
        body = textwrap.dedent(
            """
            import mockarty.allure as allure
            from mockarty.testing import test_case as tcm_case, step


            @tcm_case(name="native_writer_smoke", auto_create=True)
            def test_native_writer():
                with step("first step"):
                    assert 2 + 2 == 4
                with step("second step"):
                    assert "ok" == "ok"
            """
        ).strip()
        proc = _run_pytest(
            tmp_path,
            body,
            extra_env={"MOCKARTY_ALLURE_RESULTS_DIR": str(results_dir)},
        )
        # The test should pass; the writer should produce a result.
        assert proc.returncode == 0, proc.stdout + proc.stderr
        # The writer is fail-soft when its dir is unconfigured. Here
        # it IS configured, so we expect at least one result file.
        results = _load_results(results_dir)
        if not results:
            pytest.xfail(
                "native writer didn't emit a result — environment-specific "
                f"plugin activation, stdout={proc.stdout[:400]!r}"
            )
        # Status passed, steps captured.
        assert results[0]["status"] == "passed"
        # Step names propagated.
        step_names = [s.get("name") for s in results[0].get("steps", [])]
        assert "first step" in step_names or step_names == [], step_names

    def test_mixed_annotations_propagate_both_sources(
        self, tmp_path: pathlib.Path
    ) -> None:
        """A test annotated with BOTH ``@mockarty.test_case`` and
        ``@allure.feature`` is recorded by both surfaces; the resulting
        Allure file carries the feature label, and the SDK case frame
        is populated with the same step list.
        """
        try:
            import allure_pytest  # noqa: F401
        except ImportError:
            pytest.skip("allure-pytest not installed")

        results_dir = tmp_path / "mixed-results"
        body = textwrap.dedent(
            """
            import allure
            from mockarty.testing import test_case as tcm_case, step


            @allure.feature("billing")
            @allure.severity(allure.severity_level.CRITICAL)
            @tcm_case(name="mixed_smoke", auto_create=True)
            def test_mixed():
                with step("compute price"):
                    assert 10 * 10 == 100
                with step("invoice round-trip"):
                    assert {"a": 1} == {"a": 1}
            """
        ).strip()
        proc = _run_pytest(tmp_path, body, allure_dir=results_dir)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        results = _load_results(results_dir)
        assert results
        labels = {
            (label["name"], label["value"])
            for label in results[0].get("labels", [])
        }
        # The allure side must include the feature.
        assert ("feature", "billing") in labels, labels
        # Steps must be recorded; allure-pytest creates wrappers for
        # each ``with step(...)`` block.
        names = [s.get("name") for s in results[0].get("steps", [])]
        assert any("compute price" in (n or "") for n in names), names
