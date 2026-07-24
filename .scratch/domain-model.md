
# Content Lab -- Domain Model

Pre-schema deliverable. Present this before writing any migrations.

---

## 1. Entity Relationships

```
Project 1:many Hypothesis
Project 1:many Experiment
Hypothesis 1:1 Experiment
Experiment 1:3 Variant
Variant 1:many Video (typically 1; reruns may create more)
Video 1:many VideoMetricSnapshot
Variant 1:1 VariantObservation
Experiment 1:1 ExperimentEvidenceSnapshot
ExperimentEvidenceSnapshot 1:1 Insight
Insight 1:many FollowUpCandidate (typically 3)
FollowUpCandidate 0:1 Hypothesis (null until accepted)
Hypothesis self-referential via parent_hypothesis_id
```

---

## 2. Entities

### Project
One per founder account. `tracking_slug` is backend-generated — client must never own uniqueness.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| product_name | text | |
| product_type | text | SaaS, Mobile App, AI App, Service, Waitlist |
| product_description | text | primary AI prompt context |
| product_url | text | |
| target_audience | text | |
| problem_solved | text | |
| why_it_matters | text | |
| current_alternatives | text | |
| desired_action | text | |
| primary_cta | text | |
| tiktok_handle | text | |
| account_public | boolean | |
| manual_publish | boolean | |
| tracking_slug | text | unique; backend-generated |
| destination_url | text | initially = product_url; separately editable |
| onboarded_at | timestamp | null until onboarding complete |
| created_at | timestamp | |

---

### Hypothesis
Testable belief. Exists before experiment. Lineage explicit via parent_hypothesis_id.  
**UI label mapping:** `generated` → "Suggested", `tested` → "Learned"

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
| source_insight_id | uuid | FK Insight; null for cold-start |
| relationship_type | hypothesis_relationship | replication, mechanism_isolation, parameter_optimization, generalization, counter_hypothesis, recovery_redesign |
| previous_learning | text | carried from FollowUpCandidate on acceptance |
| remaining_unknown | text | carried from FollowUpCandidate on acceptance |
| created_at | timestamp | |
| approved_at | timestamp | |

---

### Experiment
One per approved Hypothesis. Status must be **persisted** — do not derive from variants alone.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK Project |
| hypothesis_id | uuid | FK Hypothesis; unique |
| name | text | |
| cta | text | |
| tracking_window_hours | integer | default 72 |
| status | experiment_status | ready, in_progress, tracking, analyzing, completed, cancelled |
| script_lesson | text | locked segment shared across all variants |
| script_product | text | locked segment |
| script_cta | text | locked segment |
| script_target_duration_label | text | e.g. 50s |
| created_at | timestamp | |
| completed_at | timestamp | null until status = completed |

---

### Variant
Three per experiment. Use `variant_id` as identifier — `role` (A/B/C) is not globally unique.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK Experiment |
| role | text | A, B, C; unique within experiment |
| role_label | text | Control, Hypothesis Treatment, Alternative Treatment |
| title | text | |
| variable_under_test | text | |
| hook | text | AI-generated; editable via Brief Editor |
| hook_delivery_note | text | AI-generated; editable |
| context | text | AI-generated; editable |
| on_screen_text | text | AI-generated; editable |
| status | variant_status | queued, ready_to_review, approved_for_recording, recorded, needs_url, validating, tracking, completed |
| approved_for_recording_at | timestamp | |
| recorded_at | timestamp | |
| created_at | timestamp | |

Error states: `invalid_url`, `account_mismatch`, `video_private`, `video_deleted`, `tracking_failed`

---

### Video
Published TikTok artifact. **Separate from Variant.** A future rerun may create another Video for the same Variant.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| variant_id | uuid | FK Variant |
| tiktok_url | text | |
| published_at | timestamp | starts tracking window |
| status | video_status | needs_url, validating, tracking, completed, invalid_url, account_mismatch, video_private, video_deleted, tracking_failed |
| tracking_window_ends_at | timestamp | derived at insert: published_at + window_hours |
| created_at | timestamp | |

---

### VideoMetricSnapshot
Point-in-time metrics via phone automation. Multiple per Video over the tracking window.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| video_id | uuid | FK Video |
| collected_at | timestamp | |
| views | integer | |
| likes | integer | |
| comments | integer | |
| clicks | integer | link-in-bio redirects |
| clicks_per_1k | numeric | derived at insert: clicks / views * 1000 |

---

