"""
IntelligenceProvider protocol.
Every implementation returns (result, input_payload, input_hash) tuples so
the service layer can store a single canonical ai_run per invocation.
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
        """
        Returns (hypotheses, input_payload, input_hash).
        input_payload is the canonical dict sent to the model.
        input_hash is sha256 of json.dumps(input_payload, sort_keys=True).
        """
        ...

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        """
        Returns (experiment_design, input_payload, input_hash).
        hypothesis must be the fully merged design (stored fields + request edits)
        so the hash reflects what was actually sent to the model.
        """
        ...
