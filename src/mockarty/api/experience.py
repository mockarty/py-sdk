"""Search and record reusable AutoTester run experience."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from urllib.parse import quote

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.experience import (
    ExperienceRecordResponse,
    ExperienceReviewDetail,
    ExperienceReviewPage,
    ExperienceReviewResponse,
    ExperienceSearchResponse,
)

_SEARCH_PATH = "/api/v1/autotester/context/knowledge/search"
_RECORD_PATH = "/api/v1/autotester/context/knowledge"
_REVIEW_PATH = "/api/v1/autotester/context/knowledge/review"


def _review_id_path(record_id: str) -> str:
    record_id = (record_id or "").strip()
    if not record_id:
        raise ValueError("id is required")
    return f"{_REVIEW_PATH}/{quote(record_id, safe='')}"


def _review_body(
    *,
    decision: str,
    expected_version: int,
    reason: str,
    idempotency_key: str,
    expires_at: datetime | None,
    supersedes_id: str,
    contradicts_ids: Sequence[str] | None,
) -> dict[str, object]:
    decision = (decision or "").strip()
    if decision not in {"publish", "reject"}:
        raise ValueError("decision must be publish or reject")
    reason = (reason or "").strip()
    idempotency_key = (idempotency_key or "").strip()
    if expected_version <= 0:
        raise ValueError("expected_version must be positive")
    if not reason:
        raise ValueError("reason is required")
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    if decision == "reject" and (expires_at or supersedes_id or contradicts_ids):
        raise ValueError("publish relations and expiry are not valid for reject")
    body: dict[str, object] = {
        "decision": decision,
        "expectedVersion": expected_version,
        "reason": reason,
        "idempotencyKey": idempotency_key,
    }
    if expires_at is not None:
        body["expiresAt"] = expires_at.isoformat()
    if supersedes_id:
        body["supersedesId"] = supersedes_id
    if contradicts_ids:
        body["contradictsIds"] = list(contradicts_ids)
    return body


def _search_params(
    query: str,
    kinds: Sequence[str] | None,
    min_trust: str | None,
    limit: int | None,
) -> dict[str, object]:
    text = (query or "").strip()
    if not text:
        raise ValueError("query is required")
    params: dict[str, object] = {"query": text}
    if kinds:
        params["kinds"] = ",".join(kinds)
    if min_trust:
        params["minTrust"] = min_trust
    if limit is not None:
        params["k"] = limit
    return params


def _record_body(
    *,
    text: str,
    source: str,
    kind: str,
    title: str,
    mission_id: str,
    event_seq: int,
    metadata: Mapping[str, str] | None,
) -> dict[str, object]:
    if not (text or "").strip():
        raise ValueError("text is required")
    if not (source or "").strip():
        raise ValueError("source is required")
    return {
        "text": text,
        "source": source,
        "kind": kind,
        "title": title,
        "missionId": mission_id,
        "eventSeq": event_seq,
        "metadata": dict(metadata or {}),
    }


class ExperienceAPI(SyncAPIBase):
    def search(
        self,
        *,
        query: str,
        kinds: Sequence[str] | None = None,
        min_trust: str | None = None,
        limit: int | None = None,
    ) -> ExperienceSearchResponse:
        resp = self._request(
            "GET", _SEARCH_PATH, params=_search_params(query, kinds, min_trust, limit)
        )
        return ExperienceSearchResponse.model_validate(resp.json())

    def record(
        self,
        *,
        text: str,
        source: str,
        kind: str = "product_fact",
        title: str = "",
        mission_id: str = "",
        event_seq: int = 0,
        metadata: Mapping[str, str] | None = None,
    ) -> ExperienceRecordResponse:
        resp = self._request(
            "POST",
            _RECORD_PATH,
            json=_record_body(
                text=text,
                source=source,
                kind=kind,
                title=title,
                mission_id=mission_id,
                event_seq=event_seq,
                metadata=metadata,
            ),
        )
        return ExperienceRecordResponse.model_validate(resp.json())

    def list_review(
        self, *, state: str = "candidate", limit: int | None = None, cursor: str = ""
    ) -> ExperienceReviewPage:
        params: dict[str, object] = {"state": (state or "candidate").strip()}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        resp = self._request("GET", _REVIEW_PATH, params=params)
        return ExperienceReviewPage.model_validate(resp.json())

    def get_review(self, record_id: str) -> ExperienceReviewDetail:
        resp = self._request("GET", _review_id_path(record_id))
        return ExperienceReviewDetail.model_validate(resp.json())

    def review(
        self,
        record_id: str,
        *,
        decision: str,
        expected_version: int,
        reason: str,
        idempotency_key: str,
        expires_at: datetime | None = None,
        supersedes_id: str = "",
        contradicts_ids: Sequence[str] | None = None,
    ) -> ExperienceReviewResponse:
        resp = self._request(
            "POST",
            _review_id_path(record_id),
            json=_review_body(
                decision=decision,
                expected_version=expected_version,
                reason=reason,
                idempotency_key=idempotency_key,
                expires_at=expires_at,
                supersedes_id=supersedes_id,
                contradicts_ids=contradicts_ids,
            ),
        )
        return ExperienceReviewResponse.model_validate(resp.json())


class AsyncExperienceAPI(AsyncAPIBase):
    async def search(
        self,
        *,
        query: str,
        kinds: Sequence[str] | None = None,
        min_trust: str | None = None,
        limit: int | None = None,
    ) -> ExperienceSearchResponse:
        resp = await self._request(
            "GET", _SEARCH_PATH, params=_search_params(query, kinds, min_trust, limit)
        )
        return ExperienceSearchResponse.model_validate(resp.json())

    async def record(
        self,
        *,
        text: str,
        source: str,
        kind: str = "product_fact",
        title: str = "",
        mission_id: str = "",
        event_seq: int = 0,
        metadata: Mapping[str, str] | None = None,
    ) -> ExperienceRecordResponse:
        resp = await self._request(
            "POST",
            _RECORD_PATH,
            json=_record_body(
                text=text,
                source=source,
                kind=kind,
                title=title,
                mission_id=mission_id,
                event_seq=event_seq,
                metadata=metadata,
            ),
        )
        return ExperienceRecordResponse.model_validate(resp.json())

    async def list_review(
        self, *, state: str = "candidate", limit: int | None = None, cursor: str = ""
    ) -> ExperienceReviewPage:
        params: dict[str, object] = {"state": (state or "candidate").strip()}
        if limit is not None:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        resp = await self._request("GET", _REVIEW_PATH, params=params)
        return ExperienceReviewPage.model_validate(resp.json())

    async def get_review(self, record_id: str) -> ExperienceReviewDetail:
        resp = await self._request("GET", _review_id_path(record_id))
        return ExperienceReviewDetail.model_validate(resp.json())

    async def review(
        self,
        record_id: str,
        *,
        decision: str,
        expected_version: int,
        reason: str,
        idempotency_key: str,
        expires_at: datetime | None = None,
        supersedes_id: str = "",
        contradicts_ids: Sequence[str] | None = None,
    ) -> ExperienceReviewResponse:
        resp = await self._request(
            "POST",
            _review_id_path(record_id),
            json=_review_body(
                decision=decision,
                expected_version=expected_version,
                reason=reason,
                idempotency_key=idempotency_key,
                expires_at=expires_at,
                supersedes_id=supersedes_id,
                contradicts_ids=contradicts_ids,
            ),
        )
        return ExperienceReviewResponse.model_validate(resp.json())
