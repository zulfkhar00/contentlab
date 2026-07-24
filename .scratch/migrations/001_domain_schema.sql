-- =============================================================================
-- 001_domain_schema.sql
-- Content Lab — core domain schema
--
-- Run order: extensions → enums → tables → indexes → constraints → RLS → triggers
-- All timestamps: timestamptz
-- Tenant isolation: project_id on every domain table + composite FK enforcement
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

CREATE TYPE product_type AS ENUM (
  'SaaS', 'Mobile App', 'AI App', 'Service', 'Waitlist'
);

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
  'replication',
  'mechanism_isolation',
  'parameter_optimization',
  'generalization',
  'counter_hypothesis',
  'recovery_redesign'
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

CREATE TYPE experiment_outcome AS ENUM (
  'directional_difference',
  'mixed_result',
  'little_difference',
  'all_variants_weak',
  'all_variants_strong',
  'insufficient_evidence',
  'execution_problem'
);

CREATE TYPE candidate_slot AS ENUM (
  'safest_next_step', 'highest_learning', 'highest_upside'
);

CREATE TYPE candidate_status AS ENUM ('proposed', 'accepted', 'dismissed');

CREATE TYPE fact_status AS ENUM ('verified', 'rejected');

-- ---------------------------------------------------------------------------
-- Helper: set_updated_at trigger function
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- projects
-- ---------------------------------------------------------------------------
CREATE TABLE projects (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  product_name        text        NOT NULL DEFAULT '',
  product_type        product_type NOT NULL DEFAULT 'SaaS',
  product_description text        NOT NULL DEFAULT '',
  product_url         text        NOT NULL DEFAULT '',
  target_audience     text        NOT NULL DEFAULT '',
  problem_solved      text        NOT NULL DEFAULT '',
  why_it_matters      text        NOT NULL DEFAULT '',
  current_alternatives text       NOT NULL DEFAULT '',
  desired_action      text        NOT NULL DEFAULT '',
  primary_cta         text        NOT NULL DEFAULT '',
  tiktok_handle       text        NOT NULL DEFAULT '',  -- stored without @
  account_public      boolean     NOT NULL DEFAULT false,
  manual_publish      boolean     NOT NULL DEFAULT false,
  tracking_slug       text        NOT NULL,
  destination_url     text        NOT NULL DEFAULT '',
  context_version     integer     NOT NULL DEFAULT 1,
  onboarded_at        timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  deleted_at          timestamptz,

  CONSTRAINT projects_tracking_slug_unique UNIQUE (tracking_slug)
);

-- One active project per user; deleted projects do not block re-onboarding
CREATE UNIQUE INDEX one_active_project_per_user
  ON projects (user_id)
  WHERE deleted_at IS NULL;

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- context_version increment trigger
CREATE OR REPLACE FUNCTION increment_context_version()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF (
    NEW.product_name        IS DISTINCT FROM OLD.product_name        OR
    NEW.product_type        IS DISTINCT FROM OLD.product_type        OR
    NEW.product_description IS DISTINCT FROM OLD.product_description OR
    NEW.product_url         IS DISTINCT FROM OLD.product_url         OR
    NEW.target_audience     IS DISTINCT FROM OLD.target_audience     OR
    NEW.problem_solved      IS DISTINCT FROM OLD.problem_solved      OR
    NEW.why_it_matters      IS DISTINCT FROM OLD.why_it_matters      OR
    NEW.current_alternatives IS DISTINCT FROM OLD.current_alternatives OR
    NEW.desired_action      IS DISTINCT FROM OLD.desired_action      OR
    NEW.primary_cta         IS DISTINCT FROM OLD.primary_cta         OR
    NEW.tiktok_handle       IS DISTINCT FROM OLD.tiktok_handle
  ) THEN
    NEW.context_version := OLD.context_version + 1;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER projects_context_version
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION increment_context_version();