### VariantObservation
Founder-reported execution quality. `drop_off_at` and `sentiment` are **anecdotal** — not automated.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| variant_id | uuid | FK Variant; unique |
| delivered_variable | boolean | null until founder answers |
| reason | text | why it did or did not deliver |
| notes | text | free-form qualitative notes |
| unexpected | text | surprising signals |
| drop_off_at | text | anecdotal timecode — founder-entered, not automated |
| sentiment | text | founder-read comment sentiment — not automated |
| created_at | timestamp | |
| updated_at | timestamp | |

---

### ExperimentEvidenceSnapshot
Immutable. AI receives this. **Never mutated after creation.** Insight references it; it does not reference Insight.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK Experiment; unique |
| generated_at | timestamp | |
| variant_results | jsonb | final metrics per variant |
| calculated_comparisons | jsonb | lift, clicks_per_1k per variant |
| execution_deviations | jsonb | from VariantObservation.delivered_variable = false |
| attribution_conditions | jsonb | window durations, collection timestamps |

---

### Insight
AI interpretation of evidence snapshot. References snapshot — **never duplicates raw metric columns.**

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| experiment_id | uuid | FK Experiment; unique |
| evidence_snapshot_id | uuid | FK ExperimentEvidenceSnapshot |
| research_question | text | copied from source Hypothesis at archival time |
| hypothesis_text | text | copied from source Hypothesis |
| primary_metric | text | copied from Experiment |
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
| relationship_type | hypothesis_relationship | |
| previous_learning | text | carried to new Hypothesis if accepted |
| remaining_unknown | text | carried to new Hypothesis if accepted |
| status | candidate_status | proposed, accepted, dismissed |
| accepted_hypothesis_id | uuid | FK Hypothesis; null until accepted |
| created_at | timestamp | |

---

### AIRun
Provenance for AI-generated fields. Live entity becomes canonical after approval; AIRun preserves origin. Append-only.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| entity_type | text | Hypothesis, Variant, Insight, FollowUpCandidate |
| entity_id | uuid | |
| field_name | text | e.g. hook, statement, supported_learning |
| model | text | e.g. claude-opus-4-7 |
| prompt_hash | text | sha256 of prompt used |
| output | text | raw generated text before user edits |
| created_at | timestamp | |

---

## 3. State Enums and Transition Rules

### hypothesis_status

```
generated → draft
  trigger: user opens /review and edits any field

generated → approved
  trigger: user approves directly without drafting

draft → approved
  trigger: POST /hypotheses/{id}/approve
  guard: statement + independent_variable + primary_metric must be non-empty

approved → testing
  trigger: backend sets when experiment.status transitions to in_progress

testing → tested
  trigger: backend sets when experiment.status transitions to completed

generated|draft|approved → rejected
  trigger: explicit founder rejection

rejected → draft
  trigger: founder reopens for editing
```

UI labels: `generated` = "Suggested", `tested` = "Learned"

**Gaps:**
- `approved → testing` has no explicit API call today. Backend should set this when experiment.status = in_progress.
- `testing → tested` requires backend to set this when experiment.status = completed.

---

### experiment_status

```
ready → in_progress
  trigger: first variant.status becomes tracking

in_progress → tracking
  trigger: all variants.status are tracking

tracking → analyzing
  trigger: all video tracking_window_ends_at have passed (backend cron)

analyzing → completed
  trigger: Insight is generated and FollowUpCandidates are created

ready|in_progress|tracking → cancelled
  trigger: explicit cancellation
```

**Gaps:**
- `analyzing` is a missing UI state. The frontend needs a waiting/loading screen for this transition.
- `completed` must trigger hypothesis.status → tested.

---

### variant_status

```
queued → ready_to_review
  trigger: previous variant reaches tracking (or is first in sequence)

ready_to_review → approved_for_recording
  trigger: POST /variants/{id}/approve

approved_for_recording → recorded
  trigger: POST /variants/{id}/confirm-recorded

recorded → needs_url
  trigger: implicit

needs_url → validating
  trigger: founder pastes URL + passes 3-checkbox Publication modal

validating → tracking
  trigger: backend confirms URL is valid and video is public

tracking → completed
  trigger: backend cron — tracking_window_ends_at has passed
```

Error states: `invalid_url`, `account_mismatch`, `video_private`, `video_deleted`, `tracking_failed`

**Gaps:**
- `approved_for_recording` stage is local UI state today — must be persisted as variant.status.
- `validating → tracking` requires backend URL validation; currently skipped.

---

### candidate_status

```
proposed → accepted
  trigger: POST /follow-up-candidates/{id}/accept
  side-effect: creates a new Hypothesis with lineage from the candidate

proposed → dismissed
  trigger: POST /follow-up-candidates/{id}/dismiss
  side-effect: nothing — no Hypothesis is created
```

**Critical:** A dismissed candidate is NOT a rejected Hypothesis. Do not `PATCH /hypotheses/{id} status=rejected` for this.

