# Content Lab — Domain Model v4 (Final)

**All decisions locked. Ready for migrations.**

---

## Locked Decisions

| Decision | Choice |
|---|---|
| Click attribution | Isolated 72h windows, strictly sequential |
| Retry policy | One Experiment per Hypothesis; reruns at Video level |
| Cancellation | Terminal — clone Hypothesis to restart |
| Script storage | Flexible JSONB with schemaVersion |
| Auth | Supabase Auth; projects.user_id → auth.users.id |
| Deduplication | First-party cookie + server-side HMAC fallback; one unique click per visitor per attribution window |
| Background jobs | Postgres-backed jobs table + dedicated scheduler/worker processes |
| context_version | Broad MVP field list; database trigger on UPDATE |

---

## Migration Plan

```
001_domain_schema.sql    — extensions, enums, domain tables, indexes, constraints, RLS, triggers
002_job_infrastructure.sql — jobs table, claim functions
```

Seed data and development fixtures go in a separate file or script — never in a production migration.

---

## Entity List (15 tables)

```
projects
project_facts
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

## Entities

### projects

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK default gen_random_uuid() |
| user_id | uuid | FK auth.users(id); partial unique WHERE deleted_at IS NULL |
| product_name | text | context_version trigger |
| product_type | product_type | enum; context_version trigger |
| product_description | text | context_version trigger |
| product_url | text | context_version trigger |
| target_audience | text | context_version trigger |
| problem_solved | text | context_version trigger |
| why_it_matters | text | context_version trigger |
| current_alternatives | text | context_version trigger |
| desired_action | text | context_version trigger |
| primary_cta | text | context_version trigger |
| tiktok_handle | text | context_version trigger; stored without @ |
| account_public | boolean | |
| manual_publish | boolean | |
| tracking_slug | text | UNIQUE permanent |
| destination_url | text | initially = product_url; separately editable |
| context_version | integer | default 1; DB trigger increments on listed field changes |
| onboarded_at | timestamptz | |
| created_at | timestamptz | default now() |
| updated_at | timestamptz | |
| deleted_at | timestamptz | nullable; soft deletion |

```sql
CREATE UNIQUE INDEX one_active_project_per_user
  ON projects (user_id) WHERE deleted_at IS NULL;
