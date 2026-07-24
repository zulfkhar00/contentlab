"""
Fixed evaluation suite — tests each operation against multiple fixture cases.
Covers: canonical Flagd, mixed result, insufficient evidence, execution deviation,
unsupported fact, zero-view, and duplicate cases.
"""
from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class EvalCase:
    name: str
    operation: str
    inputs: dict
    expected: dict          # subset of keys to check (use None to skip check)
    validators: list[Callable] = field(default_factory=list)


@dataclass
class EvalResult:
    case: str
    operation: str
    passed: bool
    error: str | None = None
    latency_ms: int = 0
    output_preview: str = ""


# ── Shared fixtures ───────────────────────────────────────────────────────────

_FLAGD_PROJECT = {
    "product_name": "Content Lab", "product_type": "SaaS",
    "product_description": "An experimentation lab for TikTok hypothesis testing.",
    "product_url": "https://contentlab.app",
    "target_audience": "Technical founders struggling with distribution",
    "problem_solved": "Founders do not know which message drives product clicks",
    "why_it_matters": "Wasted ad spend and guesswork instead of evidence",
    "current_alternatives": "Guessing, spreadsheets, UGC agencies",
    "desired_action": "Drive product clicks",
    "primary_cta": "Check the link in bio",
    "tiktok_handle": "founder_lab",
    "context_version": 1,
}

_FLAGD_HYPOTHESIS = {
    "id": "h-flagd",
    "title": "Pain hooks outperform product demos",
    "statement": "Founder pain stories will drive more product clicks than direct product feature demos.",
    "research_question": "Which opening framing generates more product clicks?",
    "independent_variable": "Opening framing",
    "control_condition": "Direct product feature demo opening",
    "treatment_condition": "Founder pain-story opening",
    "primary_metric": "clicks_per_1k_views",
    "controlled_elements": ["Audience", "Duration", "CTA", "Format"],
    "contradiction_condition": "Pain-story does not outperform demo after 72h.",
    "updated_at": "2026-07-24T00:00:00Z",
}

_FLAGD_EVIDENCE = {
    "items": [
        {"position": "A", "treatment_role": "control", "title": "Product Demo",
         "views_delta": 8204, "likes_delta": 412, "comments_delta": 38,
         "attributed_unique_clicks": 24, "unique_clicks_per_1k": 2.9,
         "delivered_variable": None},
        {"position": "B", "treatment_role": "hypothesis_treatment", "title": "Founder Failure Story",
         "views_delta": 4500, "likes_delta": 267, "comments_delta": 52,
         "attributed_unique_clicks": 53, "unique_clicks_per_1k": 11.7,
         "delivered_variable": True},
        {"position": "C", "treatment_role": "alternative_treatment", "title": "Contrarian Insight",
         "views_delta": 6000, "likes_delta": 180, "comments_delta": 24,
         "attributed_unique_clicks": 36, "unique_clicks_per_1k": 6.0,
         "delivered_variable": True},
    ]
}

_FLAGD_SNAPSHOT = {
    "schemaVersion": 1,
    "statement": _FLAGD_HYPOTHESIS["statement"],
    "researchQuestion": _FLAGD_HYPOTHESIS["research_question"],
    "independentVariable": _FLAGD_HYPOTHESIS["independent_variable"],
    "primaryMetric": "clicks_per_1k_views",
    "controlledElements": _FLAGD_HYPOTHESIS["controlled_elements"],
    "contradictionCondition": _FLAGD_HYPOTHESIS["contradiction_condition"],
}

