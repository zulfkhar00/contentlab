# /videos: full screen rewrite — question, dominant CTA, real KPIs (S14 follow-up)

Status: ready-for-agent
Type: task

Three principle failures on the Videos screen (the thinnest screen in the app):

a. h2="Videos" — no question. Proposed: "How are the published variants performing?"

b. No dominant primary CTA. The screen shows a list of tracking cards with equal-weight links.
   Proposed: add a contextual primary CTA that points to the next experiment step (e.g. "View Results" when a window closes).

c. Four KPI tiles at the top (Published Videos: 12, Currently Tracking: 3, Total Views: 45.2K,
   Avg Clicks / 1K Views: 26.5) are hardcoded stubs.
   They must derive from the real experiment variant data in the ExperimentProvider store.

Done when all three fixes are in and diag_full.mjs remains GREEN.
