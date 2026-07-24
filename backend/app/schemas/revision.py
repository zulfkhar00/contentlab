from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApplyRevisionRequest(BaseModel):
    """
    Optimistic concurrency check: the client must echo back the ai_run_id,
    input_hash, and base_variant_updated_at from the revision proposal.
    If the variant has been updated since the proposal was generated, return 409.
    """
    ai_run_id: UUID
    input_hash: str = Field(min_length=64, max_length=64, pattern=r'^[0-9a-f]{64}$')
    base_variant_updated_at: datetime
    hook: str | None = None
    hook_delivery_note: str | None = None
    context: str | None = None
    on_screen_text: str | None = None
