"""Step-capture vocabulary shared by every Mockarty protocol client.

The Python SDK's external_runs API posts the entire run (status, steps,
attachments) in one shot per case — there is no separate "add steps"
endpoint to stream into. The recorder shape is therefore a buffer:
each protocol client calls ``recorder.record(step)`` and the test
finishing function pulls the accumulated steps out via
``recorder.steps()`` and feeds them to
``client.external_runs().report(steps=...)``.

NopRecorder is the zero-overhead default — drops every step on the
floor — so tests that don't care about the TCM timeline pay nothing.

Thread safety: AccumulatingRecorder uses a re-entrant lock so multiple
threads / async tasks can record concurrently. The protocol clients
themselves are sync (httpx-driven); the WebSocket client offers an
async surface but still records steps synchronously via the same lock.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class Step:
    """Protocol-agnostic captured step.

    Attributes
    ----------
    key:
        Stable identifier used by the server for de-dup. Build via
        :func:`new_step_key` so retries collapse into one row.
    name:
        Human-readable label (e.g. ``"graphql:GetUser"``).
    status:
        One of ``"passed" | "failed" | "broken" | "skipped"``.
    started_at, finished_at:
        Monotonic timestamps; the recorder pre-fills them when the
        protocol client records, so the user doesn't have to.
    duration_ms:
        Convenience field derived from started/finished. The
        :meth:`to_payload` serializer recomputes it on the fly when
        the user constructs Step manually.
    parameters:
        Free-form string→string map (request/response previews,
        topic, partition, status code, etc.).
    message:
        Error message (empty on success).
    stack_trace, parent_key:
        Optional fields surfaced as-is in the wire payload.
    """

    key: str
    name: str
    status: str = "passed"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    duration_ms: int = 0
    parameters: dict[str, str] = field(default_factory=dict)
    message: str = ""
    stack_trace: str = ""
    parent_key: str = ""

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the wire shape ExternalRunsAPI.report expects."""
        out: dict[str, Any] = {
            "stepKey": self.key,
            "name": self.name,
            "status": self.status or "passed",
        }
        if self.started_at is not None:
            out["startedAt"] = _to_isoformat(self.started_at)
        if self.finished_at is not None:
            out["finishedAt"] = _to_isoformat(self.finished_at)
        dur = self.duration_ms
        if dur <= 0 and self.started_at is not None and self.finished_at is not None:
            dur = max(0, int((self.finished_at - self.started_at) * 1000))
        if dur:
            out["durationMs"] = dur
        if self.parameters:
            out["parameters"] = dict(self.parameters)
        if self.message:
            out["message"] = self.message
        if self.stack_trace:
            out["stackTrace"] = self.stack_trace
        if self.parent_key:
            out["parentKey"] = self.parent_key
        return out


def _to_isoformat(epoch_seconds: float) -> str:
    """Render an epoch-seconds float as an RFC 3339 timestamp in UTC.

    The server accepts both epoch ints and RFC 3339 strings; we ship
    the latter so a step's timeline reads naturally in raw JSON
    dumps.
    """
    # gmtime + strftime keeps stdlib-only — no datetime/timezone fuss.
    fract = int((epoch_seconds - int(epoch_seconds)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch_seconds)) + f".{fract:03d}Z"


class StepRecorder(Protocol):
    """Narrow seam between protocol clients and step sinks.

    Implementations MUST be safe for concurrent use; the protocol
    clients can fire calls from multiple threads / asyncio tasks
    in a single test.
    """

    def record(self, step: Step) -> None: ...


class NopRecorder:
    """Drops every step on the floor. The default when no recorder
    is wired so a script that doesn't care about TCM steps works
    out of the box."""

    def record(self, step: Step) -> None:  # noqa: D401 - one-liner
        """Drop the step."""
        return None


class AccumulatingRecorder:
    """Buffers steps for later submission via ExternalRunsAPI.report.

    Typical use::

        recorder = AccumulatingRecorder()
        soap = SoapClient(url, recorder=recorder)
        graphql = GraphQLClient(url, recorder=recorder)
        # ... run the test ...
        client.external_runs().report(
            case_name="my case",
            status="passed",
            steps=recorder.steps(),
        )

    The same recorder can be shared across multiple protocol clients
    inside a single test — all their calls land in one timeline.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._steps: list[Step] = []

    def record(self, step: Step) -> None:
        with self._lock:
            self._steps.append(step)

    def steps(self) -> list[dict[str, Any]]:
        """Return the accumulated steps in serialized wire shape."""
        with self._lock:
            return [s.to_payload() for s in self._steps]

    def raw_steps(self) -> list[Step]:
        """Return the accumulated steps as :class:`Step` instances."""
        with self._lock:
            return list(self._steps)

    def clear(self) -> None:
        """Drop every accumulated step. Useful between test cases
        when a single recorder is shared across a pytest module."""
        with self._lock:
            self._steps.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._steps)


def new_step_key(name: str, seq: int) -> str:
    """Build a stable per-call key from a method/topic name + a
    monotonic counter. Format matches the Go SDK so cross-language
    tests collapse retries server-side on (namespace, run, step_key).
    """
    return f"{name}#{seq}"
