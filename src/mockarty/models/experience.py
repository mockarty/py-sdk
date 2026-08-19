"""Models for reusable AutoTester run experience."""

from __future__ import annotations

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
    id: str
    kind: str
    provenance: str
