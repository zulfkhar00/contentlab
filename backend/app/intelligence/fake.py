"""
FakeIntelligenceProvider — Sprint 4 additions: analyze + candidates.
"""
import hashlib
import json

from app.intelligence.fixtures import (
    FIXTURE_HYPOTHESES,
    _fixture_candidates,
    _fixture_experiment,
    _fixture_insight,
)


def _canonical_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


class FakeIntelligenceProvider:
    MODEL = "fake"
    PROMPT_VERSION = "fixture-v1"

    async def generate_initial_hypotheses(
        self,
        project: dict,
        facts: list[dict],
        context_version: int,
    ) -> tuple[list[dict], dict, str]:
        input_payload = {
            "operation": "generateHypotheses",
            "context_version": context_version,
            "product_name": project.get("product_name"),
            "product_type": project.get("product_type"),
            "product_description": project.get("product_description"),
            "product_url": project.get("product_url"),
            "target_audience": project.get("target_audience"),
            "problem_solved": project.get("problem_solved"),
            "why_it_matters": project.get("why_it_matters"),
            "current_alternatives": project.get("current_alternatives"),
            "desired_action": project.get("desired_action"),
            "primary_cta": project.get("primary_cta"),
            "tiktok_handle": project.get("tiktok_handle"),
            "verified_facts": [f["fact_text"] for f in facts if f.get("status") == "verified"],
        }
        return FIXTURE_HYPOTHESES, input_payload, _canonical_hash(input_payload)

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        input_payload = {
            "operation": "designExperiment",
            "context_version": project.get("context_version", 1),
            "hypothesis": {
                "id": str(hypothesis.get("id")),
                "statement": hypothesis.get("statement"),
                "research_question": hypothesis.get("research_question"),
                "independent_variable": hypothesis.get("independent_variable"),
                "control_condition": hypothesis.get("control_condition"),
                "treatment_condition": hypothesis.get("treatment_condition"),
                "primary_metric": hypothesis.get("primary_metric"),
                "controlled_elements": hypothesis.get("controlled_elements", []),
                "contradiction_condition": hypothesis.get("contradiction_condition"),
            },
            "project": {
                "product_name": project.get("product_name"),
                "primary_cta": project.get("primary_cta"),
                "target_audience": project.get("target_audience"),
            },
            "verified_facts": [f["fact_text"] for f in facts if f.get("status") == "verified"],
        }
        return _fixture_experiment(hypothesis, project), input_payload, _canonical_hash(input_payload)

    async def analyze_experiment(
        self,
        evidence: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        """
        Interprets bounded pre-computed evidence.
        Code computes metrics; provider only supplies prose and classification.
        """
        input_payload = {
            "operation": "analyzeExperiment",
            "context_version": project.get("context_version", 1),
            "hypothesis_snapshot": hypothesis_snapshot,
            "evidence_items": [
                {
                    "position": item.get("position"),
                    "treatment_role": item.get("treatment_role"),
                    "views_delta": item.get("views_delta"),
                    "unique_clicks_per_1k": item.get("unique_clicks_per_1k"),
                    "execution_deviated": item.get("delivered_variable") is False,
                }
                for item in evidence.get("items", [])
            ],
            "verified_facts": [f["fact_text"] for f in facts if f.get("status") == "verified"],
        }
        return _fixture_insight(evidence, hypothesis_snapshot), input_payload, _canonical_hash(input_payload)

    async def generate_follow_up_candidates(
        self,
        insight: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[list[dict], dict, str]:
        input_payload = {
            "operation": "generateCandidates",
            "context_version": project.get("context_version", 1),
            "insight": {
                "outcome_type": insight.get("outcome_type"),
                "supported_learning": insight.get("supported_learning"),
                "recommended_next_test": insight.get("recommended_next_test"),
            },
            "hypothesis_snapshot": hypothesis_snapshot,
            "verified_facts": [f["fact_text"] for f in facts if f.get("status") == "verified"],
        }
        evidence = {"items": insight.get("evidence_items", [])}
        return _fixture_candidates(evidence, hypothesis_snapshot), input_payload, _canonical_hash(input_payload)
    async def revise_variant_brief(
        self,
        variant: dict,
        instruction: str,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        base = variant.get("hook", "")
        trimmed = instruction.strip() or "sharper framing"
        revision = {
            "hook": f"{base.rstrip('.')} — reframed around {trimmed}.",
            "hook_delivery_note": f"Deliver with {trimmed}.",
            "context": variant.get("context", ""),
            "on_screen_text": variant.get("on_screen_text", ""),
        }
        input_payload = {
            "operation": "reviseBrief",
            "instruction": instruction,
            "current_hook": base,
            "product_name": project.get("product_name"),
            "context_version": project.get("context_version", 1),
        }
        return revision, input_payload, _canonical_hash(input_payload)

