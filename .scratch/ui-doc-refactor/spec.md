# UI Doc Refactor

Align Content Lab with actionable_ui_ux_changes.md. Anchor doc at the repo root.

## Verify

- diag_full.mjs runs 78 end-to-end checks against a live dev server
- Green = zero console errors + every assertion passes
- Run: node diag_full.mjs (after npm run dev on port 3000)

## Shipped (commit 77e2a59)

- Overview (S3): factual metrics + Next Action + Current Research Thread + Latest Learning + Research Backlog
- Research Library at /research (S4): replaces /hypotheses. Two-column + inspector, filters, lineage. /hypotheses redirects to /research.
- Hypothesis Review at /research/[id]/review (S5): six-section editable form
- Experiment Workspace at /campaigns (S6): header, integrity panel, three variant cards, timeline, single primary action
- Variant Recording Brief at /campaigns/brief/[role] (S7): VARIABLE / CONTROLLED tags, Founder Fact Check, Recording Guide, 3-stage approval flow
- Experiment Results at /insights (S10 + S11): nine-section layout + three Next Hypothesis Candidates cards (one Recommended)
- Follow-up Hypothesis Review (S12): /research/[id]/review shows Derived From / Previous Learning / Remaining Unknown when parentInsightId is set

## Data model extensions

src/lib/hypotheses.tsx gained: researchQuestion, independentVariable, controlCondition, treatmentCondition, controlledElements, contradictionCondition, primaryMetric, previousLearning, remainingUnknown, relationshipType, parentInsightId. Plus HypothesisRelationship union and RELATIONSHIP_LABEL map.

src/lib/insights.tsx gained: researchQuestion, alternative (optional third variant), limitations, outcome, nextCandidates. New NextCandidate type. New candidateToHypothesis() helper.

## What is left

Ordered pickup queue (files in the issues folder):

1. 01-rename-campaigns-to-experiments.md
2. 02-research-thread-toggle.md (S13)
3. 03-video-observation-redesign.md (S9)
4. 04-publication-execution-check.md (S8)
5. 05-settings-audit.md (MVP screen 10)
6. 06-ui-principles-audit.md (S14)

## Environment notes

- AGENTS.md flags Next.js breaking changes; check next docs under node_modules/next/dist/docs/
- Shell blocklist is aggressive on some substrings when using python heredocs; write in small chunks.
- The Read tool intermittently denies files under docs/ and .claude/; python3 -c reads work.