_MIXED_EVIDENCE = {
    "items": [
        {"position": "A", "treatment_role": "control", "title": "Product Demo",
         "views_delta": 5000, "likes_delta": 200, "comments_delta": 20,
         "attributed_unique_clicks": 30, "unique_clicks_per_1k": 6.0,
         "delivered_variable": None},
        {"position": "B", "treatment_role": "hypothesis_treatment", "title": "Pain Hook",
         "views_delta": 5200, "likes_delta": 210, "comments_delta": 25,
         "attributed_unique_clicks": 31, "unique_clicks_per_1k": 5.9,
         "delivered_variable": True},
        {"position": "C", "treatment_role": "alternative_treatment", "title": "Contrarian",
         "views_delta": 4800, "likes_delta": 180, "comments_delta": 15,
         "attributed_unique_clicks": 29, "unique_clicks_per_1k": 6.0,
         "delivered_variable": True},
    ]
}

_INSUFFICIENT_EVIDENCE = {
    "items": [
        {"position": "A", "treatment_role": "control", "title": "Control",
         "views_delta": 95, "likes_delta": 3, "comments_delta": 1,
         "attributed_unique_clicks": 2, "unique_clicks_per_1k": 21.0,
         "delivered_variable": None},
        {"position": "B", "treatment_role": "hypothesis_treatment", "title": "Treatment",
         "views_delta": 80, "likes_delta": 2, "comments_delta": 0,
         "attributed_unique_clicks": 1, "unique_clicks_per_1k": 12.5,
         "delivered_variable": True},
        {"position": "C", "treatment_role": "alternative_treatment", "title": "Alternative",
         "views_delta": 110, "likes_delta": 4, "comments_delta": 1,
         "attributed_unique_clicks": 3, "unique_clicks_per_1k": 27.3,
         "delivered_variable": True},
    ]
}

_EXECUTION_DEVIATION = {
    "items": [
        {"position": "A", "treatment_role": "control", "title": "Control",
         "views_delta": 8000, "likes_delta": 400, "comments_delta": 35,
         "attributed_unique_clicks": 22, "unique_clicks_per_1k": 2.75, "delivered_variable": None},
        {"position": "B", "treatment_role": "hypothesis_treatment", "title": "Treatment (deviated)",
         "views_delta": 7500, "likes_delta": 380, "comments_delta": 40,
         "attributed_unique_clicks": 85, "unique_clicks_per_1k": 11.3,
         "delivered_variable": False},  # DEVIATION
        {"position": "C", "treatment_role": "alternative_treatment", "title": "Alternative",
         "views_delta": 6200, "likes_delta": 190, "comments_delta": 22,
         "attributed_unique_clicks": 38, "unique_clicks_per_1k": 6.1, "delivered_variable": True},
    ]
}

_ZERO_VIEWS = {
    "items": [
        {"position": "A", "treatment_role": "control", "title": "Control",
         "views_delta": 0, "likes_delta": 0, "comments_delta": 0,
         "attributed_unique_clicks": 0, "unique_clicks_per_1k": None, "delivered_variable": None},
        {"position": "B", "treatment_role": "hypothesis_treatment", "title": "Treatment",
         "views_delta": 100, "likes_delta": 5, "comments_delta": 2,
         "attributed_unique_clicks": 4, "unique_clicks_per_1k": 40.0, "delivered_variable": True},
        {"position": "C", "treatment_role": "alternative_treatment", "title": "Alternative",
         "views_delta": 50, "likes_delta": 2, "comments_delta": 1,
         "attributed_unique_clicks": 1, "unique_clicks_per_1k": 20.0, "delivered_variable": True},
    ]
}


def _make_flagd_insight() -> dict:
    return {
        "outcome_type": "directional_difference",
        "supported_learning": "The founder failure story produced noticeably higher click efficiency.",
        "do_not_infer_yet": ["Whether the effect holds with different hook wording"],
        "recommended_next_test": "Isolate the mechanism — test specificity of pain.",
        "outcome_description": "Directional difference observed.",
        "research_question": _FLAGD_HYPOTHESIS["research_question"],
        "evidence_items": _FLAGD_EVIDENCE["items"],
    }


# ── Evaluation cases ──────────────────────────────────────────────────────────

