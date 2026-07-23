# Research Thread toggle inside /research

Status: done
Type: task

Doc S13 asks for a Research Thread view that visualizes hypothesis lineage as a chain from root to follow-ups to current node. Data exists (parentInsightId on hypotheses, nextCandidates on insights). UI is missing.

Scope:

- Add a Research Thread toggle in the Research Library header at src/app/(app)/research/page.tsx
- When on, replace flat card list with a vertical tree grouped by root hypothesis
- Each node shows title, status pill, and relationship label from RELATIONSHIP_LABEL in src/lib/hypotheses.tsx
- Clicking a node opens the same inspector panel already in place
- Toggle state persists to localStorage under key research.view with values library or thread

Done when:

- Toggle is keyboard-focusable and layout does not shift on switch
- Nodes render for every hypothesis with parentInsightId
- diag_full.mjs gains a check that toggles the view and finds a lineage edge
- Zero console errors on toggle

Resolved in commit eb64ec2.