UNIQUE (tracking_slug);  -- permanent; not lifted on soft deletion
```

---

### project_facts

Verified founder facts supplied to AI script generation. Only status = 'verified' facts enter prompt context.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| fact_text | text | the factual statement |
| category | text | e.g. spend, customer_count, outcome, personal_story |
| source | text | how this was confirmed |
| status | fact_status | verified, rejected |
| verified_at | timestamptz | nullable until verified |
| created_at | timestamptz | |
| updated_at | timestamptz | |

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
| controlled_elements | text[] | |
| contradiction_condition | text | editable |
| primary_metric | primary_metric | enum |
| rationale | text | AI-generated |
| category | text | |
| status | hypothesis_status | generated, draft, approved, testing, tested, rejected |
| parent_hypothesis_id | uuid | FK hypotheses self; null = cold-start |
| source_candidate_id | uuid | FK follow_up_candidates; UNIQUE nullable; null = cold-start |
| relationship_type | hypothesis_relationship | null = cold-start; required for follow-up |
| previous_learning | text | from candidate on acceptance |
| remaining_unknown | text | from candidate on acceptance |
| recommendation_reason | text | why AI marked source candidate recommended |
| created_by_ai_run_id | uuid | FK ai_runs; nullable |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| approved_at | timestamptz | |
| rejected_at | timestamptz | |
| tested_at | timestamptz | set when linked Experiment completes |

**Lineage consistency (enforced in backend service):**
- Cold-start: parent_hypothesis_id IS NULL AND source_candidate_id IS NULL AND relationship_type IS NULL
- Follow-up: all three are NOT NULL
- parent_hypothesis_id.project_id must equal this hypothesis.project_id
- source_candidate_id.project_id must equal this hypothesis.project_id

**Edit policy:** Material edits disabled once a linked Experiment exists.

---

### experiments

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK; UNIQUE (id, project_id) enables composite FK |
| project_id | uuid | FK projects |
| hypothesis_id | uuid | FK hypotheses; UNIQUE |
| name | text | |
| tracking_window_hours | integer | default 72; CHECK > 0 |
| status | experiment_status | ready, in_progress, tracking, analyzing, completed, cancelled |
| hypothesis_design_snapshot | jsonb | immutable copy at creation; schemaVersion: 1 |
| shared_constraints | jsonb | controlled elements; schemaVersion: 1 |
| design_schema_version | integer | default 1 |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| started_at | timestamptz | when first Video reaches tracking |
| tracking_completed_at | timestamptz | when C's window closes |
| analysis_started_at | timestamptz | when evidence job begins |
| completed_at | timestamptz | when Insight and candidates are persisted |
| cancelled_at | timestamptz | nullable |
| cancellation_reason | text | nullable |

**Status transitions (in_progress and tracking cycle):**
```
ready → in_progress          A available, not yet tracking
in_progress → tracking       A's window opens
tracking → in_progress       A's window closes, B unlocked
in_progress → tracking       B's window opens
tracking → in_progress       B's window closes, C unlocked
in_progress → tracking       C's window opens
tracking → analyzing         C's window closes; sets tracking_completed_at
analyzing → completed        Insight + candidates persisted; sets completed_at
any → cancelled              terminal
```

---

### variants

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | composite FK (experiment_id, project_id) → experiments |
| experiment_id | uuid | FK experiments |
| position | variant_position | enum A, B, C |
| treatment_role | treatment_role | enum control, hypothesis_treatment, alternative_treatment |
| title | text | |
| variable_value | text | assigned value of independent variable |
| hook | text | AI-generated; editable |
| hook_delivery_note | text | AI-generated; editable |
| context | text | AI-generated; editable |
| on_screen_text | text | AI-generated; editable |
| script_sections | jsonb | [{key, startSecond, endSecond, mode, text}]; schemaVersion: 1 |
| recording_guidance | jsonb | advisory instructions |
| status | variant_design_status | queued, ready_to_review, approved_for_recording, recorded |
| generated_by_ai_run_id | uuid | FK ai_runs; nullable |
| approved_for_recording_at | timestamptz | |
| recorded_at | timestamptz | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

```sql
UNIQUE (experiment_id, position);
UNIQUE (experiment_id, treatment_role);
```

Sequential unlocking: B → ready_to_review only after A's current Video.status = completed. C after B.

---

### videos

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | composite FK (variant_id, project_id) → variants |
| variant_id | uuid | FK variants |
| attempt_number | integer | starts 1; UNIQUE (variant_id, attempt_number) |
| is_current | boolean | PARTIAL UNIQUE (variant_id) WHERE is_current = true |
| status | video_status | enum |
| submitted_url | text | nullable |
| normalized_tiktok_url | text | nullable; UNIQUE WHERE NOT NULL |
| tiktok_video_id | text | nullable; UNIQUE WHERE NOT NULL |
| user_confirmed_published_at | timestamptz | nullable |
| published_at | timestamptz | nullable |
| validated_at | timestamptz | nullable |
| tracking_started_at | timestamptz | nullable |
| tracking_window_ends_at | timestamptz | nullable; set at tracking_started_at |
| last_refreshed_at | timestamptz | nullable |
| validation_error_code | text | nullable |
| validation_error_detail | text | nullable |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

### video_metric_snapshots

TikTok public metrics only. No clicks.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | composite FK (video_id, project_id) → videos |
| video_id | uuid | FK videos |
| collected_at | timestamptz | |
| views | integer | CHECK >= 0 |
| likes | integer | CHECK >= 0 |
| comments | integer | CHECK >= 0 |
| collection_job_id | uuid | nullable |
| created_at | timestamptz | |

---

### execution_observations

Tied to Video (not Variant). Each recording can differ.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| video_id | uuid | FK videos; UNIQUE |
| delivered_variable | boolean | nullable |
| used_approved_hook | boolean | nullable |
| used_fixed_cta | boolean | nullable |
| actual_duration_seconds | integer | nullable; CHECK >= 0 |
| actual_product_reveal_seconds | integer | nullable |
| format_changed | boolean | nullable |
| audience_framing_changed | boolean | nullable |
| offer_changed | boolean | nullable |
| publishing_schedule_changed | boolean | nullable |
| reason | text | |
| notes | text | |
| unexpected | text | |
| perceived_drop_off_at | text | anecdotal; founder-entered |
| founder_observed_comment_sentiment | text | founder-read; not automated |
| created_at | timestamptz | |
| updated_at | timestamptz | |

---

### redirect_events

Every click retained. is_unique = true for the primary metric.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| attribution_window_id | uuid | nullable FK attribution_windows |
| visitor_key | text | anonymous identifier (cookie or HMAC) |
| is_unique | boolean | true if first occurrence of visitor_key in this window |
| occurred_at | timestamptz | |
| destination_url | text | |
| request_metadata | jsonb | coarse data for abuse detection; no raw IP |
| created_at | timestamptz | |

```sql
CREATE UNIQUE INDEX one_unique_click_per_visitor_window
  ON redirect_events (attribution_window_id, visitor_key)
  WHERE is_unique = true AND attribution_window_id IS NOT NULL;
