# Copyright (c) 2026 Mockarty. All rights reserved.

"""Pact matcher DSL.

A *matcher* is a sentinel object that the user nests inside their
request / response body. When the writer serialises the contract it
walks the body, extracts the matcher rules into the appropriate
``matchingRules`` block, and replaces the matcher with its example
value (so the mock server returns / accepts the example at runtime).

The same matchers serialise differently in V3 vs V4:

* **V3** — flat path keys like ``$.body.foo[0].bar``, with the matcher
  spec as the leaf value (``{"match": "type"}``).
* **V4** — nested category dict (``body`` / ``header`` / ``query`` /
  ``path``), with each path mapping to a ``{"matchers": [...]}`` list
  of matcher entries. V4 matcher entries use ``"type"`` field, not
  ``"match"``, and support ``combine`` semantics (Phase 1 always emits
  ``"AND"``).

This module intentionally does NOT execute the matchers — that is the
verifier's job. We only emit the JSON. Implementation lives next to
the matcher classes so adding a new matcher means changing exactly one
file.
"""

from __future__ import annotations

import builtins
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from mockarty.pact.types import SpecVersion

# Local aliases for ``min`` / ``max`` since matcher classes accept
# parameters named ``min`` and ``max`` (matching the Pact JSON spec
# field names), which would shadow the builtins inside ``__init__``.
_pymin = builtins.min
_pymax = builtins.max


# ── Base class ─────────────────────────────────────────────────────────


class Mismatch:
    """One mismatch the mock-server discovered while walking a request.

    ``path`` is a human-readable JSONPath (``$.user.name``). ``expected``
    is what the matcher demanded (a description, not a value); ``actual``
    is the offending value the client sent.
    """

    __slots__ = ("path", "expected", "actual")

    def __init__(self, path: str, expected: str, actual: Any) -> None:
        self.path = path
        self.expected = expected
        self.actual = actual

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return f"Mismatch(path={self.path!r}, expected={self.expected!r}, actual={self.actual!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mismatch):
            return NotImplemented
        return (
            self.path == other.path
            and self.expected == other.expected
            and self.actual == other.actual
        )

    def __hash__(self) -> int:
        return hash((self.path, self.expected, repr(self.actual)))


class Matcher:
    """Base class for every matcher.

    Subclasses MUST override :meth:`v3_rule` and :meth:`v4_rule` (the
    matcher entries themselves) and provide an ``example`` attribute
    or property — the concrete value that should appear in the request
    / response body when the contract is replayed.

    Optional :meth:`validate` lets the live mock server enforce the
    matcher against an incoming request body. The default implementation
    is permissive (no mismatch) so legacy matcher subclasses keep
    working; strict subclasses override.
    """

    __slots__ = ("example",)

    def __init__(self, example: Any) -> None:
        self.example = example

    # Each subclass implements these two:
    def v3_rule(self) -> Dict[str, Any]:  # pragma: no cover — abstract
        raise NotImplementedError

    def v4_rule(self) -> Dict[str, Any]:  # pragma: no cover — abstract
        raise NotImplementedError

    # Convenience for the writer.
    def rule_for(self, spec: SpecVersion) -> Dict[str, Any]:
        return self.v3_rule() if spec is SpecVersion.V3 else self.v4_rule()

    # Live mock-server hook. ``actual`` is the value at ``path`` inside the
    # client's request body. Subclasses should return a list of
    # :class:`Mismatch` (empty = OK).
    def validate(self, actual: Any, path: str = "$") -> List["Mismatch"]:
        return []

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return f"{type(self).__name__}({self.example!r})"


# ── Concrete matchers shared between V3 & V4 ──────────────────────────


