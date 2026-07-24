# Content Lab — Domain Model v3 (Migration-Ready)

**Attribution policy:** Isolated windows — 72h per Variant, strictly sequential.  
**Retry policy:** One Experiment per Hypothesis; reruns at Video level.  
**Cancellation:** Terminal — clone Hypothesis → new draft → new Experiment.  
**Script storage:** Flexible JSONB with schema versioning.  
**Tenant isolation:** project_id on every tenant-owned table; composite FK enforcement.

---

## Entity List (14 tables)

```
projects
hypotheses
experiments
variants
videos
video_metric_snapshots
execution_observations
redirect_events
attribution_windows
experiment_evidence_snapshots
experiment_evidence_items
insights
follow_up_candidates
ai_runs
```

---

## Tenant Isolation Pattern

Every tenant-owned table carries `project_id`. Cross-table joins enforce tenant consistency via composite FKs:

```sql
-- Parent: experiments
ALTER TABLE experiments ADD CONSTRAINT uq_experiments_id_project
  UNIQUE (id, project_id);

-- Child: variants
ALTER TABLE variants ADD CONSTRAINT fk_variants_experiment_project
  FOREIGN KEY (experiment_id, project_id)
  REFERENCES experiments (id, project_id);
```

Apply the same pattern at every level of the hierarchy. This prevents a row in one tenant from referencing a row in another tenant even if IDs are accidentally reused.

---

## Entities

### projects

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK auth.users; partial unique index WHERE deleted_at IS NULL |
| product_name | text | context_version trigger |
| product_type | product_type | enum: SaaS, Mobile App, AI App, Service, Waitlist |
| product_description | text | context_version trigger |
| product_url | text | context_version trigger |
| target_audience | text | context_version trigger |
| problem_solved | text | context_version trigger |
| why_it_matters | text | context_version trigger |
| current_alternatives | text | context_version trigger |
| desired_action | text | context_version trigger |
| primary_cta | text | context_version trigger |
| tiktok_handle | text | context_version trigger; stored without @ prefix |
| account_public | boolean | |
| manual_publish | boolean | |
| tracking_slug | text | UNIQUE (permanent, survives soft deletion) |
| destination_url | text | initially = product_url; separately editable |
| context_version | integer | default 1; backend increments on any trigger-field change |
| onboarded_at | timestamptz | null until onboarding complete |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| deleted_at | timestamptz | nullable; soft deletion |

**Constraints:**
```sql
CREATE UNIQUE INDEX one_active_project_per_user
  ON projects (user_id)
  WHERE deleted_at IS NULL;

UNIQUE (tracking_slug);  -- permanent; reserved even after soft deletion
```

`context_version` is incremented by the backend (trigger or service layer), not the client. Every AIRun records the context_version at generation time.

---

### hypotheses

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects; direct tenant boundary |
| title | text | |
| statement | text | editable in /review |
| research_question | text | editable |
| independent_variable | text | editable |
| control_condition | text | editable |
| treatment_condition | text | editable |
| controlled_elements | text[] | chip list |
| contradiction_condition | text | editable |
| primary_metric | primary_metric | enum; see §Enums |
| rationale | text | AI-generated |
| category | text | |
| status | hypothesis_status | generated, draft, approved, testing, tested, rejected |
| parent_hypothesis_id | uuid | FK hypotheses self; null for cold-start |
| source_candidate_id | uuid | FK follow_up_candidates; UNIQUE nullable; null for cold-start |
| relationship_type | hypothesis_relationship | null for cold-start; required for follow-up |
| previous_learning | text | carried from candidate on acceptance |
| remaining_unknown | text | carried from candidate on acceptance |
| recommendation_reason | text | why AI marked source candidate as recommended |
| created_by_ai_run_id | uuid | FK ai_runs; nullable for manually created |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| approved_at | timestamptz | |
| rejected_at | timestamptz | |
| tested_at | timestamptz | set when linked experiment.status = completed |

**Constraints:**
```sql
UNIQUE (source_candidate_id);  -- nullable unique

-- Lineage consistency (enforce in backend service or CHECK):
-- Cold-start: parent_hypothesis_id IS NULL AND source_candidate_id IS NULL
--             AND relationship_type IS NULL
-- Follow-up:  parent_hypothesis_id IS NOT NULL
--             AND source_candidate_id IS NOT NULL
--             AND relationship_type IS NOT NULL

-- Cross-project guard (enforce in backend):
-- parent_hypothesis_id.project_id must equal this hypothesis.project_id
-- source_candidate_id.project_id must equal this hypothesis.project_id
-- source_candidate → insight → experiment → hypothesis must be the parent
```

