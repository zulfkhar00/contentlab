"""
FakeIntelligenceProvider — deterministic Content Lab fixtures.
Returns the full canonical input_payload for each operation so the service
can store it verbatim in ai_runs and compute a stable input_hash.
"""
import hashlib
import json

from app.intelligence.fixtures import FIXTURE_HYPOTHESES, _fixture_experiment


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
        """
        Returns (hypotheses, input_payload, input_hash).
        input_payload covers all project fields passed as AI context.
        """
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
        """
        Returns (experiment_design, input_payload, input_hash).
        input_payload includes the complete merged hypothesis design so the
        hash changes if the hypothesis is edited between provider call and lock.
        """
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
