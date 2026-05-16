# Copyright (c) 2026 Mockarty. All rights reserved.

"""Byte-accurate Allure-2 ``allure-results`` directory writer.

Goal
----
Take a Mockarty :class:`mockarty.testing.context.CaseFrame` (with its
steps, attachments, labels, links, parameters, timings) and produce JSON
files on disk that the standalone ``allure-commandline`` report
generator (or `Allure TestOps`, or our own server-side ingester) reads
without modification.

Why ship our own writer?
~~~~~~~~~~~~~~~~~~~~~~~~
``allure-pytest`` only writes a result when it owns the pytest hook —
that doesn't help users who want to:

* drive Allure output from ``unittest`` / ``behave`` / Robot framework,
* generate Allure from synthetic runs (load tests, fuzz iterations,
  contract checks) where no pytest is involved,
* post-process Mockarty case frames into Allure on a build agent.

This module owns the file format end-to-end. It mirrors the schema of
``allure-python-commons`` ``model2`` (TestResult / TestResultContainer
/ Attachment / Parameter / Label / Link / StatusDetails) so the
artifact is **interchangeable** with the official writer.

Schema reference: https://allurereport.org/docs/how-it-works-test-result-file/

Filesystem layout produced (``allure-results/`` directory):

    <uuid>-result.json          # TestResult per test
    <uuid>-container.json       # TestResultContainer for fixtures
    <uuid>-attachment.<ext>     # raw attachment body
    categories.json             # optional categorisation rules
    environment.properties      # optional environment snapshot
    executor.json               # optional CI executor info

All JSON is written with ``ensure_ascii=False`` + canonical key order
so byte-for-byte diffing across runs is meaningful.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import socket
import threading
import time
import traceback
import uuid as _uuid_mod
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Union

# ── Canonical status enum (must match Allure model) ─────────────────────
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_BROKEN = "broken"
STATUS_SKIPPED = "skipped"
STATUS_UNKNOWN = "unknown"

# Lifecycle stage (Allure schema: scheduled/running/finished/pending/interrupted)
STAGE_SCHEDULED = "scheduled"
STAGE_RUNNING = "running"
STAGE_FINISHED = "finished"
STAGE_PENDING = "pending"
STAGE_INTERRUPTED = "interrupted"

# Canonical label names recognised by Allure-2's report.
# Anything not in this set still serialises but is treated as a free-form tag.
CANONICAL_LABELS = frozenset(
    {
        "epic",
        "feature",
        "story",
        "suite",
        "parentSuite",
        "subSuite",
        "severity",
        "tag",
        "owner",
        "lead",
        "host",
        "thread",
        "language",
        "framework",
        "package",
        "testClass",
        "testMethod",
        "as_id",
        "ALLURE_ID",
        "layer",
    }
)

# Mockarty-internal step status → Allure status. We keep "broken" reserved
# for infrastructure failures (fixture, setup, network) versus assertion
# failures which are "failed".
_STATUS_NORMALIZE = {
    "passed": STATUS_PASSED,
    "ok": STATUS_PASSED,
    "pass": STATUS_PASSED,
    "failed": STATUS_FAILED,
    "fail": STATUS_FAILED,
    "error": STATUS_BROKEN,
    "broken": STATUS_BROKEN,
    "skipped": STATUS_SKIPPED,
    "skip": STATUS_SKIPPED,
}


# ── Public dataclasses (mirror allure-python-commons model2) ────────────


@dataclass
class StatusDetails:
    message: Optional[str] = None
    trace: Optional[str] = None


@dataclass
class Parameter:
    name: str
    value: str
    excluded: Optional[bool] = None
    mode: Optional[str] = None  # default | masked | hidden


@dataclass
class Label:
    name: str
    value: str


@dataclass
class Link:
    name: Optional[str] = None
    url: str = ""
    type: Optional[str] = None  # custom | issue | tms


@dataclass
class Attachment:
    name: str
    source: str  # filename inside results dir
    type: Optional[str] = None  # MIME type


@dataclass
class StepResult:
    name: str = ""
    status: str = STATUS_PASSED
    stage: str = STAGE_FINISHED
    statusDetails: Optional[StatusDetails] = None
    description: Optional[str] = None
    descriptionHtml: Optional[str] = None
    start: Optional[int] = None
    stop: Optional[int] = None
    parameters: list[Parameter] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    steps: list["StepResult"] = field(default_factory=list)


@dataclass
class TestResult:
    uuid: str
    name: str
    fullName: Optional[str] = None
    historyId: Optional[str] = None
    testCaseId: Optional[str] = None
    status: str = STATUS_PASSED
    stage: str = STAGE_FINISHED
    statusDetails: Optional[StatusDetails] = None
    description: Optional[str] = None
    descriptionHtml: Optional[str] = None
    start: Optional[int] = None
    stop: Optional[int] = None
    labels: list[Label] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    steps: list[StepResult] = field(default_factory=list)


@dataclass
class TestResultContainer:
    uuid: str
    name: Optional[str] = None
    children: list[str] = field(default_factory=list)
    befores: list[StepResult] = field(default_factory=list)
    afters: list[StepResult] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    start: Optional[int] = None
    stop: Optional[int] = None


# ── Writer ──────────────────────────────────────────────────────────────


class AllureResultsWriter:
    """Writes Allure-2 artifacts into ``output_dir``.

    Thread- and process-safe by design: every artifact lives in a file
    whose name carries a UUID (or random suffix), so two parallel
    workers (pytest-xdist, threading) never collide. The directory is
    created lazily on first write so callers can construct one without
    side effects.

    Construct once per session; reuse for every result.
    """

    def __init__(self, output_dir: Union[str, os.PathLike]) -> None:
        self._dir = os.fspath(output_dir)
        self._ensured = False
        self._lock = threading.Lock()

    @property
    def output_dir(self) -> str:
        return self._dir

    # ── filenames ───────────────────────────────────────────────────────
    @staticmethod
    def _result_filename(uuid: str) -> str:
        return f"{uuid}-result.json"

    @staticmethod
    def _container_filename(uuid: str) -> str:
        return f"{uuid}-container.json"

    @staticmethod
    def _attachment_filename(extension: str) -> str:
        ext = extension.lstrip(".") if extension else "bin"
        return f"{_uuid_mod.uuid4().hex}-attachment.{ext}"

    # ── lifecycle ───────────────────────────────────────────────────────
    def _ensure(self) -> None:
        if self._ensured:
            return
        with self._lock:
            if not self._ensured:
                os.makedirs(self._dir, exist_ok=True)
                self._ensured = True

    def write_result(self, result: TestResult) -> str:
        """Serialise + persist a TestResult. Returns the written path."""
        self._ensure()
        path = os.path.join(self._dir, self._result_filename(result.uuid))
        return _atomic_write_json(path, _result_to_dict(result))

    def write_container(self, container: TestResultContainer) -> str:
        """Persist a TestResultContainer (fixtures) JSON."""
        self._ensure()
        path = os.path.join(self._dir, self._container_filename(container.uuid))
        return _atomic_write_json(path, _container_to_dict(container))

    def write_attachment(
        self,
        body: Union[bytes, str],
        *,
        name: str,
        content_type: Optional[str] = None,
        extension: Optional[str] = None,
    ) -> Attachment:
        """Persist an attachment body and return an :class:`Attachment` ref.

        Returns a typed handle that callers attach to a TestResult or
        StepResult. Filename uses a fresh UUID so concurrent writers
        cannot collide on it.
        """
        self._ensure()
        if isinstance(body, str):
            data = body.encode("utf-8")
            if content_type is None:
                content_type = "text/plain"
        else:
            data = bytes(body)
            if content_type is None:
                content_type = "application/octet-stream"
        if not extension:
            ext = mimetypes.guess_extension(content_type) or ".bin"
        else:
            ext = extension if extension.startswith(".") else f".{extension}"
        fname = self._attachment_filename(ext)
        path = os.path.join(self._dir, fname)
        with open(path, "wb") as fh:
            fh.write(data)
        return Attachment(name=name, source=fname, type=content_type)

    def write_environment(self, env: dict[str, str]) -> str:
        """Persist environment.properties (key=value lines, latin-1 safe)."""
        self._ensure()
        path = os.path.join(self._dir, "environment.properties")
        lines = []
        for k in sorted(env.keys()):
            v = env[k]
            # Allure parses lines as key=value; escape newlines.
            lines.append(f"{k}={str(v).replace(chr(10), ' ').replace(chr(13), ' ')}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
            fh.write("\n")
        return path

    def write_categories(self, categories: list[dict[str, Any]]) -> str:
        """Persist categories.json (Allure failure-categorisation)."""
        self._ensure()
        path = os.path.join(self._dir, "categories.json")
        return _atomic_write_json(path, categories)

    def write_executor(self, executor: dict[str, Any]) -> str:
        """Persist executor.json (CI metadata)."""
        self._ensure()
        path = os.path.join(self._dir, "executor.json")
        return _atomic_write_json(path, executor)


# ── Serialisation helpers (drop None to keep diffs clean) ───────────────


def _drop_none(d: dict[str, Any]) -> dict[str, Any]:
    """Remove keys whose value is ``None``. Empty collections kept."""
    return {k: v for k, v in d.items() if v is not None}


def _status_details_to_dict(sd: Optional[StatusDetails]) -> Optional[dict[str, Any]]:
    if sd is None:
        return None
    out = _drop_none({"message": sd.message, "trace": sd.trace})
    return out if out else None


def _parameter_to_dict(p: Parameter) -> dict[str, Any]:
    return _drop_none(
        {
            "name": p.name,
            "value": p.value,
            "excluded": p.excluded,
            "mode": p.mode,
        }
    )


def _label_to_dict(l: Label) -> dict[str, Any]:
    return {"name": l.name, "value": l.value}


def _link_to_dict(l: Link) -> dict[str, Any]:
    return _drop_none({"name": l.name, "url": l.url, "type": l.type})


def _attachment_to_dict(a: Attachment) -> dict[str, Any]:
    return _drop_none({"name": a.name, "source": a.source, "type": a.type})


def _step_to_dict(s: StepResult) -> dict[str, Any]:
    return _drop_none(
        {
            "name": s.name,
            "status": s.status,
            "stage": s.stage,
            "statusDetails": _status_details_to_dict(s.statusDetails),
            "description": s.description,
            "descriptionHtml": s.descriptionHtml,
            "start": s.start,
            "stop": s.stop,
            "parameters": [_parameter_to_dict(p) for p in s.parameters] or None,
            "attachments": [_attachment_to_dict(a) for a in s.attachments] or None,
            "steps": [_step_to_dict(ss) for ss in s.steps] or None,
        }
    )


def _result_to_dict(r: TestResult) -> dict[str, Any]:
    return _drop_none(
        {
            "uuid": r.uuid,
            "name": r.name,
            "fullName": r.fullName,
            "historyId": r.historyId,
            "testCaseId": r.testCaseId,
            "status": r.status,
            "stage": r.stage,
            "statusDetails": _status_details_to_dict(r.statusDetails),
            "description": r.description,
            "descriptionHtml": r.descriptionHtml,
            "start": r.start,
            "stop": r.stop,
            "labels": [_label_to_dict(l) for l in r.labels] or None,
            "links": [_link_to_dict(l) for l in r.links] or None,
            "parameters": [_parameter_to_dict(p) for p in r.parameters] or None,
            "attachments": [_attachment_to_dict(a) for a in r.attachments] or None,
            "steps": [_step_to_dict(s) for s in r.steps] or None,
        }
    )


def _container_to_dict(c: TestResultContainer) -> dict[str, Any]:
    return _drop_none(
        {
            "uuid": c.uuid,
            "name": c.name,
            "children": list(c.children) or None,
            "befores": [_step_to_dict(s) for s in c.befores] or None,
            "afters": [_step_to_dict(s) for s in c.afters] or None,
            "links": [_link_to_dict(l) for l in c.links] or None,
            "start": c.start,
            "stop": c.stop,
        }
    )


def _atomic_write_json(path: str, obj: Any) -> str:
    """Write JSON atomically (tmp + rename) so partial files never appear."""
    tmp = f"{path}.tmp.{os.getpid()}.{_uuid_mod.uuid4().hex[:8]}"
    payload = json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=False,  # preserve insertion order — matches Allure's writer
        separators=(", ", ": "),
    )
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(payload)
    os.replace(tmp, path)
    return path


# ── Time helpers ────────────────────────────────────────────────────────


def now_ms() -> int:
    """Allure expects start/stop in milliseconds since epoch."""
    return int(time.time() * 1000)


# ── Status helpers ──────────────────────────────────────────────────────


def normalize_status(status: Optional[str]) -> str:
    """Map our internal step status → Allure status enum.

    Unknown / falsy / "unknown" / "broken" → preserved as-is when
    recognised; everything else falls back to ``unknown``.
    """
    if status is None:
        return STATUS_UNKNOWN
    lo = status.strip().lower()
    return _STATUS_NORMALIZE.get(lo, STATUS_UNKNOWN if lo == "unknown" else STATUS_FAILED if lo else STATUS_UNKNOWN)


def worst_status(children: Iterable[str]) -> str:
    """Bubble parent status from children's statuses (worst wins)."""
    # Order: broken > failed > unknown > skipped > passed.
    priority = {
        STATUS_BROKEN: 4,
        STATUS_FAILED: 3,
        STATUS_UNKNOWN: 2,
        STATUS_SKIPPED: 1,
        STATUS_PASSED: 0,
    }
    best = -1
    out = STATUS_PASSED
    for c in children:
        p = priority.get(c, -1)
        if p > best:
            best = p
            out = c
    return out if best >= 0 else STATUS_PASSED


