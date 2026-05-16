# Copyright (c) 2026 Mockarty. All rights reserved.

"""Assertion DSL — declarative gates the engine applies to each response.

An assertion answers a single yes/no question about an observed
response (status code in expected range? body free of stack traces?
no crash detected? response time under N?). The transpiler emits each
assertion as a structured object under ``_sdkMeta.assertions`` — the
server's existing detector chain consumes it.

Phase 1 ships four canonical assertions plus a generic
:func:`assertion` factory for users who need to attach a one-off
descriptor without subclassing.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Dict, Iterable, Optional, Union


class Assertion:
    """Base class for fuzz assertions.

    Subclasses must override :meth:`to_dict` to produce the JSON
    descriptor the server reads. The ``kind`` attribute is the
    discriminator field used in transpiled output.
    """

    kind: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dict (must include ``kind``)."""

        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()!r})"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Assertion):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        # JSON dict isn't hashable; freeze via sorted tuple.
        return hash(tuple(sorted(self.to_dict().items())))


class AssertStatus(Assertion):
    """Pass when ``response.status`` is inside ``status_range``.

    Accepts a Python ``range`` (e.g. ``range(200, 300)``), an iterable
    of explicit ints (``[200, 201, 204]``), or a single int. The
    descriptor on the wire is normalised to a sorted ``[low, high]``
    pair for ranges and a sorted ``codes`` list for explicit sets.
    """

    kind = "status"

    def __init__(self, status_range: Union[range, Iterable[int], int]) -> None:
        if isinstance(status_range, int):
            self._range: Optional[range] = None
            self._codes = [int(status_range)]
        elif isinstance(status_range, range):
            if status_range.step != 1:
                raise ValueError("AssertStatus only supports contiguous ranges")
            if status_range.start >= status_range.stop:
                raise ValueError("AssertStatus range must be non-empty")
            self._range = status_range
            self._codes = []
        else:
            codes = sorted({int(c) for c in status_range})
            if not codes:
                raise ValueError("AssertStatus requires at least one code")
            self._range = None
            self._codes = codes

    def to_dict(self) -> Dict[str, Any]:
        if self._range is not None:
            return {
                "kind": self.kind,
                "low": self._range.start,
                "high": self._range.stop - 1,
            }
        return {"kind": self.kind, "codes": list(self._codes)}


class AssertNoCrash(Assertion):
    """Pass unless the engine detected a crash (5xx, panic trace,
    aborted connection, stack-trace fingerprint).

    The detector chain is server-side; this assertion just tells the
    engine to fail the run if any crash signal fires.
    """

    kind = "no_crash"

    def __init__(self, *, strict: bool = False) -> None:
        """``strict=True`` treats any 5xx as a crash; otherwise only
        the detector's higher-confidence signals trip the assertion.
        """

        self.strict = bool(strict)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "strict": self.strict}


class AssertResponseTimeUnder(Assertion):
    """Pass when response wall-clock time is below ``limit``.

    Accepts a :class:`datetime.timedelta` or a number of seconds
    (``float`` / ``int``).
    """

    kind = "response_time_under"

    def __init__(self, limit: Union[timedelta, float, int]) -> None:
        if isinstance(limit, timedelta):
            ms = int(limit.total_seconds() * 1000)
        else:
            ms = int(float(limit) * 1000)
        if ms <= 0:
            raise ValueError("limit must be positive")
        self.ms = ms

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "ms": self.ms}


class AssertNoErrorInBody(Assertion):
    """Pass when the response body does NOT match ``pattern``.

    The pattern is compiled at construction time so a malformed regex
    fails the test build instead of the run.
    """

    kind = "no_error_in_body"

    def __init__(
        self,
        pattern: Union[str, "re.Pattern[str]"],
        *,
        flags: int = 0,
        description: str = "",
    ) -> None:
        if isinstance(pattern, re.Pattern):
            self._pattern = pattern.pattern
            self._flags = pattern.flags
        else:
            # Compile to validate; we store the source string for wire
            # serialisation because the server uses its own regex engine.
            re.compile(pattern, flags)
            self._pattern = pattern
            self._flags = flags
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "kind": self.kind,
            "pattern": self._pattern,
            "flags": self._flags,
        }
        if self.description:
            out["description"] = self.description
        return out


def assertion(kind: str, **fields: Any) -> Assertion:
    """Build a free-form :class:`Assertion` for tests / forward-compat.

    Useful when the server adds a new assertion type before the SDK
    catches up — the user can still emit the descriptor.
    """

    if not kind:
        raise ValueError("assertion kind must be non-empty")

    class _Free(Assertion):
        pass

    _Free.kind = kind
    inst = _Free()
    inst._fields = dict(fields)  # type: ignore[attr-defined]

    def to_dict(self: _Free = inst) -> Dict[str, Any]:
        out = {"kind": kind}
        out.update(self._fields)  # type: ignore[attr-defined]
        return out

    inst.to_dict = to_dict.__get__(inst, _Free)  # type: ignore[assignment]
    return inst
