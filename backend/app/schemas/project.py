from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

PRODUCT_TYPES = ("SaaS", "Mobile App", "AI App", "Service", "Waitlist")


class ProjectCreateRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    product_type: str = "SaaS"
    product_description: str = ""
    product_url: str = ""
    target_audience: str = ""
    problem_solved: str = ""
    why_it_matters: str = ""
    current_alternatives: str = ""
    desired_action: str = ""
    primary_cta: str = ""
    tiktok_handle: str = ""
    account_public: bool = False
    manual_publish: bool = False
    onboarded: bool = False

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: str) -> str:
        if v not in PRODUCT_TYPES:
            raise ValueError(f"product_type must be one of: {', '.join(PRODUCT_TYPES)}")
        return v


class ProjectUpdateRequest(BaseModel):
    product_name: str | None = None
    product_type: str | None = None
    product_description: str | None = None
    product_url: str | None = None
    target_audience: str | None = None
    problem_solved: str | None = None
    why_it_matters: str | None = None
    current_alternatives: str | None = None
    desired_action: str | None = None
    primary_cta: str | None = None
    tiktok_handle: str | None = None
    account_public: bool | None = None
    manual_publish: bool | None = None
    destination_url: str | None = None

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: str | None) -> str | None:
        if v is not None and v not in PRODUCT_TYPES:
            raise ValueError(f"product_type must be one of: {', '.join(PRODUCT_TYPES)}")
        return v


class ProjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    product_name: str
    product_type: str
    product_description: str
    product_url: str
    target_audience: str
    problem_solved: str
    why_it_matters: str
    current_alternatives: str
    desired_action: str
    primary_cta: str
    tiktok_handle: str
    account_public: bool
    manual_publish: bool
    tracking_slug: str
    tracking_url: str
    destination_url: str
    context_version: int
    onboarded_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict, tracking_base_url: str) -> "ProjectResponse":
        return cls(
            **{k: row[k] for k in cls.model_fields if k != "tracking_url"},
            tracking_url=f"{tracking_base_url}/{row['tracking_slug']}",
        )
