"""
Deterministic fixtures for FakeIntelligenceProvider.
Sprint 4 additions: analyze_experiment + generate_follow_up_candidates.
"""

# ── Hypothesis fixtures ─────────────────────────────────────────────────────
FIXTURE_HYPOTHESES = [
    {
        "title": "Pain hooks outperform product demos",
        "statement": "Founder pain stories will drive more product clicks than direct product feature demos.",
        "category": "Pain / Founder Story",
        "primary_metric": "clicks_per_1k_views",
        "rationale": "Pain-first content creates relevance before introducing the product.",
        "research_question": "Which opening framing generates more product clicks?",
        "independent_variable": "Opening framing",
        "control_condition": "Direct product feature demo opening",
        "treatment_condition": "Founder pain-story opening",
        "controlled_elements": ["Audience", "Founder-led talking head", "Duration", "Product explanation", "Offer", "CTA"],
        "contradiction_condition": "The pain-story treatment does not outperform the product-demo control after all tracking windows complete.",
    },
    {
        "title": "Founder failure stories drive more product clicks",
        "statement": "Founder failure stories drive more product clicks than generic product demos.",
        "category": "Founder Story",
        "primary_metric": "clicks_per_1k_views",
        "rationale": "Concrete failure stories build more trust than generic pitches.",
        "research_question": "Which opening style generates more product clicks?",
        "independent_variable": "Opening angle",
        "control_condition": "Product-demo opening",
        "treatment_condition": "Concrete founder-failure opening",
        "controlled_elements": ["Audience", "Founder-led talking head", "Duration", "Product explanation", "Offer", "CTA"],
        "contradiction_condition": "The founder-failure treatment does not outperform the product-demo control after all tracking windows complete.",
    },
    {
        "title": "Distribution problem beats AI automation angle",
        "statement": "Technical founders respond more to distribution pain than generic AI automation benefits.",
        "category": "Contrarian Insight",
        "primary_metric": "clicks_per_1k_views",
        "rationale": "Distribution failure is more emotionally relevant to technical founders than generic AI benefits.",
        "research_question": "Which pain framing resonates most with technical founders?",
        "independent_variable": "Pain framing",
        "control_condition": "Generic AI automation benefits framing",
        "treatment_condition": "Distribution-problem framing",
        "controlled_elements": ["Audience", "Founder-led talking head", "Duration", "Product explanation", "Offer", "CTA"],
        "contradiction_condition": "The distribution-problem framing does not outperform the AI automation framing after all tracking windows complete.",
    },
    {
        "title": "Founder journey creates more trust",
        "statement": "Founder journey videos will generate more product-related comments per 1,000 views than polished product pitches.",
        "category": "Founder Story",
        "primary_metric": "comments_per_1k_views",
        "rationale": "Personal narratives build community trust more effectively than polished pitches.",
        "research_question": "Which style of storytelling generates more product-related comments?",
        "independent_variable": "Storytelling style",
        "control_condition": "Polished product pitch",
        "treatment_condition": "Founder journey narrative",
        "controlled_elements": ["Audience", "Founder-led talking head", "Duration", "Product explanation", "Offer", "CTA"],
        "contradiction_condition": "The founder-journey treatment does not outperform the polished-pitch control on comments per 1K views after all tracking windows complete.",
    },
    {
        "title": "Short pain-first hooks outperform long-form storytelling",
        "statement": "Videos that open with a short, concrete pain hook will generate more clicks per 1,000 views than longer narrative openings.",
        "category": "Hook Strategy",
        "primary_metric": "clicks_per_1k_views",
        "rationale": "Shorter hooks reduce drop-off before the CTA is shown.",
        "research_question": "Does opening length affect click efficiency?",
        "independent_variable": "Opening length and structure",
        "control_condition": "Long-form narrative opening",
        "treatment_condition": "Short pain-first hook",
        "controlled_elements": ["Audience", "Founder-led talking head", "Duration", "Product explanation", "Offer", "CTA"],
        "contradiction_condition": "The short pain-first hook does not outperform the long-form opening after all tracking windows complete.",
    },
]


