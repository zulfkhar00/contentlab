"""
FakeIntelligenceProvider — deterministic Content Lab fixtures.
Used for all testing and for the initial product vertical slice
before real Claude integration (Sprint 6).
"""
import hashlib
import json

from app.intelligence.fixtures import FIXTURE_HYPOTHESES, _fixture_experiment


class FakeIntelligenceProvider:
    """
    Returns canonical Content Lab seed data regardless of input.
    Suitable for development, integration tests, and the Playwright
    workflow test. Swapped out for ClaudeIntelligenceProvider in Sprint 6.
    """

    MODEL = "fake"
    PROMPT_VERSION = "fixture-v1"

    @staticmethod
    def _input_hash(payload: dict) -> str:
        """SHA-256 of the sorted JSON encoding of the prompt input."""
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def generate_initial_hypotheses(
        self,
        project: dict,
        facts: list[dict],
        context_version: int,
    ) -> tuple[list[dict], str]:
        """
        Returns (hypotheses, input_hash).
        input_hash is computed from the project context so it is
        stable for the same project but changes if context_version changes.
        """
        payload = {
            "operation": "generateHypotheses",
            "context_version": context_version,
            "product_name": project.get("product_name"),
            "product_type": project.get("product_type"),
            "target_audience": project.get("target_audience"),
            "problem_solved": project.get("problem_solved"),
            "desired_action": project.get("desired_action"),
        }
        input_hash = self._input_hash(payload)
        return FIXTURE_HYPOTHESES, input_hash

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
    ) -> tuple[dict, str]:
        """
        Returns (experiment_design, input_hash).
        """
        payload = {
            "operation": "designExperiment",
            "hypothesis_id": hypothesis.get("id"),
            "statement": hypothesis.get("statement"),
            "independent_variable": hypothesis.get("independent_variable"),
            "product_name": project.get("product_name"),
            "primary_cta": project.get("primary_cta"),
        }
        input_hash = self._input_hash(payload)
        return _fixture_experiment(hypothesis, project), input_hash