---

## 4. Frontend-to-API View Models

### ProjectDetail
**Screens:** /onboarding, /settings  
**Sources:** Project  
**Fields:** id, productName, productType, productDescription, productUrl, targetAudience, problemSolved, whyItMatters, currentAlternatives, desiredAction, primaryCta, tiktokHandle, accountPublic, manualPublish, trackingSlug, trackingUrl (server-computed), destinationUrl

---

### OverviewResponse
**Screen:** /overview  
**Sources:** Project, Experiment + Variants, Hypothesis[], Insight  
**Fields:** project summary, kpis (publishedVideos, totalClicks, completedExperiments, activeThreads), nextAction (title, description, cta — backend-computed), activeExperiment, latestInsight, hypothesisBacklog  
**Note:** `nextAction` must be calculated by the backend. Do not push this domain logic into React.

---

### HypothesisSummary
**Screen:** /research (card list)  
**Sources:** Hypothesis  
**Fields:** id, title, status, primaryMetric, category, lineagePreview, resultPreview (clicks/1k from linked Insight if tested)  
**Note:** Thread view needs parentHypothesisId on each summary to build the tree client-side without extra calls.

---

### HypothesisDetail
**Screen:** /research inspector, /research/[id]/review  
**Sources:** Hypothesis, Insight (via source_insight_id), Hypothesis (parent)  
**Fields:** all HypothesisSummary fields, statement, researchQuestion, independentVariable, controlCondition, treatmentCondition, controlledElements, contradictionCondition, rationale, lineage (parentHypothesisId, parentTitle, sourceInsightId, relationshipType, previousLearning, remainingUnknown)  
**Note:** Include lineage context inline — /review must not need a separate call.

---

### ExperimentDetail
**Screen:** /experiments  
**Sources:** Experiment, Variant[], Video[], VideoMetricSnapshot[], Hypothesis (linked), VariantObservation[]  
**Fields:** id, name, status, hypothesis (statement, independentVariable, controlledElements), primaryMetric, trackingWindowHours, cta, script, publishedCount, nextAction, variants [VariantSummary + latest Video + observation.notes presence]  
**Note:** Integrity panel reads hypothesis.independentVariable and hypothesis.controlledElements — embed in ExperimentDetail directly.

---

### VariantDetail
**Screen:** /experiments/brief/[role], /experiments/observe/[role]  
**Sources:** Variant, Experiment, Video, VideoMetricSnapshot[], VariantObservation  
**Fields:** id, role, roleLabel, title, variableUnderTest, hook, hookDeliveryNote, context, onScreenText, status, experiment (name, cta, trackingWindowHours, script), video, latestMetrics, observation  
**Note:** Brief page also needs project.targetAudience and project.primaryCta for the Keep Controlled section.

---

### VideoSummary
**Screen:** /videos (table row)  
**Sources:** Variant, Video, VideoMetricSnapshot (latest), Experiment  
**Fields:** variantId, variantRole, variantTitle, roleLabel, experimentName, tiktokUrl, publishedAt, status, trackingWindowEndsAt, latestMetrics (views, likes, comments, clicks, clicksPer1k)  
**Note:** No separate Video model at table level — VideoSummary is a join of Variant + Video + latest snapshot.

---

### InsightDetail
**Screen:** /insights (right panel)  
**Sources:** Insight, ExperimentEvidenceSnapshot, FollowUpCandidate[]  
**Fields:** id, experimentName, primaryMetric, completedAt, windowHours, researchQuestion, hypothesisText, evidence (control/treatment/alternative from snapshot), lift (computed at query time), supportedLearning, evidenceBasis, doNotInferYet, recommendedNextTest, limitations, outcome, nextCandidates [FollowUpCandidate + alreadyAccepted flag]  
**Note:** `lift` is computed from snapshot data at query time — not stored on Insight.

---

## 5. Stored vs Derived

