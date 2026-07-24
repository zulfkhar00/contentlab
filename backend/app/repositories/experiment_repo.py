from __future__ import annotations
import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scope import ProjectScope

_EXP_COLS = (
    "id, project_id, hypothesis_id, name, tracking_window_hours, status, "
    "hypothesis_design_snapshot, shared_constraints, design_schema_version, "
    "created_at, updated_at, started_at, tracking_completed_at, "
    "analysis_started_at, completed_at, cancelled_at, cancellation_reason"
)

_VAR_COLS = (
    "id, project_id, experiment_id, position, treatment_role, title, "
    "variable_value, hook, hook_delivery_note, context, on_screen_text, "
    "script_sections, recording_guidance, status, "
    "approved_for_recording_at, recorded_at, created_at, updated_at"
)


class ExperimentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active(self, scope: ProjectScope) -> dict | None:
        """Latest non-cancelled experiment for the project, with its variants."""
        sql = text(
            f"SELECT {_EXP_COLS} FROM experiments "
            "WHERE project_id = :pid AND status != 'cancelled' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        result = await self._db.execute(sql, {"pid": scope.project_id})
        row = result.mappings().first()
        if not row:
            return None
        exp = dict(row)
        exp["variants"] = await self._get_variants(exp["id"])
        return exp

    async def get_by_id(self, scope: ProjectScope, experiment_id: UUID) -> dict | None:
        sql = text(
            f"SELECT {_EXP_COLS} FROM experiments "
            "WHERE id = :eid AND project_id = :pid"
        )
        result = await self._db.execute(sql, {"eid": experiment_id, "pid": scope.project_id})
        row = result.mappings().first()
        if not row:
            return None
        exp = dict(row)
        exp["variants"] = await self._get_variants(exp["id"])
        return exp

    async def _get_variants(self, experiment_id: UUID) -> list[dict]:
        sql = text(
            f"SELECT {_VAR_COLS} FROM variants "
            "WHERE experiment_id = :eid ORDER BY position ASC"
        )
        result = await self._db.execute(sql, {"eid": experiment_id})
        return [dict(r) for r in result.mappings()]

    async def create_with_variants(
        self,
        scope: ProjectScope,
        hypothesis_id: UUID,
        exp_data: dict,
        variants_data: list[dict],
    ) -> dict:
        """
        Insert experiment + 3 variants in a single transaction.
        Called from hypothesis_service AFTER the provider call and AFTER
        the hypothesis has been locked and updated within the same transaction.
        """
        # Insert experiment
        exp_cols = ", ".join(exp_data.keys())
        exp_ph = ", ".join(f":{k}" for k in exp_data.keys())
        sql_exp = text(
            f"INSERT INTO experiments (project_id, hypothesis_id, {exp_cols}) "
            f"VALUES (:pid, :hid, {exp_ph}) "
            f"RETURNING {_EXP_COLS}"
        )
        exp_result = await self._db.execute(
            sql_exp, {"pid": scope.project_id, "hid": hypothesis_id, **exp_data}
        )
        exp = dict(exp_result.mappings().first())
        experiment_id = exp["id"]

        # Insert variants
        variants = []
        for vd in variants_data:
            # Serialize JSONB fields
            for json_field in ("script_sections", "recording_guidance"):
                if json_field in vd and not isinstance(vd[json_field], str):
                    vd = {**vd, json_field: json.dumps(vd[json_field])}
            vcols = ", ".join(vd.keys())
            vph = ", ".join(f":{k}" for k in vd.keys())
            sql_var = text(
                f"INSERT INTO variants (project_id, experiment_id, {vcols}) "
                f"VALUES (:pid, :eid, {vph}) "
                f"RETURNING {_VAR_COLS}"
            )
            vr = await self._db.execute(
                sql_var, {"pid": scope.project_id, "eid": experiment_id, **vd}
            )
            variants.append(dict(vr.mappings().first()))

        # Commit the whole transaction
        await self._db.commit()
        exp["variants"] = variants
        return exp
