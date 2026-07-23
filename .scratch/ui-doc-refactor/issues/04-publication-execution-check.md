# Publication and Execution Check (S8)

Status: ready-for-agent
Type: task

Full spec for this feature is section S8 of the actionable UX markdown at repo root.

TL;DR: add a modal before Publish in the Recording Brief 3-stage flow. Three required boxes.

  a. Video is live at the URL entered
  b. Variable was delivered as written
  c. Controlled elements were not altered

Done when:

  a. Modal appears after Publish click
  b. diag_full.mjs walks through the modal for one variant
  c. Zero console errors and no layout shift after open