import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class VariantResponse(BaseModel):
    id: UUID
    project_id: UUID
    experiment_id: UUID
    position: str
    treatment_role: str
    title: str
    variable_value: str
    hook: str
    hook_delivery_note: str | None
    context: str | None
    on_screen_text: str | None
    script_sections: dict
    recording_guidance: dict
    status: str
    approved_for_recording_at: datetime | None
    recorded_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("script_sections", "recording_guidance", mode="before")
    @classmethod
    def parse_jsonb(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class ExperimentResponse(BaseModel):
    id: UUID
    project_id: UUID
    hypothesis_id: UUID
    name: str
    tracking_window_hours: int
    status: str
    hypothesis_design_snapshot: dict
    shared_constraints: dict
    design_schema_version: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    tracking_completed_at: datetime | None
    analysis_started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    variants: list[VariantResponse]

    @field_validator("hypothesis_design_snapshot", "shared_constraints", mode="before")
    @classmethod
    def parse_jsonb(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @classmethod
    def from_row(cls, row: dict) -> "ExperimentResponse":
        variants = [VariantResponse(**v) for v in row.get("variants", [])]
        data = {**row, "variants": variants}
        return cls(**data)