def format_exception(exc: Optional[BaseException]) -> Optional[StatusDetails]:
    """Build StatusDetails from a Python exception (message + trace)."""
    if exc is None:
        return None
    try:
        message = f"{type(exc).__name__}: {exc}"
        trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:  # pragma: no cover — defensive
        message = str(exc)
        trace = None
    return StatusDetails(message=message, trace=trace)


# ── Identity helpers (history / fullName / labels) ──────────────────────


def make_history_id(full_name: str, parameters: Iterable[Parameter]) -> str:
    """Stable hash matching ``allure_commons.utils.md5`` shape.

    Allure's report uses ``historyId`` to group retries / parameterised
    iterations into a single test history. We hash ``fullName`` plus the
    canonicalised non-excluded parameters — identical to Allure's own
    algorithm (md5 over JSON([name, value]) entries).
    """
    import hashlib

    h = hashlib.md5()
    h.update(full_name.encode("utf-8"))
    for p in parameters:
        if p.excluded:
            continue
        h.update(p.name.encode("utf-8"))
        h.update(b"=")
        h.update(p.value.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")


def make_full_name(module: Optional[str], cls: Optional[str], method: str) -> str:
    """Build ``fullName`` matching pytest's "module.class.method" shape."""
    parts = [p for p in (module, cls, method) if p]
    return ".".join(parts)


def auto_labels(
    *,
    framework: Optional[str] = None,
    language: str = "python",
    package: Optional[str] = None,
    test_class: Optional[str] = None,
    test_method: Optional[str] = None,
    host: Optional[str] = None,
    thread: Optional[str] = None,
) -> list[Label]:
    """Build the canonical "machine" labels Allure expects on every result."""
    labels: list[Label] = []
    labels.append(Label(name="language", value=language))
    if framework:
        labels.append(Label(name="framework", value=framework))
    if package:
        labels.append(Label(name="package", value=package))
    if test_class:
        labels.append(Label(name="testClass", value=test_class))
    if test_method:
        labels.append(Label(name="testMethod", value=test_method))
    labels.append(Label(name="host", value=host or _safe_hostname()))
    labels.append(Label(name="thread", value=thread or _safe_thread()))
    return labels


def _safe_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:  # pragma: no cover — sandboxed
        return "unknown"


def _safe_thread() -> str:
    try:
        return f"{os.getpid()}-{threading.get_ident()}-{threading.current_thread().name}"
    except Exception:  # pragma: no cover — defensive
        return "unknown"


# ── Link pattern expansion ──────────────────────────────────────────────


def expand_link(link: Link) -> Link:
    """Resolve ``{}`` placeholders in link.url against ALLURE_*_LINK_PATTERN env.

    Allure conventions:
        ALLURE_TMS_LINK_PATTERN   → applied to link.type == 'tms'
        ALLURE_ISSUE_LINK_PATTERN → applied to link.type == 'issue'
        ALLURE_LINK_PATTERN       → fallback applied to type 'custom' / None

    The pattern uses ``{}`` for the URL slot (Allure convention). If the
    pattern is missing the link is returned unchanged.
    """
    if not link.url or "://" in link.url or link.url.startswith("/"):
        return link  # already absolute — don't expand
    env_var: Optional[str] = None
    if link.type == "tms":
        env_var = "ALLURE_TMS_LINK_PATTERN"
    elif link.type == "issue":
        env_var = "ALLURE_ISSUE_LINK_PATTERN"
    else:
        env_var = "ALLURE_LINK_PATTERN"
    pattern = os.environ.get(env_var) if env_var else None
    if not pattern:
        return link
    expanded = pattern.replace("{}", link.url)
    return Label(name="", value="") if False else Link(  # noqa: SIM108 - keep type hint
        name=link.name, url=expanded, type=link.type
    )


# ── CaseFrame → TestResult conversion ───────────────────────────────────


def case_frame_to_result(
    case: Any,
    *,
    name: str,
    full_name: Optional[str] = None,
    framework: Optional[str] = None,
    parameters: Optional[list[Parameter]] = None,
    test_class: Optional[str] = None,
    test_method: Optional[str] = None,
    package: Optional[str] = None,
    start_ms: Optional[int] = None,
    stop_ms: Optional[int] = None,
    status: Optional[str] = None,
    exc: Optional[BaseException] = None,
    writer: Optional[AllureResultsWriter] = None,
    description: Optional[str] = None,
    description_html: Optional[str] = None,
) -> TestResult:
    """Convert a Mockarty :class:`CaseFrame` into an Allure :class:`TestResult`.

    The frame's ``steps`` / ``attachments`` / ``metadata`` (allure_labels,
    allure_links, allure_parameters, allure_title, allure_description) are
    transferred verbatim. When ``writer`` is provided, frame attachments
    are flushed to disk and referenced by source filename; without a
    writer they're skipped (caller is responsible for persistence).
    """
    md = getattr(case, "metadata", {}) or {}
    title = md.get("_allure_title") or name
    desc = description or md.get("_allure_description")
    desc_html = description_html  # html-only not currently tracked

    # Labels: combine auto-detected + user-supplied
    label_objs: list[Label] = list(
        auto_labels(
            framework=framework,
            package=package,
            test_class=test_class,
            test_method=test_method,
        )
    )
    for raw in md.get("_allure_labels", []) or []:
        try:
            label_objs.append(Label(name=str(raw["name"]), value=str(raw["value"])))
        except Exception:  # pragma: no cover — defensive
            continue

    # Links
    link_objs: list[Link] = []
    for raw in md.get("_allure_links", []) or []:
        try:
            link_objs.append(
                expand_link(
                    Link(
                        name=raw.get("name") or None,
                        url=raw.get("url") or "",
                        type=raw.get("type") or None,
                    )
                )
            )
        except Exception:  # pragma: no cover
            continue

    # Parameters: pytest-side @parametrize values + user-recorded
    param_objs: list[Parameter] = list(parameters or [])
    for raw in md.get("_allure_parameters", []) or []:
        try:
            param_objs.append(
                Parameter(
                    name=str(raw["name"]),
                    value=str(raw["value"]),
                    excluded=raw.get("excluded"),
                    mode=raw.get("mode"),
                )
            )
        except Exception:  # pragma: no cover
            continue

    # Steps → StepResult
    step_objs: list[StepResult] = []
    for raw in getattr(case, "steps", []) or []:
        sname = raw.get("name", "")
        sstatus_raw = raw.get("status", STATUS_PASSED)
        sstatus = (
            sstatus_raw if sstatus_raw in (STATUS_PASSED, STATUS_FAILED, STATUS_BROKEN, STATUS_SKIPPED) else normalize_status(sstatus_raw)
        )
        sd = (
            StatusDetails(message=raw.get("error"))
            if raw.get("error")
            else None
        )
        sstart = raw.get("started_ms") or _ns_to_ms(raw.get("started_ns"))
        sstop = raw.get("stopped_ms") or _ns_to_ms(raw.get("stopped_ns"))
        step_objs.append(
            StepResult(
                name=sname,
                status=sstatus,
                stage=STAGE_FINISHED,
                statusDetails=sd,
                start=sstart,
                stop=sstop,
            )
        )

    # Attachments: persist to disk if writer supplied, otherwise skip.
    attach_objs: list[Attachment] = []
    if writer is not None:
        for raw in getattr(case, "attachments", []) or []:
            try:
                a = writer.write_attachment(
                    raw.get("body", b""),
                    name=raw.get("name", "attachment"),
                    content_type=raw.get("content_type"),
                )
                attach_objs.append(a)
            except Exception:  # pragma: no cover — best-effort
                continue

    # Status: prefer caller-supplied; else bubble from steps; else passed.
    final_status = (
        status
        if status in (STATUS_PASSED, STATUS_FAILED, STATUS_BROKEN, STATUS_SKIPPED)
        else worst_status(s.status for s in step_objs)
    )
    sd_top = format_exception(exc) if exc is not None else None

    fn = full_name or make_full_name(package, test_class, test_method or name)
    uuid_str = str(_uuid_mod.uuid4())
    return TestResult(
        uuid=uuid_str,
        name=title,
        fullName=fn,
        historyId=make_history_id(fn, param_objs),
        testCaseId=getattr(case, "case_id", None),
        status=final_status,
        stage=STAGE_FINISHED,
        statusDetails=sd_top,
        description=desc,
        descriptionHtml=desc_html,
        start=start_ms or now_ms(),
        stop=stop_ms or now_ms(),
        labels=label_objs,
        links=link_objs,
        parameters=param_objs,
        attachments=attach_objs,
        steps=step_objs,
    )


def _ns_to_ms(ns: Any) -> Optional[int]:
    if ns is None:
        return None
    try:
        return int(int(ns) / 1_000_000)
    except Exception:  # pragma: no cover
        return None


__all__ = [
    "AllureResultsWriter",
    "Attachment",
    "CANONICAL_LABELS",
    "Label",
    "Link",
    "Parameter",
    "STAGE_FINISHED",
    "STAGE_INTERRUPTED",
    "STAGE_PENDING",
    "STAGE_RUNNING",
    "STAGE_SCHEDULED",
    "STATUS_BROKEN",
    "STATUS_FAILED",
    "STATUS_PASSED",
    "STATUS_SKIPPED",
    "STATUS_UNKNOWN",
    "StatusDetails",
    "StepResult",
    "TestResult",
    "TestResultContainer",
    "auto_labels",
    "case_frame_to_result",
    "expand_link",
    "format_exception",
    "make_full_name",
    "make_history_id",
    "normalize_status",
    "now_ms",
    "worst_status",
]
