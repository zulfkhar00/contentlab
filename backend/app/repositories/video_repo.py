from __future__ import annotations
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scope import ProjectScope

_VID_COLS = (
    "id, project_id, variant_id, attempt_number, is_current, status, "
    "submitted_url, normalized_tiktok_url, tiktok_video_id, "
    "user_confirmed_published_at, published_at, validated_at, "
    "tracking_started_at, tracking_window_ends_at, last_refreshed_at, "
    "validation_error_code, validation_error_detail, created_at, updated_at"
)

_OBS_COLS = (
    "id, project_id, video_id, delivered_variable, used_approved_hook, used_fixed_cta, "
    "actual_duration_seconds, actual_product_reveal_seconds, format_changed, "
    "audience_framing_changed, offer_changed, publishing_schedule_changed, "
    "reason, notes, unexpected, perceived_drop_off_at, "
    "founder_observed_comment_sentiment, created_at, updated_at"
)


class VideoRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, scope: ProjectScope, video_id: UUID) -> dict | None:
        result = await self._db.execute(
            text(f"SELECT {_VID_COLS} FROM videos WHERE id = :vid AND project_id = :pid"),
            {"vid": video_id, "pid": scope.project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def create(self, scope: ProjectScope, variant_id: UUID, attempt_number: int) -> dict:
        # Flip current is_current to false
        await self._db.execute(
            text("UPDATE videos SET is_current = false WHERE variant_id = :vid AND project_id = :pid AND is_current = true"),
            {"vid": variant_id, "pid": scope.project_id},
        )
        result = await self._db.execute(
            text(
                f"INSERT INTO videos (project_id, variant_id, attempt_number, is_current, status) "
                f"VALUES (:pid, :vid, :att, true, 'needs_url') "
                f"RETURNING {_VID_COLS}"
            ),
            {"pid": scope.project_id, "vid": variant_id, "att": attempt_number},
        )
        await self._db.commit()
        return dict(result.mappings().first())

    async def update(self, scope: ProjectScope, video_id: UUID, fields: dict) -> dict | None:
        if not fields:
            return await self.get(scope, video_id)
        set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
        result = await self._db.execute(
            text(f"UPDATE videos SET {set_clause} WHERE id = :vid AND project_id = :pid RETURNING {_VID_COLS}"),
            {"vid": video_id, "pid": scope.project_id, **fields},
        )
        await self._db.commit()
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_observation(self, scope: ProjectScope, video_id: UUID) -> dict | None:
        result = await self._db.execute(
            text(f"SELECT {_OBS_COLS} FROM execution_observations WHERE video_id = :vid AND project_id = :pid"),
            {"vid": video_id, "pid": scope.project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def upsert_observation(self, scope: ProjectScope, video_id: UUID, fields: dict) -> dict:
        existing = await self.get_observation(scope, video_id)
        if existing:
            if fields:
                set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
                result = await self._db.execute(
                    text(f"UPDATE execution_observations SET {set_clause}, updated_at = now() "
                         f"WHERE video_id = :vid AND project_id = :pid RETURNING {_OBS_COLS}"),
                    {"vid": video_id, "pid": scope.project_id, **fields},
                )
                await self._db.commit()
                return dict(result.mappings().first())
            return existing
        else:
            cols = "project_id, video_id, " + ", ".join(fields.keys()) if fields else "project_id, video_id"
            phs = ":pid, :vid" + (", " + ", ".join(f":{k}" for k in fields.keys()) if fields else "")
            result = await self._db.execute(
                text(f"INSERT INTO execution_observations ({cols}) VALUES ({phs}) RETURNING {_OBS_COLS}"),
                {"pid": scope.project_id, "vid": video_id, **fields},
            )
            await self._db.commit()
            return dict(result.mappings().first())
