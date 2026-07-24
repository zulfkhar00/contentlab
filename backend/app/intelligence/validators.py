"""
Layered validation pipeline for intelligence output.
Layers: schema → domain → evidence → founder-fact → stale-input.
Each layer raises ValidationError with a repair hint.
"""
from app.domain.errors import DomainError


class ValidationError(DomainError):
    def __init__(self, message: str, repair_hint: str = ""):
        super().__init__(message)
        self.repair_hint = repair_hint


_VALID_METRICS = frozenset({
    "clicks_per_1k_views", "comments_per_1k_views",
    "views", "product_clicks", "comments",
})
_VALID_OUTCOMES = frozenset({
    "directional_difference", "mixed_result", "little_difference",
    "all_variants_weak", "all_variants_strong",
    "insufficient_evidence", "execution_problem",
})
_VALID_SLOTS = frozenset({"safest_next_step", "highest_learning", "highest_upside"})
_VALID_RELATIONSHIPS = frozenset({
    "replication", "mechanism_isolation", "parameter_optimization",
    "generalization", "counter_hypothesis", "recovery_redesign",
})
_VALID_POSITIONS = frozenset({"A", "B", "C"})
_VALID_ROLES = frozenset({"control", "hypothesis_treatment", "alternative_treatment"})


def validate_hypotheses(hypotheses: list[dict]) -> None:
    """Schema + domain validation for generateHypotheses output."""
    if not isinstance(hypotheses, list) or len(hypotheses) == 0:
        raise ValidationError("Output must be a non-empty JSON array", "Return a JSON array of hypothesis objects.")
    required = {"title", "statement", "primary_metric", "rationale",
                "research_question", "independent_variable",
                "control_condition", "treatment_condition",
                "controlled_elements", "contradiction_condition"}
    for i, h in enumerate(hypotheses):
        missing = required - set(h.keys())
        if missing:
            raise ValidationError(
                f"Hypothesis {i} missing keys: {missing}",
                f"Include all required keys: {sorted(required)}"
            )
        if h.get("primary_metric") not in _VALID_METRICS:
            raise ValidationError(
                f"Hypothesis {i} invalid primary_metric: {h.get('primary_metric')}",
                f"primary_metric must be one of: {sorted(_VALID_METRICS)}"
            )
        if not isinstance(h.get("controlled_elements"), list):
            raise ValidationError(
                f"Hypothesis {i} controlled_elements must be an array",
                "controlled_elements must be a JSON array of strings"
            )


def validate_experiment_design(design: dict) -> None:
    """Schema + domain validation for designExperiment output."""
    if not isinstance(design, dict):
        raise ValidationError("Output must be a JSON object", "Return a single JSON object.")
    if "variants" not in design:
        raise ValidationError("Missing 'variants' key", "Include a 'variants' array with 3 objects.")
    variants = design["variants"]
    if not isinstance(variants, list) or len(variants) != 3:
        raise ValidationError("Must have exactly 3 variants", "Return exactly 3 variant objects in the array.")
    positions = {v.get("position") for v in variants}
    if positions != _VALID_POSITIONS:
        raise ValidationError(f"Variant positions must be A, B, C; got {positions}", "Return variants with positions A, B, C.")
    roles = {v.get("treatment_role") for v in variants}
    if not roles.issubset(_VALID_ROLES):
        raise ValidationError(f"Invalid treatment_roles: {roles - _VALID_ROLES}", f"treatment_role must be one of: {sorted(_VALID_ROLES)}")
    for v in variants:
        ss = v.get("script_sections", {})
        if not isinstance(ss, dict) or "sections" not in ss:
            raise ValidationError("script_sections must be an object with 'sections' array", "Fix script_sections format.")
        if len(ss.get("sections", [])) != 5:
            raise ValidationError("script_sections.sections must have exactly 5 items", "Include hook, context, lesson, product, cta sections.")


def validate_revision(revision: dict) -> None:
    """Schema validation for reviseBrief output."""
    if not isinstance(revision, dict):
        raise ValidationError("Output must be a JSON object", "Return a JSON object.")
    required = {"hook", "hook_delivery_note", "context", "on_screen_text"}
    missing = required - set(revision.keys())
    if missing:
        raise ValidationError(f"Missing keys: {missing}", f"Include all keys: {sorted(required)}")
    if not revision.get("hook"):
        raise ValidationError("hook must not be empty", "Provide a non-empty hook.")


def validate_insight(insight: dict) -> None:
    """Schema + domain + evidence validation for analyzeExperiment output."""
    if not isinstance(insight, dict):
        raise ValidationError("Output must be a JSON object", "Return a JSON object.")
    if insight.get("outcome_type") not in _VALID_OUTCOMES:
        raise ValidationError(
            f"Invalid outcome_type: {insight.get('outcome_type')}",
            f"outcome_type must be one of: {sorted(_VALID_OUTCOMES)}"
        )
    for key in ("supported_learning", "recommended_next_test", "outcome_description"):
        if not insight.get(key):
            raise ValidationError(f"'{key}' must not be empty", f"Provide a non-empty {key}.")
    for key in ("do_not_infer_yet", "limitations"):
        if not isinstance(insight.get(key), list):
            raise ValidationError(f"'{key}' must be an array", f"Return {key} as a JSON array.")
    eb = insight.get("evidence_basis", {})
    if not isinstance(eb, dict) or eb.get("schemaVersion") != 1:
        raise ValidationError("evidence_basis must have schemaVersion:1", "Fix evidence_basis object.")


def validate_candidates(candidates: list[dict]) -> None:
    """Schema + domain validation for generateCandidates output."""
    if not isinstance(candidates, list) or len(candidates) != 3:
        raise ValidationError("Must return exactly 3 candidates", "Return a JSON array of exactly 3 candidate objects.")
    slots = {c.get("slot") for c in candidates}
    if slots != _VALID_SLOTS:
        raise ValidationError(f"Slots must be {_VALID_SLOTS}; got {slots}", f"Return one candidate per slot: {sorted(_VALID_SLOTS)}")
    recommended = [c for c in candidates if c.get("recommended")]
    if len(recommended) != 1:
        raise ValidationError(
            f"Exactly one candidate must have recommended=true; got {len(recommended)}",
            "Set recommended=true on exactly one candidate."
        )
    for c in candidates:
        if c.get("relationship_type") not in _VALID_RELATIONSHIPS:
            raise ValidationError(
                f"Invalid relationship_type: {c.get('relationship_type')}",
                f"relationship_type must be one of: {sorted(_VALID_RELATIONSHIPS)}"
            )
        for key in ("statement", "why_this_follows", "previous_learning", "remaining_unknown"):
            if not c.get(key):
                raise ValidationError(f"Candidate '{c.get('slot')}' missing '{key}'", f"Provide non-empty {key}.")


def validate_no_invented_facts(output_text: str, verified_facts: list[str]) -> None:
    """
    Check that Claude has not invented specific numerical facts (spend, user counts, etc.)
    that are not in the verified facts list. Heuristic only — not exhaustive.
    """
    import re
    # Patterns that might be invented claims: "$X,XXX", "X% of", "X customers"
    money_pattern = re.compile(r'\$[\d,]+')
    percent_pattern = re.compile(r'\d+%')
    verified_text = " ".join(verified_facts).lower()
    for match in money_pattern.finditer(output_text):
        claim = match.group()
        if claim.replace('$', '').replace(',', '') not in verified_text.replace('$', '').replace(',', ''):
            raise ValidationError(
                f"Output contains invented monetary claim: {claim}",
                f"Only use financial figures from verified facts: {verified_facts}"
            )
