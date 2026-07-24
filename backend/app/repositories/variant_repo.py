from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scope import ProjectScope

_VAR_COLS = (
    "id, project_id, experiment_id, position, treatment_role, title, "
    "variable_value, hook, hook_delivery_note, context, on_screen_text, "
    "script_sections, recording_guidance, status, generated_by_ai_run_id, "
    "approved_for_recording_at, recorded_at, created_at, updated_at"
)

_VID_COLS = (
    "id, project_id, variant_id, attempt_number, is_current, status, "
    "submitted_url, normalized_tiktok_url, tiktok_video_id, "
    "user_confirmed_published_at, published_at, validated_at, "
    "tracking_started_at, tracking_window_ends_at, last_refreshed_at, "
    "validation_error_code, validation_error_detail, created_at, updated_at"
)


class VariantRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, scope: ProjectScope, variant_id: UUID) -> dict | None:
        result = await self._db.execute(
            text(f"SELECT {_VAR_COLS} FROM variants WHERE id = :vid AND project_id = :pid"),
            {"vid": variant_id, "pid": scope.project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_by_position(self, scope: ProjectScope, experiment_id: UUID, position: str) -> dict | None:
        result = await self._db.execute(
            text(f"SELECT {_VAR_COLS} FROM variants WHERE experiment_id = :eid AND position = :pos AND project_id = :pid"),
            {"eid": experiment_id, "pos": position, "pid": scope.project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def update(self, scope: ProjectScope, variant_id: UUID, fields: dict) -> dict | None:
        if not fields:
            return await self.get(scope, variant_id)
        set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
        result = await self._db.execute(
            text(f"UPDATE variants SET {set_clause} WHERE id = :vid AND project_id = :pid RETURNING {_VAR_COLS}"),
            {"vid": variant_id, "pid": scope.project_id, **fields},
        )
        await self._db.commit()
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_current_video(self, scope: ProjectScope, variant_id: UUID) -> dict | None:
        result = await self._db.execute(
            text(f"SELECT {_VID_COLS} FROM videos WHERE variant_id = :vid AND project_id = :pid AND is_current = true"),
            {"vid": variant_id, "pid": scope.project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_next_video_attempt(self, scope: ProjectScope, variant_id: UUID) -> int:
        result = await self._db.execute(
            text("SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM videos WHERE variant_id = :vid AND project_id = :pid"),
            {"vid": variant_id, "pid": scope.project_id},
        )
        return result.scalar() or 1