def _same_type(expected: Any, actual: Any) -> bool:
    """Pact "type" semantics: bool is NOT an int, ints and floats are
    distinct unless the expected is float (in which case int promotes)."""

    if isinstance(expected, bool):
        return isinstance(actual, bool)
    if isinstance(actual, bool) and not isinstance(expected, bool):
        # bool is a subclass of int in Python — reject so ``Like(1)`` doesn't
        # accept ``True``.
        return False
    if isinstance(expected, int):
        return isinstance(actual, int) and not isinstance(actual, bool)
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool)
    if isinstance(expected, str):
        return isinstance(actual, str)
    if isinstance(expected, list):
        return isinstance(actual, list)
    if isinstance(expected, dict):
        return isinstance(actual, dict)
    if expected is None:
        return actual is None
    return type(expected) is type(actual)


class Like(Matcher):
    """Match by type — Pact's most common matcher.

    ``Like(100)`` asserts the field is an integer (the value 100 is
    just the example); ``Like("abc")`` asserts a string. Nested
    structures are matched recursively.
    """

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "type"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "type"}], "combine": "AND"}

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        return _like_validate(self.example, actual, path)


class Integer(Matcher):
    """Strict integer match (V3: ``"integer"``, V4: ``{"match": "integer"}``)."""

    def __init__(self, example: int = 0) -> None:
        super().__init__(int(example))

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "integer"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "integer"}], "combine": "AND"}

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if isinstance(actual, bool) or not isinstance(actual, int):
            return [Mismatch(path, "integer", actual)]
        return []


class Decimal(Matcher):
    """Strict decimal/float match."""

    def __init__(self, example: float = 0.0) -> None:
        super().__init__(float(example))

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "decimal"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "decimal"}], "combine": "AND"}

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        # Accept ints as decimals (JSON makes no distinction) but reject bool.
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            return [Mismatch(path, "decimal", actual)]
        return []


class Boolean(Matcher):
    """Strict boolean match."""

    def __init__(self, example: bool = False) -> None:
        super().__init__(bool(example))

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "boolean"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "boolean"}], "combine": "AND"}

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, bool):
            return [Mismatch(path, "boolean", actual)]
        return []


class Regex(Matcher):
    """Regex match. ``Regex(r"\\d{3}", "123")`` matches three digits.

    Alias :class:`Term` is kept for users coming from pact-python's
    pre-2.0 DSL where the matcher was called ``Term``.
    """

    __slots__ = ("regex", "_compiled")

    def __init__(self, regex: str, example: str) -> None:
        super().__init__(example)
        self.regex = regex
        try:
            self._compiled = re.compile(regex)
        except re.error as exc:
            raise ValueError(f"invalid regex {regex!r}: {exc}") from exc

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "regex", "regex": self.regex}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [{"match": "regex", "regex": self.regex}],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, str):
            return [Mismatch(path, f"string matching /{self.regex}/", actual)]
        if not self._compiled.search(actual):
            return [Mismatch(path, f"value matching /{self.regex}/", actual)]
        return []


# Alias for pact-python ergonomics.
Term = Regex


class Equality(Matcher):
    """V4: ``{"match": "equality"}`` — exact value match.

    On V3 we fall back to no matcher entry (equality is the default
    when no rule is registered) but we still inject the example.
    """

    def v3_rule(self) -> Dict[str, Any]:
        # V3 has no "equality" matcher; default behaviour IS equality,
        # so we register an empty rule to make the writer emit nothing.
        return {}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "equality"}], "combine": "AND"}

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if actual != self.example:
            return [Mismatch(path, f"equal to {self.example!r}", actual)]
        return []