# ── Experiment design fixture ────────────────────────────────────────────────
def _fixture_experiment(hypothesis: dict, project: dict) -> dict:
    product_name = project.get("product_name", "the product")
    cta = project.get("primary_cta", "Check the link in bio")
    audience = project.get("target_audience", "Technical founders")
    independent_var = hypothesis.get("independent_variable", "Opening angle")
    control = hypothesis.get("control_condition", "Product demonstration opening")
    treatment = hypothesis.get("treatment_condition", "Founder failure-story opening")

    return {
        "experiment_name": f"{independent_var} test — {product_name}",
        "shared_constraints": {
            "schemaVersion": 1,
            "targetDurationLabel": "50s",
            "cta": cta,
            "audience": audience,
            "format": "Founder-led talking head",
        },
        "variants": [
            {
                "position": "A",
                "treatment_role": "control",
                "title": "Product Demo",
                "variable_value": control,
                "hook": "I am building a tool that turns one startup idea into three TikTok experiments.",
                "hook_delivery_note": "Neutral, confident tone. Show the product briefly on screen.",
                "context": "It sounds simple. Distribution is the hard part.",
                "on_screen_text": "One idea. Three TikTok tests.",
                "script_sections": {"schemaVersion": 1, "sections": [
                    {"key": "hook", "startSecond": 0, "endSecond": 5, "mode": "variable", "text": "I am building a tool that turns one startup idea into three TikTok experiments."},
                    {"key": "context", "startSecond": 5, "endSecond": 15, "mode": "variable", "text": "It sounds simple. Distribution is the hard part."},
                    {"key": "lesson", "startSecond": 15, "endSecond": 30, "mode": "controlled", "text": "I thought building the product was the hard part. Then I learned that a product nobody discovers is not really a startup."},
                    {"key": "product", "startSecond": 30, "endSecond": 42, "mode": "controlled", "text": f"That is why I am building {product_name}: to help founders test which messages actually drive product clicks."},
                    {"key": "cta", "startSecond": 42, "endSecond": 48, "mode": "controlled", "text": cta},
                ]},
                "recording_guidance": {"schemaVersion": 1, "camera": "Eye level, medium close-up", "delivery": "Neutral, confident tone", "background": "Use the same environment as other variants", "durationTarget": "45-50 seconds"},
            },
            {
                "position": "B",
                "treatment_role": "hypothesis_treatment",
                "title": "Founder Failure Story",
                "variable_value": treatment,
                "hook": "I spent almost $2,000 on UGC ads and got almost no users.",
                "hook_delivery_note": "Look disappointed but analytical. Quick cut at the end.",
                "context": "The app worked. The marketing did not.",
                "on_screen_text": "$2,000 on UGC. Almost no users.",
                "script_sections": {"schemaVersion": 1, "sections": [
                    {"key": "hook", "startSecond": 0, "endSecond": 5, "mode": "variable", "text": "I spent almost $2,000 on UGC ads and got almost no users."},
                    {"key": "context", "startSecond": 5, "endSecond": 15, "mode": "variable", "text": "The app worked. The marketing did not."},
                    {"key": "lesson", "startSecond": 15, "endSecond": 30, "mode": "controlled", "text": "I thought building the product was the hard part. Then I learned that a product nobody discovers is not really a startup."},
                    {"key": "product", "startSecond": 30, "endSecond": 42, "mode": "controlled", "text": f"That is why I am building {product_name}: to help founders test which messages actually drive product clicks."},
                    {"key": "cta", "startSecond": 42, "endSecond": 48, "mode": "controlled", "text": cta},
                ]},
                "recording_guidance": {"schemaVersion": 1, "camera": "Eye level, medium close-up", "delivery": "Look disappointed but analytical. Quick cut at the end.", "background": "Use the same environment as other variants", "durationTarget": "45-50 seconds"},
            },
            {
                "position": "C",
                "treatment_role": "alternative_treatment",
                "title": "Contrarian Insight",
                "variable_value": "Contrarian distribution-problem opening",
                "hook": "Most engineers do not have a product problem. They have a distribution problem.",
                "hook_delivery_note": "Deadpan, matter-of-fact delivery.",
                "context": "They can build anything. They just cannot get anyone to see it.",
                "on_screen_text": "Everyone has a distribution problem.",
                "script_sections": {"schemaVersion": 1, "sections": [
                    {"key": "hook", "startSecond": 0, "endSecond": 5, "mode": "variable", "text": "Most engineers do not have a product problem. They have a distribution problem."},
                    {"key": "context", "startSecond": 5, "endSecond": 15, "mode": "variable", "text": "They can build anything. They just cannot get anyone to see it."},
                    {"key": "lesson", "startSecond": 15, "endSecond": 30, "mode": "controlled", "text": "I thought building the product was the hard part. Then I learned that a product nobody discovers is not really a startup."},
                    {"key": "product", "startSecond": 30, "endSecond": 42, "mode": "controlled", "text": f"That is why I am building {product_name}: to help founders test which messages actually drive product clicks."},
                    {"key": "cta", "startSecond": 42, "endSecond": 48, "mode": "controlled", "text": cta},
                ]},
                "recording_guidance": {"schemaVersion": 1, "camera": "Eye level, medium close-up", "delivery": "Deadpan, matter-of-fact", "background": "Use the same environment as other variants", "durationTarget": "45-50 seconds"},
            },
        ],
    }


