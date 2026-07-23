Yes. Before touching implementation, we should redesign the product around one clear loop:

> **Question → Hypothesis → Controlled experiment → Observations → Learning → Next hypothesis**

And we should freeze the vocabulary:

* **Hypothesis:** what we believe.
* **Experiment:** how we test it.
* **Variant:** one published video within the experiment.
* **Observation:** what happened to one variant.
* **Insight:** what the comparison across all variants supports.
* **Follow-up hypothesis:** the next uncertainty to test.

So one hypothesis creates **one experiment with three variants**, not three separate campaigns.

---

# 1. Recommended information architecture

I would slightly evolve the current navigation:

```text
Overview
Research
Experiments
Videos
Insights
Settings
```

Changes:

* `Hypotheses` becomes **Research**
* `Campaigns` becomes **Experiments**

This positioning is more valuable and more aligned with the product.

The user is not managing social campaigns. They are building knowledge about how to market their product.

## Shared shell

Top bar:

```text
@founder_lab
founderlab.ai
contentlab.app/p/founder-lab [Copy]
Notifications
Avatar
```

Sidebar CTA:

```text
+ New Hypothesis
```

or, when an Approved hypothesis exists:

```text
+ Create Experiment
```

The CTA can be contextual.

---

# 2. Full product workflow

```text
Onboarding
    ↓
Initial Hypotheses Generated
    ↓
Research Library
    ↓
Review Hypothesis
    ↓
Approve Experiment Design
    ↓
Generate Experiment
    ↓
Review Variant A
    ↓
Record → Publish → Submit URL → Track
    ↓
Review Variant B
    ↓
Record → Publish → Submit URL → Track
    ↓
Review Variant C
    ↓
Record → Publish → Submit URL → Track
    ↓
Individual Variant Observations
    ↓
Final Experiment Analysis
    ↓
Three Follow-up Hypothesis Candidates
    ↓
Review One Candidate
    ↓
New Hypothesis Added to Research Thread
```

---

# 3. Screen 1: Overview

## Purpose

Answer:

> What am I currently learning, and what should I do next?

This should not primarily be an analytics dashboard.

## Layout

### Top metrics

Keep only a small factual summary:

```text
Published Videos
Product Clicks
Completed Experiments
Active Research Thread
```

Avoid making views the dominant metric.

### Primary card: Next Action

This should be the most prominent element.

Examples:

```text
Next Action

Review Variant B
Founder Failure Story

The script is ready for your review before recording.

[Review Variant]
```

Or:

```text
Next Action

Publish Variant C

Variants A and B are currently tracking. Publish Variant C to complete the experiment.

[Open Recording Brief]
```

Or:

```text
Next Action

Review Experiment Learning

All three tracking windows are complete.

[View Results]
```

### Current Research Thread

```text
Current Question

Which opening style generates the most product clicks?

Current Hypothesis

A concrete founder-failure opening will generate more clicks per 1,000 views than a product-demo opening.

Experiment Progress

A — Completed
B — Tracking
C — Ready to Record
```

### Latest Learning

Show the most recent completed insight:

```text
Latest Learning

The concrete founder-failure opening produced 4.0x more clicks per 1,000 views than the product-demo control.

[View Evidence]
```

### Research Backlog

Show 3–4 hypotheses awaiting review.

The Overview page should always orient the user around:

```text
What are we testing?
What has happened?
What should I do next?
```

---

# 4. Screen 2: Research Library

This replaces the current Hypotheses page.

## Purpose

Answer:

> What do we believe, why do we believe it, and where did the hypothesis come from?

## Layout

Two columns:

```text
Left: Research Library
Right: Selected Hypothesis Inspector
```

## Library filters

```text
Suggested
Draft
Approved
Testing
Learned
Rejected
```

Search:

```text
Search hypotheses...
```

## Hypothesis card

Each card should show:

```text
Founder-failure openings drive more product clicks

Testing
Clicks / 1K Views

Derived from:
Initial product context
```

For follow-up hypotheses:

```text
Quantified failure beats vague failure

Draft
Clicks / 1K Views

Derived from H1
Mechanism Isolation
```

## Selected hypothesis inspector

Sections:

### Research Question

```text
Which opening style generates more product clicks?
```

### Hypothesis

```text
A concrete founder-failure opening will generate more clicks per 1,000 views than a product-demo opening.
```

### Experiment Design Preview

```text
Variable
Opening angle

Control
Product-demo opening

Treatment
Concrete founder-failure opening

Primary Metric
Clicks / 1K Views

Controlled
Audience, format, duration, product explanation, offer and CTA
```

