# Content Lab — Domain Model (Revised)

**Attribution policy locked:** Isolated windows — publish A, track 72h, then B, then C.  
**Retry policy locked:** One Experiment per Hypothesis; reruns are Video-level (multiple Video attempts per Variant).  
**Script storage:** Flexible `script_sections` JSONB on Variant; `shared_constraints` JSONB on Experiment.  
**Variant/Video state:** Clean separation — Variant owns design lifecycle; Video owns publication lifecycle.

---

## Entity List

```
Project
Hypothesis
Experiment
Variant
Video
VideoMetricSnapshot
ExecutionObservation
RedirectEvent
AttributionWindow
ExperimentEvidenceSnapshot
ExperimentEvidenceItem
Insight
FollowUpCandidate
AIRun
```

---

## Relationships

```
AuthUser 1:1 Project

Project 1:many Hypothesis
Project 1:many Experiment
Project 1:many RedirectEvent

Hypothesis 1:1 Experiment
Hypothesis self-referential via parent_hypothesis_id

Experiment 1:3 Variant
Experiment 1:many ExperimentEvidenceSnapshot (versioned)
Variant 1:many Video

Video 1:many VideoMetricSnapshot
Video 0:1 ExecutionObservation
Video 0:many AttributionWindow

ExperimentEvidenceSnapshot 1:3 ExperimentEvidenceItem
ExperimentEvidenceItem references exactly one Variant and one Video attempt
ExperimentEvidenceSnapshot 1:1 Insight

Insight 1:many FollowUpCandidate (typically 3)
FollowUpCandidate 0:1 Hypothesis
Hypothesis references its origin via source_candidate_id
```

---

## Entities

### Project

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK auth.users; unique (one project per user in MVP) |
| product_name | text | |
| product_type | product_type_enum | SaaS, Mobile App, AI App, Service, Waitlist — constrained |
| product_description | text | primary AI prompt context |
| product_url | text | |
| target_audience | text | |
| problem_solved | text | |
| why_it_matters | text | |
| current_alternatives | text | |
| desired_action | text | |
| primary_cta | text | |
| tiktok_handle | text | stored without leading @; normalized on write |
| account_public | boolean | |
| manual_publish | boolean | |
| tracking_slug | text | unique; backend-generated; never client-computed |
| destination_url | text | initially = product_url; separately editable |
| context_version | integer | default 1; incremented when AI-relevant context changes |
| onboarded_at | timestamp | null until onboarding complete |
| created_at | timestamp | |
| updated_at | timestamp | |
| deleted_at | timestamp | nullable soft deletion |

**context_version increments when user changes:** product_description, target_audience, problem_solved, why_it_matters, desired_action, primary_cta, current_alternatives.  
Every AIRun records the context_version used. This prevents stale AI output from being applied after context changes.

---

### Hypothesis

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK Project |
| title | text | |
| statement | text | editable in /review |
| research_question | text | editable in /review |
| independent_variable | text | editable in /review |
| control_condition | text | editable in /review |
| treatment_condition | text | editable in /review |
| controlled_elements | text[] | chip list |
| contradiction_condition | text | editable in /review |
| primary_metric | text | AI-proposed; user can override |
| rationale | text | AI-generated |
| category | text | |
| status | hypothesis_status | generated, draft, approved, testing, tested, rejected |
| parent_hypothesis_id | uuid | FK Hypothesis self; null for cold-start |
| source_candidate_id | uuid | FK FollowUpCandidate; UNIQUE nullable; null for cold-start |
| relationship_type | hypothesis_relationship | replication, mechanism_isolation, parameter_optimization, generalization, counter_hypothesis, recovery_redesign |
| previous_learning | text | carried from FollowUpCandidate on acceptance |
| remaining_unknown | text | carried from FollowUpCandidate on acceptance |
| recommendation_reason | text | why AI marked the source candidate as recommended |
| created_by_ai_run_id | uuid | FK AIRun; null for manually created hypotheses |
| created_at | timestamp | |
| updated_at | timestamp | |
| approved_at | timestamp | |
| rejected_at | timestamp | |
| tested_at | timestamp | set when experiment reaches completed |

