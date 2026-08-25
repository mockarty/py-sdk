"""Models for reusable AutoTester run experience."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

EXPERIENCE_KIND_MISSION_LESSON = "mission_lesson"
EXPERIENCE_KIND_PITFALL = "pitfall"
EXPERIENCE_KIND_PRODUCT_FACT = "product_fact"
EXPERIENCE_KIND_DEFECT_ROOT_CAUSE = "defect_root_cause"


class ExperienceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    metadata: dict[str, str] = Field(default_factory=dict)
    id: str
    kind: str
    title: str = ""
    text: str
    source: str
    provenance: str
    mission_id: str = Field(default="", alias="missionId")
    event_seq: int = Field(default=0, alias="eventSeq")
    score: float = 0.0


class ExperienceSearchResponse(BaseModel):
    results: list[ExperienceItem] = Field(default_factory=list)
    engine: str = ""
    total: int = 0
    available: bool = False


class ExperienceRecordResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kind: str
    provenance: str
    state: str
    review_required: bool = Field(alias="reviewRequired")


class ExperienceReviewItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str = ""
    content: str = ""
    content_sha256: str = Field(default="", alias="contentSha256")
    metadata: dict[str, str] = Field(default_factory=dict)
    kind: str = ""
    source: str = ""
    mission_id: str = Field(default="", alias="missionId")
    provenance: str = ""
    state: str
    event_seq: int = Field(default=0, alias="eventSeq")
    version: int
    confidence: float = 0.0
    content_truncated: bool = Field(default=False, alias="contentTruncated")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")


class ExperienceReviewPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[ExperienceReviewItem] = Field(default_factory=list)
    next_cursor: str = Field(default="", alias="nextCursor")


class ExperienceReviewRelation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    record_id: str = Field(alias="recordId")
    type: str
    outgoing: bool


class ExperienceReviewMutation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    operation: str
    actor: str = ""
    reason: str = ""
    version: int
    created_at: datetime | None = Field(default=None, alias="createdAt")


class ExperienceReviewDetail(BaseModel):
    item: ExperienceReviewItem
    relations: list[ExperienceReviewRelation] = Field(default_factory=list)
    history: list[ExperienceReviewMutation] = Field(default_factory=list)


class ExperienceReviewResponse(BaseModel):
    item: ExperienceReviewItem
