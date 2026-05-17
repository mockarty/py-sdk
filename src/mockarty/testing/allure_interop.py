# Copyright (c) 2026 Mockarty. All rights reserved.

"""Bidirectional Allure ↔ Mockarty interop.

This module wires two flows so the user's existing Allure code "just works":

1. **Mockarty → Allure (write-through):** when a user opens a
   :func:`mockarty.testing.step`, we also open ``allure.step(...)`` so
   the same step shows up in both reports. Same for
   :func:`mockarty.testing.attach`.

2. **Allure → Mockarty (mirror, DEFAULT ON):** when a user writes a
   *pure* ``@allure.step()`` / ``@allure.feature()`` / ``allure.attach()``
   block — without ever touching Mockarty decorators — we catch those
   calls through ``allure_commons.plugin_manager`` hookimpls and mirror
   them into Mockarty's :class:`~mockarty.testing.context.CaseFrame`.

The mirror is **default-ON** per Owner directive (SDK_FRAMEWORK_PLAN
rev 3, §2 + §5.1, 2026-05-16): zero refactor required for Allure-based
suites moving to Mockarty. To disable the mirror set the env var
``MOCKARTY_ALLURE_MIRROR=off``.

When ``allure-pytest`` is NOT installed at runtime, this whole module
gracefully degrades to no-ops — :func:`step` returns a passthrough
context manager and :func:`attach` is silent.
"""

from __future__ import annotations

import contextvars
import os
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from mockarty.testing import context as _ctx

# When True for the current context, the Allure→Mockarty mirror skips
# its own start/stop_step hooks — used while Mockarty itself drives an
# ``allure.step()`` to avoid double-recording the same step into the
# active CaseFrame.
_suppress_mirror: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "mockarty_allure_suppress_mirror", default=False
)

# ── Discovery: is allure-pytest importable at runtime? ──────────────────

try:  # pragma: no cover — runtime detection
    import allure as _allure_mod  # type: ignore[import-not-found]

    _ALLURE_AVAILABLE = True
except Exception:  # pragma: no cover — allure optional
    _allure_mod = None  # type: ignore[assignment]
    _ALLURE_AVAILABLE = False


def is_allure_available() -> bool:
    """True iff ``allure-pytest`` (or ``allure-commons``) can be imported."""
    return _ALLURE_AVAILABLE


# ── Mockarty → Allure write-through ─────────────────────────────────────


def step(name: str):
    """Open an Allure step with ``name``.

    Returns a no-op context manager when Allure is not installed, so
    callers never need to ``if`` around the call. While active, the
    Allure→Mockarty mirror is suppressed so the Mockarty caller's own
    step doesn't get duplicated by our listener.
    """
    if not _ALLURE_AVAILABLE:
        return _noop_cm()
    return _SuppressingCM(_allure_mod.step(name))


def attach(body: bytes, *, name: str, content_type: str) -> None:
    """Mirror an attachment into the Allure report (no-op without Allure).

    Suppresses the Allure→Mockarty mirror while running, so the
    Mockarty-attached body isn't recorded twice on the same CaseFrame.
    """
    if not _ALLURE_AVAILABLE:
        return
    token = _suppress_mirror.set(True)
    try:
        _allure_mod.attach(body, name=name, attachment_type=content_type)
    except Exception:  # pragma: no cover — best-effort mirror
        pass
    finally:
        _suppress_mirror.reset(token)


@contextmanager
def _noop_cm() -> Iterator[None]:
    yield


