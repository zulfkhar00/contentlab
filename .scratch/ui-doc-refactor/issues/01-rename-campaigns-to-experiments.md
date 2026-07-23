# Rename /campaigns to /experiments

Status: resolved
Type: task

Vocabulary froze on the word experiment but the route and file tree still say campaign. Doc S2 flags this.

Scope:

- Rename src/app/(app)/campaigns/ to src/app/(app)/experiments/
- Rename src/lib/campaign.tsx to src/lib/experiment.tsx if present
- Update every import path and every hardcoded href that starts with /campaigns
- Update the sidebar link in src/app/(app)/layout.tsx
- Update selectors and route pushes in diag_full.mjs
- Grep for the word campaign and reduce it to zero outside historical docs

Done when:

- npm run dev boots with no route errors
- node diag_full.mjs is green with all checks passing


## Answer

Physical rename went through git mv:

- src/app/(app)/campaigns/ -> src/app/(app)/experiments/
- src/lib/campaign.tsx -> src/lib/experiment.tsx

Every referrer now imports @/lib/experiment and hrefs /experiments. The one-shot localStorage migration reading legacy cl_campaign into cl_experiment stays as-is; diag verifies it still runs. tsc is clean and node diag_full.mjs is green with all 78 checks and zero console errors.
