"""
AnthropicIntelligenceProvider — Sprint 6B.

P0 corrections applied:
  1. Uses output_config structured outputs instead of raw-text JSON extraction.
     Schema violations are impossible — Claude returns valid JSON or errors.
  2. Model IDs updated to current: claude-sonnet-5, claude-opus-4-8, claude-haiku-4-5-20251001.
     Actual model used is recorded from response.model, not assumed.
  3. Repair attempt is a SEPARATE ai_run with attempt_number=2, parent_ai_run_id pointing
     to attempt_number=1. Both share a request_group_id.
  4. status and validation_result are distinct:
       status:            success | failed | timeout
       validation_result: valid | invalid | parse_error | not_run
  5. Production requires INTELLIGENCE_PROVIDER=claude explicitly (guard in factory.py).
  6. Transport retry (rate limit / overload) uses bounded backoff, no repair prompt.
     Semantic repair is only triggered on domain-invalid responses.
  7. claimsUsed in reviseBrief output contract for founder-fact traceability.
  8. Evidence validator cross-checks cited metric values against the evidence packet.
"""
import asyncio
import hashlib
import json
import uuid
from typing import Any

from anthropic import AsyncAnthropic, APIStatusError

from app.config import settings
from app.intelligence.context_assemblers import (
    CandidateContextAssembler,
    EvidenceContextAssembler,
    ExperimentDesignContextAssembler,
    HypothesisContextAssembler,
    ReviseBriefContextAssembler,
)
from app.intelligence.prompts.registry import PROMPTS
from app.intelligence.validators import (
    ValidationError,
    validate_candidates,
    validate_experiment_design,
    validate_hypotheses,
    validate_insight,
    validate_no_invented_facts,
    validate_revision,
)

# ── JSON schemas for structured output ───────────────────────────────────────

_HYPOTHESIS_ITEM = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "statement": {"type": "string"},
        "category": {"type": "string"},
        "primary_metric": {
            "type": "string",
            "enum": ["clicks_per_1k_views", "comments_per_1k_views", "views", "product_clicks", "comments"],
        },
        "rationale": {"type": "string"},
        "research_question": {"type": "string"},
        "independent_variable": {"type": "string"},
        "control_condition": {"type": "string"},
        "treatment_condition": {"type": "string"},
        "controlled_elements": {"type": "array", "items": {"type": "string"}},
        "contradiction_condition": {"type": "string"},
    },
    "required": [
        "title", "statement", "category", "primary_metric", "rationale",
        "research_question", "independent_variable", "control_condition",
        "treatment_condition", "controlled_elements", "contradiction_condition",
    ],
    "additionalProperties": False,
}