# ── Sprint 4: analyze_experiment fixture ─────────────────────────────────────

def _fixture_insight(evidence: dict, hypothesis_snapshot: dict) -> dict:
    """Deterministic insight interpretation adapted to evidence shape."""
    items = evidence.get("items", [])

    # Insufficient evidence: very low total views
    total_views = sum(i.get("views_delta", 0) for i in items)
    if total_views < 500:
        return {
            "outcome_type": "insufficient_evidence",
            "outcome_description": "Total view count is too low to draw conclusions.",
            "supported_learning": "Insufficient data was collected to support any learning.",
            "do_not_infer_yet": ["Cannot draw conclusions from fewer than 500 total views."],
            "recommended_next_test": "Re-run with larger tracking windows.",
            "limitations": ["Very low view counts across all variants."],
            "evidence_basis": {
                "schemaVersion": 1, "trackingWindowsCompleted": len(items),
                "requiredTrackingWindows": len(items), "attributionMethod": "isolated_window",
                "executionDeviations": [], "allVideosValidated": True,
            },
        }

    metrics = [float(i.get("unique_clicks_per_1k") or 0.0) for i in items]
    spread = max(metrics) - min(metrics)

    # Little difference: all variants within 2 clicks/1K of each other
    if spread < 2.0:
        return {
            "outcome_type": "little_difference",
            "outcome_description": "All variants performed similarly with no clear winner.",
            "supported_learning": "The independent variable did not produce a meaningful difference in this experiment.",
            "do_not_infer_yet": ["Cannot conclude the variable has no effect without a larger sample."],
            "recommended_next_test": "Test a more extreme version of the variable.",
            "limitations": ["Very small performance spread across variants."],
            "evidence_basis": {
                "schemaVersion": 1, "trackingWindowsCompleted": len(items),
                "requiredTrackingWindows": len(items), "attributionMethod": "isolated_window",
                "executionDeviations": [], "allVideosValidated": True,
            },
        }

    # Standard directional case
    deviations = [i for i in items if i.get("delivered_variable") is False]
    outcome = "execution_problem" if deviations else "directional_difference"
    winning = max(items, key=lambda x: float(x.get("unique_clicks_per_1k") or 0.0))
    control = next((x for x in items if x.get("treatment_role") == "control"), None)
    independent_var = hypothesis_snapshot.get("independentVariable", "Opening angle")
    winning_var = winning.get("title", "Hypothesis Treatment")
    control_metric = f'{float(control["unique_clicks_per_1k"]):.1f}' if control and control.get("unique_clicks_per_1k") else "—"
    winning_metric = f'{float(winning["unique_clicks_per_1k"]):.1f}' if winning.get("unique_clicks_per_1k") else "—"

    deviation_note = ""
    if deviations:
        deviation_note = f" Note: {len(deviations)} variant(s) did not deliver the variable as intended."

    return {
        "outcome_type": outcome,
        "outcome_description": (
            f"The {winning_var} produced a clear directional difference vs the control.{deviation_note} "
            "Replication or mechanism isolation is needed before treating this as a reusable rule."
        ),
        "supported_learning": (
            f"Opening with {independent_var.lower()} in the first few seconds generated "
            f"{winning_metric} unique clicks per 1K views — noticeably higher than the control "
            f"at {control_metric}. The result is directional and warrants a follow-up test."
        ),
        "do_not_infer_yet": [
            "This compares one specific execution — it does not establish an ideal value for the variable.",
            "Both videos ran on the same account; the result has not been validated on a different audience.",
        ],
        "recommended_next_test": (
            f"Test a second {independent_var.lower()} variant with a meaningfully different "
            "specific angle to see whether the effect holds beyond this particular execution."
        ),
        "limitations": [
            "Variants ran sequentially; audience composition may have shifted across the 9-day window.",
            "Only one execution of each treatment was tested — execution quality may have affected results.",
        ],
        "evidence_basis": {
            "schemaVersion": 1,
            "trackingWindowsCompleted": len(items),
            "requiredTrackingWindows": len(items),
            "attributionMethod": "isolated_window",
            "executionDeviations": [i.get("position") for i in deviations],
            "allVideosValidated": True,
        },
    }


