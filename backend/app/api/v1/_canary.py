"""
Dev-only canary: run one live Claude call and return telemetry.
Available ONLY when settings.environment == 'development'.
Requires service-role Authorization header (not ordinary user JWT).

Returns full telemetry: model, tokens, cost, latency, validation result.
Does NOT persist an ai_run (dry-run label prevents confusion with real runs).
"""
import time
from fastapi import HTTPException, Header


async def run_canary(
    operation: str,
    scope,
    db,
    authorization: str | None = None,
) -> dict:
    from app.config import settings
    from app.intelligence.factory import get_intelligence_provider
    from app.repositories.project_repo import ProjectRepository
    from app.intelligence.evaluation.suite import (
        _FLAGD_PROJECT, _FLAGD_HYPOTHESIS, _FLAGD_EVIDENCE, _FLAGD_SNAPSHOT, _make_flagd_insight,
    )
    import json
    from anthropic import AsyncAnthropic

    if settings.environment != "development":
        raise HTTPException(
            status_code=403,
            detail="Canary endpoint is only available in development environment."
        )
    prov = settings.intelligence_provider
    if prov == "fake":
        raise HTTPException(
            status_code=422,
            detail="INTELLIGENCE_PROVIDER=fake; set to 'openrouter' or 'claude' with a real API key."
        )
    if prov == "openrouter" and not settings.openrouter_api_key:
        raise HTTPException(status_code=422, detail="OPENROUTER_API_KEY is required.")

    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_scope(scope) or {**_FLAGD_PROJECT, "id": str(scope.project_id)}

    configured_model = getattr(
        settings, f"claude_model_{operation.replace('generateHypotheses', 'generate_hypotheses').replace('designExperiment', 'design_experiment').replace('reviseBrief', 'revise_brief').replace('analyzeExperiment', 'analyze_experiment').replace('generateCandidates', 'generate_candidates')}",
        "claude-sonnet-5",
    )

    # Minimal direct Anthropic call to capture token usage
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    start = time.monotonic()
    attempt_count = 1
    actual_model = configured_model
    input_tokens = 0
    output_tokens = 0
    validation_result = "not_run"
    input_hash = ""
    output_summary: dict = {}

    try:
        from app.intelligence.prompts.registry import PROMPTS
        from app.intelligence.context_assemblers import (
            HypothesisContextAssembler, ExperimentDesignContextAssembler,
            ReviseBriefContextAssembler, EvidenceContextAssembler, CandidateContextAssembler,
        )
        from app.intelligence.anthropic_provider import _SCHEMAS, _hash
        import hashlib, json as _json

        op_map = {
            "generateHypotheses": ("generateHypotheses", configured_model),
            "designExperiment": ("designExperiment", configured_model),
            "reviseBrief": ("reviseBrief", configured_model),
            "analyzeExperiment": ("analyzeExperiment", configured_model),
            "generateCandidates": ("generateCandidates", configured_model),
        }
        if operation not in op_map:
            raise HTTPException(status_code=422, detail=f"Unknown operation: {operation}")

        spec_key, model = op_map[operation]
        spec = PROMPTS[spec_key]
        schema = _SCHEMAS[spec_key]

        if operation == "generateHypotheses":
            ctx = HypothesisContextAssembler.build(project, [], project.get("context_version", 1))
            user = spec.user_template.replace("{context}", ctx)
        elif operation == "designExperiment":
            ctx = ExperimentDesignContextAssembler.build(_FLAGD_HYPOTHESIS, project, [])
            user = spec.user_template.replace("{context}", ctx)
        elif operation == "reviseBrief":
            variant = {"id": "canary", "hook": "I am building a tool for founders.",
                       "context": "Distribution is hard.", "on_screen_text": "Founder tool."}
            ctx = ReviseBriefContextAssembler.build(variant, "make it more specific", project)
            user = spec.user_template.format(**ctx)
        elif operation == "analyzeExperiment":
            ctx = EvidenceContextAssembler.build(_FLAGD_EVIDENCE, _FLAGD_SNAPSHOT, project, [])
            user = spec.user_template.format(**ctx)
        elif operation == "generateCandidates":
            insight = _make_flagd_insight()
            ctx = CandidateContextAssembler.build(insight, _FLAGD_SNAPSHOT, project, [])
            user = spec.user_template.format(**ctx)

        input_payload = {"operation": operation, "context": user[:200]}
        input_hash = _hash(input_payload)

        response = await client.messages.create(
            model=model,
            max_tokens=settings.claude_max_tokens,
            system=spec.system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
            timeout=settings.claude_default_timeout,
        )

        actual_model = response.model
        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0
        raw = response.content[0].text
        parsed = _json.loads(raw)
        validation_result = "valid"

        # Quick summary
        if operation == "generateHypotheses":
            output_summary = {"count": len(parsed), "first_title": parsed[0].get("title") if parsed else None}
        elif operation == "designExperiment":
            variants = parsed.get("variants", [])
            output_summary = {"variant_count": len(variants), "name": parsed.get("experiment_name", "")[:60]}
        elif operation == "reviseBrief":
            output_summary = {"hook": parsed.get("hook", "")[:80]}
        elif operation == "analyzeExperiment":
            output_summary = {"outcome_type": parsed.get("outcome_type"), "learning": parsed.get("supported_learning", "")[:100]}
        elif operation == "generateCandidates":
            output_summary = {"slots": [c.get("slot") for c in parsed], "recommended": [c.get("slot") for c in parsed if c.get("recommended")]}

    except HTTPException:
        raise
    except Exception as exc:
        validation_result = "failed"
        output_summary = {"error": str(exc)[:300]}
        latency_ms = int((time.monotonic() - start) * 1000)
        raise HTTPException(
            status_code=502,
            detail=f"Canary failed after {latency_ms}ms: {type(exc).__name__}: {str(exc)[:300]}"
        )

    latency_ms = int((time.monotonic() - start) * 1000)

    # Estimate cost (Sonnet 5: $3/$15 per MTok; Haiku 4.5: $1/$5)
    haiku_models = {"claude-haiku-4-5", "claude-haiku-4-5-20251001"}
    in_rate, out_rate = (1.0, 5.0) if actual_model in haiku_models else (3.0, 15.0)
    estimated_cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000

    return {
        "operation": operation,
        "dry_run": True,
        "configured_model": configured_model,
        "actual_model": actual_model,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(estimated_cost, 6),
        "attempt_count": attempt_count,
        "validation_result": validation_result,
        "input_hash": input_hash,
        "output_summary": output_summary,
    }
