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
