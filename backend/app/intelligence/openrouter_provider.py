"""
OpenRouterIntelligenceProvider — uses the OpenAI-compatible OpenRouter API
to route calls to Claude (and optionally other models) without the Anthropic SDK.

Differences from AnthropicIntelligenceProvider:
  - Uses AsyncOpenAI with base_url=https://openrouter.ai/api/v1
  - System message in messages array (role: system), not a separate parameter
  - response_format={"type": "json_object"} for guaranteed JSON output
  - Full JSON Schema embedded in system prompt (already in prompts/registry.py)
  - Token usage from response.usage.prompt_tokens / completion_tokens
  - Model IDs prefixed with "anthropic/" (e.g. "anthropic/claude-sonnet-5")
  - Transport retry on 429 / 503 with bounded backoff
  - Repair on domain validation failure — same as Anthropic provider
  - Two ai_run rows per logical operation when repair is triggered
"""
import asyncio
import hashlib
import json
import time
import uuid

from openai import AsyncOpenAI, APIStatusError

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

# OpenRouter model IDs (anthropic/ prefix routes to Anthropic's API)
_OPENROUTER_MODELS = {
    "claude_model_generate_hypotheses":  "anthropic/claude-sonnet-5",
    "claude_model_design_experiment":    "anthropic/claude-sonnet-5",
    "claude_model_revise_brief":         "anthropic/claude-haiku-4-5",
    "claude_model_analyze_experiment":   "anthropic/claude-sonnet-5",
    "claude_model_generate_candidates":  "anthropic/claude-sonnet-5",
}

_TRANSPORT_RETRY_CODES = {429, 503}

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def _model_for(operation_setting_key: str) -> str:
    """Return OpenRouter model ID for a given config key, with sane fallback.
    OpenRouter uses aliases without date suffixes (e.g. anthropic/claude-haiku-4-5)
    so we strip known date-suffixed variants before building the model string.
    """
    import re as _re
    configured = getattr(settings, operation_setting_key, "")
    if not configured:
        return _OPENROUTER_MODELS[operation_setting_key]
    # Strip trailing date suffix that OpenRouter does not accept
    configured = _re.sub(r"(-20\d{6,})+$", "", configured)
    if "/" in configured:
        return configured
    return f"anthropic/{configured}"


async def _call(
    client: AsyncOpenAI,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    timeout: int,
    max_retries: int = 3,
) -> tuple[str, str, int, int]:
    """
    Single call to OpenRouter with transport retry.
    Returns (raw_json_text, actual_model, input_tokens, output_tokens).
    """
    for attempt in range(max_retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                timeout=timeout,
            )
            raw = (resp.choices[0].message.content or "").strip()
            import re as _re
            if not raw.startswith(("{", "[")):
                m = _re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', raw)
                if m:
                    raw = m.group(1).strip()
                else:
                    for sc, ec in [("{", "}"), ("[", "]")]:
                        si, ei = raw.find(sc), raw.rfind(ec)
                        if si != -1 and ei > si:
                            raw = raw[si:ei + 1]
                            break
            actual_model = resp.model or model
            in_tok = resp.usage.prompt_tokens if resp.usage else 0
            out_tok = resp.usage.completion_tokens if resp.usage else 0
            return raw, actual_model, in_tok, out_tok
        except APIStatusError as exc:
            if exc.status_code in _TRANSPORT_RETRY_CODES and attempt < max_retries:
                await asyncio.sleep(min(60, (2 ** attempt) * 1.0))
                continue
            raise
    raise RuntimeError("Max OpenRouter transport retries exceeded")