class EachLike(Matcher):
    """Array whose each element matches the template.

    ``EachLike({"id": Like(1)}, min=2)`` means a list with ≥2 entries
    where every entry is shaped like the template. The ``example``
    rendered into the body is ``[template, template, ...]`` repeated
    ``min`` times so verifiers exercising the body see a list of the
    right size.
    """

    __slots__ = ("min", "max", "template")

    def __init__(
        self,
        template: Any,
        min: int = 1,
        max: Optional[int] = None,
    ) -> None:
        # Bind builtins locally so the shadowed ``min`` / ``max`` names
        # inside this scope don't break the bound check below.
        if min < 0:
            raise ValueError("EachLike min must be >= 0")
        if max is not None and max < min:
            raise ValueError("EachLike max must be >= min")
        super().__init__([template] * _pymax(min, 1))
        self.min = min
        self.max = max
        self.template = template

    def v3_rule(self) -> Dict[str, Any]:
        rule: Dict[str, Any] = {"match": "type", "min": self.min}
        if self.max is not None:
            rule["max"] = self.max
        return rule

    def v4_rule(self) -> Dict[str, Any]:
        entry: Dict[str, Any] = {"match": "type", "min": self.min}
        if self.max is not None:
            entry["max"] = self.max
        return {"matchers": [entry], "combine": "AND"}

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, list):
            return [Mismatch(path, "array", actual)]
        if len(actual) < self.min:
            return [Mismatch(path, f"array length >= {self.min}", len(actual))]
        if self.max is not None and len(actual) > self.max:
            return [Mismatch(path, f"array length <= {self.max}", len(actual))]
        problems: List[Mismatch] = []
        for i, item in enumerate(actual):
            problems.extend(_validate_value(self.template, item, f"{path}[{i}]"))
        return problems


class MinType(Matcher):
    """V4 array with ``min`` items, each matching the template (no upper bound)."""

    __slots__ = ("min", "template")

    def __init__(self, template: Any, min: int) -> None:
        if min < 0:
            raise ValueError("MinType min must be >= 0")
        super().__init__([template] * _pymax(min, 1))
        self.min = min
        self.template = template

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "type", "min": self.min}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [{"match": "type", "min": self.min}],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, list):
            return [Mismatch(path, "array", actual)]
        if len(actual) < self.min:
            return [Mismatch(path, f"array length >= {self.min}", len(actual))]
        problems: List[Mismatch] = []
        for i, item in enumerate(actual):
            problems.extend(_validate_value(self.template, item, f"{path}[{i}]"))
        return problems


class MaxType(Matcher):
    """V4 array with at most ``max`` items, each matching the template."""

    __slots__ = ("max", "template")

    def __init__(self, template: Any, max: int) -> None:
        if max < 0:
            raise ValueError("MaxType max must be >= 0")
        super().__init__([template])
        self.max = max
        self.template = template

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "type", "max": self.max}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [{"match": "type", "max": self.max}],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, list):
            return [Mismatch(path, "array", actual)]
        if len(actual) > self.max:
            return [Mismatch(path, f"array length <= {self.max}", len(actual))]
        problems: List[Mismatch] = []
        for i, item in enumerate(actual):
            problems.extend(_validate_value(self.template, item, f"{path}[{i}]"))
        return problems


class MinMaxType(Matcher):
    """V4 array with both bounds."""

    __slots__ = ("min", "max", "template")

    def __init__(self, template: Any, min: int, max: int) -> None:
        if min < 0 or max < min:
            raise ValueError("MinMaxType bounds invalid (need 0 <= min <= max)")
        # Render at least ``min`` examples; cap at ``max`` so the body
        # respects the bound.
        super().__init__([template] * _pymax(min, 1) if max > 0 else [])
        self.min = min
        self.max = max
        self.template = template

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "type", "min": self.min, "max": self.max}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [
                {"match": "type", "min": self.min, "max": self.max},
            ],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, list):
            return [Mismatch(path, "array", actual)]
        if len(actual) < self.min or len(actual) > self.max:
            return [
                Mismatch(
                    path,
                    f"array length in [{self.min}, {self.max}]",
                    len(actual),
                ),
            ]
        problems: List[Mismatch] = []
        for i, item in enumerate(actual):
            problems.extend(_validate_value(self.template, item, f"{path}[{i}]"))
        return problems


