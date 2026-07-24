-- =============================================================================
-- 002_job_infrastructure.sql
-- Content Lab — durable background job queue
--
-- Postgres-backed queue claimed with SELECT ... FOR UPDATE SKIP LOCKED.
-- Dedicated scheduler + worker processes poll this table.
-- pg_cron may optionally wake the scheduler, but workflow logic lives here.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- jobs table
-- ---------------------------------------------------------------------------
CREATE TABLE jobs (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       uuid        REFERENCES projects(id) ON DELETE CASCADE,

  -- What to do
  job_type         text        NOT NULL,  -- see §Job Types
  entity_type      text,                  -- e.g. Experiment, Video, Variant
  entity_id        uuid,
  payload          jsonb       NOT NULL DEFAULT '{}',

  -- Scheduling
  status           text        NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
  run_at           timestamptz NOT NULL DEFAULT now(),       -- earliest execution time

  -- Retry tracking
  attempt_count    integer     NOT NULL DEFAULT 0,
  max_attempts     integer     NOT NULL DEFAULT 3,

  -- Distributed locking
  locked_at        timestamptz,
  locked_by        text,                  -- worker instance ID
  lease_expires_at timestamptz,

  -- Idempotency
  idempotency_key  text        NOT NULL,  -- see §Idempotency Keys
  CONSTRAINT jobs_idempotency_unique UNIQUE (idempotency_key),

  -- Results
  result_payload   jsonb,
  last_error       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  completed_at     timestamptz
);

CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Indexes for claim queries
CREATE INDEX jobs_claimable ON jobs (run_at, status, locked_at)
  WHERE status = 'pending' AND (locked_at IS NULL OR lease_expires_at < now());

CREATE INDEX jobs_project ON jobs (project_id, status, run_at)
  WHERE project_id IS NOT NULL;

CREATE INDEX jobs_entity ON jobs (entity_type, entity_id)
  WHERE entity_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Claim function