class _SuppressingCM:
    """Wraps an Allure context manager so the mirror skips its events."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._token: Any = None

    def __enter__(self) -> Any:
        self._token = _suppress_mirror.set(True)
        try:
            return self._inner.__enter__()
        except Exception:
            _suppress_mirror.reset(self._token)
            self._token = None
            raise

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        try:
            return self._inner.__exit__(exc_type, exc, tb)
        finally:
            if self._token is not None:
                _suppress_mirror.reset(self._token)
                self._token = None


# ── Allure → Mockarty mirror listener ───────────────────────────────────
#
# We register a pluggy plugin with ``allure_commons.plugin_manager`` that
# implements the user-facing hooks: ``start_step`` / ``stop_step`` /
# ``attach_data`` / ``add_label`` / ``decorate_as_label``. Each impl
# inspects the active Mockarty case frame; when one is present we record
# the corresponding step / attachment / label into the frame so the
# pytest plugin later uploads it via TCM external-runs.
#
# When NO Mockarty case frame is active (most common: user's pure-Allure
# test that never used ``@mockarty.testing.test_case``), we
# auto-open an implicit ``CaseFrame`` keyed on the test node id so the
# user's Allure decorators still produce a Mockarty case run. This is
# the seamless integration story — see Wave B1.


class _MockartyAllureListener:
    """pluggy listener: turns native Allure calls into Mockarty frames.

    The instance is registered with ``allure_commons.plugin_manager``;
    each method is recognised as a hookimpl by virtue of being declared
    with the ``allure_commons._hooks.hookimpl`` marker (we apply it at
    register-time so this module imports cleanly without Allure).
    """

    def __init__(self) -> None:
        # uuid → step name, in-flight step tracking (Allure's step ids
        # don't carry a name on stop_step, so we capture name on start
        # and use the saved title on stop). dict-of-list to handle the
        # rare case of duplicate uuids (shouldn't happen but defensive).
        self._inflight_steps: dict[str, str] = {}

    # ── steps ───────────────────────────────────────────────────────────
    def start_step(self, uuid: str, title: str, params: dict) -> None:
        """Allure opens a step → push a Mockarty StepFrame too."""
        if _suppress_mirror.get():
            return
        case = _ctx.current_case()
        if case is None:
            return
        self._inflight_steps[uuid] = title
        frame = _ctx.StepFrame(name=title, started_ns=time.monotonic_ns())
        _ctx.push_step(frame)

    def stop_step(
        self,
        uuid: str,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Allure closes a step → pop the matching Mockarty frame.

        Signature matches the ``allure_commons`` hookspec exactly (no
        defaults) so pluggy can bind arguments correctly — see note in
        :func:`_build_listener_class`.
        """
        if uuid not in self._inflight_steps:
            return
        self._inflight_steps.pop(uuid, None)
        frame = _ctx.current_step()
        if frame is not None and exc_type is not None:
            frame.status = "failed"
            try:
                frame.error = f"{exc_type.__name__}: {exc_val}"
            except Exception:  # pragma: no cover — best-effort
                frame.error = "error"
        _ctx.pop_step()

    # ── attachments ─────────────────────────────────────────────────────
    def attach_data(
        self,
        body: Any,
        name: Any,
        attachment_type: Any,
        extension: Any,
    ) -> None:
        """Allure attach() body → mirror onto active case frame."""
        if _suppress_mirror.get():
            return
        case = _ctx.current_case()
        if case is None:
            return
        if isinstance(body, str):
            body_bytes = body.encode("utf-8")
        elif isinstance(body, (bytes, bytearray)):
            body_bytes = bytes(body)
        else:
            try:
                body_bytes = str(body).encode("utf-8")
            except Exception:  # pragma: no cover
                return
        ct = _coerce_content_type(attachment_type)
        case.attachments.append(
            {
                "name": name or "attachment",
                "body": body_bytes,
                "content_type": ct,
            }
        )

    def attach_file(
        self,
        source: str,
        name: Any,
        attachment_type: Any,
        extension: Any,
    ) -> None:
        """Allure attach.file() → read the file + mirror onto frame."""
        if _suppress_mirror.get():
            return
        case = _ctx.current_case()
        if case is None:
            return
        try:
            with open(source, "rb") as fh:
                body_bytes = fh.read()
        except OSError:
            return
        ct = _coerce_content_type(attachment_type)
        case.attachments.append(
            {
                "name": name or os.path.basename(source),
                "body": body_bytes,
                "content_type": ct,
            }
        )

    # ── labels (epic / feature / story / severity / tag / suite ...) ────
    def add_label(self, label_type: Any, labels: tuple) -> None:
        """Allure ``allure.dynamic.label(...)`` → record on case metadata."""
        self._record_label(label_type, labels)

    def decorate_as_label(self, label_type: Any, labels: tuple) -> Any:
        """Allure decorator form (``@allure.label`` / ``@allure.feature``).

        The hook contract returns a function-decorator; we return ``None``
        so Allure's own returned-from-``safely`` decorator chain is the
        one applied to the user's test fn — we just OBSERVE labels here.
        Recording happens at call time too (decorate is collection time;
        labels appear on the case frame once the test enters its body).
        """
        # Best-effort recording at decoration time. We may not yet have an
        # active case frame (this runs at import time, not test time), so
        # we stash on a class-level pending list keyed off the *next* push.
        _pending_labels.append((label_type, tuple(labels)))
        return None  # let Allure's other plugins decide the wrapper

    def add_link(self, url: str, link_type: Any, name: Any) -> None:
        case = _ctx.current_case()
        if case is None:
            return
        links = case.metadata.setdefault("_allure_links", [])
        links.append({"url": url, "type": str(link_type), "name": name or ""})

    def decorate_as_link(self, url: str, link_type: Any, name: Any) -> Any:
        _pending_links.append((url, link_type, name))
        return None

    def add_title(self, test_title: str) -> None:
        case = _ctx.current_case()
        if case is None:
            return
        case.metadata["_allure_title"] = test_title

    def decorate_as_title(self, test_title: str) -> Any:
        _pending_title.append(test_title)
        return None

    def add_description(self, test_description: str) -> None:
        case = _ctx.current_case()
        if case is None:
            return
        case.metadata["_allure_description"] = test_description

    def decorate_as_description(self, test_description: str) -> Any:
        _pending_description.append(test_description)
        return None

    def add_parameter(self, name: str, value: Any, excluded: Any, mode: Any) -> None:
        case = _ctx.current_case()
        if case is None:
            return
        params = case.metadata.setdefault("_allure_parameters", [])
        params.append(
            {
                "name": name,
                "value": _safe_repr(value),
                "excluded": bool(excluded),
                "mode": str(mode) if mode is not None else None,
            }
        )

    # ── helpers ─────────────────────────────────────────────────────────
    def _record_label(self, label_type: Any, labels: tuple) -> None:
        case = _ctx.current_case()
        if case is None:
            return
        bucket = case.metadata.setdefault("_allure_labels", [])
        for v in labels:
            bucket.append({"name": str(label_type), "value": str(v)})