```

Primary metric query: COUNT(*) WHERE is_unique = true AND attribution_window_id = :id

---

### attribution_windows

Non-overlap enforced at database level via range exclusion constraint.

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

```sql
UNIQUE (video_id);
CHECK (ends_at > starts_at);

CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE attribution_windows ADD CONSTRAINT no_overlapping_active_windows
  EXCLUDE USING gist (
    project_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
  ) WHERE (status IN ('scheduled', 'active'));
```

---

### experiment_evidence_snapshots

Versioned; immutable after finalization.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK; UNIQUE (id, project_id) |
| project_id | uuid | FK projects |
| experiment_id | uuid | FK experiments |
| version | integer | starts 1 |
| status | snapshot_status | pending, ready, finalized |
| attribution_method | text | 'isolated_window' |
| generated_at | timestamptz | |
| finalized_at | timestamptz | null until finalized |
| created_by_job_id | uuid | nullable |

```sql
UNIQUE (experiment_id, version);
```

---

### experiment_evidence_items

One per Variant. Renamed fields for precision.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | composite FK (evidence_snapshot_id, project_id) |
| evidence_snapshot_id | uuid | FK experiment_evidence_snapshots |
| variant_id | uuid | FK variants |
| video_id | uuid | FK videos; the specific attempt analyzed |
| start_metric_snapshot_id | uuid | FK video_metric_snapshots |
| end_metric_snapshot_id | uuid | FK video_metric_snapshots |
| views_delta | integer | end.views - start.views |
| likes_delta | integer | |
| comments_delta | integer | |
| attributed_unique_clicks | integer | COUNT(redirect_events WHERE is_unique = true) in window |
| unique_clicks_per_1k | numeric | attributed_unique_clicks / views_delta * 1000; stored immutably |
| execution_observation_id | uuid | nullable FK execution_observations |
| attribution_window_id | uuid | FK attribution_windows |
| attribution_conditions | jsonb | snapshot of window details at finalization |

---

### insights

Versioned. outcome_type is a controlled enum.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| experiment_id | uuid | FK experiments |
| evidence_snapshot_id | uuid | FK experiment_evidence_snapshots; finalized |
| version | integer | starts 1 |
| is_current | boolean | PARTIAL UNIQUE (experiment_id) WHERE is_current = true |
| superseded_at | timestamptz | nullable; set when a newer version is generated |
| generated_by_ai_run_id | uuid | FK ai_runs |
| research_question | text | copied from hypothesis_design_snapshot |
| hypothesis_text | text | copied |
| primary_metric | primary_metric | enum; copied |
| outcome_type | experiment_outcome | enum |
| evidence_basis | jsonb | structured; schemaVersion: 1 |
| supported_learning | text | AI-generated prose |
| do_not_infer_yet | text[] | AI-generated |
| recommended_next_test | text | AI-generated |
| limitations | text[] | AI-generated |
| outcome_description | text | AI-generated plain-language explanation |
| generated_at | timestamptz | |

```sql
UNIQUE (experiment_id, version);
CREATE UNIQUE INDEX one_current_insight_per_experiment
  ON insights (experiment_id) WHERE is_current = true;
```

**evidence_basis** structure (schemaVersion: 1):
```json
{
  "schemaVersion": 1,
  "trackingWindowsCompleted": 3,
  "requiredTrackingWindows": 3,
  "attributionMethod": "isolated_window",
  "executionDeviations": [],
  "allVideosValidated": true
}
```

---

### follow_up_candidates

slot = presentation choice (safest / highest learning / highest upside).
relationship_type = scientific relationship to parent.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK; UNIQUE (id, project_id) |
| project_id | uuid | FK projects |
| insight_id | uuid | FK insights |
| slot | candidate_slot | enum: safest_next_step, highest_learning, highest_upside |
| relationship_type | hypothesis_relationship | enum; the scientific relationship |
| statement | text | AI-generated |
| why_this_follows | text | AI-generated |
| recommended | boolean | AI marks one per Insight |
| recommendation_reason | text | AI-generated |
| previous_learning | text | carried to new Hypothesis if accepted |
| remaining_unknown | text | carried to new Hypothesis if accepted |
| status | candidate_status | proposed, accepted, dismissed |
| accepted_hypothesis_id | uuid | nullable FK hypotheses; set on acceptance |
| created_at | timestamptz | |

Dismissal does not create a rejected Hypothesis.

---

### ai_runs

Append-only provenance. Full prompt and output recorded.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK projects |
| entity_type | text | Hypothesis, Variant, Insight, FollowUpCandidate |
| entity_id | uuid | polymorphic; no formal FK |
| field_name | text | nullable for batch operations |
| operation | text | generateHypotheses, reviseBrief, generateInsight, generateCandidates |
| model | text | e.g. claude-opus-4-7 |
| prompt_version | text | version of the prompt template |
| context_version | integer | projects.context_version at generation time |
| input_payload | jsonb | full prompt context |
| output_payload | jsonb | raw structured output |
| validation_result | text | valid, invalid, parse_error |
| token_usage | jsonb | {inputTokens, outputTokens} |
| cost_usd | numeric | nullable |
| latency_ms | integer | nullable |
| status | text | success, failed, timeout |
| created_at | timestamptz | |

---

## Enums

```sql
product_type:           SaaS, Mobile App, AI App, Service, Waitlist
primary_metric:         clicks_per_1k_views, comments_per_1k_views, views, product_clicks, comments
hypothesis_status:      generated, draft, approved, testing, tested, rejected
hypothesis_relationship: replication, mechanism_isolation, parameter_optimization,
                          generalization, counter_hypothesis, recovery_redesign