**Edit policy:** Once a linked Experiment exists (experiments.hypothesis_id = this.id), material edits to this Hypothesis are disabled. Changes must go through cloning to a new draft Hypothesis.

UI labels: `generated` = "Suggested", `tested` = "Learned"

---

### experiments

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects; UNIQUE (id, project_id) for composite FK |
| hypothesis_id | uuid | FK hypotheses; UNIQUE |
| name | text | |
| tracking_window_hours | integer | default 72; CHECK > 0 |
| status | experiment_status | ready, in_progress, tracking, analyzing, completed, cancelled |
| hypothesis_design_snapshot | jsonb | immutable; copied at creation; schemaVersion: 1 |
| shared_constraints | jsonb | controlled elements kept constant; schemaVersion: 1 |
| design_schema_version | integer | default 1; increment when snapshot shape changes |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| started_at | timestamptz | set when first Video reaches tracking |
| tracking_completed_at | timestamptz | set when C's 72h window closes |
| analysis_started_at | timestamptz | set when evidence generation begins |
| completed_at | timestamptz | set when Insight + candidates are ready |
| cancelled_at | timestamptz | nullable |
| cancellation_reason | text | nullable |

**Removed:** `cta` column — CTA lives in `shared_constraints` and `hypothesis_design_snapshot`.

**hypothesis_design_snapshot** example:
```json
{
  "schemaVersion": 1,
  "researchQuestion": "...",
  "statement": "...",
  "independentVariable": "Opening angle",
  "controlCondition": "...",
  "treatmentCondition": "...",
  "primaryMetric": "clicks_per_1k_views",
  "controlledElements": ["Lesson", "Product", "CTA", "Duration"],
  "contradictionCondition": "..."
}
```

**Cancellation semantics:** Terminal. A cancelled Experiment cannot be resumed. The founder must clone the Hypothesis to a new draft and start a new Experiment.

**State transitions:**
```
ready → in_progress        : A's Video reaches tracking; sets started_at
in_progress → tracking     : A's window closes, B publishes, then B's, then C tracks
tracking → analyzing       : C's window closes; sets tracking_completed_at; triggers evidence job
analyzing → completed      : Evidence snapshot + Insight + candidates persisted; sets completed_at
any → cancelled            : explicit; sets cancelled_at
```

Note: `in_progress` and `tracking` are both in-flight states during the 9-day sequential process.

---

### variants

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects; composite FK with experiment_id |
| experiment_id | uuid | FK experiments; composite FK (experiment_id, project_id) |
| position | variant_position | enum: A, B, C |
| treatment_role | treatment_role | enum: control, hypothesis_treatment, alternative_treatment |
| title | text | |
| variable_value | text | this variant's assigned value of the independent variable |
| hook | text | current canonical approved text |
| hook_delivery_note | text | |
| context | text | |
| on_screen_text | text | |
| script_sections | jsonb | [{key, startSecond, endSecond, mode, text}]; schemaVersion: 1 |
| recording_guidance | jsonb | advisory instructions (camera, delivery, background, duration) |
| status | variant_design_status | queued, ready_to_review, approved_for_recording, recorded |
| generated_by_ai_run_id | uuid | FK ai_runs; nullable |
| approved_for_recording_at | timestamptz | |
| recorded_at | timestamptz | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Constraints:**
```sql
UNIQUE (experiment_id, position);
UNIQUE (experiment_id, treatment_role);
CHECK  (position IN ('A', 'B', 'C'));

-- Enforced mapping (backend transaction):
-- A → control
-- B → hypothesis_treatment
-- C → alternative_treatment
```

**Sequential unlocking rule:**
```
A: queued → ready_to_review immediately (no predecessor)
B: queued → ready_to_review only after A's current Video.status = completed
C: queued → ready_to_review only after B's current Video.status = completed
```

The backend unlocks variants; the client must not mutate B or C from queued.

**script_sections** schema (schemaVersion: 1):
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

No publication or tracking error states on Variant. Those belong to Video.

---

