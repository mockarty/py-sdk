# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""{{var}} interpolation — mirrors sdk/go-sdk/tester/interpolate.go."""

from __future__ import annotations

from typing import Mapping


def interpolate(s: str, variables: Mapping[str, str]) -> str:
    """Replace each ``{{name}}`` token in *s* with ``variables[name]``.

    Unknown names render as the literal ``{{name}}`` so failures are
    visible. Returns the original string when no ``{{`` substring is
    present (allocation-conscious path).
    """
    if "{{" not in s:
        return s
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        if i + 1 < n and s[i] == "{" and s[i + 1] == "{":
            end = s.find("}}", i + 2)
            if end < 0:
                out.append(s[i:])
                break
            name = s[i + 2 : end].strip()
            if name in variables:
                out.append(variables[name])
            else:
                out.append(s[i : end + 2])
            i = end + 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def interpolate_args(args, variables: Mapping[str, str]):
    """Apply ``interpolate`` to every string element of *args*; pass
    non-strings through unchanged. Mirrors ``interpolateArgs`` in Go."""
    return [interpolate(a, variables) if isinstance(a, str) else a for a in args]
