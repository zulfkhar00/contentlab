# UI principles audit (S14)

Status: ready-for-agent
Type: task

Section S14 of the actionable UX markdown lists five critical UI principles that must hold across every screen:

  a. Every screen answers a single question stated in the header
  b. One primary action per screen; secondary actions demote visually
  c. Learnings surface before actions (context then decision then action, top to bottom)
  d. Numbers are always paired with the hypothesis they came from
  e. Follow-up hypotheses inherit lineage visibly (not just in data)

Refactor built each screen to these principles individually but no end-to-end audit was run.

Scope: for each of the routes below, verify all five principles hold. On a fail, file a follow-up ticket instead of fixing inline.

  - /overview
  - /research
  - /research/[id]/review
  - /campaigns (or /experiments post-rename)
  - /campaigns/brief/[role]
  - /insights
  - /videos (currently thin; probably needs a rewrite)

Deliverable: a markdown table appended to this ticket file, one row per route with a pass or fail cell for each of the five principles plus a one-line note per cell. Failing rows spawn tickets 07 onwards.

Done when:

  a. Every route has been walked through in a browser
  b. The table is filled in
  c. Any fail creates a follow-up ticket in this folder