### videos

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects; composite FK with variant_id |
| variant_id | uuid | FK variants; composite FK (variant_id, project_id) |
| attempt_number | integer | starts at 1; UNIQUE (variant_id, attempt_number) |
| is_current | boolean | partial unique index: UNIQUE (variant_id) WHERE is_current = true |
| status | video_status | needs_url, validating, tracking, completed + error states |
| submitted_url | text | nullable; raw URL entered by founder |
| normalized_tiktok_url | text | nullable; UNIQUE WHERE NOT NULL |
| tiktok_video_id | text | nullable; UNIQUE WHERE NOT NULL; extracted during validation |
| user_confirmed_published_at | timestamptz | nullable; when founder confirmed via 3-checkbox modal |
| published_at | timestamptz | nullable; public timestamp when available |
| validated_at | timestamptz | nullable |
| tracking_started_at | timestamptz | nullable |
| tracking_window_ends_at | timestamptz | nullable; set at tracking start = tracking_started_at + window_hours |
| last_refreshed_at | timestamptz | nullable |
| validation_error_code | text | nullable; e.g. invalid_url, video_private |
| validation_error_detail | text | nullable; human-readable description |
| created_at | timestamptz | |
| updated_at | timestamptz | |

**Error states:** invalid_url, account_mismatch, video_private, video_deleted, tracking_failed

`tracking_window_ends_at` is computed at `tracking_started_at` assignment — not at URL submission.

---

### video_metric_snapshots

TikTok public metrics only. No attributed clicks.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects; composite FK with video_id |
| video_id | uuid | FK videos; composite FK (video_id, project_id) |
| collected_at | timestamptz | |
| views | integer | CHECK >= 0 |
| likes | integer | CHECK >= 0 |
| comments | integer | CHECK >= 0 |
| collection_job_id | uuid | nullable |
| created_at | timestamptz | |

---

### execution_observations

Tied to a specific Video attempt. Renamed from VariantObservation.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| video_id | uuid | FK videos; UNIQUE |
| delivered_variable | boolean | nullable until founder answers |
| used_approved_hook | boolean | nullable |
| used_fixed_cta | boolean | nullable |
| actual_duration_seconds | integer | nullable; CHECK >= 0 |
| actual_product_reveal_seconds | integer | nullable; CHECK >= 0 |
| format_changed | boolean | nullable |
| audience_framing_changed | boolean | nullable |
| offer_changed | boolean | nullable |
| publishing_schedule_changed | boolean | nullable |
| reason | text | |
| notes | text | |
| unexpected | text | |
| perceived_drop_off_at | text | anecdotal timecode; founder-entered; not automated |
| founder_observed_comment_sentiment | text | founder-read; not automated |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

### redirect_events

Individual permanent bio-link visits. Attribution to a variant happens via attribution_windows.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| attribution_window_id | uuid | nullable FK attribution_windows; set if click falls within an active window |
| occurred_at | timestamptz | |
| destination_url | text | |
| deduplication_key | text | UNIQUE |
| request_metadata | jsonb | minimum fields for dedup and abuse detection |
| created_at | timestamptz | |

---

### attribution_windows

Defines the interval during which redirect_events are attributed to a Video. Enforces non-overlap at the database level.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| experiment_id | uuid | FK experiments |
| variant_id | uuid | FK variants |
| video_id | uuid | FK videos; UNIQUE |
| starts_at | timestamptz | = Video.tracking_started_at |
| ends_at | timestamptz | = Video.tracking_window_ends_at |
| status | attribution_window_status | scheduled, active, closed, cancelled |
| created_at | timestamptz | |

**Constraints:**
```sql
UNIQUE (video_id);
CHECK (ends_at > starts_at);

-- Non-overlap enforcement (requires btree_gist extension):
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE attribution_windows
  ADD CONSTRAINT no_overlapping_active_windows
  EXCLUDE USING gist (
    project_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
  )
  WHERE (status IN ('scheduled', 'active'));
```

This makes the isolated-window policy a database invariant.

---

### experiment_evidence_snapshots

Versioned per experiment. Immutable after finalization.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| experiment_id | uuid | FK experiments; UNIQUE (id, project_id) for composite FK |
| version | integer | starts at 1 |
| status | snapshot_status | pending, ready, finalized |
| attribution_method | text | isolated_window (locked) |
| generated_at | timestamptz | |
| finalized_at | timestamptz | null until status = finalized |
| created_by_job_id | uuid | nullable |

---

### experiment_evidence_items

One per Variant. Identifies exact Video attempt, metric interval, and attributed clicks.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| evidence_snapshot_id | uuid | FK experiment_evidence_snapshots; composite FK (id, project_id) |
| variant_id | uuid | FK variants |
| video_id | uuid | FK videos; the specific attempt analyzed |
| start_metric_snapshot_id | uuid | FK video_metric_snapshots; first snapshot in interval |
| end_metric_snapshot_id | uuid | FK video_metric_snapshots; last snapshot in interval |
| views_delta | integer | end.views - start.views |
| likes_delta | integer | |
| comments_delta | integer | |
| attributed_clicks | integer | COUNT of redirect_events within attribution_window |
| clicks_per_1k | numeric | attributed_clicks / views_delta * 1000; stored immutably at finalization |
| execution_observation_id | uuid | nullable FK execution_observations |
| attribution_window_id | uuid | FK attribution_windows; exact window used |
| attribution_conditions | jsonb | snapshot of window details at finalization |