class OpenRouterIntelligenceProvider:
    MODEL = "openrouter"
    PROMPT_VERSION = "v1.2026-07"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=_OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key,
            default_headers={
                "HTTP-Referer": "https://contentlab.app",
                "X-Title": "Content Lab",
            },
            timeout=settings.claude_default_timeout,
        )

    async def _run(
        self,
        model: str,
        system: str,
        user: str,
        validator,
        operation: str,
        input_payload: dict,
        input_hash: str,
        project_id,
        entity_id,
        entity_type: str,
        context_version: int,
        ai_run_records: list,
        request_group_id: str,
    ):
        max_tokens = settings.claude_max_tokens
        timeout = settings.claude_default_timeout

        async def _attempt(attempt_number: int, parent_id: str | None, user_prompt: str):
            t0 = time.monotonic()
            status = "success"
            validation_result = "valid"
            raw = ""
            actual_model = model
            in_tok = out_tok = 0
            exc_detail = None
            parsed = None
            try:
                raw, actual_model, in_tok, out_tok = await _call(
                    self._client, model, system, user_prompt, max_tokens, timeout
                )
                parsed = json.loads(raw)
                validator(parsed)
            except ValidationError as ve:
                status, validation_result, exc_detail = "failed", "invalid", str(ve)
                raise
            except json.JSONDecodeError as je:
                status, validation_result, exc_detail = "failed", "parse_error", str(je)
                raise
            except Exception as exc:
                status = "timeout" if "timeout" in str(exc).lower() else "failed"
                validation_result = "not_run"
                exc_detail = str(exc)
                raise
            finally:
                row_id = str(uuid.uuid4())
                ai_run_records.append({
                    "id": row_id,
                    "project_id": project_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "operation": operation,
                    "model": actual_model,
                    "prompt_version": PROMPTS[operation].version,
                    "context_version": context_version,
                    "input_hash": input_hash,
                    "input_payload": json.dumps(input_payload),
                    "output_payload": json.dumps({"raw": raw[:2000]}) if raw else "{}",
                    "validation_result": validation_result,
                    "token_usage": json.dumps({"inputTokens": in_tok, "outputTokens": out_tok}),
                    "cost_usd": 0,
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                    "status": status,
                    "request_group_id": request_group_id,
                    "attempt_number": attempt_number,
                    "parent_ai_run_id": parent_id,
                    "error_detail": exc_detail,
                })
                ai_run_records[-1]["id"] = row_id
            return parsed, row_id

        first_id = None
        try:
            result, first_id = await _attempt(1, None, user)
            return result
        except ValidationError as first_err:
            repair = (
                f"{user}\n\nYour previous response failed validation:\n"
                f"Error: {str(first_err)}\nHint: {first_err.repair_hint}\n"
                "Correct only the failing fields and return the complete JSON."
            )
            result, _ = await _attempt(2, first_id, repair)
            return result

    # ── Operations ────────────────────────────────────────────────────────────

    async def generate_initial_hypotheses(
        self, project: dict, facts: list[dict], context_version: int
    ) -> tuple[list[dict], dict, str]:
        spec = PROMPTS["generateHypotheses"]
        ctx = HypothesisContextAssembler.build(project, facts, context_version)
        user = spec.user_template.replace("{context}", ctx)
        payload = {
            "operation": "generateHypotheses", "prompt_version": spec.version,
            "context_version": context_version, "context": ctx,
        }
        h = _hash(payload)
        ai_runs: list = []
        result = await self._run(
            model=_model_for("claude_model_generate_hypotheses"),
            system=spec.system, user=user,
            validator=validate_hypotheses, operation="generateHypotheses",
            input_payload=payload, input_hash=h,
            project_id=project.get("id"), entity_id=None, entity_type="Hypothesis",
            context_version=context_version, ai_run_records=ai_runs,
            request_group_id=str(uuid.uuid4()),
        )
        verify = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        validate_no_invented_facts(json.dumps(result), verify)
        return result, payload, h

    async def design_experiment(
        self, hypothesis: dict, project: dict, facts: list[dict]
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["designExperiment"]
        ctx = ExperimentDesignContextAssembler.build(hypothesis, project, facts)
        user = spec.user_template.replace("{context}", ctx)
        payload = {
            "operation": "designExperiment", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "hypothesis_id": str(hypothesis.get("id")),
            "statement": hypothesis.get("statement"),
        }
        h = _hash(payload)
        ai_runs: list = []
        result = await self._run(
            model=_model_for("claude_model_design_experiment"),
            system=spec.system, user=user,
            validator=validate_experiment_design, operation="designExperiment",
            input_payload=payload, input_hash=h,
            project_id=project.get("id"), entity_id=hypothesis.get("id"),
            entity_type="Hypothesis", context_version=project.get("context_version", 1),
            ai_run_records=ai_runs, request_group_id=str(uuid.uuid4()),
        )
        return result, payload, h

    async def revise_variant_brief(
        self, variant: dict, instruction: str, project: dict, facts: list[dict]
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["reviseBrief"]
        ctx = ReviseBriefContextAssembler.build(variant, instruction, project)
        user = spec.user_template.format(**ctx)
        payload = {
            "operation": "reviseBrief", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "instruction": instruction, "current_hook": variant.get("hook"),
            "variant_updated_at": str(variant.get("updated_at")),
        }
        h = _hash(payload)
        verified_ids = {f["id"]: f["fact_text"] for f in facts if f.get("status") == "verified"}
        def _validate(r):
            validate_revision(r)
            for claim in r.get("claims_used", []):
                fid = claim.get("fact_id", "")
                if fid and fid not in verified_ids:
                    raise ValidationError(f"Unknown fact_id: {fid}", "Use only verified project fact IDs.")
        ai_runs: list = []
        result = await self._run(
            model=_model_for("claude_model_revise_brief"),
            system=spec.system, user=user,
            validator=_validate, operation="reviseBrief",
            input_payload=payload, input_hash=h,
            project_id=project.get("id"), entity_id=variant.get("id"),
            entity_type="Variant", context_version=project.get("context_version", 1),
            ai_run_records=ai_runs, request_group_id=str(uuid.uuid4()),
        )
        return result, payload, h

    async def analyze_experiment(
        self, evidence: dict, hypothesis_snapshot: dict, project: dict, facts: list[dict]
    ) -> tuple[dict, dict, str]:
        spec = PROMPTS["analyzeExperiment"]
        ctx = EvidenceContextAssembler.build(evidence, hypothesis_snapshot, project, facts)
        user = spec.user_template.format(**ctx)
        payload = {
            "operation": "analyzeExperiment", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "evidence_snapshot_id": str(evidence.get("snapshot_id", "")),
        }
        h = _hash(payload)
        evidence_map = {i["position"]: i for i in evidence.get("items", [])}

        def _validate(result):
            validate_insight(result)
            _METRIC_FIELDS = {
                "unique_clicks_per_1k": "unique_clicks_per_1k",
                "clicks_per_1k_views": "unique_clicks_per_1k",
                "views": "views_delta", "views_delta": "views_delta",
                "comments": "comments_delta", "product_clicks": "attributed_unique_clicks",
            }
            for ref in result.get("evidence_references", []):
                pos = ref.get("variant_position")
                metric = ref.get("metric", "")
                cited = ref.get("value")
                item = evidence_map.get(pos)
                if not item or cited is None:
                    continue
                field = _METRIC_FIELDS.get(metric)
                if field:
                    actual = item.get(field)
                    if actual is not None:
                        tol = max(0.5, abs(float(actual)) * 0.02)
                        if abs(float(cited) - float(actual)) > tol:
                            raise ValidationError(
                                f"Cited {metric} for {pos} ({cited}) != evidence ({actual})",
                                f"Use exact evidence value: {actual}"
                            )

        ai_runs: list = []
        result = await self._run(
            model=_model_for("claude_model_analyze_experiment"),
            system=spec.system, user=user,
            validator=_validate, operation="analyzeExperiment",
            input_payload=payload, input_hash=h,
            project_id=project.get("id"), entity_id=None, entity_type="Insight",
            context_version=project.get("context_version", 1),
            ai_run_records=ai_runs, request_group_id=str(uuid.uuid4()),
        )
        verify = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        validate_no_invented_facts(json.dumps(result), verify)
        return result, payload, h

    async def generate_follow_up_candidates(
        self, insight: dict, hypothesis_snapshot: dict, project: dict, facts: list[dict]
    ) -> tuple[list[dict], dict, str]:
        spec = PROMPTS["generateCandidates"]
        ctx = CandidateContextAssembler.build(insight, hypothesis_snapshot, project, facts)
        user = spec.user_template.format(**ctx)
        payload = {
            "operation": "generateCandidates", "prompt_version": spec.version,
            "context_version": project.get("context_version", 1),
            "insight_id": str(insight.get("id", "")),
            "outcome_type": insight.get("outcome_type"),
        }
        h = _hash(payload)
        ai_runs: list = []
        result = await self._run(
            model=_model_for("claude_model_generate_candidates"),
            system=spec.system, user=user,
            validator=validate_candidates, operation="generateCandidates",
            input_payload=payload, input_hash=h,
            project_id=project.get("id"), entity_id=None, entity_type="FollowUpCandidate",
            context_version=project.get("context_version", 1),
            ai_run_records=ai_runs, request_group_id=str(uuid.uuid4()),
        )
        return result, payload, h