experiment_status:      ready, in_progress, tracking, analyzing, completed, cancelled
variant_position:       A, B, C
treatment_role:         control, hypothesis_treatment, alternative_treatment
variant_design_status:  queued, ready_to_review, approved_for_recording, recorded
video_status:           needs_url, validating, tracking, completed,
                        invalid_url, account_mismatch, video_private, video_deleted, tracking_failed
attribution_window_status: scheduled, active, closed, cancelled
snapshot_status:        pending, ready, finalized
experiment_outcome:     directional_difference, mixed_result, little_difference,
                        all_variants_weak, all_variants_strong, insufficient_evidence, execution_problem
candidate_slot:         safest_next_step, highest_learning, highest_upside
candidate_status:       proposed, accepted, dismissed
fact_status:            verified, rejected
```

UI label mapping for primary_metric:
- clicks_per_1k_views → "Clicks / 1K Views"
- comments_per_1k_views → "Comments / 1K Views"
- views → "Views"
- product_clicks → "Product Clicks"
- comments → "Comments"

---

## Stored vs Derived (final)

| Field | Classification |
|---|---|
| projects.tracking_url | derived — contentlab.app/p/{slug} at response time |
| projects.context_version | stored — DB trigger increments on listed field changes |
| experiments.cta | removed — lives in shared_constraints |
| hypotheses.source_insight_id | removed — derive via source_candidate_id → candidates → insights |
| variants.display_status | derived — Variant.status + current Video.status |
| videos.tracking_window_ends_at | stored at tracking_started_at assignment |
| video_metric_snapshots (clicks) | removed — clicks come from redirect_events |
| experiment_evidence_items.unique_clicks_per_1k | stored immutably at finalization |
| insights.lift | derived at query from evidence items |
| experiment_evidence_snapshots | stored versioned — not 1:1 with Experiment |

---

## Pre-Migration Checklist — All Items Locked

- [x] Isolated 72h windows
- [x] Video-level reruns
- [x] Terminal cancellation
- [x] Flexible JSONB with schemaVersion
- [x] project_id on every tenant-owned table
- [x] Composite FK enforcement
- [x] Partial unique index on projects.user_id
- [x] tracking_slug permanently reserved
- [x] primary_metric enum
- [x] Hypothesis lineage consistency rules
- [x] Hypothesis edit policy after Experiment creation
- [x] Experiment.cta removed
- [x] Experiment lifecycle timestamps + cycling in_progress ↔ tracking
- [x] Variant design status separated from Video status
- [x] Sequential unlocking (B after A completes, C after B)
- [x] Video attempt fields + error fields
- [x] VideoMetricSnapshot: TikTok metrics only
- [x] ExecutionObservation tied to Video
- [x] AttributionWindow no-overlap constraint
- [x] timestamptz throughout
- [x] AIRun expanded
- [x] candidate_kind → candidate_slot + relationship_type
- [x] redirect_events: visitor_key + is_unique + partial unique index
- [x] evidence items: attributed_unique_clicks + unique_clicks_per_1k
- [x] Insights versioned + is_current + outcome_type enum + evidence_basis JSONB
- [x] project_facts table
- [x] Auth: Supabase Auth
- [x] Deduplication: first-party cookie + HMAC fallback
- [x] Background jobs: Postgres jobs table + dedicated workers
- [x] context_version: broad MVP field list; DB trigger