_SCHEMAS: dict[str, dict] = {
    "generateHypotheses": {
        "type": "array",
        "items": _HYPOTHESIS_ITEM,
        "minItems": 1,
        "maxItems": 10,
    },
    "designExperiment": {
        "type": "object",
        "properties": {
            "experiment_name": {"type": "string"},
            "shared_constraints": {
                "type": "object",
                "properties": {
                    "schemaVersion": {"type": "integer"},
                    "targetDurationLabel": {"type": "string"},
                    "cta": {"type": "string"},
                    "audience": {"type": "string"},
                    "format": {"type": "string"},
                },
                "required": ["schemaVersion", "targetDurationLabel", "cta", "audience", "format"],
                "additionalProperties": False,
            },
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "position": {"type": "string", "enum": ["A", "B", "C"]},
                        "treatment_role": {"type": "string", "enum": ["control", "hypothesis_treatment", "alternative_treatment"]},
                        "title": {"type": "string"},
                        "variable_value": {"type": "string"},
                        "hook": {"type": "string"},
                        "hook_delivery_note": {"type": "string"},
                        "context": {"type": "string"},
                        "on_screen_text": {"type": "string"},
                        "script_sections": {"type": "object"},
                        "recording_guidance": {"type": "object"},
                    },
                    "required": ["position", "treatment_role", "title", "variable_value",
                                 "hook", "hook_delivery_note", "context", "on_screen_text",
                                 "script_sections", "recording_guidance"],
                    "additionalProperties": False,
                },
                "minItems": 3,
                "maxItems": 3,
            },
        },
        "required": ["experiment_name", "shared_constraints", "variants"],
        "additionalProperties": False,
    },
    "reviseBrief": {
        "type": "object",
        "properties": {
            "hook": {"type": "string"},
            "hook_delivery_note": {"type": "string"},
            "context": {"type": "string"},
            "on_screen_text": {"type": "string"},
            "claims_used": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fact_id": {"type": "string"},
                        "usage": {"type": "string"},
                    },
                    "required": ["fact_id", "usage"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["hook", "hook_delivery_note", "context", "on_screen_text", "claims_used"],
        "additionalProperties": False,
    },
    "analyzeExperiment": {
        "type": "object",
        "properties": {
            "outcome_type": {
                "type": "string",
                "enum": [
                    "directional_difference", "mixed_result", "little_difference",
                    "all_variants_weak", "all_variants_strong",
                    "insufficient_evidence", "execution_problem",
                ],
            },
            "outcome_description": {"type": "string"},
            "supported_learning": {"type": "string"},
            "do_not_infer_yet": {"type": "array", "items": {"type": "string"}},
            "recommended_next_test": {"type": "string"},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "evidence_references": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "variant_position": {"type": "string", "enum": ["A", "B", "C"]},
                        "metric": {"type": "string"},
                        "value": {"type": "number"},
                    },
                    "required": ["variant_position", "metric", "value"],
                    "additionalProperties": False,
                },
            },
            "evidence_basis": {
                "type": "object",
                "properties": {
                    "schemaVersion": {"type": "integer"},
                    "trackingWindowsCompleted": {"type": "integer"},
                    "requiredTrackingWindows": {"type": "integer"},
                    "attributionMethod": {"type": "string"},
                    "executionDeviations": {"type": "array", "items": {"type": "string"}},
                    "allVideosValidated": {"type": "boolean"},
                },
                "required": ["schemaVersion", "trackingWindowsCompleted", "requiredTrackingWindows",
                             "attributionMethod", "executionDeviations", "allVideosValidated"],
                "additionalProperties": False,
            },
        },
        "required": ["outcome_type", "outcome_description", "supported_learning",
                     "do_not_infer_yet", "recommended_next_test", "limitations",
                     "evidence_references", "evidence_basis"],
        "additionalProperties": False,
    },
    "generateCandidates": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "slot": {"type": "string", "enum": ["safest_next_step", "highest_learning", "highest_upside"]},
                "relationship_type": {
                    "type": "string",
                    "enum": ["replication", "mechanism_isolation", "parameter_optimization",
                             "generalization", "counter_hypothesis", "recovery_redesign"],
                },
                "statement": {"type": "string"},
                "why_this_follows": {"type": "string"},
                "recommended": {"type": "boolean"},
                "recommendation_reason": {"type": "string"},
                "previous_learning": {"type": "string"},
                "remaining_unknown": {"type": "string"},
            },
            "required": ["slot", "relationship_type", "statement", "why_this_follows",
                         "recommended", "recommendation_reason", "previous_learning", "remaining_unknown"],
            "additionalProperties": False,
        },
        "minItems": 3,
        "maxItems": 3,
    },
}


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


_TRANSPORT_RETRY_CODES = {429, 529}  # rate limit, overload