EVAL_CASES: list[EvalCase] = [
    # generateHypotheses
    EvalCase(
        name="gen_hyp_standard_product",
        operation="generateHypotheses",
        inputs={"project": _FLAGD_PROJECT, "facts": [], "context_version": 1},
        expected={"count": 5, "all_have_metric": True},
    ),
    EvalCase(
        name="gen_hyp_minimal_project",
        operation="generateHypotheses",
        inputs={"project": {**_FLAGD_PROJECT, "problem_solved": "", "target_audience": "founders"},
                "facts": [], "context_version": 1},
        expected={"count": 5},
    ),

    # designExperiment
    EvalCase(
        name="design_exp_flagd",
        operation="designExperiment",
        inputs={"hypothesis": _FLAGD_HYPOTHESIS, "project": _FLAGD_PROJECT, "facts": []},
        expected={"variant_count": 3, "has_script_sections": True},
    ),
    EvalCase(
        name="design_exp_comments_metric",
        operation="designExperiment",
        inputs={"hypothesis": {**_FLAGD_HYPOTHESIS, "primary_metric": "comments_per_1k_views",
                               "title": "Founder journey creates more trust"},
                "project": _FLAGD_PROJECT, "facts": []},
        expected={"variant_count": 3},
    ),

    # reviseBrief
    EvalCase(
        name="revise_brief_punchier",
        operation="reviseBrief",
        inputs={"variant": {**{k: _FLAGD_HYPOTHESIS.get(k, "") for k in ("title",)},
                            "hook": "I spent almost $2,000 on ads and got almost no users.",
                            "context": "The app worked. The marketing did not."},
                "instruction": "make it punchier", "project": _FLAGD_PROJECT, "facts": []},
        expected={"has_hook": True},
    ),
    EvalCase(
        name="revise_brief_shorten",
        operation="reviseBrief",
        inputs={"variant": {"hook": "I built a product that I thought would go viral but nobody discovered it despite months of work.",
                            "context": "Distribution is the hard part."},
                "instruction": "shorten to under 10 words", "project": _FLAGD_PROJECT, "facts": []},
        expected={"has_hook": True},
    ),

    # analyzeExperiment — canonical Flagd
    EvalCase(
        name="analyze_flagd_directional",
        operation="analyzeExperiment",
        inputs={"evidence": _FLAGD_EVIDENCE, "hypothesis_snapshot": _FLAGD_SNAPSHOT,
                "project": _FLAGD_PROJECT, "facts": []},
        expected={"outcome_type": "directional_difference"},
    ),
    # mixed result
    EvalCase(
        name="analyze_mixed_result",
        operation="analyzeExperiment",
        inputs={"evidence": _MIXED_EVIDENCE, "hypothesis_snapshot": _FLAGD_SNAPSHOT,
                "project": _FLAGD_PROJECT, "facts": []},
        expected={"outcome_type_in": ["mixed_result", "little_difference"]},
    ),
    # insufficient evidence
    EvalCase(
        name="analyze_insufficient_views",
        operation="analyzeExperiment",
        inputs={"evidence": _INSUFFICIENT_EVIDENCE, "hypothesis_snapshot": _FLAGD_SNAPSHOT,
                "project": _FLAGD_PROJECT, "facts": []},
        expected={"outcome_type": "insufficient_evidence"},
    ),
    # execution deviation
    EvalCase(
        name="analyze_execution_deviation",
        operation="analyzeExperiment",
        inputs={"evidence": _EXECUTION_DEVIATION, "hypothesis_snapshot": _FLAGD_SNAPSHOT,
                "project": _FLAGD_PROJECT, "facts": []},
        expected={"outcome_type_in": ["execution_problem", "directional_difference", "mixed_result"]},
    ),
    # zero views
    EvalCase(
        name="analyze_zero_views_variant",
        operation="analyzeExperiment",
        inputs={"evidence": _ZERO_VIEWS, "hypothesis_snapshot": _FLAGD_SNAPSHOT,
                "project": _FLAGD_PROJECT, "facts": []},
        # Zero views on A = either no data collected OR execution failure — both valid
        expected={"outcome_type_in": ["insufficient_evidence", "execution_problem"]},
    ),

    # generateCandidates
    EvalCase(
        name="candidates_from_directional",
        operation="generateCandidates",
        inputs={"insight": _make_flagd_insight(), "hypothesis_snapshot": _FLAGD_SNAPSHOT,
                "project": _FLAGD_PROJECT, "facts": []},
        expected={"count": 3, "exactly_one_recommended": True},
    ),
    EvalCase(
        name="candidates_from_mixed",
        operation="generateCandidates",
        inputs={"insight": {**_make_flagd_insight(), "outcome_type": "mixed_result"},
                "hypothesis_snapshot": _FLAGD_SNAPSHOT, "project": _FLAGD_PROJECT, "facts": []},
        expected={"count": 3, "exactly_one_recommended": True},
    ),
    EvalCase(
        name="candidates_from_insufficient",
        operation="generateCandidates",
        inputs={"insight": {**_make_flagd_insight(), "outcome_type": "insufficient_evidence"},
                "hypothesis_snapshot": _FLAGD_SNAPSHOT, "project": _FLAGD_PROJECT, "facts": []},
        expected={"count": 3, "exactly_one_recommended": True},
    ),
]