-- Returns one claimable job row, locked for this worker.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION claim_job(
  p_worker_id    text,
  p_job_types    text[],
  p_lease_seconds integer DEFAULT 120
)
RETURNS SETOF jobs LANGUAGE sql AS $$
  UPDATE jobs
  SET
    status           = 'running',
    locked_at        = now(),
    locked_by        = p_worker_id,
    lease_expires_at = now() + (p_lease_seconds || ' seconds')::interval,
    attempt_count    = attempt_count + 1,
    updated_at       = now()
  WHERE id = (
    SELECT id FROM jobs
    WHERE status = 'pending'
      AND run_at <= now()
      AND (locked_at IS NULL OR lease_expires_at < now())
      AND (p_job_types IS NULL OR job_type = ANY(p_job_types))
    ORDER BY run_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
$$;

-- ---------------------------------------------------------------------------
-- Complete / fail helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION complete_job(
  p_job_id       uuid,
  p_result       jsonb DEFAULT '{}'
)
RETURNS void LANGUAGE sql AS $$
  UPDATE jobs
  SET status        = 'completed',
      result_payload = p_result,
      completed_at  = now(),
      locked_at     = NULL,
      locked_by     = NULL,
      lease_expires_at = NULL,
      updated_at    = now()
  WHERE id = p_job_id;
$$;

CREATE OR REPLACE FUNCTION fail_job(
  p_job_id    uuid,
  p_error     text,
  p_retry_in  interval DEFAULT '60 seconds'
)
RETURNS void LANGUAGE sql AS $$
  UPDATE jobs
  SET status           = CASE WHEN attempt_count >= max_attempts THEN 'failed' ELSE 'pending' END,
      last_error       = p_error,
      run_at           = CASE WHEN attempt_count >= max_attempts THEN run_at ELSE now() + p_retry_in END,
      locked_at        = NULL,
      locked_by        = NULL,
      lease_expires_at = NULL,
      updated_at       = now()
  WHERE id = p_job_id;
$$;

-- ---------------------------------------------------------------------------
-- Enqueue helper (prevents duplicate pending jobs via idempotency_key)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enqueue_job(
  p_job_type         text,
  p_idempotency_key  text,
  p_payload          jsonb DEFAULT '{}',
  p_entity_type      text DEFAULT NULL,
  p_entity_id        uuid DEFAULT NULL,
  p_project_id       uuid DEFAULT NULL,
  p_run_at           timestamptz DEFAULT now(),
  p_max_attempts     integer DEFAULT 3
)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
  v_id uuid;
BEGIN
  INSERT INTO jobs (
    project_id, job_type, entity_type, entity_id,
    payload, idempotency_key, run_at, max_attempts
  ) VALUES (
    p_project_id, p_job_type, p_entity_type, p_entity_id,
    p_payload, p_idempotency_key, p_run_at, p_max_attempts
  )
  ON CONFLICT (idempotency_key) DO NOTHING
  RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

-- ---------------------------------------------------------------------------
-- Job Types
-- (document here; enforce in application code)
-- ---------------------------------------------------------------------------

-- refresh_video_metrics
--   payload: { video_id, experiment_id }
--   idempotency: refresh_video_metrics:{video_id}:{floor(epoch/3600)}
--   Collects views/likes/comments via phone automation; inserts VideoMetricSnapshot.

-- close_attribution_window
--   payload: { attribution_window_id }
--   idempotency: close_attribution_window:{attribution_window_id}
--   Sets window.status = 'closed'. Triggers variant unlock or evidence finalization.

-- unlock_variant
--   payload: { variant_id, next_variant_id }
--   idempotency: unlock_variant:{next_variant_id}
--   Sets next variant.status = 'ready_to_review'.

-- finalize_evidence
--   payload: { experiment_id, snapshot_version }
--   idempotency: finalize_evidence:{experiment_id}:{snapshot_version}
--   Collects evidence items; counts unique clicks; computes unique_clicks_per_1k.
--   Sets snapshot.status = 'finalized'. Sets experiment.status = 'analyzing'.

-- generate_insight
--   payload: { evidence_snapshot_id }
--   idempotency: generate_insight:{evidence_snapshot_id}
--   Calls Claude; persists Insight + FollowUpCandidates.
--   Sets experiment.status = 'completed'; hypothesis.status = 'tested'.

-- generate_hypotheses
--   payload: { project_id, context_version }
--   idempotency: generate_hypotheses:{project_id}:{context_version}
--   Calls Claude with project context; inserts batch of hypotheses.

-- revise_brief
--   payload: { variant_id, instruction, ai_run_id }
--   idempotency: revise_brief:{variant_id}:{ai_run_id}
--   Applies Claude revision to variant hook/delivery/context.

-- ---------------------------------------------------------------------------
-- Idempotency Key Examples
-- ---------------------------------------------------------------------------

-- refresh_video_metrics:{video_id}:{timestamp_hour}
-- close_attribution_window:{attribution_window_id}
-- unlock_variant:{next_variant_id}
-- finalize_evidence:{experiment_id}:{snapshot_version}
-- generate_insight:{evidence_snapshot_id}
-- generate_hypotheses:{project_id}:{context_version}
-- revise_brief:{variant_id}:{ai_run_id}

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Service-role workers claim jobs directly (bypass RLS).
-- Authenticated users may read their own project's jobs.
CREATE POLICY jobs_project_read ON jobs
  FOR SELECT USING (
    project_id IS NULL OR owns_project(project_id)
  );

-- ---------------------------------------------------------------------------
-- Comment
-- ---------------------------------------------------------------------------
COMMENT ON TABLE jobs IS
  'Durable background job queue. Claimed with SELECT ... FOR UPDATE SKIP LOCKED. '
  'Idempotency key prevents duplicate work. Workers: scheduler, general worker, phone agent.';
