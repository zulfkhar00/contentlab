"""
IntelligenceProvider protocol.
Every implementation — Fake or Claude — must satisfy this interface.
The service layer calls the provider outside any open database transaction.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class IntelligenceProvider(Protocol):
    async def generate_initial_hypotheses(
        self,
        project: dict,
        facts: list[dict],
        context_version: int,
    ) -> list[dict]:
        """
        Returns a list of hypothesis payloads (dicts) for a given project context.
        Each dict must contain at minimum:
            title, statement, category, primary_metric, rationale,
            research_question, independent_variable, control_condition,
            treatment_condition, controlled_elements, contradiction_condition
        All returned hypotheses start with status = 'generated'.
        """
        ...

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
    ) -> dict:
        """
        Returns experiment design for an approved hypothesis.
        Must contain:
            experiment_name, shared_constraints (versioned JSONB),
            variants: list of 3 dicts, each with:
                position (A|B|C), treatment_role, title, variable_value,
                hook, hook_delivery_note, context, on_screen_text,
                script_sections (versioned JSONB), recording_guidance (versioned JSONB)
        """
        ...