| Field | Classification | Notes |
|---|---|---|
| Project.tracking_slug | stored | Generated once at creation; never recomputed |
| Project.tracking_url | derived | contentlab.app/p/{slug} — constructed at query time |
| Project.destination_url | stored | Editable; initially set from product_url |
| Hypothesis.status | stored | Driven by explicit transitions; never inferred |
| Hypothesis.parent_hypothesis_id | stored | Set when created from a FollowUpCandidate |
| Experiment.status | stored | Persisted; transitions triggered by events or cron |
| ExperimentStatus (display) | derived | Re-derived from experiment.status for display labels |
| Variant.status | stored | Approval and recorded stages must not live only in React |
| Video.tracking_window_ends_at | derived | Computed at insert: published_at + window_hours |
| VideoMetricSnapshot.clicks_per_1k | stored (convenience) | Computed at insert for query performance |
| Insight.lift | derived | Computed from evidence snapshot at query time; not stored |
| ExperimentEvidenceSnapshot.* | stored (immutable) | Written once; never mutated |
| FollowUpCandidate.status | stored | Persisted; not the same as Hypothesis.status |
| OverviewResponse.nextAction | derived | Backend-computed from Experiment + Variant lifecycle |
| OverviewResponse.kpis.publishedVideos | derived | COUNT variants with status = tracking or completed |
| OverviewResponse.kpis.totalClicks | derived | SUM clicks from latest VideoMetricSnapshot per video |
| OverviewResponse.kpis.completedExperiments | derived | COUNT experiments with status = completed |
| OverviewResponse.kpis.activeThreads | derived | COUNT hypotheses with status = testing |

**Rule:** Never store a derived value as a canonical field. Exception: VideoMetricSnapshot.clicks_per_1k is stored at insert as a performance convenience.

---

## 6. AI Provenance Strategy

AI-generated fields become canonical on the entity after user approval. AIRun preserves origin. On edit, entity field is overwritten; AIRun is appended, not mutated.

### Hypothesis — AI-generated fields
`title`, `statement`, `research_question`, `independent_variable`, `primary_metric`, `rationale`, `controlled_elements` (initial), `contradiction_condition` (initial)  
**Lifecycle:** AI proposes at generation. User edits in /review overwrite the entity field. AIRun preserves the original proposal.  
**Becomes canonical after:** status = approved

### Variant — AI-generated fields
`hook`, `hook_delivery_note`, `context`, `on_screen_text`, `variable_under_test`  
**Lifecycle:** AI generates when experiment is created. Each revision attempt creates a new AIRun. Applying a revision overwrites the entity field.  
**Becomes canonical after:** status = approved_for_recording

### Insight — AI-generated fields
`supported_learning`, `evidence_basis`, `do_not_infer_yet`, `recommended_next_test`, `limitations`, `outcome_label`, `outcome_description`  
**Lifecycle:** Generated once from the immutable ExperimentEvidenceSnapshot. Never regenerated. AIRun records the exact prompt and model.  
**Becomes canonical after:** Generated — immediately canonical; not user-editable

### FollowUpCandidate — AI-generated fields
`statement`, `why_this_follows`, `recommended`, `relationship_type`, `previous_learning`, `remaining_unknown`  
**Lifecycle:** Generated alongside Insight. User accepts or dismisses — no editing. Acceptance copies AI fields to the new Hypothesis as initial values.  
**Becomes canonical after:** Acceptance creates a new Hypothesis with these as starting values; then editable in /review

---

## 7. FakeIntelligenceProvider Pattern

Before Claude is wired, all AI generation routes through a `FakeIntelligenceProvider` that returns seeded data. The interface is identical to the real provider — swapping requires no UI or schema changes.

```typescript
interface IntelligenceProvider {
  generateHypotheses(project: ProjectContext): Promise<Hypothesis[]>
  reviseBrief(variant: Variant, instruction: string): Promise<VariantBriefEdit>
  generateInsight(snapshot: ExperimentEvidenceSnapshot): Promise<InsightPayload>
  generateCandidates(insight: Insight): Promise<FollowUpCandidate[]>
}
```

Implementation order:
1. `FakeIntelligenceProvider` — returns SEED_HYPOTHESES, SEED_INSIGHTS etc.
2. `ClaudeIntelligenceProvider` — calls real API
3. Switch via environment config — no UI or schema changes required

---

## 8. Pre-Migration Checklist

Before writing migrations, confirm all of the following:

- [ ] Backend uses `variant_id` as identifier — not `role`. Role is not globally unique.
- [ ] `Experiment.status` is persisted — not derived from variant statuses alone.
- [ ] Variant approval stages (`approved_for_recording`, `recorded`) are persisted as `variant.status` — not local React state.
- [ ] `Video` is a separate table — not a field on Variant.
- [ ] `FollowUpCandidate.status = dismissed` does NOT create a rejected Hypothesis.
- [ ] `VariantObservation.drop_off_at` and `.sentiment` are founder-entered qualitative fields — not automated.
- [ ] Public metrics are collected via phone automation — not a TikTok API dependency.
- [ ] `Insight` references an immutable `ExperimentEvidenceSnapshot` — does not duplicate raw metric columns.
- [ ] `trackingSlug` is backend-generated — browser must never own uniqueness.
- [ ] `experiment.status = analyzing` is a persisted state — the UI needs a waiting screen for it.
- [ ] `FollowUpCandidate` dismissal does not call `PATCH /hypotheses/{id}` — candidates have their own status lifecycle.
