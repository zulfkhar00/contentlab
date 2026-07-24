"""
AnthropicIntelligenceProvider — production Claude integration.

Architecture:
  - Each operation builds context via ContextAssembler
  - Calls Claude with tool_use for reliable structured JSON
  - Validates output through layered validators
  - Permits one repair attempt if validation fails
  - Returns (result, input_payload, input_hash)

The provider never queries the database. All required data is passed in
by the service layer.
"""
import hashlib
import json
import time
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.intelligence.context_assemblers import (
    CandidateContextAssembler,
    EvidenceContextAssembler,
    ExperimentDesignContextAssembler,
    HypothesisContextAssembler,
    ReviseBriefContextAssembler,
)
from app.intelligence.prompt_registry import PROMPTS
from app.intelligence.validators import (
    ValidationError,
    validate_candidates,
    validate_experiment_design,
    validate_hypotheses,
    validate_insight,
    validate_no_invented_facts,
    validate_revision,
)


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


async def _call_claude(
    client: AsyncAnthropic,
    model: str,
    system: str,
    user: str,
    timeout: int,
    max_tokens: int,
) -> str:
    """Single Claude call; returns raw text content."""
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout=timeout,
    )
    return response.content[0].text


def _parse_json(raw: str) -> Any:
    """Extract JSON from Claude response, stripping any surrounding text."""
    raw = raw.strip()
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Look for JSON array or object delimiters
    for start_char, end_char in [('[', ']'), ('{', '}')]:
        s = raw.find(start_char)
        e = raw.rfind(end_char)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(raw[s:e + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError(f"Could not parse JSON from response: {raw[:200]}")


def _repair_prompt(original_user: str, raw_output: str, error: str) -> str:
    return (
        f"{original_user}\n\n"
        f"Your previous response failed validation with this error:\n{error}\n\n"
        f"Your previous (invalid) response was:\n{raw_output[:500]}\n\n"
        "Please fix the issue and return only valid JSON."
    )


class AnthropicIntelligenceProvider:
    MODEL = "claude"
    PROMPT_VERSION = "v1.2026-07"

    def __init__(self) -> None:
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.claude_default_timeout,
        )

    async def _call_with_repair(
        self,
        model: str,
        system: str,
        user: str,
        validator,
        operation: str,
    ) -> tuple[Any, str]:
        """
        Call Claude, validate, permit one repair attempt.
        Returns (parsed_output, raw_text).
        Raises ValidationError on second failure.
        """
        timeout = settings.claude_default_timeout
        max_tokens = settings.claude_max_tokens

        raw = await _call_claude(self._client, model, system, user, timeout, max_tokens)
        try:
            parsed = _parse_json(raw)
            validator(parsed)
            return parsed, raw
        except (ValueError, ValidationError) as first_err:
            # One repair attempt
            repair_user = _repair_prompt(user, raw, str(first_err))
            raw2 = await _call_claude(self._client, model, system, repair_user, timeout, max_tokens)
            parsed2 = _parse_json(raw2)
            validator(parsed2)
            return parsed2, raw2

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
        model = settings.claude_model_generate_hypotheses

        input_payload = {
            "operation": "generateHypotheses",
            "prompt_version": spec.version,
            "context_version": context_version,
            "context": context_str,
        }
        parsed, _ = await self._call_with_repair(
            model, spec.system, user,
            validate_hypotheses, "generateHypotheses"
        )
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        validate_no_invented_facts(json.dumps(parsed), verified)
        return parsed, input_payload, _hash(input_payload)

    async def design_experiment(
        self,
        hypothesis: dict,
        project: dict,
        facts: list[dict],
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["designExperiment"]
        context_str = ExperimentDesignContextAssembler.build(hypothesis, project, facts)
        user = spec.user_template.replace("{context}", context_str)
        model = settings.claude_model_design_experiment

        input_payload = {
            "operation": "designExperiment",
            "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "hypothesis": {
                "id": str(hypothesis.get("id")),
                "statement": hypothesis.get("statement"),
                "independent_variable": hypothesis.get("independent_variable"),
                "primary_metric": hypothesis.get("primary_metric"),
            },
            "project": {"product_name": project.get("product_name"), "primary_cta": project.get("primary_cta")},
        }
        parsed, _ = await self._call_with_repair(
            model, spec.system, user,
            validate_experiment_design, "designExperiment"
        )
        return parsed, input_payload, _hash(input_payload)

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
        model = settings.claude_model_revise_brief

        input_payload = {
            "operation": "reviseBrief",
            "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "instruction": instruction,
            "current_hook": variant.get("hook"),
            "variant_updated_at": str(variant.get("updated_at")),
        }
        parsed, _ = await self._call_with_repair(
            model, spec.system, user,
            validate_revision, "reviseBrief"
        )
        return parsed, input_payload, _hash(input_payload)

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
        model = settings.claude_model_analyze_experiment

        input_payload = {
            "operation": "analyzeExperiment",
            "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "hypothesis_snapshot": hypothesis_snapshot,
            "evidence_items": [
                {k: v for k, v in item.items()
                 if k in ("position", "treatment_role", "title", "views_delta",
                          "attributed_unique_clicks", "unique_clicks_per_1k")}
                for item in evidence.get("items", [])
            ],
        }
        parsed, _ = await self._call_with_repair(
            model, spec.system, user,
            validate_insight, "analyzeExperiment"
        )
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        validate_no_invented_facts(json.dumps(parsed), verified)
        return parsed, input_payload, _hash(input_payload)

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
        model = settings.claude_model_generate_candidates

        input_payload = {
            "operation": "generateCandidates",
            "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "insight_outcome_type": insight.get("outcome_type"),
            "insight_supported_learning": insight.get("supported_learning"),
        }
        parsed, _ = await self._call_with_repair(
            model, spec.system, user,
            validate_candidates, "generateCandidates"
        )
        return parsed, input_payload, _hash(input_payload)