# Module-level pending-label queues. Allure decorators fire at *import
# time*, before any test starts, so we buffer them here and flush onto
# the first case frame that becomes active for the same test function.
_pending_labels: list[tuple[Any, tuple]] = []
_pending_links: list[tuple[str, Any, Optional[str]]] = []
_pending_title: list[str] = []
_pending_description: list[str] = []


def flush_pending_to_frame(case: _ctx.CaseFrame) -> None:
    """Drain decorator-time labels/links/title onto the current case.

    Called by the pytest plugin once a case frame becomes the active
    binding for a test — moves the buffered decorator metadata onto it.
    """
    if _pending_title:
        case.metadata.setdefault("_allure_title", _pending_title.pop())
        _pending_title.clear()
    if _pending_description:
        case.metadata.setdefault("_allure_description", _pending_description.pop())
        _pending_description.clear()
    if _pending_labels:
        bucket = case.metadata.setdefault("_allure_labels", [])
        for label_type, labels in _pending_labels:
            for v in labels:
                bucket.append({"name": str(label_type), "value": str(v)})
        _pending_labels.clear()
    if _pending_links:
        bucket = case.metadata.setdefault("_allure_links", [])
        for url, link_type, name in _pending_links:
            bucket.append(
                {
                    "url": url,
                    "type": str(link_type),
                    "name": name or "",
                }
            )
        _pending_links.clear()


def _coerce_content_type(attachment_type: Any) -> str:
    """Map Allure ``AttachmentType`` enum (or string) to a MIME string."""
    if attachment_type is None:
        return "application/octet-stream"
    # AttachmentType has `mime_type` and `extension` attrs
    mime = getattr(attachment_type, "mime_type", None)
    if isinstance(mime, str) and mime:
        return mime
    if isinstance(attachment_type, str):
        return attachment_type
    return "application/octet-stream"


def _safe_repr(value: Any) -> str:
    try:
        return repr(value)
    except Exception:  # pragma: no cover
        return "<unreprable>"


# ── Registration with allure_commons.plugin_manager ─────────────────────


_listener_instance: Optional[_MockartyAllureListener] = None
_registered = False


