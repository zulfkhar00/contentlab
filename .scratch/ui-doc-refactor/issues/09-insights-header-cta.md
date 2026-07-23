# /insights: no header question + candidate cards carry co-equal CTAs (S14 follow-up)

Status: ready-for-agent
Type: task

Two principle failures found during S14 audit:

a. The Insights detail view uses the experiment title as its h2. No question is posed in the header.
   Proposed fix: add a subtitle such as "What did we learn and what should we test next?"

b. Three Next Hypothesis Candidate cards each carry a "Review Hypothesis" CTA of equal visual weight.
   The doc says one primary CTA per screen; secondary CTAs must be demoted visually.
   Proposed fix: mark the Recommended candidate CTA as the primary button and demote the other two
   to outline style so one choice is visually dominant.

Done when both fixes are in and diag_full.mjs remains GREEN.
