"""
Hypothesis service — all operations require ProjectScope.
Provider calls happen outside transactions.
ai_runs inserts happen after commits.
"""
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError, ProjectNotFound
from app.domain.hypothesis import assert_can_approve, assert_can_patch, assert_can_reject
from app.domain.scope import ProjectScope
from app.repositories.hypothesis_repo import HypothesisRepository
from app.repositories.experiment_repo import ExperimentRepository


class HypothesisService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = HypothesisRepository(db)
        self._exp_repo = ExperimentRepository(db)

    # ── Generate ────────────────────────────────────────────────────────

    async def generate_initial(
        self,
        scope: ProjectScope,
        project: dict,
        facts: list[dict],
        provider,
    ) -> list[dict]:
        """
        Generate initial hypotheses using the provider.
        Raises DomainError if hypotheses already exist for this project.
        Provider call is outside any transaction.
        """
        existing_count = await self._repo.count_by_project(scope)
        if existing_count > 0:
            raise DomainError("Hypotheses already generated for this project.")

        context_version = project.get("context_version", 1)

        # Provider call — OUTSIDE transaction
        hypotheses_data, input_hash = await provider.generate_initial_hypotheses(
            project=project, facts=facts, context_version=context_version
        )

        # Revalidate: ensure context_version hasn't changed since we read it
        current_cv = await self._get_current_context_version(scope)
        if current_cv != context_version:
            raise DomainError(
                f"Project context changed (was v{context_version}, now v{current_cv}). "
                "Retry generation."
            )

        # Prepare items for batch insert
        items = []
        for h in hypotheses_data:
            items.append({
                "title": h["title"],
                "statement": h["statement"],
                "research_question": h.get("research_question", ""),
                "independent_variable": h.get("independent_variable", ""),
                "control_condition": h.get("control_condition", ""),
                "treatment_condition": h.get("treatment_condition", ""),
                "controlled_elements": h.get("controlled_elements", []),
                "contradiction_condition": h.get("contradiction_condition", ""),
                "primary_metric": h.get("primary_metric", "clicks_per_1k_views"),
                "rationale": h.get("rationale", ""),
                "category": h.get("category", ""),
                "status": "generated",
            })

        created = await self._repo.create_batch(scope, items)

        # Insert ai_runs AFTER commit — append-only table
        for h_row in created:
            await self._insert_ai_run(
                scope=scope,
                entity_type="Hypothesis",
                entity_id=h_row["id"],
                operation="generateHypotheses",
                model=provider.MODEL,
                prompt_version=provider.PROMPT_VERSION,
                input_hash=input_hash,
                context_version=context_version,
            )
        await self._db.commit()

        return created

    # ── Read ────────────────────────────────────────────────────────────

    async def list(
        self,
        scope: ProjectScope,
        status_filter: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        return await self._repo.list_by_project(scope, status_filter, search)

    async def get(self, scope: ProjectScope, hypothesis_id: UUID) -> dict:
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        return h

    # ── Patch ───────────────────────────────────────────────────────────

    async def patch(self, scope: ProjectScope, hypothesis_id: UUID, data: dict) -> dict:
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_patch(h["status"])

        # Strip forbidden fields
        forbidden = {"id", "project_id", "status", "created_at", "approved_at", "tested_at"}
        fields = {k: v for k, v in data.items() if k not in forbidden and v is not None}

        # primary_metric must be a valid enum value
        valid_metrics = {"clicks_per_1k_views", "comments_per_1k_views", "views", "product_clicks", "comments"}
        if "primary_metric" in fields and fields["primary_metric"] not in valid_metrics:
            raise DomainError(f"Invalid primary_metric: {fields['primary_metric']}")

        # Transition to draft on any edit
        if h["status"] == "generated":
            fields["status"] = "draft"

        updated = await self._repo.update(scope, hypothesis_id, fields)
        if not updated:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        return updated

    # ── Reject ──────────────────────────────────────────────────────────

    async def reject(self, scope: ProjectScope, hypothesis_id: UUID) -> dict:
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_reject(h["status"])
        updated = await self._repo.update(
            scope, hypothesis_id,
            {"status": "rejected", "rejected_at": datetime.now(timezone.utc)}
        )
        return updated

    # ── Approve & Generate Experiment ───────────────────────────────────

    async def approve_and_generate_experiment(
        self,
        scope: ProjectScope,
        hypothesis_id: UUID,
        design_fields: dict,
        project: dict,
        provider,
    ) -> dict:
        """
        1. Read hypothesis (outside txn).
        2. Apply design_fields in memory.
        3. Call provider.design_experiment (outside txn).
        4. BEGIN short txn:
              lock hypothesis FOR UPDATE
              re-validate status
              UPDATE hypothesis (design fields + approved)
              INSERT experiment + 3 variants
           COMMIT
        5. INSERT ai_run (after commit).
        Returns the created experiment with variants.
        """
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_approve(h["status"])

        # Merge design fields with existing hypothesis for provider call
        merged = {**h, **{k: v for k, v in design_fields.items() if v is not None}}

        # Provider call — OUTSIDE transaction
        exp_design, input_hash = await provider.design_experiment(
            hypothesis=merged, project=project
        )

        # Build hypothesis_design_snapshot
        snapshot = {
            "schemaVersion": 1,
            "researchQuestion": merged.get("research_question", ""),
            "statement": merged.get("statement", ""),
            "independentVariable": merged.get("independent_variable", ""),
            "controlCondition": merged.get("control_condition", ""),
            "treatmentCondition": merged.get("treatment_condition", ""),
            "primaryMetric": merged.get("primary_metric", "clicks_per_1k_views"),
            "controlledElements": merged.get("controlled_elements", []),
            "contradictionCondition": merged.get("contradiction_condition", ""),
        }

        # Short transaction: lock → update hypothesis → create experiment + variants
        h_locked = await self._repo.get_for_update(scope, hypothesis_id)
        if not h_locked:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_approve(h_locked["status"])

        # Apply design edits to hypothesis
        h_fields = {k: v for k, v in design_fields.items() if v is not None}
        h_fields["status"] = "approved"
        h_fields["approved_at"] = datetime.now(timezone.utc)
        await self._db.execute(
            text("UPDATE hypotheses SET " + ", ".join(f"{k} = :{k}" for k in h_fields) +
                 " WHERE id = :hid AND project_id = :pid"),
            {"hid": hypothesis_id, "pid": scope.project_id, **h_fields}
        )

        # Create experiment
        exp_data = {
            "name": exp_design["experiment_name"],
            "tracking_window_hours": 72,
            "status": "ready",
            "hypothesis_design_snapshot": json.dumps(snapshot),
            "shared_constraints": json.dumps(exp_design["shared_constraints"]),
            "design_schema_version": 1,
        }

        # Create variants (A = ready_to_review, B+C = queued)
        variants_data = []
        for vd in exp_design["variants"]:
            v_status = "ready_to_review" if vd["position"] == "A" else "queued"
            variants_data.append({
                "position": vd["position"],
                "treatment_role": vd["treatment_role"],
                "title": vd["title"],
                "variable_value": vd["variable_value"],
                "hook": vd["hook"],
                "hook_delivery_note": vd.get("hook_delivery_note", ""),
                "context": vd.get("context", ""),
                "on_screen_text": vd.get("on_screen_text", ""),
                "script_sections": vd["script_sections"],
                "recording_guidance": vd["recording_guidance"],
                "status": v_status,
            })

        experiment = await self._exp_repo.create_with_variants(
            scope, hypothesis_id, exp_data, variants_data
        )
        # create_with_variants commits the transaction

        # ai_run for experiment design — AFTER commit
        await self._insert_ai_run(
            scope=scope,
            entity_type="Hypothesis",
            entity_id=hypothesis_id,
            operation="designExperiment",
            model=provider.MODEL,
            prompt_version=provider.PROMPT_VERSION,
            input_hash=input_hash,
            context_version=project.get("context_version", 1),
        )
        await self._db.commit()

        return experiment

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _get_current_context_version(self, scope: ProjectScope) -> int:
        result = await self._db.execute(
            text("SELECT context_version FROM projects WHERE id = :pid AND deleted_at IS NULL"),
            {"pid": scope.project_id}
        )
        row = result.first()
        return row[0] if row else 1

    async def _insert_ai_run(
        self, scope: ProjectScope, entity_type: str, entity_id: UUID,
        operation: str, model: str, prompt_version: str,
        input_hash: str, context_version: int,
    ) -> None:
        import json as _json
        zero_usage = _json.dumps({"inputTokens": 0, "outputTokens": 0})
        await self._db.execute(
            text(
                "INSERT INTO ai_runs "
                "(project_id, entity_type, entity_id, operation, model, prompt_version, "
                "context_version, input_hash, input_payload, output_payload, "
                "validation_result, token_usage, cost_usd, latency_ms, status) "
                "VALUES (:pid, :etype, :eid, :op, :model, :pv, "
                ":cv, :ih, '{}', '{}', "
                "'valid', :tu, 0, 0, 'success')"
            ),
            {
                "pid": scope.project_id,
                "etype": entity_type,
                "eid": entity_id,
                "op": operation,
                "model": model,
                "pv": prompt_version,
                "cv": context_version,
                "ih": input_hash,
                "tu": zero_usage,
            }
        )
