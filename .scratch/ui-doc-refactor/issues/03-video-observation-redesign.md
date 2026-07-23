# Variant Observation view (S9)

Status: ready-for-agent
Type: task

Doc S9 asks for a per-variant Video Observation view during a running experiment. Founder logs qualitative observations and marks whether the variant delivered the variable as intended.

Scope:

- Add route src/app/(app)/experiments/[experimentId]/variant/[variantId]/observe/page.tsx (or the /campaigns equivalent until issue 01 lands)
- Left zone: embed the video player using publish URL from Recording Brief step 3
- Right zone top: Delivered the variable? boolean with a reason field
- Right zone middle: multi-line Observations input
- Right zone bottom: three canned observation fields for drop-off time-code, comment sentiment reading, unexpected signals
- variant.observation data lives at src/lib/campaign.tsx (or experiment.tsx post-rename) using these keys: deliveredVariable, reason, notes, dropOffAt, sentiment, unexpected
- Link into this view from the Experiment Workspace variant card once a publish URL exists

Done when:

- Route renders for every variant with a publish URL
- Observations round-trip through localStorage
- Variant card shows an Observed badge when variant.observation.notes is non-empty
- diag_full.mjs adds a check that visits the observe route and edits the observation