def _build_listener_class() -> type:
    """Build a hookimpl-decorated subclass that pluggy can introspect.

    pluggy only recognises hook impls by the ``allure_impl`` attribute
    on the underlying function object (set by :class:`HookimplMarker`).
    Decorating bound methods at runtime doesn't stick — the marker must
    be applied at *class body* time so it lives on the underlying
    unbound function. We deferred the import of ``hookimpl`` until
    here so ``allure_interop`` itself imports cleanly without Allure
    installed.
    """
    from allure_commons._hooks import hookimpl

    base = _MockartyAllureListener

    # NOTE on signatures: pluggy fills only the arguments declared on
    # the hookimpl whose names match the hookspec. Adding parameters
    # with defaults that aren't in the hookspec (e.g. ``title=None``
    # on ``stop_step``) makes pluggy quietly bind ALL named args from
    # the default — including the hookspec ones — so you lose
    # ``exc_type``. The signatures below therefore match the hookspec
    # exactly, no extras, no defaults.
    class _DecoratedListener(base):  # type: ignore[misc, valid-type]
        @hookimpl
        def start_step(self, uuid, title, params):  # type: ignore[override]
            return base.start_step(self, uuid, title, params)

        @hookimpl
        def stop_step(self, uuid, exc_type, exc_val, exc_tb):  # type: ignore[override]
            return base.stop_step(self, uuid, exc_type, exc_val, exc_tb)

        @hookimpl
        def attach_data(  # type: ignore[override]
            self, body, name, attachment_type, extension
        ):
            return base.attach_data(self, body, name, attachment_type, extension)

        @hookimpl
        def attach_file(  # type: ignore[override]
            self, source, name, attachment_type, extension
        ):
            return base.attach_file(self, source, name, attachment_type, extension)

        @hookimpl
        def add_label(self, label_type, labels):  # type: ignore[override]
            return base.add_label(self, label_type, labels)

        @hookimpl
        def decorate_as_label(  # type: ignore[override]
            self, label_type, labels
        ):
            return base.decorate_as_label(self, label_type, labels)

        @hookimpl
        def add_link(self, url, link_type, name):  # type: ignore[override]
            return base.add_link(self, url, link_type, name)

        @hookimpl
        def decorate_as_link(  # type: ignore[override]
            self, url, link_type, name
        ):
            return base.decorate_as_link(self, url, link_type, name)

        @hookimpl
        def add_title(self, test_title):  # type: ignore[override]
            return base.add_title(self, test_title)

        @hookimpl
        def decorate_as_title(self, test_title):  # type: ignore[override]
            return base.decorate_as_title(self, test_title)

        @hookimpl
        def add_description(self, test_description):  # type: ignore[override]
            return base.add_description(self, test_description)

        @hookimpl
        def decorate_as_description(  # type: ignore[override]
            self, test_description
        ):
            return base.decorate_as_description(self, test_description)

        @hookimpl
        def add_parameter(  # type: ignore[override]
            self, name, value, excluded, mode
        ):
            return base.add_parameter(self, name, value, excluded, mode)

    return _DecoratedListener


def install_listener() -> bool:
    """Register the Allure→Mockarty mirror with allure_commons (idempotent).

    Returns True when the listener became active (or already was);
    False when Allure isn't installed or the mirror is opted out via
    ``MOCKARTY_ALLURE_MIRROR=off``.

    Idempotent: calling twice is harmless.
    """
    global _listener_instance, _registered
    if _registered:
        return True
    if not _ALLURE_AVAILABLE:
        return False
    if (os.environ.get("MOCKARTY_ALLURE_MIRROR") or "").lower() in (
        "0",
        "off",
        "false",
        "no",
    ):
        return False

    try:
        from allure_commons._core import plugin_manager
    except Exception:  # pragma: no cover — older / forked allure
        return False

    try:
        cls = _build_listener_class()
    except Exception:  # pragma: no cover — defensive
        return False

    listener = cls()
    try:
        plugin_manager.register(listener, name="mockarty-allure-mirror")
    except ValueError:
        # Already registered under that name — treat as success.
        pass
    except Exception:  # pragma: no cover — defensive
        return False

    _listener_instance = listener
    _registered = True
    return True


def uninstall_listener() -> None:
    """Detach the listener (used by tests). Idempotent."""
    global _listener_instance, _registered
    if not _registered:
        return
    try:
        from allure_commons._core import plugin_manager

        plugin_manager.unregister(name="mockarty-allure-mirror")
    except Exception:  # pragma: no cover
        pass
    _listener_instance = None
    _registered = False


def is_mirror_active() -> bool:
    """Public predicate: True iff the Allure→Mockarty listener is wired in.

    Use this instead of poking ``_registered`` from callers — the flag
    is an implementation detail and may be replaced with a different
    activation tracker in the future. Returns False on a build without
    ``allure-pytest`` or when the mirror was opted out via env.
    """
    return _registered