### Why This Matters

```text
Your previous product-focused content generated views but few product clicks. This test evaluates whether a founder narrative creates stronger product intent.
```

### Lineage

For an initial hypothesis:

```text
Source
Generated from onboarding context
```

For a follow-up:

```text
Derived From
H1 — Founder-failure opening vs product demo

Relationship
Mechanism Isolation

Previous Learning
The founder-failure treatment produced greater click efficiency.

Remaining Unknown
Whether specificity or vulnerability caused the difference.
```

## Actions by status

### Suggested or Draft

```text
Review Hypothesis
Reject
```

### Approved

```text
Create Experiment
Edit
```

### Testing

```text
View Experiment
```

### Learned

```text
View Insight
Create Follow-up
```

---

# 5. Screen 3: Hypothesis Review

This should be a dedicated screen, not merely a small modal.

## Purpose

Answer:

> Is this a useful and testable question?

The user approves the experiment logic before Content Lab creates scripts.

## Header

```text
Review Hypothesis

Ensure this tests one meaningful variable before generating the experiment.
```

## Section 1: Research Question

Editable:

```text
Which opening style generates more product clicks?
```

## Section 2: Hypothesis Statement

Editable:

```text
A concrete founder-failure opening will generate more clicks per 1,000 views than a product-demo opening.
```

## Section 3: Experiment Design

Use structured fields:

```text
Independent Variable
Opening angle

Control Condition
Product-demo opening

Treatment Condition
Concrete founder-failure opening

Primary Metric
Clicks / 1K Views
```

## Section 4: Controlled Elements

Checkbox/tag-style structured fields:

```text
Audience
Founder-led talking head
Duration
Product explanation
Offer
CTA
Caption format
Publishing account
```

The user should be able to edit these.

## Section 5: Contradiction Condition

```text
This hypothesis would not be supported if the founder-failure treatment does not outperform the product-demo control after all tracking windows complete.
```

This makes the experiment feel rigorous.

## Section 6: Source and Reason

```text
Why This Test

Founder stories may create stronger emotional relevance than direct feature explanation.

Based On

Product context and previous content performance.
```

For follow-up hypotheses, this section references the previous insight.

## Primary actions

```text
Save Draft
Approve & Generate Experiment
```

Approving locks the experiment design unless the user explicitly reopens it.

---

# 6. Screen 4: Experiment Workspace

This evolves the current Campaigns screen.

## Purpose

Answer:

> Is the experiment being executed consistently?

## Header

```text
Experiment 01

Founder Failure Hook vs Product Demo

Status: In Progress
Primary Metric: Clicks / 1K Views
Tracking Window: 72 hours
```

## Hypothesis summary

```text
A concrete founder-failure opening will generate more clicks per 1,000 views than a product-demo opening.
```

## Experiment integrity panel

This is a high-value addition.

```text
Variable Under Test

Opening angle

Keep Controlled

Audience
Founder-led talking head
45–50 seconds
Same product explanation
Same offer
CTA: Check link in bio
Same publishing account
```

If deviations exist:

```text
Experiment Integrity

1 possible deviation detected

Variant B duration was 68 seconds instead of the planned 45–50 seconds.

[Review Deviation]
```

Do not use a score.

## Three variant cards

### A — Product Demo

```text
Role
Control

Variable Value
Product-demo opening

Status
Completed

Views
8,204

Clicks / 1K
2.9

[View Observation]
```

### B — Founder Failure Story

```text
Role
Hypothesis Treatment

Variable Value
Concrete founder-failure opening

Status
Tracking

Tracking ends in 18 hours

[View Tracking]
```

### C — Contrarian Insight

```text
Role
Alternative Treatment

Variable Value
Contrarian distribution framing

Status
Ready to Record

[Review Variant]
```

## Experiment timeline

```text
A approved
A published
A tracking completed
B approved
B published
B tracking
C awaiting review
```

## Contextual primary action

Only one dominant action:

```text
Review Variant C
```

or:

```text
Review Experiment Results
```

---

# 7. Screen 5: Variant Review and Recording Brief

## Purpose

Answer:

> Can the founder execute this variant while preserving the experiment design?

## Header

```text
Variant B — Founder Failure Story

Hypothesis Treatment
```

## Experiment context

Always visible:

```text
Variable Under Test
Opening angle

This Variant Changes
Concrete founder-failure opening

Keep Controlled
Audience, format, product explanation, duration, offer and CTA
```

## Script editor

Break into timed sections:

