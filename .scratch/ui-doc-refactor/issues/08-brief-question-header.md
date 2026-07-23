# /experiments/brief/[role]: Variant Brief header does not pose a question (S14 follow-up)

Status: ready-for-agent
Type: task

The header on the Recording Brief page reads "Variant B — Founder Failure Story". This is a label, not a question.

The doc says every screen must answer a single question stated in the header.

Proposed fix: add a subtitle or reframe the h2 as a question, such as "Can you execute this variant while preserving the experiment design?" (matching the top-level comment already in the file).

Done when the header or subtitle clearly poses one question and diag_full.mjs remains GREEN.
