# /experiments: variant metric cards do not surface the hypothesis they test (S14 follow-up)

Status: ready-for-agent
Type: task

Principle d failure: numbers must always be paired with the hypothesis they came from.

On the Experiment Workspace page, the variant cards for tracking or completed variants show
metrics (Views, Clicks/1K) but do not visually connect these numbers to the hypothesis being tested.

The experiment hypothesis is shown in the header block, but no line draws the connection when
the user is looking at the metric numbers on the variant cards.

Proposed fix: add a small MonoLabel inside each metric card that reads "Testing: [hypothesis fragment]"
or displays the variable under test next to the metric numbers, so the founder never reads a number
without knowing what question it is answering.

Done when variant metric cards include a visible hypothesis or variable reference and diag_full.mjs remains GREEN.
