"""Search and record reusable AutoTester run experience."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from mockarty.api._base import AsyncAPIBase, SyncAPIBase
from mockarty.models.experience import (
    ExperienceRecordResponse,
    ExperienceSearchResponse,
)

_SEARCH_PATH = "/api/v1/autotester/context/knowledge/search"
_RECORD_PATH = "/api/v1/autotester/context/knowledge"


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