```text
0–5s
Hook

5–15s
Context

15–30s
Lesson

30–42s
Product connection

42–48s
CTA
```

Each section should be labeled:

```text
VARIABLE
```

or:

```text
CONTROLLED
```

For example:

```text
Hook
VARIABLE

“I spent almost $2,000 on UGC ads and got almost no users.”
```

```text
CTA
CONTROLLED

“Check the link in my bio.”
```

## Truth check

Before approval:

```text
Founder Fact Check

The script says you spent almost $2,000 on UGC ads.

Is this accurate?

Yes
Edit
Remove
```

The AI must not invent stories.

## Recording guide

Advisory, not hard blockers:

```text
Camera
Eye level, medium close-up

Delivery
Calm, direct, slightly reflective

Background
Use the same environment as other variants

Duration Target
45–50 seconds
```

## Approval

```text
Approve for Recording
```

After approval:

```text
I Have Recorded This Variant
```

Then:

```text
I Have Published This Variant on TikTok
```

---

# 8. Screen 6: Publication and Execution Check

This can be a modal or a state within the Variant page.

## Purpose

Capture whether the real video matched the planned experiment.

## Step 1: Publication confirmation

```text
Published on TikTok?

Confirm that the video is publicly visible on @founder_lab.
```

## Step 2: TikTok URL

```text
Paste Published TikTok URL
```

States:

```text
Validating…
Valid Video
Invalid URL
Account Mismatch
Video Private
```

## Step 3: Execution Check

Ask only structured questions:

```text
Did you use the approved hook?
Yes / Changed

Did you use the fixed CTA?
Yes / Changed

Actual duration
48 seconds

Product reveal time
23 seconds

Did the format change?
No / Yes

Did the offer change?
No / Yes
```

If changed:

```text
What changed?
```

## Result

```text
Experiment Check

The hook, CTA and format matched the approved design.

Duration was 3 seconds longer than planned.

[Start Tracking]
```

Do not prevent tracking because of a minor deviation. Record it for analysis.

---

# 9. Screen 7: Video Observation

This can live inside Videos or as a dedicated detail page.

## Purpose

Answer:

> What factually happened to this one variant?

## Header

```text
Variant B Observation

Founder Failure Story
Tracking Complete
```

## Snapshot

```text
Views
8,204

Likes
412

Comments
67

Product Clicks
96

Clicks / 1K Views
11.7
```

## Tracking window

```text
Published
23 July, 10:00

Window completed
26 July, 10:00

Last refreshed
26 July, 10:04
```

## Attribution facts

```text
Attribution Method
Campaign-window estimation

Other active variants
Variant A remained within its 72-hour window for the first 6 hours.

Campaign overlap
None
```

## Comment themes

```text
Founder marketing frustration
Questions about UGC
Interest in the product
```

## Factual observation

```text
Variant B produced 11.7 clicks per 1,000 views during its completed tracking window.
```

Allowed:

> This is currently the highest click efficiency in the experiment.

Not allowed:

> Founder-failure stories work better.

## Bottom message

```text
Global conclusions will be generated after all three variants complete their tracking windows.
```

---

# 10. Screen 8: Experiment Results

This should become the most important screen in the product.

## Purpose

Answer:

> What did we learn, what remains unknown, and what should we test next?

## Header

```text
Experiment Results

Founder Failure Hook vs Product Demo

Completed
```

## Section 1: Research Question

```text
Which opening style generates more product clicks?
```

## Section 2: Hypothesis Tested

```text
A concrete founder-failure opening will generate more clicks per 1,000 views than a product-demo opening.
```

## Section 3: Variant comparison

| Variant              | Role        | Views | Clicks | Clicks / 1K |
| -------------------- | ----------- | ----: | -----: | ----------: |
| A Product Demo       | Control     | 8,204 |     24 |         2.9 |
| B Founder Failure    | Treatment   | 8,188 |     96 |        11.7 |
| C Contrarian Insight | Alternative | 7,930 |     48 |         6.1 |

## Section 4: Observed result

```text
Variant B produced 4.0x more clicks per 1,000 views than Variant A.
```

## Section 5: Supported Learning

```text
In this experiment, the concrete founder-failure opening generated greater product-click efficiency than the product-demo opening.
```

## Section 6: What Is Not Proven

```text
This experiment does not determine:

• Whether the specific $2,000 amount caused the difference
• Whether vulnerability or specificity mattered more
• Whether founder stories outperform every product demo
• Whether the pattern will repeat in another campaign
```

## Section 7: Experiment limitations