**Removed:** `source_insight_id` — derive via `source_candidate_id → FollowUpCandidate → Insight`.  
**UI labels:** `generated` = "Suggested", `tested` = "Learned"

---

### Experiment

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK Project |
| hypothesis_id | uuid | FK Hypothesis; UNIQUE |
| name | text | |
| cta | text | |
| tracking_window_hours | integer | default 72; CHECK > 0 |
| status | experiment_status | ready, in_progress, tracking, analyzing, completed, cancelled |
| hypothesis_design_snapshot | jsonb | immutable copy of approved design at experiment creation time |
| shared_constraints | jsonb | elements kept constant across all variants (replaces fixed script columns) |
| created_at | timestamp | |
| completed_at | timestamp | null until status = completed |

**hypothesis_design_snapshot** contains: researchQuestion, statement, independentVariable, controlCondition, treatmentCondition, primaryMetric, controlledElements, contradictionCondition — copied at experiment creation and never updated.

**shared_constraints** example:
```json
{
  "lesson": "I thought building the product was the hard part.",
  "product": "That is why I built Content Lab...",
  "cta": "Check the link in my bio.",
  "targetDurationLabel": "50s",
  "audience": "Technical founders",
  "format": "Talking head"
}
```

---

### Variant

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK Experiment |
| position | text | A, B, C; UNIQUE within experiment; CHECK IN ('A','B','C') |
| treatment_role | text | control, hypothesis_treatment, alternative_treatment |
| title | text | |
| variable_value | text | this variant's assigned value of the variable under test |
| hook | text | AI-generated; editable via Brief Editor |
| hook_delivery_note | text | AI-generated; editable |
| context | text | AI-generated; editable |
| on_screen_text | text | AI-generated; editable |
| script_sections | jsonb | flexible section array (see schema below) |
| status | variant_status | queued, ready_to_review, approved_for_recording, recorded |
| approved_for_recording_at | timestamp | |
| recorded_at | timestamp | |
| created_at | timestamp | |

**Variant.status is the design lifecycle only.** Publication state lives on Video.

**script_sections** schema:
```json
[
  {
    "key": "hook",
    "startSecond": 0,
    "endSecond": 5,
    "mode": "variable",
    "text": "I spent almost $2,000 on ads..."
  },
  {
    "key": "product",
    "startSecond": 25,
    "endSecond": 42,
    "mode": "controlled",
    "text": "That is why I built Content Lab..."
  }
]
```

`mode` values: `variable` or `controlled`. This replaces fixed `script_lesson`, `script_product`, `script_cta` columns and supports any future variable being tested.

**Frontend display status** is derived from Variant.status + current Video.status — not stored:
```
Variant.approved_for_recording + Video.tracking = display "Tracking"
Variant.recorded + Video.needs_url              = display "Paste URL"
```

---

### Video

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| variant_id | uuid | FK Variant |
| attempt_number | integer | starts at 1; UNIQUE with variant_id |
| is_current | boolean | true for one attempt per Variant; partial unique index |
| status | video_status | needs_url, validating, tracking, completed + error states |
| submitted_url | text | nullable; URL entered by founder |
| normalized_tiktok_url | text | nullable; canonical URL after validation |
| tiktok_video_id | text | nullable; extracted during validation; unique when set |
| user_confirmed_published_at | timestamp | nullable; when founder confirmed publication |
| published_at | timestamp | nullable; public timestamp when available |
| validated_at | timestamp | nullable; when backend confirmed video is accessible |
| tracking_started_at | timestamp | nullable; when tracking window opened |
| tracking_window_ends_at | timestamp | nullable; = tracking_started_at + experiment.tracking_window_hours |
| last_refreshed_at | timestamp | nullable; last metric collection time |
| created_at | timestamp | |
| updated_at | timestamp | |

