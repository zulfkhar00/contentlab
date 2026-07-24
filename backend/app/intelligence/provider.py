"""
IntelligenceProvider protocol — extended for Sprint 4.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class IntelligenceProvider(Protocol):
    async def generate_initial_hypotheses(
        self,
        project: dict,
        facts: list[dict],
        context_version: int,
    ) -> tuple[list[dict], dict, str]:
        """Returns (hypotheses, input_payload, input_hash)."""
        ...

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        """Returns (experiment_design, input_payload, input_hash)."""
        ...

    async def analyze_experiment(
        self,
        evidence: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        """
        Interprets bounded evidence. Code has already computed all metrics.
        evidence contains pre-computed comparisons; provider only supplies prose.

        Returns (insight_payload, input_payload, input_hash).
        insight_payload must contain:
            supported_learning, evidence_basis (versioned JSONB),
            do_not_infer_yet, recommended_next_test, limitations,
            outcome_type, outcome_description
        """
        ...

    async def generate_follow_up_candidates(
        self,
        insight: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[list[dict], dict, str]:
        """
        Generate exactly 3 follow-up candidates: one per slot.
        Slots: safest_next_step, highest_learning, highest_upside.
        Exactly one candidate must have recommended=True.

        Returns (candidates, input_payload, input_hash).
        Each candidate must contain:
            slot, relationship_type, statement, why_this_follows,
            recommended, recommendation_reason,
            previous_learning, remaining_unknown
        """
        ...
    async def revise_variant_brief(
        self,
        variant: dict,
        instruction: str,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        """
        Returns (revision, input_payload, input_hash).
        revision contains proposed hook, hook_delivery_note, context, on_screen_text.
        Not applied until the user explicitly calls PATCH /brief.
        """
        ...