---

### insights

References finalized evidence snapshot. Never duplicates raw metric columns.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| experiment_id | uuid | FK experiments |
| evidence_snapshot_id | uuid | FK experiment_evidence_snapshots; finalized snapshot |
| research_question | text | copied from hypothesis_design_snapshot |
| hypothesis_text | text | copied |
| primary_metric | primary_metric | enum; copied |
| supported_learning | text | AI-generated |
| evidence_basis | text | AI-generated |
| do_not_infer_yet | text[] | AI-generated |
| recommended_next_test | text | AI-generated |
| limitations | text[] | AI-generated |
| outcome_label | text | AI-generated |
| outcome_description | text | AI-generated |
| generated_at | timestamptz | |

---

### follow_up_candidates

Dismissal does not create a rejected Hypothesis.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects; UNIQUE (id, project_id) for composite FK |
| insight_id | uuid | FK insights |
| kind | candidate_kind | enum: Replication, MechanismIsolation, ParameterOptimization |
| statement | text | AI-generated |
| why_this_follows | text | AI-generated |
| recommended | boolean | AI marks one per Insight |
| recommendation_reason | text | AI-generated |
| relationship_type | hypothesis_relationship | |
| previous_learning | text | carried to new Hypothesis if accepted |
| remaining_unknown | text | carried to new Hypothesis if accepted |
| status | candidate_status | proposed, accepted, dismissed |
| accepted_hypothesis_id | uuid | nullable FK hypotheses; set on acceptance |
| created_at | timestamptz | |

---

### ai_runs

Provenance for every AI generation. Append-only.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| entity_type | text | Hypothesis, Variant, Insight, FollowUpCandidate |
| entity_id | uuid | |
| field_name | text | e.g. hook, statement, supported_learning (null for batch ops) |
| operation | text | generateHypotheses, reviseBrief, generateInsight, generateCandidates |
| model | text | e.g. claude-opus-4-7 |
| prompt_version | text | version identifier of the prompt template used |
| context_version | integer | projects.context_version at time of generation |
| input_payload | jsonb | full prompt context sent to the model |
| output_payload | jsonb | raw structured output from the model |
| validation_result | text | valid, invalid, parse_error |
| token_usage | jsonb | {inputTokens, outputTokens} |
| cost_usd | numeric | nullable |
| latency_ms | integer | nullable |
| status | text | success, failed, timeout |
| created_at | timestamptz | |

---

## Enums

```sql
CREATE TYPE product_type AS ENUM ('SaaS', 'Mobile App', 'AI App', 'Service', 'Waitlist');

CREATE TYPE primary_metric AS ENUM (
  'clicks_per_1k_views',
  'comments_per_1k_views',
  'views',
  'product_clicks',
  'comments'
);

CREATE TYPE hypothesis_status AS ENUM (
  'generated', 'draft', 'approved', 'testing', 'tested', 'rejected'
);

CREATE TYPE hypothesis_relationship AS ENUM (
  'replication', 'mechanism_isolation', 'parameter_optimization',
  'generalization', 'counter_hypothesis', 'recovery_redesign'
);

CREATE TYPE experiment_status AS ENUM (
  'ready', 'in_progress', 'tracking', 'analyzing', 'completed', 'cancelled'
);

CREATE TYPE variant_position AS ENUM ('A', 'B', 'C');

CREATE TYPE treatment_role AS ENUM (
  'control', 'hypothesis_treatment', 'alternative_treatment'
);

CREATE TYPE variant_design_status AS ENUM (
  'queued', 'ready_to_review', 'approved_for_recording', 'recorded'
);

CREATE TYPE video_status AS ENUM (
  'needs_url', 'validating', 'tracking', 'completed',
  'invalid_url', 'account_mismatch', 'video_private', 'video_deleted', 'tracking_failed'
);

CREATE TYPE attribution_window_status AS ENUM (
  'scheduled', 'active', 'closed', 'cancelled'
);

CREATE TYPE snapshot_status AS ENUM ('pending', 'ready', 'finalized');

CREATE TYPE candidate_kind AS ENUM (
  'Replication', 'MechanismIsolation', 'ParameterOptimization'
);

CREATE TYPE candidate_status AS ENUM ('proposed', 'accepted', 'dismissed');
```

