from __future__ import annotations
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scope import ProjectScope

_COLS = (
    "id, user_id, product_name, product_type, product_description, product_url, "
    "target_audience, problem_solved, why_it_matters, current_alternatives, "
    "desired_action, primary_cta, tiktok_handle, account_public, manual_publish, "
    "tracking_slug, destination_url, context_version, onboarded_at, "
    "created_at, updated_at"
)


class ProjectRepository:
    """All queries are project-scoped — never global."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def find_active_by_user(self, user_id: UUID) -> dict | None:
        sql = text(
            f"SELECT {_COLS} FROM projects "
            "WHERE user_id = :uid AND deleted_at IS NULL LIMIT 1"
        )
        result = await self._db.execute(sql, {"uid": user_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_by_scope(self, scope: ProjectScope) -> dict | None:
        sql = text(
            f"SELECT {_COLS} FROM projects "
            "WHERE id = :pid AND user_id = :uid AND deleted_at IS NULL"
        )
        result = await self._db.execute(
            sql, {"pid": scope.project_id, "uid": scope.user_id}
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def slug_exists(self, slug: str) -> bool:
        result = await self._db.execute(
            text("SELECT 1 FROM projects WHERE tracking_slug = :s"), {"s": slug}
        )
        return result.first() is not None

    async def create(self, *, user_id: UUID, fields: dict) -> dict:
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(f":{k}" for k in fields.keys())
        sql = text(
            f"INSERT INTO projects (user_id, {cols}) "
            f"VALUES (:uid, {placeholders}) "
            f"RETURNING {_COLS}"
        )
        result = await self._db.execute(sql, {"uid": user_id, **fields})
        await self._db.commit()
        return dict(result.mappings().first())

    async def update(self, scope: ProjectScope, fields: dict) -> dict | None:
        if not fields:
            return await self.get_by_scope(scope)
        set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
        sql = text(
            f"UPDATE projects SET {set_clause} "
            "WHERE id = :pid AND user_id = :uid AND deleted_at IS NULL "
            f"RETURNING {_COLS}"
        )
        result = await self._db.execute(
            sql, {"pid": scope.project_id, "uid": scope.user_id, **fields}
        )
        await self._db.commit()
        row = result.mappings().first()
        return dict(row) if row else None
