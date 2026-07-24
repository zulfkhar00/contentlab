-- =============================================================================
-- 001_domain_schema.sql  (v3 — all review corrections applied)
--
-- Changes from v2:
--  P0.3  EvidenceItem trigger covers INSERT + UPDATE (both old+new snapshot) + DELETE
--  P0.4  parent_hypothesis_id composite tenant FK
--  P0.5  JSONB schema enforcement: CHECK (object + schemaVersion) on all versioned cols
--  P1.6  ai_runs append-only trigger; input_hash NOT NULL (no default); ai_runs CHECKs
--  P1.9  Wider unique keys on variants + videos for chain validation
--        attribution_windows FKs use 3-column (variant,experiment,project) form
--        evidence_items video FK uses 3-column (video,variant,project) form
--        evidence_items metric snapshot FKs use 3-column form
--  P1.10 redirect_events CHECK(NOT is_unique OR attribution_window_id IS NOT NULL)
--        evidence_items CHECKs on deltas and clicks
--  SEC   authenticated SELECT removed from redirect_events and ai_runs
-- =============================================================================

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
  'clicks_per_1k_views', 'comments_per_1k_views', 'views', 'product_clicks', 'comments'
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
CREATE TYPE variant_position      AS ENUM ('A', 'B', 'C');
CREATE TYPE treatment_role        AS ENUM ('control', 'hypothesis_treatment', 'alternative_treatment');
CREATE TYPE variant_design_status AS ENUM ('queued', 'ready_to_review', 'approved_for_recording', 'recorded');
CREATE TYPE video_status AS ENUM (
  'needs_url', 'validating', 'tracking', 'completed',
  'invalid_url', 'account_mismatch', 'video_private', 'video_deleted', 'tracking_failed'
);
CREATE TYPE attribution_window_status AS ENUM ('scheduled', 'active', 'closed', 'cancelled');
CREATE TYPE snapshot_status           AS ENUM ('pending', 'ready', 'finalized');
CREATE TYPE experiment_outcome AS ENUM (
  'directional_difference', 'mixed_result', 'little_difference',
  'all_variants_weak', 'all_variants_strong', 'insufficient_evidence', 'execution_problem'
);
CREATE TYPE candidate_slot   AS ENUM ('safest_next_step', 'highest_learning', 'highest_upside');
CREATE TYPE candidate_status AS ENUM ('proposed', 'accepted', 'dismissed');
CREATE TYPE fact_status      AS ENUM ('verified', 'rejected');

-- ---------------------------------------------------------------------------
-- Shared trigger helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END; $$;

-- ---------------------------------------------------------------------------
-- projects
-- ---------------------------------------------------------------------------
CREATE TABLE projects (
  id                   uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              uuid         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  product_name         text         NOT NULL DEFAULT '',
  product_type         product_type NOT NULL DEFAULT 'SaaS',
  product_description  text         NOT NULL DEFAULT '',
  product_url          text         NOT NULL DEFAULT '',
  target_audience      text         NOT NULL DEFAULT '',
  problem_solved       text         NOT NULL DEFAULT '',
  why_it_matters       text         NOT NULL DEFAULT '',
  current_alternatives text         NOT NULL DEFAULT '',
  desired_action       text         NOT NULL DEFAULT '',
  primary_cta          text         NOT NULL DEFAULT '',
  tiktok_handle        text         NOT NULL DEFAULT '',
  account_public       boolean      NOT NULL DEFAULT false,
  manual_publish       boolean      NOT NULL DEFAULT false,
  tracking_slug        text         NOT NULL,
  destination_url      text         NOT NULL DEFAULT '',
  context_version      integer      NOT NULL DEFAULT 1,
  onboarded_at         timestamptz,
  created_at           timestamptz  NOT NULL DEFAULT now(),
  updated_at           timestamptz  NOT NULL DEFAULT now(),
  deleted_at           timestamptz,
  CONSTRAINT projects_tracking_slug_unique UNIQUE (tracking_slug),
  CONSTRAINT projects_id_user_unique       UNIQUE (id, user_id)
);

CREATE UNIQUE INDEX one_active_project_per_user
  ON projects (user_id) WHERE deleted_at IS NULL;

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION increment_context_version()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  IF (
    NEW.product_name         IS DISTINCT FROM OLD.product_name         OR
    NEW.product_type         IS DISTINCT FROM OLD.product_type         OR
    NEW.product_description  IS DISTINCT FROM OLD.product_description  OR
    NEW.product_url          IS DISTINCT FROM OLD.product_url          OR
    NEW.target_audience      IS DISTINCT FROM OLD.target_audience      OR
    NEW.problem_solved       IS DISTINCT FROM OLD.problem_solved       OR
    NEW.why_it_matters       IS DISTINCT FROM OLD.why_it_matters       OR
    NEW.current_alternatives IS DISTINCT FROM OLD.current_alternatives OR
    NEW.desired_action       IS DISTINCT FROM OLD.desired_action       OR
    NEW.primary_cta          IS DISTINCT FROM OLD.primary_cta          OR
    NEW.tiktok_handle        IS DISTINCT FROM OLD.tiktok_handle
  ) THEN
    NEW.context_version := OLD.context_version + 1;
  END IF;
  RETURN NEW;