class ArrayContains(Matcher):
    """V4 ``array-contains`` — list must contain each given variant.

    Each ``variant`` is a value (or nested matcher). The example body is
    the list of example values; the matcher entry references variant
    indices per V4 spec.
    """

    __slots__ = ("variants",)

    def __init__(self, variants: Sequence[Any]) -> None:
        if not variants:
            raise ValueError("ArrayContains needs ≥ 1 variant")
        self.variants = list(variants)
        super().__init__(
            [v.example if isinstance(v, Matcher) else v for v in self.variants],
        )

    def v3_rule(self) -> Dict[str, Any]:
        # V3 doesn't natively support array-contains; degrade to type-match.
        return {"match": "type"}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [
                {
                    "match": "arrayContains",
                    "variants": [{"index": idx} for idx, _ in enumerate(self.variants)],
                },
            ],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, list):
            return [Mismatch(path, "array", actual)]
        missing: List[Mismatch] = []
        for idx, variant in enumerate(self.variants):
            # At least one actual element must satisfy the variant.
            matched = False
            for item in actual:
                if not _validate_value(variant, item, f"{path}[?]"):
                    matched = True
                    break
            if not matched:
                missing.append(
                    Mismatch(
                        path,
                        f"array contains variant[{idx}]={variant.example if isinstance(variant, Matcher) else variant!r}",
                        actual,
                    )
                )
        return missing


class EachKey(Matcher):
    """V4 ``each-key`` — every key in the map matches the inner matcher."""

    __slots__ = ("inner",)

    def __init__(self, inner: Matcher, example: Mapping[str, Any]) -> None:
        if not isinstance(inner, Matcher):
            raise TypeError("EachKey inner must be a Matcher")
        super().__init__(dict(example))
        self.inner = inner

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "type"}  # graceful V3 fallback

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [
                {"match": "eachKey", "rules": [self.inner.v4_rule()]},
            ],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, dict):
            return [Mismatch(path, "object", actual)]
        problems: List[Mismatch] = []
        for k in actual.keys():
            problems.extend(self.inner.validate(k, f"{path}.<key:{k}>"))
        return problems


class EachValue(Matcher):
    """V4 ``each-value`` — every value in the map matches the inner matcher."""

    __slots__ = ("inner",)

    def __init__(self, inner: Matcher, example: Mapping[str, Any]) -> None:
        if not isinstance(inner, Matcher):
            raise TypeError("EachValue inner must be a Matcher")
        super().__init__(dict(example))
        self.inner = inner

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "type"}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [
                {"match": "eachValue", "rules": [self.inner.v4_rule()]},
            ],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        if not isinstance(actual, dict):
            return [Mismatch(path, "object", actual)]
        problems: List[Mismatch] = []
        for k, v in actual.items():
            problems.extend(self.inner.validate(v, f"{path}.{k}"))
        return problems


# Alias requested by spec (`EachKeyLike` is the more common verb in
# pact-python documentation).
EachKeyLike = EachKey


# ── V4 JSONPath / XMLPath ──────────────────────────────────────────────


def _jsonpath_lookup(body: Any, path: str) -> Tuple[bool, Any]:
    """Tiny JSONPath subset: ``$.a.b[0].c``. Returns (found, value).

    We intentionally keep this dependency-free; a full JSONPath engine
    is out of scope for the SDK. Bracket notation ``["foo bar"]`` is
    accepted; ``$..deep`` recursion is not.
    """

    if not path.startswith("$"):
        return False, None
    rest = path[1:]
    cur: Any = body
    i = 0
    while i < len(rest):
        ch = rest[i]
        if ch == ".":
            j = i + 1
            while j < len(rest) and rest[j] not in ".[":
                j += 1
            key = rest[i + 1 : j]
            if not isinstance(cur, dict) or key not in cur:
                return False, None
            cur = cur[key]
            i = j
        elif ch == "[":
            j = rest.index("]", i)
            inner = rest[i + 1 : j]
            if inner.startswith('"') and inner.endswith('"'):
                key = inner[1:-1]
                if not isinstance(cur, dict) or key not in cur:
                    return False, None
                cur = cur[key]
            else:
                try:
                    idx = int(inner)
                except ValueError:
                    return False, None
                if not isinstance(cur, list) or idx < 0 or idx >= len(cur):
                    return False, None
                cur = cur[idx]
            i = j + 1
        else:
            return False, None
    return True, cur


