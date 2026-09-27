# Copyright (c) 2026 Mockarty. All rights reserved.
# Licensed under the Mockarty SDK License Agreement. See LICENSE file for details.

"""Bounded, loss-aware Allure media preflight shared by directory uploads."""
from pathlib import Path
from typing import Any


def read_source(directory: str, source: str, limit: int) -> bytes:
    if not isinstance(source, str) or not source or "\\" in source or ":" in source:
        raise ValueError("allure: invalid source path")
    parts = source.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("allure: invalid source path")
    path = Path(directory)
    for part in parts:
        path /= part
        if path.is_symlink():
            raise ValueError(f"allure: source {source!r} is a symlink")
    if not path.is_file():
        raise ValueError(f"allure: source {source!r} is not a regular file")
    with path.open("rb") as file:
        body = file.read(limit + 1)
    if not body or len(body) > limit:
        raise ValueError(f"allure: source {source!r} is empty or exceeds {limit} bytes")
    return body


def collect_media(doc: dict[str, Any], directory: str):
    steps, attachments = [], []
    paths: dict[str, list[str]] = {}
    total = 0

    def visit(node, path, prefix, depth):
        nonlocal total
        if not isinstance(node, dict):
            raise ValueError(f"allure: invalid object at {path}")
        if depth > 64:
            raise ValueError("allure: step depth exceeds 64")
        refs = node.get("attachments") or []
        if not isinstance(refs, list):
            raise ValueError(f"allure: invalid attachments at {path}")
        for att in refs:
            if not isinstance(att, dict):
                raise ValueError(f"allure: invalid attachment at {path}")
            source = att.get("source")
            if not isinstance(source, str):
                raise ValueError("allure: missing attachment source")
            if source not in paths:
                if len(attachments) >= 32:
                    raise ValueError("allure: more than 32 attachments per result")
                body = read_source(directory, source, 256 << 10)
                total += len(body)
                if total > 1 << 20:
                    raise ValueError("allure: result attachments exceed 1 MiB")
                attachments.append({"name": att.get("name") or source, "body": body,
                                    "contentType": att.get("type") or "application/octet-stream"})
                paths[source] = []
            paths[source].append(path)
        children = node.get("steps") or []
        if not isinstance(children, list):
            raise ValueError(f"allure: invalid steps at {path}")
        for index, step in enumerate(children):
            if not isinstance(step, dict):
                raise ValueError(f"allure: invalid step at {path}")
            if len(steps) >= 5000:
                raise ValueError("allure: more than 5000 steps")
            child_path = f"{path}/steps/{index}"
            status = str(step.get("status") or "").strip().lower()
            if status not in ("passed", "failed", "skipped", "broken"):
                status = "broken"
            detail = step.get("statusDetails") or {}
            error = (str(detail.get("message") or "") + "\n" + str(detail.get("trace") or "")).strip()
            start, stop = step.get("start"), step.get("stop")
            duration = max(0, int(stop) - int(start)) if start is not None and stop is not None else 0
            name = step.get("name") or ""
            if prefix:
                name = prefix + " / " + name
            steps.append({"name": name, "status": status, "error": error,
                          "durationMs": duration, "metadata": {"allurePath": child_path}})
            visit(step, child_path, name, depth + 1)

    visit(doc, "result", "", 0)
    return steps, attachments, paths, total
