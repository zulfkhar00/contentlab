# Content Lab Sprint Checkpoint — commit eb53cbb

## Intelligence (Sprint 6 complete)

- Provider: OpenRouterIntelligenceProvider (INTELLIGENCE_PROVIDER=openrouter)
- All 14 eval cases passing against real claude-sonnet-5 via OpenRouter
- generateHypotheses prompt v1.1.2026-07 (no-invented-facts clause added)
- All other prompts v1.2026-07
- Repair: second ai_run row with parent_ai_run_id; request_group_id groups both
- Eval command: `cd backend && PYTHONPATH=. python3 -m app.intelligence.evaluation.run --provider openrouter --suite all`

## Tests

- 90 passing
- Run: `PYTHONPATH=. ENVIRONMENT=test pytest tests/ -q --import-mode importlib`

## Running services

- Supabase port 54322: `supabase start --exclude edge-runtime,logflare`
- FastAPI port 8000: `cd backend && uvicorn app.main:app --port 8000`
- Next.js port 3000: `npm run dev`
- Migrations 001-004 applied to both local Supabase and test_cl

## API (all implemented)

Projects, Hypotheses, Experiments, Variants, Videos, ExecutionObservations,
Insights, FollowUpCandidates, dev seed endpoints, canary endpoint.

## Frontend

TanStack Query installed. QueryProvider wraps root layout.
query-hooks.ts has typed hooks for all 7 entities.
SEED_HYPOTHESES, SEED_INSIGHTS, createDefaultExperiment removed from all fallback paths.
ExperimentProvider is presentation-only state.

## Sprint 7 scope (next)

- Real TikTok metric collection via phone automation
- Redirect ingestion from permanent bio link (RedirectEvent table ready)
- Workers: close_attribution_window, unlock_next_variant, finalize_evidence, generate_insight
- Jobs table and claim_job/fail_job/extend_job_lease/enqueue_job in migration 002

## Known gaps

- Auth: anonymous Supabase sign-in only, no login UI
- ExperimentProvider still holds local stage state (not canonical)
- SEED_INSIGHTS still imported in some files but not used as canonical source