-- ---------------------------------------------------------------------------
-- project_facts
-- ---------------------------------------------------------------------------
CREATE TABLE project_facts (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  fact_text    text        NOT NULL,
  category     text        NOT NULL DEFAULT '',  -- spend, customer_count, outcome, personal_story
  source       text        NOT NULL DEFAULT '',
  status       fact_status NOT NULL DEFAULT 'verified',
  verified_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER project_facts_updated_at
  BEFORE UPDATE ON project_facts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- hypotheses
-- (source_candidate_id FK added after follow_up_candidates; created_by_ai_run_id after ai_runs)
-- ---------------------------------------------------------------------------
CREATE TABLE hypotheses (
  id                      uuid                   PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id              uuid                   NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title                   text                   NOT NULL DEFAULT '',
  statement               text                   NOT NULL DEFAULT '',
  research_question       text,
  independent_variable    text,
  control_condition       text,
  treatment_condition     text,
  controlled_elements     text[]                 NOT NULL DEFAULT '{}',
  contradiction_condition text,
  primary_metric          primary_metric         NOT NULL DEFAULT 'clicks_per_1k_views',
  rationale               text,
  category                text,
  status                  hypothesis_status      NOT NULL DEFAULT 'generated',
  parent_hypothesis_id    uuid                   REFERENCES hypotheses(id),
  source_candidate_id     uuid                   UNIQUE,    -- FK added after follow_up_candidates
  relationship_type       hypothesis_relationship,
  previous_learning       text,
  remaining_unknown       text,
  recommendation_reason   text,
  created_by_ai_run_id    uuid,                             -- FK added after ai_runs
  created_at              timestamptz            NOT NULL DEFAULT now(),
  updated_at              timestamptz            NOT NULL DEFAULT now(),
  approved_at             timestamptz,
  rejected_at             timestamptz,
  tested_at               timestamptz,

  -- Lineage consistency: both null (cold-start) or both non-null (follow-up)
  CONSTRAINT hypothesis_lineage_consistency CHECK (
    (parent_hypothesis_id IS NULL) = (source_candidate_id IS NULL)
  ),
  CONSTRAINT hypothesis_relationship_consistency CHECK (
    (source_candidate_id IS NULL) = (relationship_type IS NULL)
  )
);

CREATE TRIGGER hypotheses_updated_at
  BEFORE UPDATE ON hypotheses
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- experiments
-- ---------------------------------------------------------------------------
CREATE TABLE experiments (
  id                           uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                   uuid              NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hypothesis_id                uuid              NOT NULL REFERENCES hypotheses(id),
  name                         text              NOT NULL DEFAULT '',
  tracking_window_hours        integer           NOT NULL DEFAULT 72,
  status                       experiment_status NOT NULL DEFAULT 'ready',
  hypothesis_design_snapshot   jsonb             NOT NULL DEFAULT '{}',
  shared_constraints           jsonb             NOT NULL DEFAULT '{}',
  design_schema_version        integer           NOT NULL DEFAULT 1,
  created_at                   timestamptz       NOT NULL DEFAULT now(),
  updated_at                   timestamptz       NOT NULL DEFAULT now(),
  started_at                   timestamptz,
  tracking_completed_at        timestamptz,
  analysis_started_at          timestamptz,
  completed_at                 timestamptz,
  cancelled_at                 timestamptz,
  cancellation_reason          text,

  CONSTRAINT experiments_tracking_window_positive CHECK (tracking_window_hours > 0),
  CONSTRAINT experiments_hypothesis_unique UNIQUE (hypothesis_id),
  -- Expose (id, project_id) for composite FK enforcement on child tables
  CONSTRAINT experiments_id_project_unique UNIQUE (id, project_id)
);

CREATE TRIGGER experiments_updated_at
  BEFORE UPDATE ON experiments
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- variants
-- ---------------------------------------------------------------------------
CREATE TABLE variants (
  id                         uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                 uuid                  NOT NULL,
  experiment_id              uuid                  NOT NULL,
  position                   variant_position      NOT NULL,
  treatment_role             treatment_role        NOT NULL,
  title                      text                  NOT NULL DEFAULT '',
  variable_value             text                  NOT NULL DEFAULT '',
  hook                       text                  NOT NULL DEFAULT '',
  hook_delivery_note         text,
  context                    text,
  on_screen_text             text,
  script_sections            jsonb                 NOT NULL DEFAULT '[]',
  recording_guidance         jsonb                 NOT NULL DEFAULT '{}',
  status                     variant_design_status NOT NULL DEFAULT 'queued',
  generated_by_ai_run_id     uuid,                            -- FK added after ai_runs
  approved_for_recording_at  timestamptz,
  recorded_at                timestamptz,
  created_at                 timestamptz           NOT NULL DEFAULT now(),
  updated_at                 timestamptz           NOT NULL DEFAULT now(),

  CONSTRAINT variants_experiment_project_fk FOREIGN KEY (experiment_id, project_id)
    REFERENCES experiments (id, project_id) ON DELETE CASCADE,
  CONSTRAINT variants_position_unique UNIQUE (experiment_id, position),
  CONSTRAINT variants_role_unique UNIQUE (experiment_id, treatment_role)
);

CREATE TRIGGER variants_updated_at
  BEFORE UPDATE ON variants
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Enforce A=control, B=hypothesis_treatment, C=alternative_treatment
-- (validated in backend transaction; no pure SQL constraint without a lookup)

-- Expose (id, project_id) for child table composite FKs
ALTER TABLE variants ADD CONSTRAINT variants_id_project_unique UNIQUE (id, project_id);

-- ---------------------------------------------------------------------------
-- videos
-- ---------------------------------------------------------------------------
CREATE TABLE videos (
  id                           uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                   uuid         NOT NULL,
  variant_id                   uuid         NOT NULL,
  attempt_number               integer      NOT NULL DEFAULT 1,
  is_current                   boolean      NOT NULL DEFAULT true,
  status                       video_status NOT NULL DEFAULT 'needs_url',
  submitted_url                text,
  normalized_tiktok_url        text,
  tiktok_video_id              text,
  user_confirmed_published_at  timestamptz,
  published_at                 timestamptz,
  validated_at                 timestamptz,
  tracking_started_at          timestamptz,
  tracking_window_ends_at      timestamptz,
  last_refreshed_at            timestamptz,
  validation_error_code        text,
  validation_error_detail      text,
  created_at                   timestamptz  NOT NULL DEFAULT now(),
  updated_at                   timestamptz  NOT NULL DEFAULT now(),

  CONSTRAINT videos_variant_project_fk FOREIGN KEY (variant_id, project_id)
    REFERENCES variants (id, project_id) ON DELETE CASCADE,
  CONSTRAINT videos_attempt_unique UNIQUE (variant_id, attempt_number),
  CONSTRAINT videos_attempt_positive CHECK (attempt_number >= 1)
);

-- One current attempt per Variant
CREATE UNIQUE INDEX one_current_video_per_variant
  ON videos (variant_id)
  WHERE is_current = true;

-- Global URL uniqueness (when set)
CREATE UNIQUE INDEX videos_tiktok_video_id_unique
  ON videos (tiktok_video_id)
  WHERE tiktok_video_id IS NOT NULL;

CREATE UNIQUE INDEX videos_normalized_url_unique
  ON videos (normalized_tiktok_url)
  WHERE normalized_tiktok_url IS NOT NULL;

-- Expose (id, project_id) for child composite FKs
ALTER TABLE videos ADD CONSTRAINT videos_id_project_unique UNIQUE (id, project_id);

CREATE TRIGGER videos_updated_at
  BEFORE UPDATE ON videos
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- video_metric_snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE video_metric_snapshots (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        uuid        NOT NULL,
  video_id          uuid        NOT NULL,
  collected_at      timestamptz NOT NULL,
  views             integer     NOT NULL DEFAULT 0,
  likes             integer     NOT NULL DEFAULT 0,
  comments          integer     NOT NULL DEFAULT 0,
  collection_job_id uuid,
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT vms_video_project_fk FOREIGN KEY (video_id, project_id)
    REFERENCES videos (id, project_id) ON DELETE CASCADE,
  CONSTRAINT vms_views_nonneg   CHECK (views    >= 0),
  CONSTRAINT vms_likes_nonneg   CHECK (likes    >= 0),
  CONSTRAINT vms_comments_nonneg CHECK (comments >= 0)
);

CREATE INDEX vms_video_id_collected_at ON video_metric_snapshots (video_id, collected_at DESC);

-- ---------------------------------------------------------------------------
-- execution_observations
-- ---------------------------------------------------------------------------
CREATE TABLE execution_observations (
  id                                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                         uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  video_id                           uuid        NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  delivered_variable                 boolean,
  used_approved_hook                 boolean,
  used_fixed_cta                     boolean,
  actual_duration_seconds            integer,
  actual_product_reveal_seconds      integer,
  format_changed                     boolean,
  audience_framing_changed           boolean,
  offer_changed                      boolean,
  publishing_schedule_changed        boolean,
  reason                             text,
  notes                              text,
  unexpected                         text,
  perceived_drop_off_at              text,
  founder_observed_comment_sentiment text,
  created_at                         timestamptz NOT NULL DEFAULT now(),
  updated_at                         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT eo_video_unique UNIQUE (video_id),
  CONSTRAINT eo_duration_nonneg CHECK (actual_duration_seconds IS NULL OR actual_duration_seconds >= 0),
  CONSTRAINT eo_reveal_nonneg   CHECK (actual_product_reveal_seconds IS NULL OR actual_product_reveal_seconds >= 0)
);

CREATE TRIGGER execution_observations_updated_at
  BEFORE UPDATE ON execution_observations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- attribution_windows
-- ---------------------------------------------------------------------------
CREATE TABLE attribution_windows (
  id             uuid                       PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     uuid                       NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  experiment_id  uuid                       NOT NULL REFERENCES experiments(id),
  variant_id     uuid                       NOT NULL REFERENCES variants(id),
  video_id       uuid                       NOT NULL REFERENCES videos(id),
  starts_at      timestamptz                NOT NULL,
  ends_at        timestamptz                NOT NULL,
  status         attribution_window_status  NOT NULL DEFAULT 'scheduled',
  created_at     timestamptz                NOT NULL DEFAULT now(),

  CONSTRAINT aw_video_unique UNIQUE (video_id),
  CONSTRAINT aw_ends_after_starts CHECK (ends_at > starts_at),
  -- Non-overlapping active windows per project (requires btree_gist)
  CONSTRAINT no_overlapping_active_windows EXCLUDE USING gist (
    project_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
  ) WHERE (status IN ('scheduled', 'active'))
);

CREATE INDEX aw_project_range ON attribution_windows USING gist (
  project_id,
  tstzrange(starts_at, ends_at, '[)')
) WHERE status IN ('scheduled', 'active');

-- ---------------------------------------------------------------------------
-- redirect_events
-- ---------------------------------------------------------------------------
CREATE TABLE redirect_events (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  attribution_window_id uuid        REFERENCES attribution_windows(id),
  visitor_key           text        NOT NULL,
  is_unique             boolean     NOT NULL DEFAULT false,
  occurred_at           timestamptz NOT NULL,
  destination_url       text        NOT NULL,
  request_metadata      jsonb       NOT NULL DEFAULT '{}',
  created_at            timestamptz NOT NULL DEFAULT now()
);

-- One unique click per visitor per window
CREATE UNIQUE INDEX one_unique_click_per_visitor_window
  ON redirect_events (attribution_window_id, visitor_key)
  WHERE is_unique = true AND attribution_window_id IS NOT NULL;

CREATE INDEX re_project_occurred ON redirect_events (project_id, occurred_at DESC);
CREATE INDEX re_window ON redirect_events (attribution_window_id) WHERE attribution_window_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- experiment_evidence_snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE experiment_evidence_snapshots (
  id                  uuid            PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id          uuid            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  experiment_id       uuid            NOT NULL REFERENCES experiments(id),
  version             integer         NOT NULL DEFAULT 1,
  status              snapshot_status NOT NULL DEFAULT 'pending',
  attribution_method  text            NOT NULL DEFAULT 'isolated_window',
  generated_at        timestamptz     NOT NULL DEFAULT now(),
  finalized_at        timestamptz,
  created_by_job_id   uuid,

  CONSTRAINT ees_version_unique UNIQUE (experiment_id, version),
  CONSTRAINT ees_id_project_unique UNIQUE (id, project_id)
);

-- ---------------------------------------------------------------------------
-- experiment_evidence_items
-- ---------------------------------------------------------------------------
CREATE TABLE experiment_evidence_items (
  id                          uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                  uuid    NOT NULL,
  evidence_snapshot_id        uuid    NOT NULL,
  variant_id                  uuid    NOT NULL REFERENCES variants(id),
  video_id                    uuid    NOT NULL REFERENCES videos(id),
  start_metric_snapshot_id    uuid    NOT NULL REFERENCES video_metric_snapshots(id),
  end_metric_snapshot_id      uuid    NOT NULL REFERENCES video_metric_snapshots(id),
  views_delta                 integer NOT NULL DEFAULT 0,
  likes_delta                 integer NOT NULL DEFAULT 0,
  comments_delta              integer NOT NULL DEFAULT 0,
  attributed_unique_clicks    integer NOT NULL DEFAULT 0,
  unique_clicks_per_1k        numeric,  -- stored immutably at finalization
  execution_observation_id    uuid    REFERENCES execution_observations(id),
  attribution_window_id       uuid    NOT NULL REFERENCES attribution_windows(id),
  attribution_conditions      jsonb   NOT NULL DEFAULT '{}',

  CONSTRAINT eei_snapshot_project_fk FOREIGN KEY (evidence_snapshot_id, project_id)
    REFERENCES experiment_evidence_snapshots (id, project_id) ON DELETE CASCADE,
  CONSTRAINT eei_variant_snapshot_unique UNIQUE (evidence_snapshot_id, variant_id)
);

-- ---------------------------------------------------------------------------
-- insights
-- ---------------------------------------------------------------------------
CREATE TABLE insights (
  id                      uuid               PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id              uuid               NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  experiment_id           uuid               NOT NULL REFERENCES experiments(id),
  evidence_snapshot_id    uuid               NOT NULL REFERENCES experiment_evidence_snapshots(id),
  version                 integer            NOT NULL DEFAULT 1,
  is_current              boolean            NOT NULL DEFAULT true,
  superseded_at           timestamptz,
  generated_by_ai_run_id  uuid,              -- FK added after ai_runs
  research_question       text,
  hypothesis_text         text,
  primary_metric          primary_metric,
  outcome_type            experiment_outcome,
  evidence_basis          jsonb              NOT NULL DEFAULT '{}',
  supported_learning      text,
  do_not_infer_yet        text[]             NOT NULL DEFAULT '{}',
  recommended_next_test   text,
  limitations             text[]             NOT NULL DEFAULT '{}',
  outcome_description     text,
  generated_at            timestamptz        NOT NULL DEFAULT now(),

  CONSTRAINT insights_version_unique UNIQUE (experiment_id, version)
);

CREATE UNIQUE INDEX one_current_insight_per_experiment
  ON insights (experiment_id)
  WHERE is_current = true;

-- ---------------------------------------------------------------------------
-- follow_up_candidates
-- ---------------------------------------------------------------------------
CREATE TABLE follow_up_candidates (
  id                      uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id              uuid                  NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  insight_id              uuid                  NOT NULL REFERENCES insights(id),
  slot                    candidate_slot        NOT NULL,
  relationship_type       hypothesis_relationship NOT NULL,
  statement               text                  NOT NULL DEFAULT '',
  why_this_follows        text,
  recommended             boolean               NOT NULL DEFAULT false,
  recommendation_reason   text,
  previous_learning       text,
  remaining_unknown       text,
  status                  candidate_status      NOT NULL DEFAULT 'proposed',
  accepted_hypothesis_id  uuid,                 -- FK added after hypotheses gets the deferred FK
  created_at              timestamptz           NOT NULL DEFAULT now(),

  CONSTRAINT fuc_slot_unique UNIQUE (insight_id, slot),
  CONSTRAINT fuc_id_project_unique UNIQUE (id, project_id)
);

-- ---------------------------------------------------------------------------
-- ai_runs
-- ---------------------------------------------------------------------------
CREATE TABLE ai_runs (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  entity_type       text        NOT NULL,  -- Hypothesis, Variant, Insight, FollowUpCandidate
  entity_id         uuid,                  -- polymorphic; no formal FK
  field_name        text,                  -- null for batch operations
  operation         text        NOT NULL,  -- generateHypotheses, reviseBrief, generateInsight, generateCandidates
  model             text        NOT NULL,
  prompt_version    text        NOT NULL DEFAULT '1',
  context_version   integer     NOT NULL DEFAULT 1,
  input_payload     jsonb       NOT NULL DEFAULT '{}',
  output_payload    jsonb       NOT NULL DEFAULT '{}',
  validation_result text        NOT NULL DEFAULT 'valid',
  token_usage       jsonb       NOT NULL DEFAULT '{}',
  cost_usd          numeric,
  latency_ms        integer,
  status            text        NOT NULL DEFAULT 'success',
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ai_runs_entity ON ai_runs (entity_type, entity_id);
CREATE INDEX ai_runs_project ON ai_runs (project_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Deferred / circular foreign keys
-- (added after all tables exist)
-- ---------------------------------------------------------------------------

-- hypotheses.source_candidate_id → follow_up_candidates
ALTER TABLE hypotheses
  ADD CONSTRAINT hypotheses_source_candidate_fk
  FOREIGN KEY (source_candidate_id) REFERENCES follow_up_candidates(id);

-- hypotheses.created_by_ai_run_id → ai_runs
ALTER TABLE hypotheses
  ADD CONSTRAINT hypotheses_ai_run_fk
  FOREIGN KEY (created_by_ai_run_id) REFERENCES ai_runs(id);

-- variants.generated_by_ai_run_id → ai_runs
ALTER TABLE variants
  ADD CONSTRAINT variants_ai_run_fk
  FOREIGN KEY (generated_by_ai_run_id) REFERENCES ai_runs(id);

-- follow_up_candidates.accepted_hypothesis_id → hypotheses
ALTER TABLE follow_up_candidates
  ADD CONSTRAINT fuc_accepted_hypothesis_fk
  FOREIGN KEY (accepted_hypothesis_id) REFERENCES hypotheses(id);

-- insights.generated_by_ai_run_id → ai_runs
ALTER TABLE insights
  ADD CONSTRAINT insights_ai_run_fk
  FOREIGN KEY (generated_by_ai_run_id) REFERENCES ai_runs(id);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------

-- Helper: auth.uid() must match the project's user_id
-- Applied to every table through project_id ownership check

ALTER TABLE projects                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_facts             ENABLE ROW LEVEL SECURITY;
ALTER TABLE hypotheses                ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiments               ENABLE ROW LEVEL SECURITY;
ALTER TABLE variants                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_metric_snapshots    ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_observations    ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_windows       ENABLE ROW LEVEL SECURITY;
ALTER TABLE redirect_events           ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_evidence_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_evidence_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE follow_up_candidates      ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_runs                   ENABLE ROW LEVEL SECURITY;

-- projects: user owns their project
CREATE POLICY projects_owner ON projects
  FOR ALL USING (user_id = auth.uid());

-- project_facts and all project-scoped tables: project must belong to auth.uid()
CREATE OR REPLACE FUNCTION owns_project(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT EXISTS (
    SELECT 1 FROM projects
    WHERE id = p_project_id
      AND user_id = auth.uid()
      AND deleted_at IS NULL
  );
$$;

CREATE POLICY project_facts_owner ON project_facts
  FOR ALL USING (owns_project(project_id));

CREATE POLICY hypotheses_owner ON hypotheses
  FOR ALL USING (owns_project(project_id));

CREATE POLICY experiments_owner ON experiments
  FOR ALL USING (owns_project(project_id));

CREATE POLICY variants_owner ON variants
  FOR ALL USING (owns_project(project_id));

CREATE POLICY videos_owner ON videos
  FOR ALL USING (owns_project(project_id));

CREATE POLICY vms_owner ON video_metric_snapshots
  FOR ALL USING (owns_project(project_id));

CREATE POLICY eo_owner ON execution_observations
  FOR ALL USING (owns_project(project_id));

CREATE POLICY aw_owner ON attribution_windows
  FOR ALL USING (owns_project(project_id));

CREATE POLICY re_owner ON redirect_events
  FOR ALL USING (owns_project(project_id));

CREATE POLICY ees_owner ON experiment_evidence_snapshots
  FOR ALL USING (owns_project(project_id));

CREATE POLICY eei_owner ON experiment_evidence_items
  FOR ALL USING (owns_project(project_id));

CREATE POLICY insights_owner ON insights
  FOR ALL USING (owns_project(project_id));

CREATE POLICY fuc_owner ON follow_up_candidates
  FOR ALL USING (owns_project(project_id));

CREATE POLICY ai_runs_owner ON ai_runs
  FOR ALL USING (owns_project(project_id));

-- Service-role workers bypass RLS by default in Supabase.
-- Workers must still pass project_id and validate entity ownership in application code.

-- ---------------------------------------------------------------------------
-- Comments
-- ---------------------------------------------------------------------------
COMMENT ON TABLE projects IS
  'One per authenticated user. tracking_slug permanently reserved even after soft deletion.';

COMMENT ON TABLE project_facts IS
  'Verified founder statements. Only status=verified facts enter AI prompt context.';

COMMENT ON TABLE hypotheses IS
  'Testable beliefs. Cold-start: parent_hypothesis_id and source_candidate_id are NULL. '
  'Follow-up: both set; relationship_type required. Edit policy: material edits disabled '
  'once a linked experiment exists.';

COMMENT ON TABLE experiments IS
  'One per approved hypothesis. status alternates between in_progress and tracking '
  'during the sequential 3-variant isolated-window process. Cancellation is terminal.';

COMMENT ON TABLE variants IS
  'Three per experiment (A, B, C). Design lifecycle only: queued → ready_to_review → '
  'approved_for_recording → recorded. Publication state lives on videos. '
  'B unlocks after A video completes; C unlocks after B video completes.';

COMMENT ON TABLE videos IS
  'Published TikTok artifact. Multiple attempts per variant. is_current = true on active attempt. '
  'tracking_window_ends_at set at tracking_started_at, not at URL submission.';

COMMENT ON TABLE video_metric_snapshots IS
  'TikTok public metrics only (views, likes, comments). No clicks. '
  'Clicks are tracked via redirect_events and attributed via attribution_windows.';

COMMENT ON TABLE execution_observations IS
  'Founder-reported execution quality for a specific video attempt. '
  'perceived_drop_off_at and founder_observed_comment_sentiment are anecdotal; never automated.';

COMMENT ON TABLE attribution_windows IS
  'Time interval during which redirect_events are attributed to a video. '
  'Non-overlap enforced via range exclusion constraint. Isolated-window policy only.';

COMMENT ON TABLE redirect_events IS
  'Every permanent bio-link click retained. is_unique=true for primary metric (one per visitor per window). '
  'visitor_key = first-party cookie or server-side HMAC; no raw IP stored.';

COMMENT ON TABLE experiment_evidence_snapshots IS
  'Versioned, immutable after finalization. AI receives the finalized snapshot.';

COMMENT ON TABLE experiment_evidence_items IS
  'One per variant per snapshot. Identifies exact video attempt, metric interval, and unique clicks.';

COMMENT ON TABLE insights IS
  'AI interpretation of a finalized evidence snapshot. Versioned. '
  'Never duplicates raw metric columns. outcome_type is a controlled enum.';

COMMENT ON TABLE follow_up_candidates IS
  'AI-proposed next hypotheses. slot = presentation position; relationship_type = scientific relationship. '
  'Dismissal does NOT create a rejected hypothesis. Acceptance creates a new hypothesis with lineage.';

COMMENT ON TABLE ai_runs IS
  'Append-only provenance for every AI generation. Records context_version at generation time '
  'so stale output can be detected.';
