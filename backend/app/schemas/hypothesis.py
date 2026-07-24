from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

_VALID_METRICS = ("clicks_per_1k_views", "comments_per_1k_views", "views", "product_clicks", "comments")
_VALID_STATUSES = ("generated", "draft", "approved", "testing", "tested", "rejected", "all")


class HypothesisPatchRequest(BaseModel):
    title: str | None = None
    statement: str | None = None
    research_question: str | None = None
    independent_variable: str | None = None
    control_condition: str | None = None
    treatment_condition: str | None = None
    controlled_elements: list[str] | None = None
    contradiction_condition: str | None = None
    primary_metric: str | None = None
    rationale: str | None = None
    category: str | None = None


class ApproveAndGenerateRequest(BaseModel):
    """
    Design fields submitted from the Hypothesis Review screen.
    All fields are optional — the service merges with the stored values.
    """
    title: str | None = None
    statement: str | None = None
    research_question: str | None = None
    independent_variable: str | None = None
    control_condition: str | None = None
    treatment_condition: str | None = None
    controlled_elements: list[str] | None = None
    contradiction_condition: str | None = None
    primary_metric: str | None = None
    # Override the default 72h window; non-production only (for accelerated tests)
    tracking_window_hours: float | None = None


class HypothesisResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    statement: str
    research_question: str | None
    independent_variable: str | None
    control_condition: str | None
    treatment_condition: str | None
    controlled_elements: list[str]
    contradiction_condition: str | None
    primary_metric: str
    rationale: str | None
    category: str | None
    status: str
    parent_hypothesis_id: UUID | None
    source_candidate_id: UUID | None
    relationship_type: str | None
    previous_learning: str | None
    remaining_unknown: str | None
    recommendation_reason: str | None
    created_by_ai_run_id: UUID | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    tested_at: datetime | None

    @classmethod
    def from_row(cls, row: dict) -> "HypothesisResponse":
        data = dict(row)
        data.setdefault("controlled_elements", [])
        return cls(**data)