async def _call_structured(
    client: AsyncAnthropic,
    model: str,
    system: str,
    user: str,
    schema: dict,
    timeout: int,
    max_tokens: int,
    max_transport_retries: int = 3,
) -> tuple[Any, str, str]:
    """
    Call Claude with structured output + bounded transport retry.
    Returns (parsed_output, raw_text, actual_model_id).

    Transport retry: rate-limit / overload → exponential backoff with jitter.
    No "repair prompt" on transport failure.
    """
    for attempt in range(max_transport_retries + 1):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
                timeout=timeout,
            )
            raw = response.content[0].text
            actual_model = response.model
            parsed = json.loads(raw)  # Schema-guaranteed valid JSON; parse error is a bug
            return parsed, raw, actual_model
        except APIStatusError as exc:
            if exc.status_code in _TRANSPORT_RETRY_CODES and attempt < max_transport_retries:
                jitter = 0.5 + (attempt * 0.5)
                await asyncio.sleep(min(60, 2 ** attempt * jitter))
                continue
            raise
    raise RuntimeError("Max transport retries exceeded")  # should not reach here


class AnthropicIntelligenceProvider:
    MODEL = "claude"
    PROMPT_VERSION = "v1.2026-07"

    def __init__(self) -> None:
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.claude_default_timeout,
        )

    async def _run_with_optional_repair(
        self,
        model: str,
        system: str,
        user: str,
        schema: dict,
        operation: str,
        validator,
        ai_run_records: list,
        request_group_id: str,
        project_id,
        entity_type: str,
        entity_id,
        input_payload: dict,
        input_hash: str,
        context_version: int,
    ) -> tuple[Any, str]:
        """
        First attempt + optional semantic repair.
        Each call creates one ai_run entry appended to ai_run_records.
        Returns (validated_output, actual_model).
        """
        max_tokens = settings.claude_max_tokens
        timeout = settings.claude_default_timeout

        async def _attempt(attempt_number: int, parent_run_id: str | None, user_prompt: str) -> tuple[Any, str, str]:
            start_import = __import__("time").monotonic()
            exc_info = None
            status = "success"
            validation_result = "valid"
            raw = ""
            actual_model = model
            parsed = None
            try:
                parsed, raw, actual_model = await _call_structured(
                    self._client, model, system, user_prompt, schema, timeout, max_tokens
                )
                validator(parsed)
            except ValidationError as ve:
                status = "failed"
                validation_result = "invalid"
                exc_info = str(ve)
                raise
            except Exception as exc:
                if "timeout" in str(exc).lower():
                    status = "timeout"
                    validation_result = "not_run"
                elif "parse" in str(exc).lower() or isinstance(exc, json.JSONDecodeError):
                    status = "failed"
                    validation_result = "parse_error"
                else:
                    status = "failed"
                    validation_result = "not_run"
                exc_info = str(exc)
                raise
            finally:
                latency_ms = int((__import__("time").monotonic() - start_import) * 1000)
                ai_run_records.append({
                    "project_id": project_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "field_name": None,
                    "operation": operation,
                    "model": actual_model,
                    "prompt_version": PROMPTS[operation].version,
                    "context_version": context_version,
                    "input_hash": input_hash,
                    "input_payload": json.dumps(input_payload),
                    "output_payload": json.dumps({"raw": raw[:2000]}) if raw else "{}",
                    "validation_result": validation_result,
                    "status": status,
                    "latency_ms": latency_ms,
                    "token_usage": json.dumps({"inputTokens": 0, "outputTokens": 0}),
                    "cost_usd": 0,
                    "request_group_id": request_group_id,
                    "attempt_number": attempt_number,
                    "parent_ai_run_id": parent_run_id,
                    "error_detail": exc_info,
                })
            return parsed, raw, actual_model

        # Attempt 1
        first_run_id = str(uuid.uuid4())
        try:
            parsed, raw, actual_model = await _attempt(1, None, user)
            ai_run_records[-1]["id"] = first_run_id
            return parsed, actual_model
        except ValidationError as first_err:
            ai_run_records[-1]["id"] = first_run_id
            # Semantic repair: send specific violations back to Claude
            repair_user = (
                f"{user}\n\nYour previous response failed domain validation:\n"
                f"Error: {str(first_err)}\n"
                f"Hint: {first_err.repair_hint}\n"
                f"Please correct only the failing fields and return the complete corrected JSON."
            )
            second_run_id = str(uuid.uuid4())
            parsed, raw, actual_model = await _attempt(2, first_run_id, repair_user)
            ai_run_records[-1]["id"] = second_run_id
            return parsed, actual_model

    # ── Operations ────────────────────────────────────────────────────────────

    async def generate_initial_hypotheses(
        self,
        project: dict,
        facts: list[dict],
        context_version: int,
    ) -> tuple[list[dict], dict, str]:
        spec = PROMPTS["generateHypotheses"]
        context_str = HypothesisContextAssembler.build(project, facts, context_version)
        user = spec.user_template.replace("{context}", context_str)
        input_payload = {
            "operation": "generateHypotheses", "prompt_version": spec.version,
            "context_version": context_version, "context": context_str,
        }
        input_hash = _hash(input_payload)
        ai_runs: list = []
        rg = str(uuid.uuid4())
        model = settings.claude_model_generate_hypotheses
        result, _ = await self._run_with_optional_repair(
            model=model, system=spec.system, user=user,
            schema=_SCHEMAS["generateHypotheses"], operation="generateHypotheses",
            validator=validate_hypotheses, ai_run_records=ai_runs,
            request_group_id=rg, project_id=project.get("id"),
            entity_type="Hypothesis", entity_id=None,
            input_payload=input_payload, input_hash=input_hash,
            context_version=context_version,
        )
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        validate_no_invented_facts(json.dumps(result), verified)
        return result, input_payload, input_hash

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["designExperiment"]
        context_str = ExperimentDesignContextAssembler.build(hypothesis, project, facts)
        user = spec.user_template.replace("{context}", context_str)
        input_payload = {
            "operation": "designExperiment", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "hypothesis_id": str(hypothesis.get("id")),
            "statement": hypothesis.get("statement"),
            "independent_variable": hypothesis.get("independent_variable"),
        }
        input_hash = _hash(input_payload)
        ai_runs: list = []
        rg = str(uuid.uuid4())
        result, _ = await self._run_with_optional_repair(
            model=settings.claude_model_design_experiment,
            system=spec.system, user=user,
            schema=_SCHEMAS["designExperiment"], operation="designExperiment",
            validator=validate_experiment_design, ai_run_records=ai_runs,
            request_group_id=rg, project_id=project.get("id"),
            entity_type="Hypothesis", entity_id=hypothesis.get("id"),
            input_payload=input_payload, input_hash=input_hash,
            context_version=project.get("context_version", 1),
        )
        return result, input_payload, input_hash

    async def revise_variant_brief(
        self,
        variant: dict,
        instruction: str,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["reviseBrief"]
        ctx = ReviseBriefContextAssembler.build(variant, instruction, project)
        user = spec.user_template.format(**ctx)
        input_payload = {
            "operation": "reviseBrief", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "instruction": instruction,
            "current_hook": variant.get("hook"),
            "variant_updated_at": str(variant.get("updated_at")),
        }
        input_hash = _hash(input_payload)

        def _validate_revision_with_facts(result: dict) -> None:
            validate_revision(result)
            # Verify any claimed facts are from verified list
            verified_ids = {f["id"]: f["fact_text"] for f in facts if f.get("status") == "verified"}
            for claim in result.get("claims_used", []):
                fid = claim.get("fact_id", "")
                if fid and fid not in verified_ids:
                    from app.intelligence.validators import ValidationError
                    raise ValidationError(
                        f"Brief references unverified or unknown fact_id: {fid}",
                        "Only reference fact_ids from the verified project facts list."
                    )

        ai_runs: list = []
        rg = str(uuid.uuid4())
        result, _ = await self._run_with_optional_repair(
            model=settings.claude_model_revise_brief,
            system=spec.system, user=user,
            schema=_SCHEMAS["reviseBrief"], operation="reviseBrief",
            validator=_validate_revision_with_facts, ai_run_records=ai_runs,
            request_group_id=rg, project_id=project.get("id"),
            entity_type="Variant", entity_id=variant.get("id"),
            input_payload=input_payload, input_hash=input_hash,
            context_version=project.get("context_version", 1),
        )
        return result, input_payload, input_hash

    async def analyze_experiment(
        self,
        evidence: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["analyzeExperiment"]
        ctx = EvidenceContextAssembler.build(evidence, hypothesis_snapshot, project, facts)
        user = spec.user_template.format(**ctx)
        evidence_snapshot_id = evidence.get("snapshot_id")
        input_payload = {
            "operation": "analyzeExperiment", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "evidence_snapshot_id": str(evidence_snapshot_id) if evidence_snapshot_id else None,
            "hypothesis_statement": hypothesis_snapshot.get("statement"),
            "evidence_items": [
                {k: v for k, v in item.items()
                 if k in ("position", "treatment_role", "unique_clicks_per_1k", "views_delta")}
                for item in evidence.get("items", [])
            ],
        }
        input_hash = _hash(input_payload)

        # Build evidence lookup for cross-checking
        evidence_map = {
            item["position"]: item
            for item in evidence.get("items", [])
        }

        def _validate_with_evidence(result: dict) -> None:
            validate_insight(result)
            # Cross-check cited metric values against evidence packet
            from app.intelligence.validators import ValidationError
            for ref in result.get("evidence_references", []):
                pos = ref.get("variant_position")
                metric = ref.get("metric")
                cited_value = ref.get("value")
                actual_item = evidence_map.get(pos)
                if not actual_item:
                    continue
                actual_value = actual_item.get("unique_clicks_per_1k")
                if metric == "unique_clicks_per_1k" and actual_value is not None and cited_value is not None:
                    if abs(float(cited_value) - float(actual_value)) > 0.5:
                        raise ValidationError(
                            f"Cited metric for variant {pos} ({cited_value}) does not match "
                            f"evidence packet ({actual_value})",
                            f"Use the exact value from the evidence: {actual_value}"
                        )

        ai_runs: list = []
        rg = str(uuid.uuid4())
        result, _ = await self._run_with_optional_repair(
            model=settings.claude_model_analyze_experiment,
            system=spec.system, user=user,
            schema=_SCHEMAS["analyzeExperiment"], operation="analyzeExperiment",
            validator=_validate_with_evidence, ai_run_records=ai_runs,
            request_group_id=rg, project_id=project.get("id"),
            entity_type="Insight", entity_id=None,
            input_payload=input_payload, input_hash=input_hash,
            context_version=project.get("context_version", 1),
        )
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        validate_no_invented_facts(json.dumps(result), verified)
        return result, input_payload, input_hash

    async def generate_follow_up_candidates(
        self,
        insight: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[list[dict], dict, str]:
        spec = PROMPTS["generateCandidates"]
        ctx = CandidateContextAssembler.build(insight, hypothesis_snapshot, project, facts)
        user = spec.user_template.format(**ctx)
        input_payload = {
            "operation": "generateCandidates", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "insight_id": str(insight.get("id")) if insight.get("id") else None,
            "outcome_type": insight.get("outcome_type"),
            "supported_learning": insight.get("supported_learning"),
        }
        input_hash = _hash(input_payload)
        ai_runs: list = []
        rg = str(uuid.uuid4())
        result, _ = await self._run_with_optional_repair(
            model=settings.claude_model_generate_candidates,
            system=spec.system, user=user,
            schema=_SCHEMAS["generateCandidates"], operation="generateCandidates",
            validator=validate_candidates, ai_run_records=ai_runs,
            request_group_id=rg, project_id=project.get("id"),
            entity_type="FollowUpCandidate", entity_id=None,
            input_payload=input_payload, input_hash=input_hash,
            context_version=project.get("context_version", 1),
        )
        return result, input_payload, input_hash
