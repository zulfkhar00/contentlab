"""Sprint 6 unit tests: validators + evaluation suite (fake provider)."""
import sys, os, asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.intelligence.validators import (
    ValidationError,
    validate_candidates,
    validate_experiment_design,
    validate_hypotheses,
    validate_insight,
    validate_no_invented_facts,
    validate_revision,
)
from app.intelligence.evaluation.suite import EVAL_CASES, run_eval


# ── Validator unit tests ──────────────────────────────────────────────────────

def test_validate_hypotheses_valid():
    hyps = [{
        "title": "T", "statement": "S", "category": "C",
        "primary_metric": "clicks_per_1k_views", "rationale": "R",
        "research_question": "Q", "independent_variable": "IV",
        "control_condition": "Ctrl", "treatment_condition": "Treat",
        "controlled_elements": ["A", "B"], "contradiction_condition": "X",
    }]
    validate_hypotheses(hyps)  # no exception


def test_validate_hypotheses_invalid_metric():
    with pytest.raises(ValidationError, match="primary_metric"):
        validate_hypotheses([{
            "title": "T", "statement": "S", "category": "C",
            "primary_metric": "engagement_rate",
            "rationale": "R", "research_question": "Q",
            "independent_variable": "IV", "control_condition": "C",
            "treatment_condition": "T", "controlled_elements": [],
            "contradiction_condition": "X",
        }])


def test_validate_hypotheses_empty_list():
    with pytest.raises(ValidationError):
        validate_hypotheses([])


def test_validate_insight_valid():
    insight = {
        "outcome_type": "directional_difference",
        "outcome_description": "Treatment won.",
        "supported_learning": "B outperformed A.",
        "do_not_infer_yet": ["not proven at scale"],
        "recommended_next_test": "Replicate with different hook.",
        "limitations": ["small sample"],
        "evidence_basis": {"schemaVersion": 1, "trackingWindowsCompleted": 3,
                           "requiredTrackingWindows": 3, "attributionMethod": "isolated_window",
                           "executionDeviations": [], "allVideosValidated": True},
    }
    validate_insight(insight)


def test_validate_insight_invalid_outcome():
    with pytest.raises(ValidationError, match="outcome_type"):
        validate_insight({"outcome_type": "unclear", "outcome_description": "x",
                          "supported_learning": "x", "do_not_infer_yet": [],
                          "recommended_next_test": "x", "limitations": [],
                          "evidence_basis": {"schemaVersion": 1}})


def test_validate_candidates_valid():
    cands = [
        {"slot": "safest_next_step", "relationship_type": "replication",
         "statement": "S", "why_this_follows": "W", "recommended": False,
         "recommendation_reason": "", "previous_learning": "P", "remaining_unknown": "R"},
        {"slot": "highest_learning", "relationship_type": "mechanism_isolation",
         "statement": "S2", "why_this_follows": "W2", "recommended": True,
         "recommendation_reason": "Best learning.", "previous_learning": "P2", "remaining_unknown": "R2"},
        {"slot": "highest_upside", "relationship_type": "parameter_optimization",
         "statement": "S3", "why_this_follows": "W3", "recommended": False,
         "recommendation_reason": "", "previous_learning": "P3", "remaining_unknown": "R3"},
    ]
    validate_candidates(cands)


def test_validate_candidates_wrong_slot_count():
    with pytest.raises(ValidationError):
        validate_candidates([
            {"slot": "safest_next_step", "relationship_type": "replication",
             "statement": "S", "why_this_follows": "W", "recommended": True,
             "recommendation_reason": "x", "previous_learning": "P", "remaining_unknown": "R"},
        ])


def test_validate_candidates_two_recommended():
    with pytest.raises(ValidationError, match="recommended"):
        validate_candidates([
            {"slot": "safest_next_step", "relationship_type": "replication",
             "statement": "S", "why_this_follows": "W", "recommended": True,
             "recommendation_reason": "x", "previous_learning": "P", "remaining_unknown": "R"},
            {"slot": "highest_learning", "relationship_type": "mechanism_isolation",
             "statement": "S2", "why_this_follows": "W2", "recommended": True,
             "recommendation_reason": "y", "previous_learning": "P2", "remaining_unknown": "R2"},
            {"slot": "highest_upside", "relationship_type": "parameter_optimization",
             "statement": "S3", "why_this_follows": "W3", "recommended": False,
             "recommendation_reason": "", "previous_learning": "P3", "remaining_unknown": "R3"},
        ])


def test_validate_no_invented_facts_clean():
    validate_no_invented_facts("The variant outperformed by 20%.", [])


def test_validate_no_invented_facts_invented_money():
    with pytest.raises(ValidationError, match="invented monetary"):
        validate_no_invented_facts("I spent $5,000 on ads.", ["I spent $2,000 on UGC ads."])


# ── Evaluation suite (fake provider) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_eval_suite_fake_all_pass():
    from app.intelligence.fake import FakeIntelligenceProvider
    provider = FakeIntelligenceProvider()
    results = await run_eval(provider)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Eval failures:\n" + "\n".join(f"  {r.case}: {r.error}" for r in failures)


@pytest.mark.asyncio
async def test_eval_suite_case_count():
    assert len(EVAL_CASES) >= 14, f"Expected at least 14 eval cases, got {len(EVAL_CASES)}"