`tracking_window_ends_at` is computed only after `tracking_started_at` is set — not at URL submission.

Error states: `invalid_url`, `account_mismatch`, `video_private`, `video_deleted`, `tracking_failed`

---

### VideoMetricSnapshot

TikTok-sourced metrics only. **Does not contain clicks** — clicks come from RedirectEvent via AttributionWindow.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| video_id | uuid | FK Video |
| collected_at | timestamp | |
| views | integer | CHECK >= 0 |
| likes | integer | CHECK >= 0 |
| comments | integer | CHECK >= 0 |
| collection_job_id | uuid | nullable; FK to background job that triggered collection |
| created_at | timestamp | |

---

### ExecutionObservation

Founder-reported quality of a **specific Video attempt** — not the abstract Variant.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| video_id | uuid | FK Video; UNIQUE |
| delivered_variable | boolean | nullable until founder answers |
| used_approved_hook | boolean | nullable |
| used_fixed_cta | boolean | nullable |
| actual_duration_seconds | integer | nullable; CHECK >= 0 |
| actual_product_reveal_seconds | integer | nullable; CHECK >= 0 |
| format_changed | boolean | nullable |
| audience_framing_changed | boolean | nullable |
| offer_changed | boolean | nullable |
| publishing_schedule_changed | boolean | nullable |
| reason | text | why variable was or was not delivered |
| notes | text | free-form qualitative notes |
| unexpected | text | surprising signals |
| perceived_drop_off_at | text | anecdotal timecode — founder-entered, never automated |
| founder_observed_comment_sentiment | text | founder-read sentiment — never automated |
| created_at | timestamp | |
| updated_at | timestamp | |

---

### RedirectEvent

Click event from the permanent tracking link. Attribution to a Variant happens via AttributionWindow, not directly on this table.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK Project |
| occurred_at | timestamp | |
| destination_url | text | URL the visitor was sent to |
| deduplication_key | text | unique; prevents double-counting |
| request_metadata | jsonb | minimum fields for dedup and abuse detection only |
| created_at | timestamp | |

---

### AttributionWindow

Defines the time interval during which RedirectEvents are attributed to a specific Video attempt. Under the **isolated windows** policy, windows are non-overlapping.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK Project |
| experiment_id | uuid | FK Experiment |
| variant_id | uuid | FK Variant |
| video_id | uuid | FK Video |
| method | attribution_method | isolated_window, exclusive_interval, experiment_only |
| starts_at | timestamp | |
| ends_at | timestamp | |
| created_at | timestamp | |

**Isolated window policy:** `starts_at` = Video.tracking_started_at; `ends_at` = Video.tracking_window_ends_at. No two windows for the same experiment overlap.

To count attributed clicks:
```sql
SELECT COUNT(*) FROM redirect_events r
JOIN attribution_windows w ON w.project_id = r.project_id
  AND r.occurred_at BETWEEN w.starts_at AND w.ends_at
WHERE w.video_id = ?
```

---

### ExperimentEvidenceSnapshot

Versioned per-experiment evidence record. Not permanently 1:1 — supports regeneration if attribution windows are refined.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK Experiment |
| version | integer | starts at 1 |
| status | snapshot_status | pending, ready, finalized |
| attribution_method | attribution_method | matches the method used for all items |
| generated_at | timestamp | |
| finalized_at | timestamp | null until status = finalized |
| created_by_job_id | uuid | nullable; background job that triggered generation |

---

### ExperimentEvidenceItem

