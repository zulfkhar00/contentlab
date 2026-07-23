# UI principles audit (S14)

Status: done
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

Resolved in commit ddcc527 (audit) and bb0b73a (fixes).

---

# UI Principles Audit (S14)

| Route | a. Question in header | b. One primary CTA | c. Context before action | d. Numbers linked | e. Lineage visible |
|---|---|---|---|---|---|
| /overview | FAIL — h2=Overview, no question | PASS — Next Action card, one CTA | FAIL — metrics and CTA before Latest Learning | FAIL — KPI tiles hardcoded, not from hypothesis | WARN — no lineage chain shown |
| /research | WARN — subtitle is a statement, not a question | PASS — Generate More is the only header CTA | PASS — filter then inspect, no CTA-first | FAIL — primaryMetric on cards not linked to experiment | PASS — DerivedFromLine shows lineage on every card |
| /research/[id]/review | PASS — title implies the review question | PASS — Approve and Generate is the sole CTA | PASS — 6 context sections then CTA | N/A — no numeric KPIs on this screen | PASS — lineage card rendered for follow-ups |
| /experiments | PASS — subtitle "Is the experiment being executed consistently?" | PASS — primary-action-strip, one CTA | PASS — context then integrity then variants then CTA | FAIL — variant metrics shown without hypothesis link | N/A — execution phase |
| /experiments/brief/[role] | FAIL — "Variant X — Title" is not a question | PASS — staged approval buttons are in order | PASS — context, script, guide, then CTA | N/A — no experiment KPIs | N/A — single variant |
| /insights | FAIL — left list has no header question | FAIL — three next-candidate cards compete with equal CTAs | PASS — 8 analysis sections before candidates | PASS — Variant Comparison pairs metrics with hypothesis | PASS — candidates show follow-up relationship |
| /videos | FAIL — h2=Videos, no question | FAIL — no dominant CTA, many tracking links compete | N/A — tracking and management screen | FAIL — four KPI tiles hardcoded, unconnected to hypothesis | N/A |

## Follow-up tickets spawned

- **07** `/overview` — missing question header; CTA before learning; hardcoded KPIs
- **08** `/experiments/brief/[role]` — Variant Brief header does not pose a question
- **09** `/insights` — no header question; three candidate cards carry co-equal CTAs
- **10** `/videos` — full rewrite needed: question header, one dominant CTA, real KPIs from experiment data
- **11** `/experiments` — variant metric cards do not surface the hypothesis they test
- **12** `/research` — primaryMetric on hypothesis cards not linked to experiment or source hypothesis
