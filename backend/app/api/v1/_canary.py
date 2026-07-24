"""
Dev-only canary endpoint for Sprint 6B live validation.
POST /api/dev/intelligence/canary?operation=generateHypotheses
Runs one real call and returns tokens, latency, model, validation result.
Requires INTELLIGENCE_PROVIDER=claude and a valid ANTHROPIC_API_KEY.
"""
from uuid import UUID
from fastapi import HTTPException


async def run_canary(operation: str, scope, db) -> dict:
    from app.intelligence.factory import get_intelligence_provider
    from app.repositories.project_repo import ProjectRepository
    from app.intelligence.evaluation.suite import (
        _FLAGD_PROJECT, _FLAGD_HYPOTHESIS, _FLAGD_EVIDENCE, _FLAGD_SNAPSHOT,
        _make_flagd_insight, EVAL_CASES,
    )
    from app.config import settings
    import time

    if settings.intelligence_provider == "fake":
        raise HTTPException(
            status_code=422,
            detail="INTELLIGENCE_PROVIDER=fake; set to 'claude' with a real API key to run canary."
        )

    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_scope(scope) or _FLAGD_PROJECT

    provider = get_intelligence_provider()

    start = time.monotonic()
    try:
        if operation == "generateHypotheses":
            result, payload, h = await provider.generate_initial_hypotheses(
                project=project, facts=[], context_version=project.get("context_version", 1)
            )
            summary = {"count": len(result), "first_title": result[0].get("title") if result else None}

        elif operation == "designExperiment":
            result, payload, h = await provider.design_experiment(
                hypothesis=_FLAGD_HYPOTHESIS, project=project, facts=[]
            )
            variants = result.get("variants", [])
            summary = {"variant_count": len(variants), "experiment_name": result.get("experiment_name")}

        elif operation == "reviseBrief":
            variant = {
                "id": "canary-variant", "hook": "I am building a tool for founders.",
                "context": "Distribution is the hard part.",
                "on_screen_text": "Founder tool.", "updated_at": "2026-07-24T00:00:00Z",
            }
            result, payload, h = await provider.revise_variant_brief(
                variant=variant, instruction="make it more specific",
                project=project, facts=[]
            )
            summary = {"hook_length": len(result.get("hook", "")), "hook": result.get("hook", "")[:80]}

        elif operation == "analyzeExperiment":
            result, payload, h = await provider.analyze_experiment(
                evidence=_FLAGD_EVIDENCE, hypothesis_snapshot=_FLAGD_SNAPSHOT,
                project=project, facts=[]
            )
            summary = {"outcome_type": result.get("outcome_type"), "supported_learning": result.get("supported_learning", "")[:100]}

        elif operation == "generateCandidates":
            insight = _make_flagd_insight()
            result, payload, h = await provider.generate_follow_up_candidates(
                insight=insight, hypothesis_snapshot=_FLAGD_SNAPSHOT,
                project=project, facts=[]
            )
            summary = {"count": len(result), "slots": [c.get("slot") for c in result]}

        else:
            raise HTTPException(status_code=422, detail=f"Unknown operation: {operation}")

        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "operation": operation,
            "status": "success",
            "latency_ms": latency_ms,
            "input_hash": h,
            "summary": summary,
            "note": "Tokens and cost are not tracked in canary mode (no ai_run persisted).",
        }

    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        raise HTTPException(
            status_code=502,
            detail=f"Canary failed after {latency_ms}ms: {type(exc).__name__}: {str(exc)[:300]}"
        )