One row per Variant in the snapshot. Identifies exactly which Video attempt and which metric interval were analyzed.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| evidence_snapshot_id | uuid | FK ExperimentEvidenceSnapshot |
| variant_id | uuid | FK Variant |
| video_id | uuid | FK Video; the specific attempt analyzed |
| start_metric_snapshot_id | uuid | FK VideoMetricSnapshot; first snapshot in interval |
| end_metric_snapshot_id | uuid | FK VideoMetricSnapshot; last snapshot in interval |
| views_delta | integer | views at end minus views at start |
| likes_delta | integer | |
| comments_delta | integer | |
| attributed_clicks | integer | RedirectEvents within AttributionWindow for this video |
| clicks_per_1k | numeric | = attributed_clicks / views_delta * 1000 |
| execution_observation_id | uuid | FK ExecutionObservation; nullable if not submitted |
| attribution_conditions | jsonb | snapshot of the AttributionWindow used |

---

### Insight

References the finalized evidence snapshot. Never duplicates raw metric columns.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK Experiment |
| evidence_snapshot_id | uuid | FK ExperimentEvidenceSnapshot; the exact snapshot analyzed |
| research_question | text | copied from hypothesis_design_snapshot at archival time |
| hypothesis_text | text | copied from hypothesis_design_snapshot |
| primary_metric | text | copied from hypothesis_design_snapshot |
| supported_learning | text | AI-generated |
| evidence_basis | text | AI-generated |
| do_not_infer_yet | text[] | AI-generated |
| recommended_next_test | text | AI-generated |
| limitations | text[] | AI-generated |
| outcome_label | text | AI-generated plain-language verdict |
| outcome_description | text | AI-generated |
| generated_at | timestamp | |

---

### FollowUpCandidate

Proposed next hypothesis. Dismissal does **not** create a rejected Hypothesis.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| insight_id | uuid | FK Insight |
| kind | text | Replication, MechanismIsolation, ParameterOptimization |
| statement | text | AI-generated |
| why_this_follows | text | AI-generated |
| recommended | boolean | AI marks one candidate |
| recommendation_reason | text | AI-generated; why this one is recommended |
| relationship_type | hypothesis_relationship | |
| previous_learning | text | carried to Hypothesis if accepted |
| remaining_unknown | text | carried to Hypothesis if accepted |
| status | candidate_status | proposed, accepted, dismissed |
| accepted_hypothesis_id | uuid | FK Hypothesis; null until accepted |
| created_at | timestamp | |

---

### AIRun

Provenance for AI-generated fields. Append-only. Entity field becomes canonical after user approval; AIRun preserves origin.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| entity_type | text | Hypothesis, Variant, Insight, FollowUpCandidate |
| entity_id | uuid | |
| field_name | text | e.g. hook, statement, supported_learning |
| model | text | e.g. claude-opus-4-7 |
| context_version | integer | Project.context_version at time of generation |
| prompt_hash | text | sha256 of prompt |
| output | text | raw generated text before user edits |
| created_at | timestamp | |

---

## State Enums and Transition Rules

### hypothesis_status

```
generated → draft
  trigger: user opens /review and edits any field

generated → approved
  trigger: user approves directly without drafting

draft → approved
  trigger: POST /hypotheses/{id}/approve
  guard: statement + independent_variable + primary_metric non-empty

approved → testing
  trigger: backend sets when experiment.status = in_progress

testing → tested
  trigger: backend sets when experiment.status = completed

generated|draft|approved → rejected
  trigger: explicit founder action

rejected → draft
  trigger: founder reopens
```

### experiment_status

```
ready → in_progress
  trigger: first variant's current Video reaches tracking

in_progress → tracking
  trigger: all three variants' current Videos are tracking

tracking → analyzing
  trigger: all AttributionWindows have ended (cron)
  side-effect: creates ExperimentEvidenceSnapshot, queues evidence collection

analyzing → completed
  trigger: Insight and FollowUpCandidates generated
  side-effect: sets hypothesis.tested_at; transitions hypothesis to tested

ready|in_progress|tracking → cancelled
  trigger: explicit cancellation
```

