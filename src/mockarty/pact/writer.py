# Copyright (c) 2026 Mockarty. All rights reserved.

"""Serialise a :class:`mockarty.pact.types.Pact` to V3- or V4-shaped JSON.

The writer is intentionally separated from the model so that we can
unit-test the V3↔V4 transformation in isolation. The flow is:

1. The DSL builds a :class:`Pact` model populated with raw bodies that
   may contain :class:`Matcher` sentinels.
2. The writer walks each interaction's request + response body,
   replacing matchers with their example values and accumulating
   ``matchingRules`` entries.
3. The writer dumps the model to a dict, then post-processes the
   shape to match the spec version (V3 flattens, V4 nests).

Determinism: we sort keys at the top level of each interaction so
two runs of the same test produce byte-identical pact.json files.
This matters because pact.json files are typically committed to git
or compared in CI.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from mockarty.pact.matchers import Matcher
from mockarty.pact.types import Interaction, Pact, SpecVersion


# Sentinel used in path encoding to denote an array index — kept as a
# tuple so we can distinguish "field named '0'" from "array index 0"
# when reconstructing the JSONPath / category-path string.
_ARRAY = object()


def _walk(
    body: Any,
    path: List[Any],
    rules: Dict[str, Any],
    spec: SpecVersion,
) -> Any:
    """Recursively replace matchers with their examples; collect rules.

    ``path`` is a stack of (key|index|_ARRAY) elements describing where
    we are inside the body. ``rules`` is the V3-flat accumulator that
    the V4 transformer later expands.
    """

    if isinstance(body, Matcher):
        rule = body.rule_for(spec)
        if rule:
            rules[_path_to_v3(path)] = rule
        # Recurse into the example so nested matchers inside (e.g.
        # `Like({"id": Like(1)})`) get unwrapped too.
        return _walk(body.example, path, rules, spec)
    if isinstance(body, dict):
        return {k: _walk(v, path + [str(k)], rules, spec) for k, v in body.items()}
    if isinstance(body, list):
        return [_walk(v, path + [_ARRAY, i], rules, spec) for i, v in enumerate(body)]
    if isinstance(body, (bytes, bytearray)):
        # V4 binary body — encode as a base64 envelope dict so the
        # pact.json stays valid UTF-8 JSON. V3 doesn't formally support
        # this, but a base64 string is still legal there.
        return {
            "contentType": "application/octet-stream",
            "encoded": "base64",
            "content": base64.b64encode(bytes(body)).decode("ascii"),
        }
    return body


def _path_to_v3(path: List[Any]) -> str:
    """Render a path stack as a V3 JSONPath-ish key.

    ``["body", "user", _ARRAY, 0, "id"]`` → ``"$.body.user[0].id"``.
    The leading ``$`` and the ``body`` / ``header`` / ``path`` prefix
    are added by the caller; this helper produces the suffix.
    """

    out = ["$"]
    i = 0
    while i < len(path):
        seg = path[i]
        if seg is _ARRAY:
            i += 1
            out.append(f"[{path[i]}]")
        else:
            out.append(f".{seg}")
        i += 1
    return "".join(out)


def _build_v3_part_rules(
    body_rules: Dict[str, Any],
    header_rules: Dict[str, Any],
) -> Dict[str, Any]:
    """Combine the per-part V3 ``matchingRules`` dict (flat keys).

    V3 keeps everything under one ``matchingRules`` object on each
    request / response with flat ``$.body...`` and ``$.headers...`` keys.
    """

    out: Dict[str, Any] = {}
    for k, v in body_rules.items():
        # ``$`` (the root) is stored as ``$.body`` per V3 convention.
        out[f"$.body{k[1:]}" if k != "$" else "$.body"] = v
    for k, v in header_rules.items():
        # Headers in V3 use ``$.headers.X`` form.
        clean = k[2:] if k.startswith("$.") else k
        out[f"$.headers.{clean}"] = v
    return out


def _build_v4_part_rules(
    body_rules: Dict[str, Any],
    header_rules: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the V4 nested ``matchingRules`` block."""

    out: Dict[str, Any] = {}
    if body_rules:
        out["body"] = body_rules
    if header_rules:
        # V4 header matcher entries are keyed by header name (no JSONPath).
        out["header"] = {
            (k[2:] if k.startswith("$.") else k): v for k, v in header_rules.items()
        }
    return out


