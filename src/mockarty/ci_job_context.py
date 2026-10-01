"""Private selected CI delivery context, never a stored report property."""
from __future__ import annotations

import base64
import copy
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

CI_CONTEXT_ENVIRONMENT = "MOCKARTY_CI_CONTEXT"
_ZERO = str(uuid.UUID(int=0))
_ERROR = "invalid or unmatched selected CI context"


def _uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and value != _ZERO and str(uuid.UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _text(value: Any, maximum: int) -> bool:
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and len(value.encode("utf-8")) <= maximum
            and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value))


@dataclass(frozen=True)
class CICallback:
    token: str = field(repr=False)
    launch_id: str
    group_id: str
    attempt_id: str
    invocation_id: str
    item_uid: str = _ZERO

    def to_wire(self, *, completion: bool = False) -> dict[str, str]:
        if (not isinstance(self.token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", self.token)
                or base64.urlsafe_b64encode(base64.urlsafe_b64decode(self.token + "=")).decode().rstrip("=") != self.token
                or not all(_uuid(x) for x in (self.launch_id, self.group_id, self.attempt_id, self.invocation_id))
                or (self.item_uid not in ("", _ZERO) if completion else not _uuid(self.item_uid))):
            raise ValueError(_ERROR)
        return {"token": self.token, "launchId": self.launch_id, "groupId": self.group_id,
                "attemptId": self.attempt_id, "invocationId": self.invocation_id,
                "itemUid": _ZERO if completion else self.item_uid}


@dataclass(frozen=True)
class CIJobContext:
    namespace: str
    callback: CICallback = field(repr=False)
    _items: tuple[dict[str, Any], ...] = field(repr=False)
    _raw: str = field(repr=False)

    def _matches_report(self, payload: dict[str, Any]) -> bool:
        matches = [i for i in self._items
                   if (not i["selector"].get("id") or i["selector"]["id"] in (payload.get("externalId"), payload.get("testCaseId")))
                   and (not i["selector"].get("selector") or i["selector"]["selector"] == payload.get("fullName"))]
        if len(matches)>1:
            raise ValueError(_ERROR)
        return len(matches)==1

    def bind_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        matches = [i for i in self._items
                   if (not i["selector"].get("id") or i["selector"]["id"] in (payload.get("externalId"), payload.get("testCaseId")))
                   and (not i["selector"].get("selector") or i["selector"]["selector"] == payload.get("fullName"))]
        if len(matches) != 1 or payload.get("caseId") not in (None, "", matches[0]["caseId"]):
            raise ValueError(_ERROR)
        item = matches[0]
        cb = CICallback(self.callback.token, self.callback.launch_id, self.callback.group_id,
                        self.callback.attempt_id, self.callback.invocation_id, item["itemUid"]).to_wire()
        if payload.get("ciContext") not in (None, cb):
            raise ValueError(_ERROR)
        out = copy.deepcopy(payload)
        out.update(caseId=item["caseId"], ciContext=cb, autoCreate=False, claimCaseOwnership=False)
        out.pop("planId", None)
        out.pop("planRunId", None)
        return out


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(_ERROR)
        out[key] = value
    return out


def load_ci_job_context(raw: str) -> CIJobContext:
    try:
        if not isinstance(raw, str) or not 0 < len(raw) <= 1 << 20 or not re.fullmatch(r"[A-Za-z0-9_-]+", raw):
            raise ValueError(_ERROR)
        data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if base64.urlsafe_b64encode(data).decode().rstrip("=") != raw:
            raise ValueError(_ERROR)
        job = json.loads(data, object_pairs_hook=_unique_object)
        if set(job) != {"format", "namespace", "token", "launchId", "groupId", "attemptId", "invocationId", "items"}:
            raise ValueError(_ERROR)
        cb = CICallback(job["token"], job["launchId"], job["groupId"], job["attemptId"], job["invocationId"])
        cb.to_wire(completion=True)
        if job["format"] != "mockarty.native-ci-job/v1" or not _text(job["namespace"], 255) or not isinstance(job["items"], list) or not 0 < len(job["items"]) <= 1000:
            raise ValueError(_ERROR)
        seen = set()
        for item in job["items"]:
            if set(item) != {"selector", "itemUid", "caseId", "versionId", "jobConfigId", "groupId", "attemptId"}:
                raise ValueError(_ERROR)
            if (not all(_uuid(item[k]) for k in ("itemUid", "caseId", "versionId", "jobConfigId"))
                    or item["groupId"] != cb.group_id or item["attemptId"] != cb.attempt_id or item["itemUid"] in seen):
                raise ValueError(_ERROR)
            sel = item["selector"]
            if not isinstance(sel, dict) or set(sel) - {"id", "selector"} or not (sel.get("id") or sel.get("selector")):
                raise ValueError(_ERROR)
            for k, size in (("id", 512), ("selector", 2048)):
                if k in sel and (not isinstance(sel[k], str) or (sel[k] != "" and not _text(sel[k], size))):
                    raise ValueError(_ERROR)
            seen.add(item["itemUid"])
        return CIJobContext(job["namespace"], cb, tuple(job["items"]), raw)
    except (ValueError, TypeError, KeyError, UnicodeError, AttributeError, RecursionError):
        raise ValueError(_ERROR) from None


def _clean(value: Any, secrets: list[str], depth: int = 0, attachment: bool = False) -> Any:
    if depth > 64:
        raise ValueError(_ERROR)
    if isinstance(value, dict):
        if str(value.get("name", "")).upper() == CI_CONTEXT_ENVIRONMENT:
            return None
        out = {}
        for key, item in value.items():
            if str(key).upper() == CI_CONTEXT_ENVIRONMENT:
                continue
            if key == "bodyB64" and attachment and depth == 2:
                try:
                    data = base64.b64decode(item, validate=True)
                except (ValueError, TypeError):
                    raise ValueError("invalid attachment encoding") from None
                if any(s.encode() in data for s in secrets):
                    raise ValueError("attachment contains private CI capability")
                # Only the typed root attachment field is opaque file bytes.
                if attachment and depth == 2:
                    out[key] = item
                    continue
            out[key] = _clean(item, secrets, depth + 1, depth == 0 and key == "attachments")
        return out
    if isinstance(value, list):
        return [result for item in value if (result := _clean(item, secrets, depth + 1, attachment)) is not None]
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
    return value


def prepare_ci_report(namespace: str, payload: dict[str, Any], callback: CICallback | None = None) -> dict[str, Any]:
    raw = os.environ.get(CI_CONTEXT_ENVIRONMENT, "")
    out = copy.deepcopy(payload)
    if callback is not None:
        out["ciContext"] = callback.to_wire()
    if raw:
        job = load_ci_job_context(raw)
        if job.namespace != namespace:
            raise ValueError(_ERROR)
        out = job.bind_report(out)
    ci = out.pop("ciContext", None)
    if ci is None:
        return out
    if not isinstance(ci, dict) or set(ci) != {"token", "launchId", "groupId", "attemptId", "invocationId", "itemUid"}:
        raise ValueError(_ERROR)
    CICallback(ci["token"], ci["launchId"], ci["groupId"], ci["attemptId"], ci["invocationId"], ci["itemUid"]).to_wire()
    out = _clean(out, [ci["token"]] + ([raw] if raw else []))
    out["ciContext"] = ci
    _validate_selected_report(out)
    return out


def sanitize_ci_environment(env: dict[str, str]) -> dict[str, str]:
    """Omit private delivery context before framework files are persisted."""
    raw = os.environ.get(CI_CONTEXT_ENVIRONMENT, "")
    secrets = [v for k, v in env.items() if k.upper() == CI_CONTEXT_ENVIRONMENT and v]
    if not raw and secrets:
        raw = secrets[0]
    if raw:
        secrets.append(raw)
        try:
            token = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))).get("token")
            if isinstance(token, str) and token:
                secrets.append(token)
        except (ValueError, TypeError, AttributeError, UnicodeError):
            pass
    return _clean({k: v for k, v in env.items() if k.upper() != CI_CONTEXT_ENVIRONMENT}, secrets)