UI label mapping for primary_metric:
```
clicks_per_1k_views  → "Clicks / 1K Views"
comments_per_1k_views → "Comments / 1K Views"
views               → "Views"
product_clicks      → "Product Clicks"
comments            → "Comments"
```

---

## Sequential Variant Unlocking

```
A:
  status = ready_to_review immediately (no predecessor)
  → approved_for_recording: POST /variants/{a_id}/approve
  → recorded: POST /variants/{a_id}/confirm-recorded
  → Video A created, tracked for 72h

B:
  status = queued until A's current Video.status = completed
  Backend unlocks B → ready_to_review; client cannot do this

C:
  status = queued until B's current Video.status = completed
  Backend unlocks C → ready_to_review

After C completes:
  tracking_completed_at set on Experiment
  Experiment transitions to analyzing
```

Total experiment duration: approximately 9 days (3 × 72h + transitions).

---

## Display Status Derivation (never stored)

| Variant.status | Current Video.status | Frontend display |
|---|---|---|
| queued | n/a | Queued |
| ready_to_review | n/a | Ready to Record |
| approved_for_recording | n/a | Approved |
| recorded | needs_url | Paste URL |
| recorded | validating | Validating |
| recorded | tracking | Tracking |
| recorded | completed | Completed |
| recorded | any error state | Error (show validation_error_code) |

---

## Stored vs Derived (final)

| Field | Classification | Notes |
|---|---|---|
| projects.tracking_slug | stored (permanent) | Never changes; never released, even after soft deletion |
| projects.tracking_url | derived | contentlab.app/p/{slug} — constructed at response time |
| projects.context_version | stored | Incremented by backend on trigger-field changes |
| hypotheses.source_insight_id | removed | Derive: source_candidate_id → follow_up_candidates → insights |
| experiments.cta | removed | Lives in shared_constraints and hypothesis_design_snapshot |
| experiments.hypothesis_design_snapshot | stored (immutable) | Copied at creation; never updated |
| variants.display_status | derived | Variant.status + current Video.status combination |
| videos.tracking_window_ends_at | stored | Computed at tracking_started_at assignment |
| video_metric_snapshots.clicks | removed | Clicks come from redirect_events via attribution_windows |
| experiment_evidence_items.clicks_per_1k | stored (immutable) | Computed at evidence finalization; never recalculated |
| insights.lift | derived | Computed at query from evidence items |
| experiment_evidence_snapshots | stored (versioned) | Not permanently 1:1; supports regeneration |

---

## Open Infrastructure Decisions (4 remaining)

These are not schema-structural. Migrations can begin once locked:

1. **Auth integration** — Supabase Auth or custom. Determines `projects.user_id` FK target.
2. **RedirectEvent deduplication** — Key strategy: device fingerprint, session token, or IP+UA hash. Determines `deduplication_key` population logic.
3. **Background job infrastructure** — pg_cron, Supabase Edge Functions, or external scheduler. Drives Experiment status transitions and metric collection.
4. **context_version increment triggers** — Confirm the complete field list above is correct for the project's AI operations.

---

## Pre-Migration Checklist

- [x] Click attribution: isolated 72h windows locked
- [x] Retry policy: Video-level locked
- [x] Cancellation: terminal locked
- [x] Script storage: flexible JSONB with schemaVersion locked
- [x] project_id on every tenant-owned table
- [x] Composite FK enforcement pattern defined
- [x] Partial unique index on projects.user_id WHERE deleted_at IS NULL
- [x] tracking_slug permanently reserved
- [x] primary_metric is an enum
- [x] Hypothesis lineage consistency rules defined
- [x] Hypothesis edit policy after Experiment creation defined
- [x] Experiment.cta removed; CTA lives in shared_constraints
- [x] Experiment lifecycle timestamps defined
- [x] Variant design status separated from Video publication status
- [x] Sequential unlocking (B after A completes, C after B completes)
- [x] Video owns attempt_number + is_current; validation error fields
- [x] VideoMetricSnapshot contains only TikTok metrics (no clicks)
- [x] ExecutionObservation tied to Video, not Variant
- [x] AttributionWindow no-overlap enforced via range exclusion constraint
- [x] All timestamps are timestamptz
- [x] AIRun expanded with operation, input/output payload, cost, latency, status
- [ ] Auth integration decided
- [ ] RedirectEvent deduplication strategy decided
- [ ] Background job infrastructure decided
- [ ] context_version trigger field list confirmed with product
