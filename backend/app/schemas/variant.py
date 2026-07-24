import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BriefPatchRequest(BaseModel):
    hook: str | None = None
    hook_delivery_note: str | None = None
    context: str | None = None
    on_screen_text: str | None = None
    script_sections: dict | None = None
    recording_guidance: dict | None = None


class ReviseBriefRequest(BaseModel):
    instruction: str = Field(min_length=1)


class SubmitUrlRequest(BaseModel):
    url: str = Field(min_length=10)
    video_live: bool = False
    variable_delivered: bool = False
    controlled_preserved: bool = False


class ExecutionObservationRequest(BaseModel):
    delivered_variable: bool | None = None
    used_approved_hook: bool | None = None
    used_fixed_cta: bool | None = None
    actual_duration_seconds: int | None = None
    actual_product_reveal_seconds: int | None = None
    format_changed: bool | None = None
    audience_framing_changed: bool | None = None
    offer_changed: bool | None = None
    publishing_schedule_changed: bool | None = None
    reason: str | None = None
    notes: str | None = None
    unexpected: str | None = None
    perceived_drop_off_at: str | None = None
    founder_observed_comment_sentiment: str | None = None


class VideoResponse(BaseModel):
    id: UUID
    project_id: UUID
    variant_id: UUID
    attempt_number: int
    is_current: bool
    status: str
    submitted_url: str | None
    normalized_tiktok_url: str | None
    tiktok_video_id: str | None
    validated_at: datetime | None
    tracking_started_at: datetime | None
    tracking_window_ends_at: datetime | None
    validation_error_code: str | None
    validation_error_detail: str | None
    created_at: datetime
    updated_at: datetime


class ObservationResponse(BaseModel):
    id: UUID
    video_id: UUID
    delivered_variable: bool | None
    used_approved_hook: bool | None
    used_fixed_cta: bool | None
    actual_duration_seconds: int | None
    actual_product_reveal_seconds: int | None
    format_changed: bool | None
    audience_framing_changed: bool | None
    offer_changed: bool | None
    publishing_schedule_changed: bool | None
    reason: str | None
    notes: str | None
    unexpected: str | None
    perceived_drop_off_at: str | None
    founder_observed_comment_sentiment: str | None
    created_at: datetime
    updated_at: datetime


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
    current_video: VideoResponse | None = None
    observation: ObservationResponse | None = None

    @field_validator("script_sections", "recording_guidance", mode="before")
    @classmethod
    def parse_jsonb(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v or {"schemaVersion": 1}

    @classmethod
    def from_row(cls, row: dict) -> "VariantResponse":
        cv = row.get("current_video")
        obs = row.get("observation")
        return cls(
            **{k: v for k, v in row.items() if k not in ("current_video", "observation")},
            current_video=VideoResponse(**cv) if cv else None,
            observation=ObservationResponse(**obs) if obs else None,
        )