END; $$;

CREATE TRIGGER projects_context_version
  BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION increment_context_version();

-- ---------------------------------------------------------------------------
-- project_facts  + context_version sync trigger
-- ---------------------------------------------------------------------------
CREATE TABLE project_facts (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  fact_text   text        NOT NULL,
  category    text        NOT NULL DEFAULT '',
  source      text        NOT NULL DEFAULT '',
  status      fact_status NOT NULL DEFAULT 'verified',
  verified_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER project_facts_updated_at
  BEFORE UPDATE ON project_facts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION sync_facts_context_version()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_project_id  uuid;
  v_should_bump boolean := false;
BEGIN
  IF TG_OP = 'DELETE' THEN
    v_project_id  := OLD.project_id;
    v_should_bump := (OLD.status = 'verified');
    IF v_should_bump THEN
      UPDATE public.projects SET context_version = context_version + 1 WHERE id = v_project_id;
    END IF;
    RETURN OLD;
  END IF;
  v_project_id := NEW.project_id;
  IF TG_OP = 'INSERT' THEN
    v_should_bump := (NEW.status = 'verified');
  ELSE
    v_should_bump := (
      (OLD.status = 'rejected' AND NEW.status = 'verified') OR
      (OLD.status = 'verified' AND NEW.status = 'rejected') OR
      (NEW.status = 'verified' AND OLD.fact_text IS DISTINCT FROM NEW.fact_text)
    );
  END IF;
  IF v_should_bump THEN
    UPDATE public.projects SET context_version = context_version + 1 WHERE id = v_project_id;
  END IF;
  RETURN NEW;
END; $$;

CREATE TRIGGER project_facts_context_version
  AFTER INSERT OR UPDATE OR DELETE ON project_facts
  FOR EACH ROW EXECUTE FUNCTION sync_facts_context_version();

-- ---------------------------------------------------------------------------
-- hypotheses
-- parent_hypothesis_id: inline FK removed; composite FK added post-create [P0.4]
-- ---------------------------------------------------------------------------
CREATE TABLE hypotheses (
  id                      uuid                    PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id              uuid                    NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title                   text                    NOT NULL DEFAULT '',
  statement               text                    NOT NULL DEFAULT '',
  research_question       text,
  independent_variable    text,
  control_condition       text,
  treatment_condition     text,
  controlled_elements     text[]                  NOT NULL DEFAULT '{}',
  contradiction_condition text,
  primary_metric          primary_metric          NOT NULL DEFAULT 'clicks_per_1k_views',
  rationale               text,
  category                text,
  status                  hypothesis_status       NOT NULL DEFAULT 'generated',
  -- [P0.4] inline FK removed; composite self-ref added post-create
  parent_hypothesis_id    uuid,
  source_candidate_id     uuid                    UNIQUE,
  relationship_type       hypothesis_relationship,
  previous_learning       text,
  remaining_unknown       text,
  recommendation_reason   text,
  created_by_ai_run_id    uuid,
  created_at              timestamptz             NOT NULL DEFAULT now(),
  updated_at              timestamptz             NOT NULL DEFAULT now(),
  approved_at             timestamptz,
  rejected_at             timestamptz,
  tested_at               timestamptz,

  CONSTRAINT hypothesis_lineage_consistency CHECK (
    (parent_hypothesis_id IS NULL) = (source_candidate_id IS NULL)
  ),
  CONSTRAINT hypothesis_relationship_consistency CHECK (
    (source_candidate_id IS NULL) = (relationship_type IS NULL)
  ),
  CONSTRAINT hypotheses_id_project_unique UNIQUE (id, project_id)
);

CREATE TRIGGER hypotheses_updated_at
  BEFORE UPDATE ON hypotheses FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- experiments
-- [P0.5] hypothesis_design_snapshot: no default, CHECK enforced
-- [P0.5] shared_constraints: versioned default + CHECK
-- ---------------------------------------------------------------------------

-- Helper: JSONB object with schemaVersion check
CREATE OR REPLACE FUNCTION is_versioned_jsonb(j jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT
    jsonb_typeof(j) = 'object'
    AND j ? 'schemaVersion'
    AND j->>'schemaVersion' = '1';
$$;

CREATE TABLE experiments (
  id                         uuid              PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                 uuid              NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hypothesis_id              uuid              NOT NULL,
  name                       text              NOT NULL DEFAULT '',
  tracking_window_hours      integer           NOT NULL DEFAULT 72,
  status                     experiment_status NOT NULL DEFAULT 'ready',
  -- [P0.5] no default; application must supply; CHECK enforced
  hypothesis_design_snapshot jsonb             NOT NULL
    CONSTRAINT exp_design_snapshot_versioned CHECK (is_versioned_jsonb(hypothesis_design_snapshot)),
  -- [P0.5] versioned default
  shared_constraints         jsonb             NOT NULL DEFAULT '{"schemaVersion":1}'
    CONSTRAINT exp_shared_constraints_versioned CHECK (is_versioned_jsonb(shared_constraints)),
  design_schema_version      integer           NOT NULL DEFAULT 1,
  created_at                 timestamptz       NOT NULL DEFAULT now(),
  updated_at                 timestamptz       NOT NULL DEFAULT now(),
  started_at                 timestamptz,
  tracking_completed_at      timestamptz,
  analysis_started_at        timestamptz,
  completed_at               timestamptz,
  cancelled_at               timestamptz,
  cancellation_reason        text,

  CONSTRAINT experiments_tracking_window_positive CHECK (tracking_window_hours > 0),
  CONSTRAINT experiments_hypothesis_unique        UNIQUE (hypothesis_id),
  CONSTRAINT experiments_id_project_unique        UNIQUE (id, project_id),
  CONSTRAINT experiments_hypothesis_project_fk
    FOREIGN KEY (hypothesis_id, project_id) REFERENCES hypotheses(id, project_id)
);

CREATE TRIGGER experiments_updated_at
  BEFORE UPDATE ON experiments FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION prevent_design_snapshot_change()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  IF NEW.hypothesis_design_snapshot IS DISTINCT FROM OLD.hypothesis_design_snapshot THEN
    RAISE EXCEPTION 'experiments.hypothesis_design_snapshot is immutable (id: %)', OLD.id;
  END IF;
  RETURN NEW;
END; $$;

CREATE TRIGGER experiments_snapshot_immutable
  BEFORE UPDATE ON experiments FOR EACH ROW EXECUTE FUNCTION prevent_design_snapshot_change();

-- ---------------------------------------------------------------------------
-- variants
-- [P0.5] script_sections + recording_guidance versioned + CHECK
-- [P0.6] position ↔ treatment_role mapping
-- [P1.9] wider unique key (id, experiment_id, project_id)
-- ---------------------------------------------------------------------------
CREATE TABLE variants (
  id                        uuid                  PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                uuid                  NOT NULL,
  experiment_id             uuid                  NOT NULL,
  position                  variant_position      NOT NULL,
  treatment_role            treatment_role        NOT NULL,
  title                     text                  NOT NULL DEFAULT '',
  variable_value            text                  NOT NULL DEFAULT '',
  hook                      text                  NOT NULL DEFAULT '',
  hook_delivery_note        text,
  context                   text,
  on_screen_text            text,
  -- [P0.5] object with sections array
  script_sections           jsonb                 NOT NULL DEFAULT '{"schemaVersion":1,"sections":[]}'
    CONSTRAINT variants_script_sections_versioned CHECK (is_versioned_jsonb(script_sections)),
  -- [P0.5] versioned
  recording_guidance        jsonb                 NOT NULL DEFAULT '{"schemaVersion":1}'
    CONSTRAINT variants_recording_guidance_versioned CHECK (is_versioned_jsonb(recording_guidance)),
  status                    variant_design_status NOT NULL DEFAULT 'queued',
  generated_by_ai_run_id    uuid,
  approved_for_recording_at timestamptz,
  recorded_at               timestamptz,
  created_at                timestamptz           NOT NULL DEFAULT now(),
  updated_at                timestamptz           NOT NULL DEFAULT now(),

  CONSTRAINT variants_experiment_project_fk
    FOREIGN KEY (experiment_id, project_id) REFERENCES experiments(id, project_id)
    ON DELETE CASCADE,
  CONSTRAINT variants_position_unique  UNIQUE (experiment_id, position),
  CONSTRAINT variants_role_unique      UNIQUE (experiment_id, treatment_role),
  -- [P0.6] canonical mapping
  CONSTRAINT variants_position_role_mapping CHECK (
    (position = 'A' AND treatment_role = 'control')              OR
    (position = 'B' AND treatment_role = 'hypothesis_treatment') OR
    (position = 'C' AND treatment_role = 'alternative_treatment')
  ),
  CONSTRAINT variants_id_project_unique          UNIQUE (id, project_id),
  -- [P1.9] wider key for chain validation
  CONSTRAINT variants_id_experiment_project_unique UNIQUE (id, experiment_id, project_id)
);

CREATE TRIGGER variants_updated_at
  BEFORE UPDATE ON variants FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- videos
-- [P1.9] wider unique key (id, variant_id, project_id) for chain validation
-- ---------------------------------------------------------------------------
CREATE TABLE videos (
  id                          uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                  uuid         NOT NULL,
  variant_id                  uuid         NOT NULL,
  attempt_number              integer      NOT NULL DEFAULT 1,
  is_current                  boolean      NOT NULL DEFAULT true,
  status                      video_status NOT NULL DEFAULT 'needs_url',
  submitted_url               text,
  normalized_tiktok_url       text,
  tiktok_video_id             text,
  user_confirmed_published_at timestamptz,
  published_at                timestamptz,
  validated_at                timestamptz,
  tracking_started_at         timestamptz,
  tracking_window_ends_at     timestamptz,
  last_refreshed_at           timestamptz,
  validation_error_code       text,
  validation_error_detail     text,
  created_at                  timestamptz  NOT NULL DEFAULT now(),
  updated_at                  timestamptz  NOT NULL DEFAULT now(),

  CONSTRAINT videos_variant_project_fk
    FOREIGN KEY (variant_id, project_id) REFERENCES variants(id, project_id)
    ON DELETE CASCADE,
  CONSTRAINT videos_attempt_unique    UNIQUE (variant_id, attempt_number),
  CONSTRAINT videos_attempt_positive  CHECK  (attempt_number >= 1),
  CONSTRAINT videos_id_project_unique UNIQUE (id, project_id),
  -- [P1.9] wider key for EvidenceItem chain validation
  CONSTRAINT videos_id_variant_project_unique UNIQUE (id, variant_id, project_id)
);

CREATE UNIQUE INDEX one_current_video_per_variant
  ON videos (variant_id) WHERE is_current = true;
CREATE UNIQUE INDEX videos_tiktok_video_id_unique
  ON videos (tiktok_video_id) WHERE tiktok_video_id IS NOT NULL;
CREATE UNIQUE INDEX videos_normalized_url_unique
  ON videos (normalized_tiktok_url) WHERE normalized_tiktok_url IS NOT NULL;

CREATE TRIGGER videos_updated_at
  BEFORE UPDATE ON videos FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- video_metric_snapshots
-- [P1.9] wider unique key (id, video_id, project_id) for EvidenceItem chain
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

  CONSTRAINT vms_video_project_fk
    FOREIGN KEY (video_id, project_id) REFERENCES videos(id, project_id)
    ON DELETE CASCADE,
  CONSTRAINT vms_views_nonneg     CHECK (views    >= 0),
  CONSTRAINT vms_likes_nonneg     CHECK (likes    >= 0),
  CONSTRAINT vms_comments_nonneg  CHECK (comments >= 0),
  CONSTRAINT vms_video_time_unique UNIQUE (video_id, collected_at),
  CONSTRAINT vms_id_project_unique UNIQUE (id, project_id),
  -- [P1.9] wider key so EvidenceItem can validate snapshot belongs to correct video
  CONSTRAINT vms_id_video_project_unique UNIQUE (id, video_id, project_id)
);

CREATE INDEX vms_video_id_collected_at ON video_metric_snapshots (video_id, collected_at DESC);

-- ---------------------------------------------------------------------------
-- execution_observations
-- ---------------------------------------------------------------------------
CREATE TABLE execution_observations (
  id                                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                         uuid        NOT NULL,
  video_id                           uuid        NOT NULL,
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

  CONSTRAINT eo_video_project_fk
    FOREIGN KEY (video_id, project_id) REFERENCES videos(id, project_id)
    ON DELETE CASCADE,
  CONSTRAINT eo_video_unique    UNIQUE (video_id),
  CONSTRAINT eo_duration_nonneg CHECK (actual_duration_seconds         IS NULL OR actual_duration_seconds >= 0),
  CONSTRAINT eo_reveal_nonneg   CHECK (actual_product_reveal_seconds   IS NULL OR actual_product_reveal_seconds >= 0),
  CONSTRAINT eo_id_project_unique UNIQUE (id, project_id)
);

CREATE TRIGGER execution_observations_updated_at
  BEFORE UPDATE ON execution_observations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- attribution_windows
-- [P1.9] 3-column FKs for variant (ensures variant in experiment) and video (ensures video on variant)
-- ---------------------------------------------------------------------------
CREATE TABLE attribution_windows (
  id             uuid                      PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     uuid                      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  experiment_id  uuid                      NOT NULL,
  variant_id     uuid                      NOT NULL,
  video_id       uuid                      NOT NULL,
  starts_at      timestamptz               NOT NULL,
  ends_at        timestamptz               NOT NULL,
  status         attribution_window_status NOT NULL DEFAULT 'scheduled',
  created_at     timestamptz               NOT NULL DEFAULT now(),

  CONSTRAINT aw_video_unique       UNIQUE (video_id),
  CONSTRAINT aw_ends_after_starts  CHECK  (ends_at > starts_at),

  -- experiment must belong to project
  CONSTRAINT aw_experiment_project_fk
    FOREIGN KEY (experiment_id, project_id) REFERENCES experiments(id, project_id),

  -- [P1.9] variant must belong to the correct experiment within project
  CONSTRAINT aw_variant_experiment_project_fk
    FOREIGN KEY (variant_id, experiment_id, project_id)
    REFERENCES variants(id, experiment_id, project_id),

  -- [P1.9] video must belong to the correct variant within project
  CONSTRAINT aw_video_variant_project_fk
    FOREIGN KEY (video_id, variant_id, project_id)
    REFERENCES videos(id, variant_id, project_id),

  CONSTRAINT aw_id_project_unique UNIQUE (id, project_id),

  CONSTRAINT no_overlapping_active_windows EXCLUDE USING gist (
    project_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
  ) WHERE (status IN ('scheduled', 'active'))
);

CREATE INDEX aw_project_range ON attribution_windows USING gist (
  project_id, tstzrange(starts_at, ends_at, '[)')
) WHERE status IN ('scheduled', 'active');

-- ---------------------------------------------------------------------------
-- redirect_events
-- [P1.10] CHECK: is_unique requires attribution_window_id
-- [SEC]   no authenticated SELECT (sensitive visitor_key data)
-- ---------------------------------------------------------------------------
CREATE TABLE redirect_events (
  id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  attribution_window_id uuid,
  visitor_key           text        NOT NULL,
  is_unique             boolean     NOT NULL DEFAULT false,
  occurred_at           timestamptz NOT NULL,
  destination_url       text        NOT NULL,
  request_metadata      jsonb       NOT NULL DEFAULT '{}',
  created_at            timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT re_window_project_fk
    FOREIGN KEY (attribution_window_id, project_id)
    REFERENCES attribution_windows(id, project_id),

  -- [P1.10] a unique attributed click must have a window
  CONSTRAINT re_unique_requires_window CHECK (
    NOT is_unique OR attribution_window_id IS NOT NULL
  )
);

CREATE UNIQUE INDEX one_unique_click_per_visitor_window
  ON redirect_events (attribution_window_id, visitor_key)
  WHERE is_unique = true AND attribution_window_id IS NOT NULL;

CREATE INDEX re_project_occurred ON redirect_events (project_id, occurred_at DESC);
CREATE INDEX re_window           ON redirect_events (attribution_window_id)
  WHERE attribution_window_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- experiment_evidence_snapshots
-- [P0.5] attribution_conditions moved to items (no versioned JSONB here)
-- [P0.8] immutable after finalization
-- ---------------------------------------------------------------------------
CREATE TABLE experiment_evidence_snapshots (
  id                 uuid            PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id         uuid            NOT NULL,
  experiment_id      uuid            NOT NULL,
  version            integer         NOT NULL DEFAULT 1,
  status             snapshot_status NOT NULL DEFAULT 'pending',
  attribution_method text            NOT NULL DEFAULT 'isolated_window',
  generated_at       timestamptz     NOT NULL DEFAULT now(),
  finalized_at       timestamptz,
  created_by_job_id  uuid,

  CONSTRAINT ees_experiment_project_fk
    FOREIGN KEY (experiment_id, project_id) REFERENCES experiments(id, project_id),
  CONSTRAINT ees_version_unique    UNIQUE (experiment_id, version),
  CONSTRAINT ees_id_project_unique UNIQUE (id, project_id)
);

CREATE OR REPLACE FUNCTION prevent_finalized_snapshot_mutation()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  IF OLD.status = 'finalized' THEN
    RAISE EXCEPTION 'Finalized evidence snapshots are immutable (id: %)', OLD.id;
  END IF;
  IF TG_OP = 'UPDATE' THEN RETURN NEW; END IF;
  RETURN OLD;
END; $$;

CREATE TRIGGER ees_finalized_immutable
  BEFORE UPDATE OR DELETE ON experiment_evidence_snapshots
  FOR EACH ROW EXECUTE FUNCTION prevent_finalized_snapshot_mutation();

-- ---------------------------------------------------------------------------
-- experiment_evidence_items
-- [P0.3]  BEFORE INSERT OR UPDATE OR DELETE; checks NEW and OLD snapshot IDs
-- [P0.5]  attribution_conditions: versioned default + CHECK
-- [P1.9]  3-column FK for video (ensures video belongs to variant)
--         3-column FKs for metric snapshots (ensures snapshots belong to video)
-- [P1.10] non-negative delta + click CHECKs
-- ---------------------------------------------------------------------------
CREATE TABLE experiment_evidence_items (
  id                       uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id               uuid    NOT NULL,
  evidence_snapshot_id     uuid    NOT NULL,
  variant_id               uuid    NOT NULL,
  video_id                 uuid    NOT NULL,
  start_metric_snapshot_id uuid    NOT NULL,
  end_metric_snapshot_id   uuid    NOT NULL,
  views_delta              integer NOT NULL DEFAULT 0,
  likes_delta              integer NOT NULL DEFAULT 0,
  comments_delta           integer NOT NULL DEFAULT 0,
  attributed_unique_clicks integer NOT NULL DEFAULT 0,
  unique_clicks_per_1k     numeric,
  execution_observation_id uuid,
  attribution_window_id    uuid    NOT NULL,
  -- [P0.5] versioned
  attribution_conditions   jsonb   NOT NULL DEFAULT '{"schemaVersion":1}'
    CONSTRAINT eei_attribution_conditions_versioned CHECK (is_versioned_jsonb(attribution_conditions)),

  -- snapshot must belong to project
  CONSTRAINT eei_snapshot_project_fk
    FOREIGN KEY (evidence_snapshot_id, project_id)
    REFERENCES experiment_evidence_snapshots(id, project_id)
    ON DELETE CASCADE,

  -- variant must belong to project
  CONSTRAINT eei_variant_project_fk
    FOREIGN KEY (variant_id, project_id) REFERENCES variants(id, project_id),

  -- [P1.9] video must belong to the correct variant
  CONSTRAINT eei_video_variant_project_fk
    FOREIGN KEY (video_id, variant_id, project_id)
    REFERENCES videos(id, variant_id, project_id),

  -- [P1.9] metric snapshots must belong to the correct video
  CONSTRAINT eei_start_snapshot_fk
    FOREIGN KEY (start_metric_snapshot_id, video_id, project_id)
    REFERENCES video_metric_snapshots(id, video_id, project_id),
  CONSTRAINT eei_end_snapshot_fk
    FOREIGN KEY (end_metric_snapshot_id, video_id, project_id)
    REFERENCES video_metric_snapshots(id, video_id, project_id),

  CONSTRAINT eei_eo_project_fk
    FOREIGN KEY (execution_observation_id, project_id)
    REFERENCES execution_observations(id, project_id),
  CONSTRAINT eei_aw_project_fk
    FOREIGN KEY (attribution_window_id, project_id)
    REFERENCES attribution_windows(id, project_id),

  CONSTRAINT eei_variant_snapshot_unique UNIQUE (evidence_snapshot_id, variant_id),

  -- [P1.10] non-negative evidence values
  CONSTRAINT eei_views_delta_nonneg   CHECK (views_delta              >= 0),
  CONSTRAINT eei_likes_delta_nonneg   CHECK (likes_delta              >= 0),
  CONSTRAINT eei_comments_delta_nonneg CHECK (comments_delta          >= 0),
  CONSTRAINT eei_clicks_nonneg        CHECK (attributed_unique_clicks >= 0),
  CONSTRAINT eei_clicks_per_1k_nonneg CHECK (unique_clicks_per_1k IS NULL OR unique_clicks_per_1k >= 0)
);

-- [P0.3] Trigger covers INSERT + UPDATE (checks both old and new snapshot) + DELETE
CREATE OR REPLACE FUNCTION prevent_finalized_item_mutation()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = '' AS $$
DECLARE
  v_snap_id   uuid;
  v_snap_ids  uuid[];
  v_status    text;
BEGIN
  -- Build list of snapshot IDs to check
  IF TG_OP = 'INSERT' THEN
    v_snap_ids := ARRAY[NEW.evidence_snapshot_id];
  ELSIF TG_OP = 'DELETE' THEN
    v_snap_ids := ARRAY[OLD.evidence_snapshot_id];
  ELSE -- UPDATE: check both old and new parent
    v_snap_ids := ARRAY[OLD.evidence_snapshot_id, NEW.evidence_snapshot_id];
  END IF;

  FOREACH v_snap_id IN ARRAY v_snap_ids LOOP
    SELECT status INTO v_status
    FROM public.experiment_evidence_snapshots
    WHERE id = v_snap_id;

    IF v_status = 'finalized' THEN
      RAISE EXCEPTION
        'Evidence items under finalized snapshots are immutable (snapshot_id: %)', v_snap_id;
    END IF;
  END LOOP;

  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$;

CREATE TRIGGER eei_finalized_immutable
  BEFORE INSERT OR UPDATE OR DELETE ON experiment_evidence_items
  FOR EACH ROW EXECUTE FUNCTION prevent_finalized_item_mutation();

-- ---------------------------------------------------------------------------
-- insights
-- [P0.5] evidence_basis versioned default + CHECK
-- ---------------------------------------------------------------------------
CREATE TABLE insights (
  id                     uuid               PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id             uuid               NOT NULL,
  experiment_id          uuid               NOT NULL,
  evidence_snapshot_id   uuid               NOT NULL,
  version                integer            NOT NULL DEFAULT 1,
  is_current             boolean            NOT NULL DEFAULT true,
  superseded_at          timestamptz,
  generated_by_ai_run_id uuid,
  research_question      text,
  hypothesis_text        text,
  primary_metric         primary_metric,
  outcome_type           experiment_outcome,
  -- [P0.5] versioned
  evidence_basis         jsonb              NOT NULL DEFAULT '{"schemaVersion":1}'
    CONSTRAINT insights_evidence_basis_versioned CHECK (is_versioned_jsonb(evidence_basis)),
  supported_learning     text,
  do_not_infer_yet       text[]             NOT NULL DEFAULT '{}',
  recommended_next_test  text,
  limitations            text[]             NOT NULL DEFAULT '{}',
  outcome_description    text,
  generated_at           timestamptz        NOT NULL DEFAULT now(),

  CONSTRAINT insights_experiment_project_fk
    FOREIGN KEY (experiment_id, project_id) REFERENCES experiments(id, project_id),
  CONSTRAINT insights_snapshot_project_fk
    FOREIGN KEY (evidence_snapshot_id, project_id)
    REFERENCES experiment_evidence_snapshots(id, project_id),
  CONSTRAINT insights_version_unique    UNIQUE (experiment_id, version),
  CONSTRAINT insights_id_project_unique UNIQUE (id, project_id)
);

CREATE UNIQUE INDEX one_current_insight_per_experiment
  ON insights (experiment_id) WHERE is_current = true;

-- ---------------------------------------------------------------------------
-- follow_up_candidates
-- [P0.3 / Patch 3] accepted_hypothesis_id removed
-- [P0.4] one recommended per insight partial unique index
-- ---------------------------------------------------------------------------
CREATE TABLE follow_up_candidates (
  id                    uuid                    PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id            uuid                    NOT NULL,
  insight_id            uuid                    NOT NULL,
  slot                  candidate_slot          NOT NULL,
  relationship_type     hypothesis_relationship NOT NULL,
  statement             text                    NOT NULL DEFAULT '',
  why_this_follows      text,
  recommended           boolean                 NOT NULL DEFAULT false,
  recommendation_reason text,
  previous_learning     text,
  remaining_unknown     text,
  status                candidate_status        NOT NULL DEFAULT 'proposed',
  created_at            timestamptz             NOT NULL DEFAULT now(),

  CONSTRAINT fuc_insight_project_fk
    FOREIGN KEY (insight_id, project_id) REFERENCES insights(id, project_id),
  CONSTRAINT fuc_slot_unique       UNIQUE (insight_id, slot),
  CONSTRAINT fuc_id_project_unique UNIQUE (id, project_id)
);

CREATE UNIQUE INDEX one_recommended_candidate_per_insight
  ON follow_up_candidates (insight_id) WHERE recommended = true;

-- ---------------------------------------------------------------------------
-- ai_runs
-- [P1.6] input_hash NOT NULL, no default; format CHECK; additional CHECKs
-- [P1.6] append-only trigger
-- [SEC]  no authenticated SELECT (raw AI payloads)
-- ---------------------------------------------------------------------------
CREATE TABLE ai_runs (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        uuid        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  entity_type       text        NOT NULL,
  entity_id         uuid,
  field_name        text,
  operation         text        NOT NULL,
  model             text        NOT NULL,
  prompt_version    text        NOT NULL DEFAULT '1',
  context_version   integer     NOT NULL DEFAULT 1,
  -- [P1.6] no default; application must compute and supply sha256 hex digest
  input_hash        text        NOT NULL
    CONSTRAINT ai_runs_input_hash_format CHECK (input_hash ~ '^[0-9a-f]{64}$'),
  input_payload     jsonb       NOT NULL DEFAULT '{}',
  output_payload    jsonb       NOT NULL DEFAULT '{}',
  validation_result text        NOT NULL DEFAULT 'valid'
    CONSTRAINT ai_runs_validation_result_check
      CHECK (validation_result IN ('valid', 'invalid', 'parse_error')),
  token_usage       jsonb       NOT NULL DEFAULT '{}',
  cost_usd          numeric
    CONSTRAINT ai_runs_cost_nonneg  CHECK (cost_usd  IS NULL OR cost_usd  >= 0),
  latency_ms        integer
    CONSTRAINT ai_runs_latency_nonneg CHECK (latency_ms IS NULL OR latency_ms >= 0),
  status            text        NOT NULL DEFAULT 'success'
    CONSTRAINT ai_runs_status_check CHECK (status IN ('success', 'failed', 'timeout')),
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ai_runs_context_version_pos CHECK (context_version > 0),
  CONSTRAINT ai_runs_id_project_unique   UNIQUE (id, project_id)
);

CREATE INDEX ai_runs_entity       ON ai_runs (entity_type, entity_id);
CREATE INDEX ai_runs_project_time ON ai_runs (project_id, created_at DESC);
CREATE INDEX ai_runs_project_hash ON ai_runs (project_id, input_hash);

-- [P1.6] ai_runs is append-only
CREATE OR REPLACE FUNCTION prevent_ai_run_mutation()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  RAISE EXCEPTION 'ai_runs is append-only';
END; $$;

CREATE TRIGGER ai_runs_append_only
  BEFORE UPDATE OR DELETE ON ai_runs
  FOR EACH ROW EXECUTE FUNCTION prevent_ai_run_mutation();

-- ---------------------------------------------------------------------------
-- Deferred / circular foreign keys
-- [P0.4] parent_hypothesis_id composite self-ref (now DEFERRABLE)
-- ---------------------------------------------------------------------------

-- [P0.4] parent Hypothesis must belong to same project
ALTER TABLE hypotheses
  ADD CONSTRAINT hypotheses_parent_project_fk
  FOREIGN KEY (parent_hypothesis_id, project_id)
  REFERENCES hypotheses(id, project_id)
  DEFERRABLE INITIALLY DEFERRED;

-- source_candidate_id (composite)
ALTER TABLE hypotheses
  ADD CONSTRAINT hypotheses_source_candidate_fk
  FOREIGN KEY (source_candidate_id, project_id)
  REFERENCES follow_up_candidates(id, project_id);

-- created_by_ai_run_id (composite)
ALTER TABLE hypotheses
  ADD CONSTRAINT hypotheses_ai_run_fk
  FOREIGN KEY (created_by_ai_run_id, project_id)
  REFERENCES ai_runs(id, project_id);

-- variants.generated_by_ai_run_id (composite)
ALTER TABLE variants
  ADD CONSTRAINT variants_ai_run_fk
  FOREIGN KEY (generated_by_ai_run_id, project_id)
  REFERENCES ai_runs(id, project_id);

-- insights.generated_by_ai_run_id (composite)
ALTER TABLE insights
  ADD CONSTRAINT insights_ai_run_fk
  FOREIGN KEY (generated_by_ai_run_id, project_id)
  REFERENCES ai_runs(id, project_id);

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- [P9 / SEC] FOR SELECT only; redirect_events and ai_runs have NO authenticated SELECT
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION owns_project(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.projects
    WHERE id = p_project_id AND user_id = auth.uid() AND deleted_at IS NULL
  );
$$;

REVOKE ALL ON FUNCTION owns_project(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION owns_project(uuid) TO authenticated;

ALTER TABLE projects                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_facts                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE hypotheses                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiments                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE variants                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos                        ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_metric_snapshots        ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_observations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE attribution_windows           ENABLE ROW LEVEL SECURITY;
ALTER TABLE redirect_events               ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_evidence_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE experiment_evidence_items     ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE follow_up_candidates          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_runs                       ENABLE ROW LEVEL SECURITY;

CREATE POLICY projects_select          ON projects               FOR SELECT USING (user_id = auth.uid() AND deleted_at IS NULL);
CREATE POLICY project_facts_select     ON project_facts          FOR SELECT USING (owns_project(project_id));
CREATE POLICY hypotheses_select        ON hypotheses             FOR SELECT USING (owns_project(project_id));
CREATE POLICY experiments_select       ON experiments            FOR SELECT USING (owns_project(project_id));
CREATE POLICY variants_select          ON variants               FOR SELECT USING (owns_project(project_id));
CREATE POLICY videos_select            ON videos                 FOR SELECT USING (owns_project(project_id));
CREATE POLICY vms_select               ON video_metric_snapshots FOR SELECT USING (owns_project(project_id));
CREATE POLICY eo_select                ON execution_observations FOR SELECT USING (owns_project(project_id));
CREATE POLICY aw_select                ON attribution_windows    FOR SELECT USING (owns_project(project_id));
-- [SEC] redirect_events: NO authenticated SELECT (raw visitor_key data)
CREATE POLICY ees_select ON experiment_evidence_snapshots FOR SELECT USING (owns_project(project_id));
CREATE POLICY eei_select ON experiment_evidence_items     FOR SELECT USING (owns_project(project_id));
CREATE POLICY insights_select ON insights                 FOR SELECT USING (owns_project(project_id));
CREATE POLICY fuc_select ON follow_up_candidates          FOR SELECT USING (owns_project(project_id));
-- [SEC] ai_runs: NO authenticated SELECT (raw AI payloads)