def _validate_selected_report(body: dict[str, Any]) -> None:
    if type(body.get("schemaVersion", 0)) is not int or body.get("schemaVersion", 0) not in (0, 1) or body.get("status") not in ("passed", "failed", "skipped", "cancelled", "broken", "error"):
        raise ValueError(_ERROR)
    steps, attachments = body.get("steps"), body.get("attachments")
    steps = [] if steps is None else steps
    attachments = [] if attachments is None else attachments
    if not isinstance(steps, list) or not isinstance(attachments, list) or len(steps) > 1000 or len(attachments) > 32:
        raise ValueError(_ERROR)
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("name"), str) or not step["name"].strip() or step.get("status") not in ("passed", "failed", "skipped", "broken", "error"):
            raise ValueError(_ERROR)
    total = 0
    for attachment in attachments:
        if not isinstance(attachment, dict) or not isinstance(attachment.get("name"), str) or not attachment["name"].strip():
            raise ValueError(_ERROR)
        inline, ref = attachment.get("bodyB64", ""), attachment.get("blobUri", "")
        if not isinstance(inline, str) or not isinstance(ref, str) or bool(inline.strip()) == bool(ref.strip()):
            raise ValueError(_ERROR)
        if ref.strip():
            continue
        if len(inline) > (256 << 10) * 4 // 3 + 4:
            raise ValueError(_ERROR)
        try:
            data = base64.b64decode(inline, validate=True)
        except (ValueError, TypeError):
            raise ValueError(_ERROR) from None
        total += len(data)
        if len(data) > 256 << 10 or total > 1 << 20:
            raise ValueError(_ERROR)
