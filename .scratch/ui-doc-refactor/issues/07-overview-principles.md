# /overview: question header + learning-before-CTA order + hardcoded KPIs (S14 follow-up)

Status: done
Type: task

Three principle failures found during S14 audit:

a. Header h2="Overview" does not pose a question. Doc says every screen must answer one stated question.
   Proposed fix: change h2 to a question such as "What should I work on today?" or similar.

b. Layout order: KPI metrics tile row and Next Action card appear BEFORE Latest Learning section.
   Principle says context then decision then CTA, top to bottom.
   Proposed fix: move Latest Learning and Current Research Thread above the KPI row and Next Action card.

c. The four top KPI tiles (Published Videos, Product Clicks, Completed Experiments, Active Research Thread)
   are hardcoded stubs. They must pull from real experiment and hypothesis store data.

Done when all three fixes are applied and diag_full.mjs remains GREEN.

Resolved in commit bb0b73a.
