"""
ContextAssemblers — one per operation.
Each assembler takes pre-loaded dicts (never queries the database)
and formats them into a string or dict for prompt rendering.
"""
import json


class HypothesisContextAssembler:
    @staticmethod
    def build(project: dict, facts: list[dict], context_version: int) -> str:
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        lines = [
            f"Product name: {project.get('product_name', '')}",
            f"Product type: {project.get('product_type', '')}",
            f"Description: {project.get('product_description', '')}",
            f"URL: {project.get('product_url', '')}",
            f"Target audience: {project.get('target_audience', '')}",
            f"Problem solved: {project.get('problem_solved', '')}",
            f"Why it matters: {project.get('why_it_matters', '')}",
            f"Current alternatives: {project.get('current_alternatives', '')}",
            f"Desired action: {project.get('desired_action', '')}",
            f"Primary CTA: {project.get('primary_cta', '')}",
            f"TikTok handle: @{project.get('tiktok_handle', '')}",
        ]
        if verified:
            lines.append("\nVerified founder facts (do not invent others):")
            for fact in verified:
                lines.append(f"  - {fact}")
        return "\n".join(lines)


class ExperimentDesignContextAssembler:
    @staticmethod
    def build(hypothesis: dict, project: dict, facts: list[dict]) -> str:
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        lines = [
            f"Hypothesis title: {hypothesis.get('title', '')}",
            f"Statement: {hypothesis.get('statement', '')}",
            f"Research question: {hypothesis.get('research_question', '')}",
            f"Independent variable: {hypothesis.get('independent_variable', '')}",
            f"Control condition: {hypothesis.get('control_condition', '')}",
            f"Treatment condition: {hypothesis.get('treatment_condition', '')}",
            f"Primary metric: {hypothesis.get('primary_metric', 'clicks_per_1k_views')}",
            f"Controlled elements: {', '.join(hypothesis.get('controlled_elements', []))}",
            "",
            f"Product: {project.get('product_name', '')} ({project.get('product_type', '')})",
            f"Audience: {project.get('target_audience', '')}",
            f"CTA: {project.get('primary_cta', '')}",
            f"TikTok: @{project.get('tiktok_handle', '')}",
        ]
        if verified:
            lines.append("\nVerified facts:")
            for fact in verified:
                lines.append(f"  - {fact}")
        return "\n".join(lines)


class ReviseBriefContextAssembler:
    @staticmethod
    def build(variant: dict, instruction: str, project: dict) -> dict:
        return {
            "current_hook": variant.get("hook", ""),
            "current_context": variant.get("context", ""),
            "instruction": instruction,
            "product_name": project.get("product_name", ""),
            "target_audience": project.get("target_audience", ""),
        }


class EvidenceContextAssembler:
    @staticmethod
    def build(
        evidence: dict,
        hypothesis_snapshot: dict,
        project: dict,
        facts: list[dict],
    ) -> dict:
        verified = [f["fact_text"] for f in facts if f.get("status") == "verified"]
        items_text = []
        for item in evidence.get("items", []):
            role = item.get("treatment_role", "")
            title = item.get("title", "")
            views = item.get("views_delta", 0)
            clicks = item.get("attributed_unique_clicks", 0)
            cper1k = item.get("unique_clicks_per_1k")
            delivered = item.get("delivered_variable")
            cper1k_str = f"{cper1k:.1f}" if cper1k is not None else "N/A (zero views)"
            deviated = "" if delivered is not False else " [EXECUTION DEVIATION: variable not delivered]"
            items_text.append(
                f"  {item.get('position','?')} ({title}, {role}): "
                f"{views:,} views, {clicks} unique clicks, {cper1k_str} per 1K views{deviated}"
            )
        return {
            "experiment_name": hypothesis_snapshot.get("researchQuestion", "")[:80],
            "hypothesis_statement": hypothesis_snapshot.get("statement", ""),
            "independent_variable": hypothesis_snapshot.get("independentVariable", ""),
            "primary_metric": hypothesis_snapshot.get("primaryMetric", "clicks_per_1k_views"),
            "evidence_items": "\n".join(items_text),
            "verified_facts": "\n".join(f"  - {f}" for f in verified) or "  (none recorded)",
        }


class CandidateContextAssembler:
    @staticmethod
    def build(insight: dict, hypothesis_snapshot: dict, project: dict, facts: list[dict]) -> dict:
        dniy = insight.get("do_not_infer_yet", [])
        if isinstance(dniy, str):
            import json
            try:
                dniy = json.loads(dniy)
            except Exception:
                dniy = [dniy]
        return {
            "experiment_name": insight.get("research_question", "")[:80],
            "hypothesis_statement": hypothesis_snapshot.get("statement", ""),
            "independent_variable": hypothesis_snapshot.get("independentVariable", ""),
            "outcome_type": insight.get("outcome_type", ""),
            "supported_learning": insight.get("supported_learning", ""),
            "do_not_infer_yet": "\n  - ".join(dniy) if dniy else "(none recorded)",
            "recommended_next_test": insight.get("recommended_next_test", ""),
        }