class JSONPath(Matcher):
    """V4 ``$path`` matcher — applies an inner matcher to a JSONPath
    selection of the body. The example is the surrounding body so the
    response is concrete, while validation peeks into the selected node.
    """

    __slots__ = ("path_expr", "inner")

    def __init__(self, path: str, inner: Matcher, example: Any) -> None:
        if not isinstance(inner, Matcher):
            raise TypeError("JSONPath inner must be a Matcher")
        if not path.startswith("$"):
            raise ValueError("JSONPath expression must start with '$'")
        super().__init__(example)
        self.path_expr = path
        self.inner = inner

    def v3_rule(self) -> Dict[str, Any]:
        # V3 stores the rule under the JSONPath itself; render as a
        # plain type-match fallback (V3 has no nested path rule type).
        return self.inner.v3_rule()

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [
                {
                    "match": "values",
                    "path": self.path_expr,
                    "rules": [self.inner.v4_rule()],
                },
            ],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        found, value = _jsonpath_lookup(actual, self.path_expr)
        if not found:
            return [Mismatch(path, f"node at {self.path_expr}", actual)]
        return self.inner.validate(value, self.path_expr)


class XMLPath(Matcher):
    """V4 XML path matcher — validates a node selected by a simple
    ``/root/child[0]/leaf`` expression.

    Stdlib-only — we parse the actual XML via :mod:`xml.etree.ElementTree`
    only when validate runs. ``inner.validate`` is applied to the node's
    text content (the most common use case for contract testing).
    """

    __slots__ = ("path_expr", "inner")

    def __init__(self, path: str, inner: Matcher, example: Any) -> None:
        if not isinstance(inner, Matcher):
            raise TypeError("XMLPath inner must be a Matcher")
        if not path.startswith("/"):
            raise ValueError("XMLPath expression must start with '/'")
        super().__init__(example)
        self.path_expr = path
        self.inner = inner

    def v3_rule(self) -> Dict[str, Any]:
        return self.inner.v3_rule()

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [
                {
                    "match": "values",
                    "path": self.path_expr,
                    "rules": [self.inner.v4_rule()],
                    "syntax": "xpath",
                },
            ],
            "combine": "AND",
        }

    def validate(self, actual: Any, path: str = "$") -> List[Mismatch]:
        # Lazy import — XML is not always needed.
        import xml.etree.ElementTree as ET  # noqa: N814

        try:
            if isinstance(actual, (bytes, bytearray)):
                root = ET.fromstring(bytes(actual))
            elif isinstance(actual, str):
                root = ET.fromstring(actual)
            else:
                return [Mismatch(path, "XML document", actual)]
        except ET.ParseError as exc:
            return [Mismatch(path, f"valid XML ({exc})", actual)]

        # Translate ``/root/child[0]/leaf`` to ElementTree's relative form.
        parts = [p for p in self.path_expr.lstrip("/").split("/") if p]
        if not parts:
            return [Mismatch(path, "non-empty XML path", self.path_expr)]
        # First segment must match root tag.
        if parts[0] != root.tag:
            return [Mismatch(path, f"root <{parts[0]}>", f"<{root.tag}>")]
        if len(parts) == 1:
            return self.inner.validate(root.text or "", self.path_expr)
        # Build an XPath relative to root for the remaining segments.
        rel = "./" + "/".join(parts[1:])
        node = root.find(rel)
        if node is None:
            return [Mismatch(path, f"node at {self.path_expr}", actual)]
        return self.inner.validate(node.text or "", self.path_expr)