def _fixture_candidates(evidence: dict, hypothesis_snapshot: dict) -> list[dict]:
    """Exactly 3 candidates — one per slot, exactly one recommended."""
    independent_var = hypothesis_snapshot.get("independentVariable", "Opening angle")
    winning = max(evidence["items"], key=lambda x: x["unique_clicks_per_1k"])
    winning_title = winning.get("title", "the winning variant")

    return [
        {
            "slot": "safest_next_step",
            "relationship_type": "replication",
            "recommended": False,
            "statement": (
                f"A different execution of the same {independent_var.lower()} will also "
                "outperform the control on unique clicks per 1K views."
            ),
            "why_this_follows": "The current result has been observed once. Replication confirms it is not execution noise.",
            "recommendation_reason": "",
            "previous_learning": f"The {winning_title} produced a directional click improvement over the control in this experiment.",
            "remaining_unknown": f"Whether the effect holds when the specific words or delivery of {independent_var.lower()} change.",
        },
        {
            "slot": "highest_learning",
            "relationship_type": "mechanism_isolation",
            "recommended": True,
            "statement": (
                f"A variant that isolates one dimension of {independent_var.lower()} will "
                "reveal which specific aspect drove the click improvement."
            ),
            "why_this_follows": (
                f"The winning treatment changed multiple things at once. "
                "Isolating one dimension identifies the mechanism, not just the surface effect."
            ),
            "recommendation_reason": (
                "This candidate produces the most durable learning per experiment run "
                "by identifying the causal mechanism rather than confirming the surface result."
            ),
            "previous_learning": f"The {winning_title} outperformed the control, but two or more things changed simultaneously.",
            "remaining_unknown": f"Whether the improvement came from one specific dimension of {independent_var.lower()} or the combination.",
        },
        {
            "slot": "highest_upside",
            "relationship_type": "parameter_optimization",
            "recommended": False,
            "statement": (
                f"Adjusting a key parameter of the {winning_title} execution "
                "will further increase unique clicks per 1K views."
            ),
            "why_this_follows": "The winning treatment established a direction; parameter optimization extracts more value from that direction.",
            "recommendation_reason": "",
            "previous_learning": f"The {winning_title} held attention and converted at a higher rate. The baseline is now established.",
            "remaining_unknown": "Whether parameter adjustments compound the gain or produce diminishing returns.",
        },
    ]