**Missing UI state:** `analyzing` needs a loading/waiting screen on the frontend.

### variant_status — design lifecycle only

```
queued → ready_to_review
  trigger: previous Variant's current Video reaches tracking
  (or: is position A, which has no predecessor)

ready_to_review → approved_for_recording
  trigger: POST /variants/{id}/approve

approved_for_recording → recorded
  trigger: POST /variants/{id}/confirm-recorded
```

### video_status — publication lifecycle only

```
(new row created) → needs_url
  trigger: POST /variants/{id}/videos creates a new Video attempt

needs_url → validating
  trigger: founder submits URL + passes 3-checkbox Publication modal

validating → tracking
  trigger: backend confirms URL valid and video public
  side-effect: sets tracking_started_at and tracking_window_ends_at
               creates AttributionWindow (method = isolated_window)

tracking → completed
  trigger: cron — tracking_window_ends_at has passed
  side-effect: closes AttributionWindow
```

Error states on Video: `invalid_url`, `account_mismatch`, `video_private`, `video_deleted`, `tracking_failed`

**Display status derivation (never stored):**

| Variant status | Current Video status | Display |
|---|---|---|
| queued | n/a | Queued |
| ready_to_review | n/a | Ready to Record |
| approved_for_recording | n/a | Approved |
| recorded | needs_url | Paste URL |
| recorded | validating | Validating |
| recorded | tracking | Tracking |
| recorded | completed | Completed |
| recorded | any error | Error (+ error code) |

### candidate_status

```
proposed → accepted
  trigger: POST /follow-up-candidates/{id}/accept
  side-effect: creates Hypothesis with lineage from candidate
               sets candidate.accepted_hypothesis_id

proposed → dismissed
  trigger: POST /follow-up-candidates/{id}/dismiss
  side-effect: nothing — no Hypothesis is created
```

---

## Attribution Policy: Isolated Windows

With isolated windows, Variant A publishes first and its AttributionWindow runs for exactly `tracking_window_hours` before Variant B publishes. Windows are strictly non-overlapping.

```
A publishes  ──[  72h window A  ]──> B publishes ──[  72h window B  ]──> C publishes ──[  72h window C  ]──>
```

Click count for a Variant:
```sql
SELECT COUNT(DISTINCT r.deduplication_key)
FROM redirect_events r
JOIN attribution_windows w
  ON w.project_id = r.project_id
  AND r.occurred_at BETWEEN w.starts_at AND w.ends_at
WHERE w.video_id = :video_id
```

Clicks/1K for evidence:
```
attributed_clicks / views_delta * 1000
```

`views_delta` uses the metric snapshot taken at window start and end — not total lifetime views — so all three variants have comparable denominators.

---

## Required Constraints

```sql
-- Tenancy
UNIQUE (projects.user_id)
UNIQUE (projects.tracking_slug)

-- Hypothesis lineage
UNIQUE (hypotheses.source_candidate_id)  -- nullable unique

-- Experiment design integrity
UNIQUE (experiments.hypothesis_id)

-- Variant positioning
UNIQUE (variants.experiment_id, variants.position)
CHECK  (variants.position IN ('A', 'B', 'C'))

-- Video attempt integrity
UNIQUE (videos.variant_id, videos.attempt_number)
-- Partial unique index for is_current:
CREATE UNIQUE INDEX ON videos (variant_id) WHERE is_current = true;
UNIQUE (videos.tiktok_video_id) WHERE tiktok_video_id IS NOT NULL
UNIQUE (videos.normalized_tiktok_url) WHERE normalized_tiktok_url IS NOT NULL

-- Metric non-negativity
CHECK (video_metric_snapshots.views >= 0)
CHECK (video_metric_snapshots.likes >= 0)
CHECK (video_metric_snapshots.comments >= 0)
CHECK (execution_observations.actual_duration_seconds >= 0)

-- Evidence integrity
CHECK (experiments.tracking_window_hours > 0)
```

