"""
Insight service — analyze_experiment + candidate acceptance/dismissal.
All operations require ProjectScope.
"""
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope
from app.repositories.insight_repo import InsightRepository
from app.repositories.hypothesis_repo import HypothesisRepository
from app.repositories.project_repo import ProjectRepository


_REQUIRED_SLOTS = frozenset({"safest_next_step", "highest_learning", "highest_upside"})


class InsightService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = InsightRepository(db)

    # ── Analyze ──────────────────────────────────────────────────────────────

    async def analyze(
        self,
        scope: ProjectScope,
        experiment_id: UUID,
        provider,
    ) -> dict:
        """
        Reads finalized evidence, computes metrics, calls provider, creates
        Insight + exactly 3 FollowUpCandidates + ai_run in one transaction.
        Updates experiment.status to 'completed'.
        """
        # Verify experiment in analyzing status
        exp_result = await self._db.execute(
            text(
                "SELECT id, status, hypothesis_design_snapshot, project_id "
                "FROM experiments WHERE id = :eid AND project_id = :pid"
            ),
            {"eid": experiment_id, "pid": scope.project_id},
        )
        exp_row = exp_result.mappings().first()
        if not exp_row:
            raise ProjectNotFound(f"Experiment {experiment_id} not found")
        if exp_row["status"] != "analyzing":
            raise DomainError(
                f"Experiment must be in 'analyzing' status; current: {exp_row['status']}"
            )

        # Check for existing insight
        existing = await self._repo.get_current_for_experiment(scope, experiment_id)
        if existing:
            raise DomainError("Insight already exists for this experiment.")

        # Load hypothesis snapshot + evidence
        hypothesis_snapshot = exp_row["hypothesis_design_snapshot"]
        if isinstance(hypothesis_snapshot, str):
            hypothesis_snapshot = json.loads(hypothesis_snapshot)

        snapshot = await self._repo.get_snapshot_for_experiment(scope, experiment_id)
        if not snapshot:
            raise DomainError("No finalized evidence snapshot found. Seed evidence first.")

        items = await self._repo.get_evidence_items(scope, snapshot["id"])
        evidence = _build_evidence_dict(items)

        # Get project + facts for provider
        project_repo = ProjectRepository(self._db)
        project = await project_repo.get_by_scope(scope)
        facts: list[dict] = []  # Sprint 5: wire project_facts

        context_version = project.get("context_version", 1)

        # Provider calls — OUTSIDE transaction
        insight_data, insight_input, insight_hash = await provider.analyze_experiment(
            evidence=evidence,
            hypothesis_snapshot=hypothesis_snapshot,
            project=project,
            facts=facts,
        )
        candidates_data, cand_input, cand_hash = await provider.generate_follow_up_candidates(
            insight={**insight_data, "evidence_items": evidence["items"]},
            hypothesis_snapshot=hypothesis_snapshot,
            project=project,
            facts=facts,
        )

        # Validate candidates: exactly 3 slots, exactly 1 recommended
        _validate_candidates(candidates_data)

        # Build insight row
        version = await self._repo.get_next_version(scope, experiment_id)
        now = datetime.now(timezone.utc)

        insight_insert = {
            "project_id": scope.project_id,
            "experiment_id": experiment_id,
            "evidence_snapshot_id": snapshot["id"],
            "version": version,
            "is_current": True,
            "research_question": hypothesis_snapshot.get("researchQuestion", ""),
            "hypothesis_text": hypothesis_snapshot.get("statement", ""),
            "primary_metric": hypothesis_snapshot.get("primaryMetric", "clicks_per_1k_views"),
            "outcome_type": insight_data["outcome_type"],
            "evidence_basis": json.dumps(insight_data["evidence_basis"]),
            "supported_learning": insight_data["supported_learning"],
            "do_not_infer_yet": insight_data["do_not_infer_yet"],
            "recommended_next_test": insight_data["recommended_next_test"],
            "limitations": insight_data["limitations"],
            "outcome_description": insight_data["outcome_description"],
            "generated_at": now,
        }

        cols = ", ".join(insight_insert.keys())
        phs = ", ".join(f":{k}" for k in insight_insert.keys())
        ins_result = await self._db.execute(
            text(
                f"INSERT INTO insights ({cols}) VALUES ({phs}) "
                "RETURNING id, project_id, experiment_id, evidence_snapshot_id, "
                "version, is_current, research_question, hypothesis_text, "
                "primary_metric, outcome_type, evidence_basis, supported_learning, "
                "do_not_infer_yet, recommended_next_test, limitations, "
                "outcome_description, generated_at, superseded_at, "
                "generated_by_ai_run_id"
            ),
            insight_insert,
        )
        insight_row = dict(ins_result.mappings().first())
        insight_id = insight_row["id"]

        # Insert exactly 3 candidates
        for cd in candidates_data:
            cd_insert = {
                "project_id": scope.project_id,
                "insight_id": insight_id,
                "slot": cd["slot"],
                "relationship_type": cd["relationship_type"],
                "statement": cd["statement"],
                "why_this_follows": cd.get("why_this_follows", ""),
                "recommended": bool(cd.get("recommended", False)),
                "recommendation_reason": cd.get("recommendation_reason", ""),
                "previous_learning": cd.get("previous_learning", ""),
                "remaining_unknown": cd.get("remaining_unknown", ""),
                "status": "proposed",
            }
            cd_cols = ", ".join(cd_insert.keys())
            cd_phs = ", ".join(f":{k}" for k in cd_insert.keys())
            await self._db.execute(
                text(f"INSERT INTO follow_up_candidates ({cd_cols}) VALUES ({cd_phs})"),
                cd_insert,
            )

        # Two ai_runs: one for analyze, one for candidates — both in same txn
        for op, h, ip in [
            ("analyzeExperiment", insight_hash, insight_input),
            ("generateCandidates", cand_hash, cand_input),
        ]:
            zero = json.dumps({"inputTokens": 0, "outputTokens": 0})
            await self._db.execute(
                text(
                    "INSERT INTO ai_runs "
                    "(project_id, entity_type, entity_id, operation, model, prompt_version, "
                    "context_version, input_hash, input_payload, output_payload, "
                    "validation_result, token_usage, cost_usd, latency_ms, status) "
                    "VALUES (:pid, 'Insight', :eid, :op, :model, :pv, "
                    ":cv, :ih, :ip, '{}', 'valid', :tu, 0, 0, 'success')"
                ),
                {
                    "pid": scope.project_id, "eid": insight_id, "op": op,
                    "model": provider.MODEL, "pv": provider.PROMPT_VERSION,
                    "cv": context_version, "ih": h, "ip": json.dumps(ip), "tu": zero,
                },
            )

        # Mark experiment completed
        await self._db.execute(
            text(
                "UPDATE experiments SET status = 'completed', completed_at = :now "
                "WHERE id = :eid AND project_id = :pid"
            ),
            {"now": now, "eid": experiment_id, "pid": scope.project_id},
        )

        await self._db.commit()

        # Return full insight with candidates
        insight_row["candidates"] = await self._repo.get_candidates(scope, insight_id)
        insight_row["evidence_items"] = evidence["items"]
        return insight_row

    # ── Read ─────────────────────────────────────────────────────────────────

    async def list(self, scope: ProjectScope) -> list[dict]:
        return await self._repo.list_by_project(scope)

    async def get(self, scope: ProjectScope, insight_id: UUID) -> dict:
        row = await self._repo.get_by_id(scope, insight_id)
        if not row:
            raise ProjectNotFound(f"Insight {insight_id} not found")
        return row

    # ── Candidate acceptance ─────────────────────────────────────────────────

    async def accept_candidate(
        self, scope: ProjectScope, candidate_id: UUID
    ) -> dict:
        """
        Lock candidate → verify proposed → create child Hypothesis → update candidate.
        Returns the created Hypothesis.
        """
        candidate = await self._repo.get_candidate_for_update(scope, candidate_id)
        if not candidate:
            raise ProjectNotFound(f"Candidate {candidate_id} not found")
        if candidate["status"] != "proposed":
            raise DomainError(
                f"Candidate already {candidate['status']}. Cannot accept."
            )

        # Resolve parent hypothesis via insight → experiment → hypothesis
        parent_hyp = await self._resolve_parent_hypothesis(scope, candidate["insight_id"])
        if not parent_hyp:
            raise DomainError("Cannot resolve parent hypothesis for lineage.")

        # Get insight for context
        insight = await self._repo.get_by_id(scope, candidate["insight_id"])

        # Create child Hypothesis
        now = datetime.now(timezone.utc)
        h_insert = {
            "project_id": scope.project_id,
            "title": f"{candidate['slot'].replace('_', ' ').title()}: {candidate['statement'][:60]}",
            "statement": candidate["statement"],
            "primary_metric": parent_hyp.get("primary_metric", "clicks_per_1k_views"),
            "rationale": candidate["why_this_follows"],
            "status": "generated",
            "parent_hypothesis_id": parent_hyp["id"],
            "source_candidate_id": candidate_id,
            "relationship_type": candidate["relationship_type"],
            "previous_learning": candidate["previous_learning"],
            "remaining_unknown": candidate["remaining_unknown"],
            "recommendation_reason": candidate["recommendation_reason"],
        }
        h_cols = ", ".join(h_insert.keys())
        h_phs = ", ".join(f":{k}" for k in h_insert.keys())
        h_result = await self._db.execute(
            text(
                f"INSERT INTO hypotheses ({h_cols}) VALUES ({h_phs}) "
                "RETURNING id, project_id, title, statement, primary_metric, "
                "rationale, status, parent_hypothesis_id, source_candidate_id, "
                "relationship_type, previous_learning, remaining_unknown, "
                "recommendation_reason, created_at, updated_at, "
                "research_question, independent_variable, control_condition, "
                "treatment_condition, controlled_elements, contradiction_condition, "
                "category, approved_at, rejected_at, tested_at, created_by_ai_run_id"
            ),
            h_insert,
        )
        h_row = dict(h_result.mappings().first())

        # Update candidate
        await self._db.execute(
            text(
                "UPDATE follow_up_candidates "
                "SET status = 'accepted' "
                "WHERE id = :cid AND project_id = :pid"
            ),
            {"cid": candidate_id, "pid": scope.project_id},
        )

        await self._db.commit()
        return h_row

    async def dismiss_candidate(
        self, scope: ProjectScope, candidate_id: UUID
    ) -> dict:
        candidate = await self._repo.get_candidate_for_update(scope, candidate_id)
        if not candidate:
            raise ProjectNotFound(f"Candidate {candidate_id} not found")
        if candidate["status"] != "proposed":
            raise DomainError(f"Candidate already {candidate['status']}.")

        await self._db.execute(
            text(
                "UPDATE follow_up_candidates SET status = 'dismissed' "
                "WHERE id = :cid AND project_id = :pid"
            ),
            {"cid": candidate_id, "pid": scope.project_id},
        )
        await self._db.commit()
        return {**candidate, "status": "dismissed"}

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _resolve_parent_hypothesis(
        self, scope: ProjectScope, insight_id: UUID
    ) -> dict | None:
        result = await self._db.execute(
            text(
                "SELECT h.id, h.primary_metric, h.title "
                "FROM hypotheses h "
                "JOIN experiments e ON e.hypothesis_id = h.id "
                "JOIN insights ins ON ins.experiment_id = e.id "
                "WHERE ins.id = :iid AND h.project_id = :pid"
            ),
            {"iid": insight_id, "pid": scope.project_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


def _build_evidence_dict(items: list[dict]) -> dict:
    """Build the evidence dict passed to the provider."""
    return {
        "items": [
            {
                "variant_id": str(item.get("variant_id")),
                "position": item.get("position"),
                "treatment_role": item.get("treatment_role"),
                "title": item.get("title"),
                "views_delta": item.get("views_delta", 0),
                "likes_delta": item.get("likes_delta", 0),
                "comments_delta": item.get("comments_delta", 0),
                "attributed_unique_clicks": item.get("attributed_unique_clicks", 0),
                "unique_clicks_per_1k": float(item.get("unique_clicks_per_1k") or 0),
                "delivered_variable": None,  # from ExecutionObservation if available
            }
            for item in items
        ]
    }


def _validate_candidates(candidates: list[dict]) -> None:
    if len(candidates) != 3:
        raise DomainError(f"Provider must return exactly 3 candidates; got {len(candidates)}")
    slots = {c["slot"] for c in candidates}
    if slots != _REQUIRED_SLOTS:
        raise DomainError(f"Provider must return slots {_REQUIRED_SLOTS}; got {slots}")
    recommended_count = sum(1 for c in candidates if c.get("recommended"))
    if recommended_count != 1:
        raise DomainError(
            f"Exactly one candidate must be recommended; got {recommended_count}"
        )
