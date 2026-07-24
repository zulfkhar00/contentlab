"""
Standalone Claude evaluation runner.

Usage:
    python -m app.intelligence.evaluation.run \
        --provider fake \
        --suite all \
        --output reports/eval.json

    python -m app.intelligence.evaluation.run \
        --provider claude \
        --suite all \
        --repeat-high-risk 3 \
        --output reports/claude-eval.json

Live provider calls are never invoked by normal pytest. This module is
the only entry point for paid evaluation runs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Allow running as `python -m app.intelligence.evaluation.run`
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.intelligence.evaluation.suite import EVAL_CASES, EvalCase, EvalResult, run_eval

_HIGH_RISK_CASES = {
    "analyze_flagd_directional",     # canonical directional — baseline
    "analyze_insufficient_views",    # insufficient evidence
    "analyze_execution_deviation",   # execution problem
    "analyze_mixed_result",          # mixed result
    "analyze_zero_views_variant",    # zero views
    "gen_hyp_standard_product",      # duplicate hypothesis guard
    "design_exp_flagd",              # A/B/C role mapping
}


def _make_provider(provider_name: str):
    if provider_name == "fake":
        from app.intelligence.fake import FakeIntelligenceProvider
        return FakeIntelligenceProvider()
    elif provider_name == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            sys.exit("ANTHROPIC_API_KEY is required for --provider claude")
        # Patch settings so the provider picks up the key
        from app.config import settings
        if not settings.anthropic_api_key:
            object.__setattr__(settings, "anthropic_api_key", api_key)
        from app.intelligence.anthropic_provider import AnthropicIntelligenceProvider
        return AnthropicIntelligenceProvider()
    else:
        sys.exit(f"Unknown provider: {provider_name}. Use 'fake' or 'claude'.")


def _print_summary(results: list[EvalResult]) -> None:
    pass_count = sum(1 for r in results if r.passed)
    fail_count = len(results) - pass_count
    total_latency = sum(r.latency_ms for r in results)
    print(f"\n{'='*60}")
    print(f"EVAL RESULTS: {pass_count}/{len(results)} passed  ({fail_count} failed)")
    print(f"Total latency: {total_latency}ms")
    print("─"*60)
    for r in results:
        icon = "✓" if r.passed else "✗"
        print(f"  {icon} [{r.operation:25s}] {r.case} ({r.latency_ms}ms)")
        if not r.passed:
            print(f"      ERROR: {r.error}")
    print("="*60)


async def _main(args: argparse.Namespace) -> int:
    provider = _make_provider(args.provider)

    # Determine which cases to run
    if args.suite == "all":
        cases_to_run = None  # run all
    else:
        ops = [op.strip() for op in args.suite.split(",")]
        cases_to_run = [c.name for c in EVAL_CASES if c.operation in ops]

    print(f"\nRunning eval suite with provider={args.provider}")
    if cases_to_run:
        print(f"  Filtered to cases: {cases_to_run}")
    print(f"  High-risk repeat: {args.repeat_high_risk}x")
    print()

    all_results: list[EvalResult] = []

    # Normal run (once)
    results = await run_eval(provider, cases_to_run)
    all_results.extend(results)

    # High-risk repeats (live provider only)
    if args.repeat_high_risk > 1 and args.provider == "claude":
        high_risk = [c.name for c in EVAL_CASES if c.name in _HIGH_RISK_CASES]
        if cases_to_run:
            high_risk = [n for n in high_risk if n in cases_to_run]
        for rep in range(2, args.repeat_high_risk + 1):
            print(f"\nHigh-risk repeat {rep}/{args.repeat_high_risk}...")
            rep_results = await run_eval(provider, high_risk)
            for r in rep_results:
                r.case = f"{r.case}__rep{rep}"
            all_results.extend(rep_results)

    _print_summary(all_results)

    # Build report
    report = {
        "provider": args.provider,
        "total_cases": len(all_results),
        "passed": sum(1 for r in all_results if r.passed),
        "failed": sum(1 for r in all_results if not r.passed),
        "results": [
            {
                "case": r.case,
                "operation": r.operation,
                "passed": r.passed,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "output_preview": r.output_preview,
            }
            for r in all_results
        ],
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to: {out_path}")

    return 0 if all(r.passed for r in all_results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Content Lab intelligence evaluation runner")
    parser.add_argument("--provider", choices=["fake", "claude"], default="fake",
                        help="Provider to evaluate (fake=no cost, claude=live API calls)")
    parser.add_argument("--suite", default="all",
                        help="'all' or comma-separated operation names")
    parser.add_argument("--repeat-high-risk", type=int, default=1,
                        help="Number of times to repeat high-risk cases (live provider only)")
    parser.add_argument("--output", default=None,
                        help="Path to write JSON report")
    args = parser.parse_args()

    if args.provider == "claude" and args.repeat_high_risk == 1:
        print("Tip: use --repeat-high-risk 3 to test model variability on hard cases.")

    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
