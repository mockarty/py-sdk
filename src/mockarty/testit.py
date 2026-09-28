"""Focused Test IT pytest source compatibility for Mockarty reporting.

Replace ``import testit`` with ``import mockarty.testit as testit``. The
supported annotations, step context manager and attachments retain their
call shapes; the Mockarty pytest plugin sends the result only to Mockarty.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Callable, TypeVar

from mockarty.testing import context as _ctx
from mockarty.testing.decorators import attach, step


F = TypeVar("F", bound=Callable[..., Any])
EXTERNAL_ID_ATTR = "__mockarty_testit_external_id__"
DISPLAY_NAME_ATTR = "__mockarty_testit_display_name__"
_MAX_ATTACHMENT_BYTES = 256 * 1024
_MAX_TOTAL_BYTES = 1024 * 1024
_MAX_ATTACHMENTS = 32


def _annotation(attr: str, value: str) -> Callable[[F], F]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Test IT compatibility annotation requires non-empty text")

    def decorate(fn: F) -> F:
        setattr(fn, attr, value.strip())
        return fn

    return decorate


def externalId(value: str) -> Callable[[F], F]:  # noqa: N802 - vendor call shape
    """Keep the autotest's source ID as the Mockarty external result ID."""
    return _annotation(EXTERNAL_ID_ATTR, value)


def displayName(value: str) -> Callable[[F], F]:  # noqa: N802 - vendor call shape
    """Use the source display name when creating the Mockarty TCM case."""
    return _annotation(DISPLAY_NAME_ATTR, value)


def addAttachments(  # noqa: N802 - vendor call shape
    data: str | Path | bytes | list[str | Path] | tuple[str | Path, ...],
    is_text: bool = False,
    name: str | None = None,
) -> None:
    """Attach text or existing files to the current Mockarty test result.

    This compatibility subset stores media at result level. A file added
    inside ``with testit.step(...)`` remains accessible in the result, but
    does not acquire the vendor's step-owned attachment relationship.
    """
    if is_text:
        if not isinstance(data, (str, bytes)):
            raise TypeError("text attachment must be str or bytes")
        body = data.encode("utf-8") if isinstance(data, str) else data
        _attach_inline(name or "attachment.txt", body, "text/plain; charset=utf-8")
        return
    paths = data if isinstance(data, (list, tuple)) else [data]
    if not paths:
        raise ValueError("at least one attachment path is required")
    for value in paths:
        if not isinstance(value, (str, Path)):
            raise TypeError("file attachment must be a path or list of paths")
        path = Path(value)
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size > _MAX_ATTACHMENT_BYTES:
            raise ValueError("inline attachment exceeds 256 KiB")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as stream:
            body = stream.read(_MAX_ATTACHMENT_BYTES + 1)
        _attach_inline(path.name, body, content_type)


def _attach_inline(name: str, body: bytes, content_type: str) -> None:
    if len(body) > _MAX_ATTACHMENT_BYTES:
        raise ValueError("inline attachment exceeds 256 KiB")
    case = _ctx.current_case()
    if case is not None:
        if len(case.attachments) >= _MAX_ATTACHMENTS:
            raise ValueError("external result permits at most 32 attachments")
        total = sum(len(a["body"]) for a in case.attachments) + len(body)
        if total > _MAX_TOTAL_BYTES:
            raise ValueError("inline attachments exceed 1 MiB total")
    attach(name, body, content_type=content_type)


__all__ = ["addAttachments", "displayName", "externalId", "step"]