Three Variants per Experiment cannot be enforced by a check constraint alone — create all three in one backend transaction and validate count before setting status = ready.

---

## View Models (unchanged from previous version except where noted)

### ProjectDetail
Added: trackingUrl (computed), contextVersion, updatedAt

### ExperimentDetail
Now embeds hypothesisDesignSnapshot fields directly (researchQuestion, statement, independentVariable, controlledElements) — reads from snapshot, not live Hypothesis.

### VariantDetail
Added: currentVideo (Video + ExecutionObservation), scriptSections array  
Removed: variableUnderTest → replaced by variableValue

### VideoSummary
New fields: attemptNumber, isCurrent, validatedAt, trackingStartedAt, attributedClicks (from latest AttributionWindow)  
Removed: clicks, clicksPer1k (now from EvidenceItem, not snapshot)

### InsightDetail
Added: evidenceItems (array — one per Variant — with views_delta, attributed_clicks, clicks_per_1k, video attempt reference, execution observation summary)  
Removed: raw views/clicks duplication

---

## Stored vs Derived (revised)

| Field | Classification | Notes |
|---|---|---|
| Project.tracking_slug | stored | Backend-generated once; never recomputed |
| Project.tracking_url | derived | contentlab.app/p/{slug} — computed at response time |
| Project.context_version | stored | Incremented by backend on relevant field changes |
| Hypothesis.source_insight_id | removed | Derive via source_candidate_id → FollowUpCandidate → Insight |
| Experiment.hypothesis_design_snapshot | stored (immutable) | Copied at creation; Hypothesis edits do not affect it |
| Variant.display_status | derived | Computed from Variant.status + current Video.status |
| Video.tracking_window_ends_at | stored | Computed at tracking start; stored for query performance |
| VideoMetricSnapshot.clicks | removed | Clicks come from RedirectEvent + AttributionWindow |
| ExperimentEvidenceItem.clicks_per_1k | stored | Computed at evidence finalization; stored immutably |
| Insight.lift | derived | Computed at query from EvidenceItems |
| ExperimentEvidenceSnapshot | stored (versioned) | Not permanently 1:1 with Experiment |

---

## AI Provenance (revised)

AIRun now records `context_version` alongside the entity reference. This makes it possible to detect when AI output was generated from a stale project context.

Invalidation rule: if `hypothesis.created_by_ai_run_id → AIRun.context_version` is less than the current `Project.context_version`, the hypothesis was generated before the user updated their context. Surface a warning in the UI.

---

## FakeIntelligenceProvider Interface

```typescript
interface IntelligenceProvider {
  generateHypotheses(project: ProjectDetail): Promise<HypothesisPayload[]>
  reviseBrief(variant: VariantDetail, instruction: string): Promise<VariantBriefEdit>
  generateInsight(snapshot: ExperimentEvidenceSnapshot, items: ExperimentEvidenceItem[]): Promise<InsightPayload>
  generateCandidates(insight: InsightDetail): Promise<FollowUpCandidatePayload[]>
}
```

---

## Pre-Migration Checklist (all items must be confirmed)

- [x] **Attribution policy:** Isolated windows locked.
- [x] **Retry model:** One Experiment per Hypothesis; reruns at Video level locked.
- [x] **Variant/Video state separation:** Variant owns design lifecycle; Video owns publication lifecycle.
- [x] **Script storage:** Flexible `script_sections` JSONB on Variant; `shared_constraints` JSONB on Experiment.
- [ ] `projects.user_id` auth integration decided (Supabase Auth or custom).
- [ ] `RedirectEvent` deduplication strategy confirmed (device fingerprint? session token?).
- [ ] Background job infrastructure decided (cron for window close, metric collection, insight generation).
- [ ] `context_version` increment triggers confirmed with product — which field changes are meaningful enough to invalidate prior AI output.
