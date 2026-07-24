import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class EvidenceItemResponse(BaseModel):
    variant_id: UUID
    position: str
    treatment_role: str
    title: str
    views_delta: int
    likes_delta: int
    comments_delta: int
    attributed_unique_clicks: int
    unique_clicks_per_1k: float


class CandidateResponse(BaseModel):
    id: UUID
    project_id: UUID
    insight_id: UUID
    slot: str
    relationship_type: str
    statement: str
    why_this_follows: str | None
    recommended: bool
    recommendation_reason: str | None
    previous_learning: str | None
    remaining_unknown: str | None
    status: str
    created_at: datetime


class InsightSummaryResponse(BaseModel):
    id: UUID
    project_id: UUID
    experiment_id: UUID
    version: int
    is_current: bool
    research_question: str | None
    hypothesis_text: str | None
    primary_metric: str | None
    outcome_type: str | None
    outcome_description: str | None
    supported_learning: str | None
    generated_at: datetime


class InsightDetailResponse(BaseModel):
    id: UUID
    project_id: UUID
    experiment_id: UUID
    evidence_snapshot_id: UUID
    version: int
    is_current: bool
    superseded_at: datetime | None
    generated_by_ai_run_id: UUID | None
    research_question: str | None
    hypothesis_text: str | None
    primary_metric: str | None
    outcome_type: str | None
    evidence_basis: dict
    supported_learning: str | None
    do_not_infer_yet: list[str]
    recommended_next_test: str | None
    limitations: list[str]
    outcome_description: str | None
    generated_at: datetime
    candidates: list[CandidateResponse]
    evidence_items: list[EvidenceItemResponse]

    @field_validator("evidence_basis", mode="before")
    @classmethod
    def parse_evidence_basis(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v or {"schemaVersion": 1}

    @field_validator("do_not_infer_yet", "limitations", mode="before")
    @classmethod
    def parse_arrays(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v or []

    @classmethod
    def from_row(cls, row: dict) -> "InsightDetailResponse":
        candidates = [CandidateResponse(**c) for c in row.get("candidates", [])]
        items = [EvidenceItemResponse(**i) for i in row.get("evidence_items", [])]
        return cls(**{k: v for k, v in row.items() if k not in ("candidates", "evidence_items")},
                   candidates=candidates, evidence_items=items)
