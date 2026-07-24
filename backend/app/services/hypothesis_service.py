"""
Hypothesis service — all operations require ProjectScope.

Corrections applied:
  1. One ai_run per provider invocation (not one per hypothesis).
  2. ai_run inserted in the same transaction as domain entities.
     The append-only trigger blocks UPDATE/DELETE — INSERT is allowed in-txn.
  3. Canonical input_hash computed from the full payload passed to the
     provider. After locking the Hypothesis, the hash is rebuilt from the
     locked state and compared; mismatch → DomainError (retry).
  5. generate_initial raises 409 when hypotheses exist.
     Generate More is explicitly deferred (not yet implemented).
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

    # ── Generate ────────────────────────────────────────────────────────────

    async def generate_initial(
        self,
        scope: ProjectScope,
        project: dict,
        facts: list[dict],
        provider,
    ) -> list[dict]:
        """
        Generate initial hypotheses using the provider.
        Raises DomainError if hypotheses already exist.

        Transaction: context_version revalidation + hypothesis inserts
                     + ONE ai_run insert — all in a single commit.
        """
        existing_count = await self._repo.count_by_project(scope)
        if existing_count > 0:
            raise DomainError(
                "Hypotheses already exist for this project. "
                "Generate More is not yet implemented."
            )

        context_version = project.get("context_version", 1)

        # Provider call — OUTSIDE transaction
        hypotheses_data, input_payload, input_hash = await provider.generate_initial_hypotheses(
            project=project, facts=facts, context_version=context_version
        )

        # Short transaction: revalidate context_version + insert all + ai_run
        current_cv = await self._get_current_context_version(scope)
        if current_cv != context_version:
            raise DomainError(
                f"Project context changed (was v{context_version}, now v{current_cv}). "
                "Retry generation."
            )

        items = [
            {
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
            }
            for h in hypotheses_data
        ]

        created = await self._repo.create_batch(scope, items)
        hypothesis_ids = [str(h["id"]) for h in created]

        # ONE ai_run for the entire invocation, in the same transaction
        # output_payload records which hypothesis IDs were created
        output_payload = json.dumps({"hypothesis_ids": hypothesis_ids})
        await self._insert_ai_run(
            scope=scope,
            entity_type="Hypothesis",
            entity_id=None,                       # batch: no single entity
            operation="generateHypotheses",
            model=provider.MODEL,
            prompt_version=provider.PROMPT_VERSION,
            input_hash=input_hash,
            input_payload=json.dumps(input_payload),
            output_payload=output_payload,
            context_version=context_version,
        )
        await self._db.commit()

        return created

    # ── Read ────────────────────────────────────────────────────────────────

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

    # ── Patch ───────────────────────────────────────────────────────────────

    async def patch(self, scope: ProjectScope, hypothesis_id: UUID, data: dict) -> dict:
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_patch(h["status"])

        forbidden = {"id", "project_id", "status", "created_at", "approved_at", "tested_at"}
        fields = {k: v for k, v in data.items() if k not in forbidden and v is not None}

        valid_metrics = {
            "clicks_per_1k_views", "comments_per_1k_views",
            "views", "product_clicks", "comments",
        }
        if "primary_metric" in fields and fields["primary_metric"] not in valid_metrics:
            raise DomainError(f"Invalid primary_metric: {fields['primary_metric']}")

        if h["status"] == "generated":
            fields["status"] = "draft"

        updated = await self._repo.update(scope, hypothesis_id, fields)
        if not updated:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        return updated

    # ── Reject ──────────────────────────────────────────────────────────────

    async def reject(self, scope: ProjectScope, hypothesis_id: UUID) -> dict:
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_reject(h["status"])
        return await self._repo.update(
            scope, hypothesis_id,
            {"status": "rejected", "rejected_at": datetime.now(timezone.utc)}
        )

    # ── Approve & Generate Experiment ────────────────────────────────────────

    async def approve_and_generate_experiment(
        self,
        scope: ProjectScope,
        hypothesis_id: UUID,
        design_fields: dict,
        project: dict,
        facts: list[dict],
        provider,
        tracking_window_hours: float | None = None,
    ) -> dict:
        """
        1. Read hypothesis (outside txn).
        2. Merge design_fields in memory → build canonical input_payload.
        3. Compute pre-lock input_hash.
        4. Call provider.design_experiment (outside txn).
        5. BEGIN transaction:
             a. Lock hypothesis FOR UPDATE.
             b. Rebuild canonical input_payload from LOCKED state.
             c. Recompute hash → compare with pre-lock hash.
                Mismatch → DomainError (hypothesis was edited; client must retry).
             d. UPDATE hypothesis (design fields + approved).
             e. INSERT experiment + 3 variants.
             f. INSERT ONE ai_run for the designExperiment invocation.
           COMMIT.
        Returns the created experiment with variants.
        """
        h = await self._repo.get(scope, hypothesis_id)
        if not h:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_approve(h["status"])

        # Merge design edits for the provider call
        merged = {**h, **{k: v for k, v in design_fields.items() if v is not None}}

        # Provider call — OUTSIDE transaction
        exp_design, input_payload, pre_lock_hash = await provider.design_experiment(
            hypothesis=merged, project=project, facts=facts
        )

        # Build snapshot
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

        # ── Short transaction ───────────────────────────────────────────────
        h_locked = await self._repo.get_for_update(scope, hypothesis_id)
        if not h_locked:
            raise ProjectNotFound(f"Hypothesis {hypothesis_id} not found")
        assert_can_approve(h_locked["status"])

        # Correction 3: rebuild hash from LOCKED state + request edits
        locked_merged = {**h_locked, **{k: v for k, v in design_fields.items() if v is not None}}
        _, locked_payload, post_lock_hash = await provider.design_experiment(
            hypothesis=locked_merged, project=project, facts=facts
        )
        if post_lock_hash != pre_lock_hash:
            raise DomainError(
                "Hypothesis was modified between generation and commit. "
                "Reload and retry."
            )

        # Apply design edits
        h_fields = {k: v for k, v in design_fields.items() if v is not None}
        h_fields["status"] = "approved"
        h_fields["approved_at"] = datetime.now(timezone.utc)
        await self._db.execute(
            text(
                "UPDATE hypotheses SET "
                + ", ".join(f"{k} = :{k}" for k in h_fields)
                + " WHERE id = :hid AND project_id = :pid"
            ),
            {"hid": hypothesis_id, "pid": scope.project_id, **h_fields},
        )

        exp_data = {
            "name": exp_design["experiment_name"],
            "tracking_window_hours": tracking_window_hours if tracking_window_hours is not None else 72,
            "status": "ready",
            "hypothesis_design_snapshot": json.dumps(snapshot),
            "shared_constraints": json.dumps(exp_design["shared_constraints"]),
            "design_schema_version": 1,
        }
        variants_data = []
        for vd in exp_design["variants"]:
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
                "status": "ready_to_review" if vd["position"] == "A" else "queued",
            })

        experiment = await self._exp_repo.create_with_variants(
            scope, hypothesis_id, exp_data, variants_data
        )

        # ONE ai_run for the designExperiment invocation, in the same transaction
        output_payload = json.dumps({"experiment_id": str(experiment["id"])})
        await self._insert_ai_run(
            scope=scope,
            entity_type="Hypothesis",
            entity_id=hypothesis_id,
            operation="designExperiment",
            model=provider.MODEL,
            prompt_version=provider.PROMPT_VERSION,
            input_hash=pre_lock_hash,
            input_payload=json.dumps(input_payload),
            output_payload=output_payload,
            context_version=project.get("context_version", 1),
        )
        await self._db.commit()

        return experiment

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _get_current_context_version(self, scope: ProjectScope) -> int:
        result = await self._db.execute(
            text(
                "SELECT context_version FROM projects "
                "WHERE id = :pid AND deleted_at IS NULL"
            ),
            {"pid": scope.project_id},
        )
        row = result.first()
        return row[0] if row else 1

    async def _insert_ai_run(
        self,
        scope: ProjectScope,
        entity_type: str,
        entity_id,
        operation: str,
        model: str,
        prompt_version: str,
        input_hash: str,
        input_payload: str,
        output_payload: str,
        context_version: int,
        request_group_id: str | None = None,
        attempt_number: int = 1,
        parent_ai_run_id=None,
        error_detail: str | None = None,
        status: str = "success",
        validation_result: str = "valid",
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
                ":cv, :ih, :ip, :outp, "
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
                "ip": input_payload,
                "outp": output_payload,
                "vr": validation_result,
                "tu": zero_usage,
                "status": status,
                "rg": request_group_id,
                "att": attempt_number,
                "par": str(parent_ai_run_id) if parent_ai_run_id else None,
                "errd": error_detail,
            },
        )