```text
Variant B was 18 seconds longer than planned.

Variants A and B had a 6-hour attribution-window overlap.

No other campaigns were active.
```

## Section 8: Outcome classification

Use plain language:

```text
Outcome

Directional Difference

The treatment produced a clear observed difference, but replication or mechanism isolation is needed before treating it as a reusable rule.
```

No confidence score.

---

# 11. Screen 9: Next Hypothesis Candidates

This should be on the bottom of Experiment Results, not hidden elsewhere.

## Purpose

Answer:

> What is the most valuable uncertainty to test next?

Show exactly three candidates.

## Candidate 1: Safest Next Step

```text
Replication

Test whether a different founder-failure story also outperforms the product-demo control.

Why This Follows

The current result has only been observed once.
```

## Candidate 2: Highest-Learning Next Step

```text
Mechanism Isolation

A quantified failure statement will generate more clicks per 1,000 views than the same failure described without a number.

Why This Follows

The winning treatment changed both specificity and emotional framing. This test isolates specificity.
```

## Candidate 3: Highest-Upside Next Step

```text
Optimization

Showing the product at 10 seconds instead of 25 seconds after the same founder-failure hook will increase clicks per 1,000 views.

Why This Follows

The opening generated click interest. Earlier product context may convert that attention more efficiently.
```

One card gets:

```text
Recommended
```

But never:

```text
92% confidence
```

## Actions

Each candidate:

```text
Review Hypothesis
```

Secondary:

```text
Not Relevant
```

The system does not automatically create an experiment.

---

# 12. Screen 10: Follow-up Hypothesis Review

This uses the same Hypothesis Review screen, with lineage added.

## Header

```text
Review Follow-up Hypothesis
```

## Derived from

```text
Parent Hypothesis

H1 — Founder-failure opening vs product demo

Source Insight

The concrete founder-failure opening produced 4.0x more clicks per 1,000 views.

Relationship

Mechanism Isolation
```

## Previous learning

```text
The founder-failure treatment generated greater click efficiency.
```

## Remaining unknown

```text
Whether the observed difference came from the specific number, the failure narrative, or vulnerability.
```

## Proposed new hypothesis

```text
A quantified founder-failure statement will generate more clicks per 1,000 views than the same failure described without a number.
```

## New experiment design

```text
Variable
Failure specificity

Control
Vague failure statement

Treatment
Quantified failure statement

Controlled
Failure story, script structure, duration, product explanation, CTA and publishing account
```

## Actions

```text
Save as Draft
Approve Hypothesis
```

After approval:

```text
Create Experiment
```

---

# 13. Research lineage UX

Do not build a complex graph yet.

Use a simple vertical research thread:

```text
H1
Founder failure vs product demo
Completed

↓ Mechanism Isolation

H2
Quantified failure vs vague failure
Testing

↓ Optimization

H3
Early vs late product reveal
Draft
```

Each node can expand to show:

* hypothesis;
* experiment;
* supported learning;
* next relationship.

Place this view as a toggle inside Research:

```text
Library | Research Thread
```

This is where the compounding value becomes visible.

---

# 14. Critical UI principles

## Separate facts from interpretation

Use explicit labels:

```text
Observed Result
Supported Learning
Not Proven
Recommended Next Test
```

Never mix them into one AI paragraph.

## Show the tested variable everywhere

Every hypothesis, experiment and variant screen should display:

```text
Variable Under Test
```

This is the core of the product.

## One dominant action per screen

Examples:

```text
Review Hypothesis
Approve Experiment Design
Review Variant
Start Tracking
View Results
Review Next Hypothesis
```

Avoid multiple equally prominent buttons.

## Preserve user control

AI proposes.

The user:

* edits;
* approves;
* publishes;
* confirms deviations;
* accepts the next hypothesis.

## Do not reward volume

Do not make:

```text
Videos Posted
Daily Streak
Content Calendar
Ideas Generated
```

the central success metrics.

Reward:

```text
Experiments Completed
Learnings Produced
Findings Replicated
Research Threads Advanced
```

---

# 15. Minimum MVP screen set

To deliver the core value, the actual required screens are:

```text
1. Overview
2. Research Library
3. Hypothesis Review
4. Experiment Workspace
5. Variant Review / Recording Brief
6. Publication / Execution Check
7. Video Observation
8. Experiment Results
9. Next Hypothesis Selection
10. Settings
```

The existing Videos page can remain a registry, but it is supporting functionality rather than the product centre.

The next design step should be to redesign the **Research Library and Hypothesis Review flow first**, because every later screen depends on the quality of the approved experiment design.
