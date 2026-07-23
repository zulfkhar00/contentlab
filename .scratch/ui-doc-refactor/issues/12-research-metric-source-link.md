# /research: primaryMetric on cards not linked to experiment or hypothesis source (S14 follow-up)

Status: ready-for-agent
Type: task

Principle d failure: numbers must always be paired with the hypothesis they came from.

Each hypothesis card in the Research Library shows a primaryMetric (e.g. "Clicks / 1K Views") as a
mono label at the bottom. This metric string appears in isolation — there is no visible link to
which experiment measured it or what result was achieved.

Proposed fix: for hypotheses with status "learned" or "testing", surface the source insight's
metric result alongside the metric label when available. For example: "Clicks / 1K Views — 11.7"
or add a link to the insight that produced the number.

Done when the metric label on cards for learned/testing hypotheses is paired with a source reference
and diag_full.mjs remains GREEN.
