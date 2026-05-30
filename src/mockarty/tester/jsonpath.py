# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Minimal JSONPath walker — mirrors sdk/go-sdk/tester/jsonpath.go.

Supports::

    $            → document root
    $.a.b.c      → nested object keys
    $.arr[0]     → array index
    $.arr[-1]    → last element
    $.arr[*]     → every element (returns a list)
    $.arr[0].x   → combined

Anything fancier (filters, recursive descent) is intentionally excluded
to keep the SDK dep-free. Callers that need full JSONPath plug in their
own resolver.
"""

from __future__ import annotations

from typing import Any


class JSONPathError(ValueError):
    pass


def resolve_jsonpath(root: Any, path: str) -> Any:
    if path == "" or path == "$":
        return root
    if not path.startswith("$"):
        raise JSONPathError(f"jsonpath must start with $: {path!r}")
    segments = _split_path(path[1:])
    cur = root
    for i, seg in enumerate(segments):
        try:
            cur = _step(cur, seg)
        except JSONPathError as e:
            raise JSONPathError(f"at {''.join(segments[: i + 1])}: {e}") from e
    return cur


def _split_path(s: str) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == ".":
            i += 1
            j = i
            while j < len(s) and s[j] != "." and s[j] != "[":
                j += 1
            if j == i:
                raise JSONPathError(f"empty segment at offset {i}")
            out.append(s[i:j])
            i = j
        elif c == "[":
            end = s.find("]", i)
            if end < 0:
                raise JSONPathError(f"unterminated [ at offset {i}")
            out.append(s[i : end + 1])
            i = end + 1
        else:
            raise JSONPathError(f"unexpected char {c!r} at offset {i}")
    return out


def _step(cur: Any, seg: str) -> Any:
    if seg.startswith("["):
        inner = seg[1:-1]
        if not isinstance(cur, list):
            raise JSONPathError(f"indexer on non-array ({type(cur).__name__})")
        if inner == "*":
            return list(cur)
        try:
            idx = int(inner)
        except ValueError as e:
            raise JSONPathError(f"invalid index {inner!r}") from e
        if idx < 0:
            idx += len(cur)
        if idx < 0 or idx >= len(cur):
            raise JSONPathError(f"index {inner} out of range (len={len(cur)})")
        return cur[idx]
    if not isinstance(cur, dict):
        raise JSONPathError(f"key access on non-object ({type(cur).__name__})")
    if seg not in cur:
        raise JSONPathError(f"key {seg!r} not found")
    return cur[seg]


def equal_json_scalar(got: Any, want: Any) -> bool:
    """Loose equality used by Expect assertions — numbers compare by
    float, everything else by Python ``==``."""
    if got is None and want is None:
        return True
    if got is None or want is None:
        return False
    if isinstance(want, bool) and isinstance(got, bool):
        return got == want
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return float(got) == float(want)
    return got == want