def _check_result(result: Any, expected: dict) -> None:
    if "count" in expected:
        assert len(result) == expected["count"], f"Expected {expected['count']} items, got {len(result)}"
    if "all_have_metric" in expected and expected["all_have_metric"]:
        for h in result:
            assert h.get("primary_metric"), "Hypothesis missing primary_metric"
    if "variant_count" in expected:
        assert len(result.get("variants", [])) == expected["variant_count"]
    if "has_script_sections" in expected:
        for v in result.get("variants", []):
            assert "script_sections" in v and "sections" in v["script_sections"]
    if "has_hook" in expected:
        assert result.get("hook"), "Revision missing hook"
    if "outcome_type" in expected:
        assert result.get("outcome_type") == expected["outcome_type"], \
            f"Expected {expected['outcome_type']}, got {result.get('outcome_type')}"
    if "outcome_type_in" in expected:
        assert result.get("outcome_type") in expected["outcome_type_in"], \
            f"Expected one of {expected['outcome_type_in']}, got {result.get('outcome_type')}"
    if "exactly_one_recommended" in expected:
        rec = [c for c in result if c.get("recommended")]
        assert len(rec) == 1, f"Expected 1 recommended, got {len(rec)}"


async def run_eval(provider, case_names: list[str] | None = None) -> list[EvalResult]:
    """
    Run evaluation cases against the given provider.
    If case_names is provided, only run those cases.
    """
    results = []
    for case in EVAL_CASES:
        if case_names and case.name not in case_names:
            continue
        start = time.monotonic()
        try:
            op = case.operation
            inputs = case.inputs
            if op == "generateHypotheses":
                result, _, _ = await provider.generate_initial_hypotheses(**inputs)
            elif op == "designExperiment":
                result, _, _ = await provider.design_experiment(**inputs)
            elif op == "reviseBrief":
                result, _, _ = await provider.revise_variant_brief(**inputs)
            elif op == "analyzeExperiment":
                result, _, _ = await provider.analyze_experiment(**inputs)
            elif op == "generateCandidates":
                result, _, _ = await provider.generate_follow_up_candidates(**inputs)
            else:
                raise ValueError(f"Unknown operation: {op}")

            _check_result(result, case.expected)
            latency = int((time.monotonic() - start) * 1000)
            results.append(EvalResult(
                case=case.name, operation=op, passed=True,
                latency_ms=latency,
                output_preview=json.dumps(result)[:120],
            ))
        except Exception as exc:
            latency = int((time.monotonic() - start) * 1000)
            results.append(EvalResult(
                case=case.name, operation=case.operation, passed=False,
                error=str(exc)[:300], latency_ms=latency,
            ))
    return results