# ── Walker (shared by Like / EachLike / consumers) ────────────────────


def _like_validate(template: Any, actual: Any, path: str) -> List[Mismatch]:
    """Pact "Like" semantics: type-only match all the way down.

    Used by :class:`Like` so that ``Like({"name": "Alice"})`` validates
    any object with a string ``name`` field — the example value is
    illustrative, not enforced.

    Nested :class:`Matcher` instances inside the template still take
    precedence (so the user can mix ``Like`` with strict matchers like
    ``Regex`` or ``Equality``).
    """

    if isinstance(template, Matcher):
        return template.validate(actual, path)
    if not _same_type(template, actual):
        return [
            Mismatch(
                path,
                f"same type as {type(template).__name__}",
                actual,
            ),
        ]
    if isinstance(template, dict):
        problems: List[Mismatch] = []
        for k, v in template.items():
            sub_path = f"{path}.{k}"
            if k not in actual:
                problems.append(Mismatch(sub_path, f"key {k!r} present", actual))
                continue
            problems.extend(_like_validate(v, actual[k], sub_path))
        return problems
    if isinstance(template, list):
        problems = []
        template_one = template[0] if template else None
        if template_one is None:
            return []
        for i, item in enumerate(actual):
            problems.extend(_like_validate(template_one, item, f"{path}[{i}]"))
        return problems
    return []


def _validate_value(template: Any, actual: Any, path: str) -> List[Mismatch]:
    """Recursively validate ``actual`` against ``template``.

    The template may be a matcher (delegated to its ``validate``), a
    nested dict (validate keys + recurse), a nested list (recurse
    pairwise; lengths must match for plain lists — use ``EachLike`` for
    variable-length), or a plain scalar (exact equality)."""

    if isinstance(template, Matcher):
        return template.validate(actual, path)
    if isinstance(template, dict):
        if not isinstance(actual, dict):
            return [Mismatch(path, "object", actual)]
        problems: List[Mismatch] = []
        for k, v in template.items():
            sub_path = f"{path}.{k}"
            if k not in actual:
                problems.append(Mismatch(sub_path, f"key {k!r} present", actual))
                continue
            problems.extend(_validate_value(v, actual[k], sub_path))
        return problems
    if isinstance(template, list):
        if not isinstance(actual, list):
            return [Mismatch(path, "array", actual)]
        if len(actual) != len(template):
            return [Mismatch(path, f"array length == {len(template)}", len(actual))]
        problems = []
        for i, (t, a) in enumerate(zip(template, actual)):
            problems.extend(_validate_value(t, a, f"{path}[{i}]"))
        return problems
    if template != actual:
        return [Mismatch(path, repr(template), actual)]
    return []


# ── Discriminator for the writer ──────────────────────────────────────


class MatchType(str):
    """Symbolic match-type names — kept as plain strings so user code can
    spell ``"type"`` or use ``MatchType.TYPE`` interchangeably.

    This is also used by the writer to look up which matcher name to
    emit when round-tripping a matcher rule.
    """

    TYPE = "type"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    REGEX = "regex"
    EQUALITY = "equality"
    EACH_KEY = "eachKey"
    EACH_VALUE = "eachValue"
    ARRAY_CONTAINS = "arrayContains"
    VALUES = "values"


MatcherLike = Union[Matcher, Any]


__all__ = [
    "ArrayContains",
    "Boolean",
    "Decimal",
    "EachKey",
    "EachKeyLike",
    "EachLike",
    "EachValue",
    "Equality",
    "Integer",
    "JSONPath",
    "Like",
    "MatchType",
    "Matcher",
    "MatcherLike",
    "MaxType",
    "MinMaxType",
    "MinType",
    "Mismatch",
    "Regex",
    "Term",
    "XMLPath",
]
