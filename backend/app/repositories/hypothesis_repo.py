import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scope import ProjectScope

_COLS = (
    "id, project_id, title, statement, research_question, independent_variable, "
    "control_condition, treatment_condition, controlled_elements, contradiction_condition, "
    "primary_metric, rationale, category, status, parent_hypothesis_id, "
    "source_candidate_id, relationship_type, previous_learning, remaining_unknown, "
    "recommendation_reason, created_by_ai_run_id, "
    "created_at, updated_at, approved_at, rejected_at, tested_at"
)


class HypothesisRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_by_project(
        self,
        scope: ProjectScope,
        status_filter: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        conditions = ["project_id = :pid"]
        params: dict = {"pid": scope.project_id}
        if status_filter and status_filter != "all":
            conditions.append("status = :status")
            params["status"] = status_filter
        if search:
            conditions.append("title ILIKE :search")
            params["search"] = f"%{search}%"
        where = " AND ".join(conditions)
        sql = text(
            f"SELECT {_COLS} FROM hypotheses WHERE {where} "
            "ORDER BY created_at ASC LIMIT :lim"
        )
        params["lim"] = limit
        result = await self._db.execute(sql, params)
        return [dict(r) for r in result.mappings()]

    async def get(self, scope: ProjectScope, hypothesis_id: UUID) -> dict | None:
        sql = text(
            f"SELECT {_COLS} FROM hypotheses "
            "WHERE id = :hid AND project_id = :pid"
        )
        result = await self._db.execute(sql, {"hid": hypothesis_id, "pid": scope.project_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_for_update(self, scope: ProjectScope, hypothesis_id: UUID) -> dict | None:
        """SELECT ... FOR UPDATE — use inside an open transaction."""
        sql = text(
            f"SELECT {_COLS} FROM hypotheses "
            "WHERE id = :hid AND project_id = :pid FOR UPDATE"
        )
        result = await self._db.execute(sql, {"hid": hypothesis_id, "pid": scope.project_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def create_batch(self, scope: ProjectScope, items: list[dict]) -> list[dict]:
        """Insert multiple hypotheses and return them."""
        created = []
        for item in items:
            cols = ", ".join(item.keys())
            placeholders = ", ".join(f":{k}" for k in item.keys())
            sql = text(
                f"INSERT INTO hypotheses (project_id, {cols}) "
                f"VALUES (:pid, {placeholders}) "
                f"RETURNING {_COLS}"
            )
            result = await self._db.execute(sql, {"pid": scope.project_id, **item})
            created.append(dict(result.mappings().first()))
        await self._db.commit()
        return created

    async def update(self, scope: ProjectScope, hypothesis_id: UUID, fields: dict) -> dict | None:
        if not fields:
            return await self.get(scope, hypothesis_id)
        set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
        sql = text(
            f"UPDATE hypotheses SET {set_clause} "
            "WHERE id = :hid AND project_id = :pid "
            f"RETURNING {_COLS}"
        )
        result = await self._db.execute(
            sql, {"hid": hypothesis_id, "pid": scope.project_id, **fields}
        )
        await self._db.commit()
        row = result.mappings().first()
        return dict(row) if row else None

    async def count_by_project(self, scope: ProjectScope) -> int:
        result = await self._db.execute(
            text("SELECT COUNT(1) FROM hypotheses WHERE project_id = :pid"),
            {"pid": scope.project_id},
        )
        return result.scalar() or 0
