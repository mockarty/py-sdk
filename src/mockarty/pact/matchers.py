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
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from mockarty.pact.types import SpecVersion

# Local aliases for ``min`` / ``max`` since matcher classes accept
# parameters named ``min`` and ``max`` (matching the Pact JSON spec
# field names), which would shadow the builtins inside ``__init__``.
_pymin = builtins.min
_pymax = builtins.max


# ── Base class ─────────────────────────────────────────────────────────


class Matcher:
    """Base class for every matcher.

    Subclasses MUST override :meth:`v3_rule` and :meth:`v4_rule` (the
    matcher entries themselves) and provide an ``example`` attribute
    or property — the concrete value that should appear in the request
    / response body when the contract is replayed.
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

    def __repr__(self) -> str:  # pragma: no cover — cosmetic
        return f"{type(self).__name__}({self.example!r})"


# ── Concrete matchers shared between V3 & V4 ──────────────────────────


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


class Integer(Matcher):
    """Strict integer match (V3: ``"integer"``, V4: ``{"match": "integer"}``)."""

    def __init__(self, example: int = 0) -> None:
        super().__init__(int(example))

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "integer"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "integer"}], "combine": "AND"}


class Decimal(Matcher):
    """Strict decimal/float match."""

    def __init__(self, example: float = 0.0) -> None:
        super().__init__(float(example))

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "decimal"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "decimal"}], "combine": "AND"}


class Boolean(Matcher):
    """Strict boolean match."""

    def __init__(self, example: bool = False) -> None:
        super().__init__(bool(example))

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "boolean"}

    def v4_rule(self) -> Dict[str, Any]:
        return {"matchers": [{"match": "boolean"}], "combine": "AND"}


class Regex(Matcher):
    """Regex match. ``Regex(r"\\d{3}", "123")`` matches three digits.

    Alias :class:`Term` is kept for users coming from pact-python's
    pre-2.0 DSL where the matcher was called ``Term``.
    """

    __slots__ = ("regex",)

    def __init__(self, regex: str, example: str) -> None:
        super().__init__(example)
        self.regex = regex

    def v3_rule(self) -> Dict[str, Any]:
        return {"match": "regex", "regex": self.regex}

    def v4_rule(self) -> Dict[str, Any]:
        return {
            "matchers": [{"match": "regex", "regex": self.regex}],
            "combine": "AND",
        }


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


# Alias requested by spec (`EachKeyLike` is the more common verb in
# pact-python documentation).
EachKeyLike = EachKey


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
    "Like",
    "MatchType",
    "Matcher",
    "MatcherLike",
    "MaxType",
    "MinMaxType",
    "MinType",
    "Regex",
    "Term",
]
