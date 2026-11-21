"""Compare Ruff diagnostics to the published source before the CI repair.

Lint counts are tracked by file and rule message. The formatter reports a
single diagnostic for each unformatted file.
"""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory


BASELINE = "606f9b91864f3467643d3ef0cd1910e92c7ea04b"


def diagnostics(root: Path, config: Path, *args: str) -> list[dict]:
    result = subprocess.run(
        [
            "ruff",
            *args,
            "--config",
            config,
            "--target-version",
            "py39",
            "--output-format",
            "json",
            "src/",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        text=True,
    )
    if result.returncode not in (0, 1):
        result.check_returncode()
    return json.loads(result.stdout)


def compare(baseline: Path, current: Path, *args: str) -> int:
    config = current / "pyproject.toml"
    previous = diagnostics(baseline, config, *args)
    present = diagnostics(current, config, *args)
    allowance = Counter(
        (Path(item["filename"]).relative_to(baseline), item["code"], item["message"])
        for item in previous
    )
    regressions = 0
    for item in present:
        path = Path(item["filename"]).relative_to(current)
        key = (path, item["code"], item["message"])
        if allowance[key]:
            allowance[key] -= 1
            continue
        row = item["location"]["row"]
        print(f"{path}:{row}: {item['code']} {item['message']}")
        regressions += 1
    print(
        f"Ruff {args[0]}: {regressions} new, {len(present) - regressions} existing diagnostics"
    )
    return regressions


def main() -> int:
    current = Path(__file__).resolve().parent.parent
    with TemporaryDirectory() as staging:
        baseline = Path(staging).resolve()
        archive = baseline / "src.tar"
        subprocess.run(
            ["git", "archive", "-o", archive, BASELINE, "src"], cwd=current, check=True
        )
        subprocess.run(["tar", "-xf", archive, "-C", baseline], check=True)
        regressions = compare(baseline, current, "check")
        regressions += compare(baseline, current, "format", "--check")
    return int(regressions != 0)


if __name__ == "__main__":
    sys.exit(main())