def _process_interaction(
    interaction: Interaction,
    spec: SpecVersion,
) -> Interaction:
    """Return a copy of the interaction with bodies materialised + rules
    populated. Pure function — does not mutate the input.
    """

    req_body_rules: Dict[str, Any] = {}
    req_header_rules: Dict[str, Any] = {}
    resp_body_rules: Dict[str, Any] = {}
    resp_header_rules: Dict[str, Any] = {}

    new_req_body = _walk(interaction.request.body, [], req_body_rules, spec)
    new_req_headers = {
        k: _walk(v, [], req_header_rules, spec)
        for k, v in interaction.request.headers.items()
    }
    new_resp_body = _walk(interaction.response.body, [], resp_body_rules, spec)
    new_resp_headers = {
        k: _walk(v, [], resp_header_rules, spec)
        for k, v in interaction.response.headers.items()
    }

    # Strip header rules whose keys are just ``$`` (unmatched at the
    # value level). They came from non-matcher values in headers; nothing
    # to record there.
    req_header_rules = {k: v for k, v in req_header_rules.items() if k != "$"}
    resp_header_rules = {k: v for k, v in resp_header_rules.items() if k != "$"}

    if spec is SpecVersion.V3:
        req_rules = _build_v3_part_rules(req_body_rules, req_header_rules)
        resp_rules = _build_v3_part_rules(resp_body_rules, resp_header_rules)
    else:
        req_rules = _build_v4_part_rules(req_body_rules, req_header_rules)
        resp_rules = _build_v4_part_rules(resp_body_rules, resp_header_rules)

    new_request = interaction.request.model_copy(
        update={
            "body": new_req_body,
            "headers": new_req_headers,
            "matching_rules": req_rules,
        }
    )
    new_response = interaction.response.model_copy(
        update={
            "body": new_resp_body,
            "headers": new_resp_headers,
            "matching_rules": resp_rules,
        }
    )

    update: Dict[str, Any] = {"request": new_request, "response": new_response}
    if spec is SpecVersion.V4:
        update["type"] = interaction.type or "Synchronous/HTTP"
        # Stable per-interaction key — derived from description + state names.
        if interaction.key is None:
            key_src = (
                interaction.description
                + "|"
                + "|".join(s.name for s in interaction.provider_states)
            )
            update["key"] = f"{abs(hash(key_src)) & 0xFFFFFFFF:08x}"
        if interaction.pending is None:
            update["pending"] = False
    return interaction.model_copy(update=update)


def _strip_none(value: Any) -> Any:
    """Recursively drop ``None`` and empty dict / list fields so the
    pact.json doesn't contain noise."""

    if isinstance(value, dict):
        return {
            k: _strip_none(v)
            for k, v in value.items()
            if v is not None and v != {} and v != []
        }
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value


def render(pact: Pact, spec: SpecVersion) -> Dict[str, Any]:
    """Build the pact.json dict for the given spec version.

    Pure function — call :func:`write` for the file-system side effect.
    """

    new_interactions = [_process_interaction(it, spec) for it in pact.interactions]

    new_pact = pact.model_copy(
        update={
            "interactions": new_interactions,
            "metadata": pact.metadata.model_copy(
                update={
                    "pact_specification": pact.metadata.pact_specification.model_copy(
                        update={"version": spec.value},
                    ),
                    # Plugins are V4-only; drop the field on V3 dumps.
                    "plugins": (
                        pact.metadata.plugins if spec is SpecVersion.V4 else None
                    ),
                }
            ),
        }
    )

    raw = new_pact.model_dump(mode="json", by_alias=True, exclude_none=True)

    # Per-spec interaction shape touches.
    if spec is SpecVersion.V3:
        for it in raw.get("interactions", []):
            # V3 uses singular ``providerState`` (string).
            states = it.pop("providerStates", None)
            if states:
                it["providerState"] = states[0]["name"]
            it.pop("type", None)
            it.pop("key", None)
            it.pop("pending", None)
    else:
        for it in raw.get("interactions", []):
            it.setdefault("type", "Synchronous/HTTP")

    return _strip_none(raw)


def _safe_name(s: str) -> str:
    """Sanitise a consumer / provider name so it's a valid filename."""

    cleaned = "".join(c if c.isalnum() or c in "_-." else "_" for c in s).strip("_")
    return cleaned or "unnamed"


def _default_filename(pact: Pact) -> str:
    """Pact's canonical filename: ``<consumer>-<provider>.json``."""

    return f"{_safe_name(pact.consumer.name)}-{_safe_name(pact.provider.name)}.json"


def write(
    pact: Pact,
    spec: SpecVersion,
    output_dir: str | os.PathLike[str],
    filename: str | None = None,
    indent: int = 2,
) -> Path:
    """Render and write the pact.json file. Returns the path written."""

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    target = out_path / (filename or _default_filename(pact))
    payload = render(pact, spec)
    target.write_text(
        json.dumps(payload, indent=indent, ensure_ascii=False, sort_keys=False),
        encoding="utf-8",
    )
    return target


def parse(raw: str | bytes | Dict[str, Any]) -> Pact:
    """Parse a pact.json blob into a :class:`Pact` model.

    Used by tests + the hypothesis fuzz harness to ensure round-trip
    fidelity. Accepts either a JSON string / bytes or a pre-parsed dict.
    """

    if isinstance(raw, (str, bytes)):
        data = json.loads(raw)
    else:
        data = raw

    # Coerce V3's singular providerState into V4's plural shape on the
    # way in so the model only has to know one schema.
    for it in data.get("interactions", []):
        if "providerState" in it and "providerStates" not in it:
            it["providerStates"] = [
                {"name": it.pop("providerState"), "params": {}},
            ]

    return Pact.model_validate(data)
