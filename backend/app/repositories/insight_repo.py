"""
Insight + FollowUpCandidate repository.
All queries require ProjectScope.
"""
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scope import ProjectScope

_INSIGHT_COLS = (
    "id, project_id, experiment_id, evidence_snapshot_id, version, is_current, "
    "superseded_at, generated_by_ai_run_id, research_question, hypothesis_text, "
    "primary_metric, outcome_type, evidence_basis, supported_learning, "
    "do_not_infer_yet, recommended_next_test, limitations, outcome_description, "
    "generated_at"
)

_CANDIDATE_COLS = (
    "id, project_id, insight_id, slot, relationship_type, statement, "
    "why_this_follows, recommended, recommendation_reason, "
    "previous_learning, remaining_unknown, status, created_at"
)

_EVI_ITEM_COLS = (
    "eei.id, eei.variant_id, eei.views_delta, eei.likes_delta, eei.comments_delta, "
    "eei.attributed_unique_clicks, eei.unique_clicks_per_1k, "
    "eei.execution_observation_id, eei.attribution_window_id, "
    "v.position, v.treatment_role, v.title"
)


class InsightRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Insights ─────────────────────────────────────────────────────────────

    async def list_by_project(self, scope: ProjectScope, limit: int = 20) -> list[dict]:
        sql = text(
            f"SELECT {_INSIGHT_COLS} FROM insights "
            "WHERE project_id = :pid AND is_current = true "
            "ORDER BY generated_at DESC LIMIT :lim"
        )
        result = await self._db.execute(sql, {"pid": scope.project_id, "lim": limit})
        return [dict(r) for r in result.mappings()]

    async def get_by_id(self, scope: ProjectScope, insight_id: UUID) -> dict | None:
        sql = text(
            f"SELECT {_INSIGHT_COLS} FROM insights "
            "WHERE id = :iid AND project_id = :pid"
        )
        result = await self._db.execute(sql, {"iid": insight_id, "pid": scope.project_id})
        row = result.mappings().first()
        if not row:
            return None
        insight = dict(row)
        insight["candidates"] = await self.get_candidates(scope, insight_id)
        insight["evidence_items"] = await self._get_evidence_items_for_insight(scope, insight_id)
        return insight

    async def get_current_for_experiment(
        self, scope: ProjectScope, experiment_id: UUID
    ) -> dict | None:
        sql = text(
            f"SELECT {_INSIGHT_COLS} FROM insights "
            "WHERE experiment_id = :eid AND project_id = :pid AND is_current = true"
        )
        result = await self._db.execute(sql, {"eid": experiment_id, "pid": scope.project_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_next_version(self, scope: ProjectScope, experiment_id: UUID) -> int:
        result = await self._db.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 FROM insights WHERE experiment_id = :eid AND project_id = :pid"),
            {"eid": experiment_id, "pid": scope.project_id},
        )
        return result.scalar() or 1

    # ── Candidates ───────────────────────────────────────────────────────────

    async def get_candidates(self, scope: ProjectScope, insight_id: UUID) -> list[dict]:
        sql = text(
            f"SELECT {_CANDIDATE_COLS} FROM follow_up_candidates "
            "WHERE insight_id = :iid AND project_id = :pid ORDER BY slot ASC"
        )
        result = await self._db.execute(sql, {"iid": insight_id, "pid": scope.project_id})
        return [dict(r) for r in result.mappings()]

    async def get_candidate(self, scope: ProjectScope, candidate_id: UUID) -> dict | None:
        sql = text(
            f"SELECT {_CANDIDATE_COLS} FROM follow_up_candidates "
            "WHERE id = :cid AND project_id = :pid"
        )
        result = await self._db.execute(sql, {"cid": candidate_id, "pid": scope.project_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_candidate_for_update(self, scope: ProjectScope, candidate_id: UUID) -> dict | None:
        sql = text(
            f"SELECT {_CANDIDATE_COLS} FROM follow_up_candidates "
            "WHERE id = :cid AND project_id = :pid FOR UPDATE"
        )
        result = await self._db.execute(sql, {"cid": candidate_id, "pid": scope.project_id})
        row = result.mappings().first()
        return dict(row) if row else None

    # ── Evidence items (for display in insight detail) ────────────────────────

    async def _get_evidence_items_for_insight(
        self, scope: ProjectScope, insight_id: UUID
    ) -> list[dict]:
        """Join evidence items with variant info for display."""
        sql = text(
            f"SELECT {_EVI_ITEM_COLS} "
            "FROM experiment_evidence_items eei "
            "JOIN variants v ON v.id = eei.variant_id "
            "JOIN experiment_evidence_snapshots ees ON ees.id = eei.evidence_snapshot_id "
            "JOIN insights ins ON ins.evidence_snapshot_id = ees.id "
            "WHERE ins.id = :iid AND eei.project_id = :pid "
            "ORDER BY v.position ASC"
        )
        result = await self._db.execute(sql, {"iid": insight_id, "pid": scope.project_id})
        return [dict(r) for r in result.mappings()]

    # ── Evidence snapshot ─────────────────────────────────────────────────────

    async def get_snapshot_for_experiment(
        self, scope: ProjectScope, experiment_id: UUID
    ) -> dict | None:
        sql = text(
            "SELECT id, project_id, experiment_id, version, status, attribution_method, "
            "generated_at, finalized_at "
            "FROM experiment_evidence_snapshots "
            "WHERE experiment_id = :eid AND project_id = :pid AND status = 'finalized' "
            "ORDER BY version DESC LIMIT 1"
        )
        result = await self._db.execute(sql, {"eid": experiment_id, "pid": scope.project_id})
        row = result.mappings().first()
        return dict(row) if row else None

    async def get_evidence_items(
        self, scope: ProjectScope, snapshot_id: UUID
    ) -> list[dict]:
        sql = text(
            f"SELECT {_EVI_ITEM_COLS} "
            "FROM experiment_evidence_items eei "
            "JOIN variants v ON v.id = eei.variant_id "
            "WHERE eei.evidence_snapshot_id = :sid AND eei.project_id = :pid "
            "ORDER BY v.position ASC"
        )
        result = await self._db.execute(sql, {"sid": snapshot_id, "pid": scope.project_id})
        return [dict(r) for r in result.mappings()]
