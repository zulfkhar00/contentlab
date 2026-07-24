-- =============================================================================
-- 002_job_infrastructure.sql  (v3 — all review corrections applied)
--
-- Changes from v2:
--  P0.1  ROW_COUNT assigned to integer, not boolean
--  P0.2  claim_job: reaper for final-attempt crashes; input validation
--  P1.7  extend_job_lease heartbeat function with input validation
--  P1.8  UNIQUE(id, project_id) on jobs; composite FKs for job provenance
--  P0.1  complete_job / fail_job: p_worker_id guard + correct integer type
--  SEC   jobs: no authenticated SELECT; all functions revoked from PUBLIC/anon/authenticated
-- =============================================================================

CREATE TABLE jobs (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       uuid        REFERENCES projects(id) ON DELETE CASCADE,
  job_type         text        NOT NULL,
  entity_type      text,
  entity_id        uuid,
  payload          jsonb       NOT NULL DEFAULT '{}',
  -- [P0 / P1.5] CHECK constraint on status
  status           text        NOT NULL DEFAULT 'pending'
    CONSTRAINT jobs_status_check
      CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  run_at           timestamptz NOT NULL DEFAULT now(),
  -- [P1.5] retry value constraints
  attempt_count    integer     NOT NULL DEFAULT 0  CONSTRAINT jobs_attempt_nonneg   CHECK (attempt_count  >= 0),
  max_attempts     integer     NOT NULL DEFAULT 3  CONSTRAINT jobs_max_attempts_pos CHECK (max_attempts   >= 1),
  locked_at        timestamptz,
  locked_by        text,
  lease_expires_at timestamptz,
  idempotency_key  text        NOT NULL,
  CONSTRAINT jobs_idempotency_unique UNIQUE (idempotency_key),
  result_payload   jsonb,
  last_error       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  completed_at     timestamptz,
  -- [P1.8] expose for composite FK references from other tables
  CONSTRAINT jobs_id_project_unique UNIQUE (id, project_id)
);

CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- [P0.1 / P0.2] Separate constant-predicate indexes
CREATE INDEX jobs_pending        ON jobs (run_at ASC)           WHERE status = 'pending';
CREATE INDEX jobs_running_expired ON jobs (lease_expires_at ASC) WHERE status = 'running';
CREATE INDEX jobs_project_status  ON jobs (project_id, status, run_at) WHERE project_id IS NOT NULL;
CREATE INDEX jobs_entity          ON jobs (entity_type, entity_id)     WHERE entity_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- [P1.8] Job provenance FKs (tables created in 001)
-- ---------------------------------------------------------------------------
ALTER TABLE video_metric_snapshots
  ADD CONSTRAINT vms_collection_job_fk
  FOREIGN KEY (collection_job_id, project_id)
  REFERENCES jobs(id, project_id);

ALTER TABLE experiment_evidence_snapshots
  ADD CONSTRAINT ees_created_by_job_fk
  FOREIGN KEY (created_by_job_id, project_id)
  REFERENCES jobs(id, project_id);

-- ---------------------------------------------------------------------------
-- [P0.1 / P0.2] claim_job — PL/pgSQL for reaper + input validation
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION claim_job(
  p_worker_id     text,
  p_job_types     text[]      DEFAULT NULL,
  p_lease_seconds integer     DEFAULT 120
)
RETURNS SETOF jobs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  -- [P0.2] Input validation
  IF p_worker_id IS NULL OR p_worker_id = '' THEN
    RAISE EXCEPTION 'p_worker_id must not be empty';
  END IF;
  IF p_lease_seconds <= 0 THEN
    RAISE EXCEPTION 'p_lease_seconds must be > 0 (got: %)', p_lease_seconds;
  END IF;

  -- [P0.2] Reap running jobs that exhausted all attempts when their lease expired
  -- These cannot be reclaimed (attempt_count >= max_attempts) so they must be reaped first.
  UPDATE public.jobs
  SET
    status           = 'failed',
    locked_at        = NULL,
    locked_by        = NULL,
    lease_expires_at = NULL,
    completed_at     = now(),
    last_error       = COALESCE(last_error, 'Worker lease expired after final attempt'),
    updated_at       = now()
  WHERE status           = 'running'
    AND lease_expires_at <= now()
    AND attempt_count    >= max_attempts;

  -- Claim one eligible job
  RETURN QUERY
  UPDATE public.jobs
  SET
    status           = 'running',
    locked_at        = now(),
    locked_by        = p_worker_id,
    lease_expires_at = now() + (p_lease_seconds || ' seconds')::interval,
    attempt_count    = attempt_count + 1,
    updated_at       = now()
  WHERE id = (
    SELECT id FROM public.jobs
    WHERE (
      -- Pending job whose time has arrived
      (status = 'pending' AND run_at <= now())
      OR
      -- Running job with expired lease that still has attempts remaining
      (status = 'running' AND lease_expires_at < now() AND attempt_count < max_attempts)
    )
    AND attempt_count < max_attempts
    AND (p_job_types IS NULL OR job_type = ANY(p_job_types))
    ORDER BY run_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
END;
$$;

-- ---------------------------------------------------------------------------
-- [P0.1 / P0.3] complete_job — integer ROW_COUNT; p_worker_id guard
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION complete_job(
  p_job_id    uuid,
  p_worker_id text,
  p_result    jsonb DEFAULT '{}'
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_row_count integer;   -- [P0.1] integer, not boolean
BEGIN
  UPDATE public.jobs
  SET
    status           = 'completed',
    result_payload   = p_result,
    completed_at     = now(),
    locked_at        = NULL,
    locked_by        = NULL,
    lease_expires_at = NULL,
    updated_at       = now()
  WHERE id        = p_job_id
    AND locked_by = p_worker_id   -- [P0.3] only the owning worker
    AND status    = 'running';

  GET DIAGNOSTICS v_row_count = ROW_COUNT;  -- [P0.1] correct assignment
  RETURN v_row_count > 0;
END;
$$;

-- ---------------------------------------------------------------------------
-- [P0.1 / P0.3] fail_job — integer ROW_COUNT; p_worker_id guard
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fail_job(
  p_job_id    uuid,
  p_worker_id text,
  p_error     text,
  p_retry_in  interval DEFAULT '60 seconds'
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_row_count integer;   -- [P0.1] integer, not boolean
BEGIN
  UPDATE public.jobs
  SET
    status           = CASE
                         WHEN attempt_count >= max_attempts THEN 'failed'
                         ELSE 'pending'
                       END,
    last_error       = p_error,
    run_at           = CASE
                         WHEN attempt_count >= max_attempts THEN run_at
                         ELSE now() + p_retry_in
                       END,
    locked_at        = NULL,
    locked_by        = NULL,
    lease_expires_at = NULL,
    updated_at       = now()
  WHERE id        = p_job_id
    AND locked_by = p_worker_id   -- [P0.3] only the owning worker
    AND status    = 'running';

  GET DIAGNOSTICS v_row_count = ROW_COUNT;  -- [P0.1] correct assignment
  RETURN v_row_count > 0;
END;
$$;

-- ---------------------------------------------------------------------------
-- [P1.7] extend_job_lease heartbeat
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION extend_job_lease(
  p_job_id        uuid,
  p_worker_id     text,
  p_lease_seconds integer DEFAULT 120
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_row_count integer;
BEGIN
  IF p_worker_id IS NULL OR p_worker_id = '' THEN
    RAISE EXCEPTION 'p_worker_id must not be empty';
  END IF;
  IF p_lease_seconds <= 0 THEN
    RAISE EXCEPTION 'p_lease_seconds must be > 0 (got: %)', p_lease_seconds;
  END IF;

  UPDATE public.jobs
  SET
    lease_expires_at = now() + (p_lease_seconds || ' seconds')::interval,
    updated_at       = now()
  WHERE id        = p_job_id
    AND locked_by = p_worker_id
    AND status    = 'running';

  GET DIAGNOSTICS v_row_count = ROW_COUNT;
  RETURN v_row_count > 0;
END;
$$;

-- ---------------------------------------------------------------------------
-- [P0.4 / P1.4] enqueue_job — returns existing ID on conflict
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION enqueue_job(
  p_job_type        text,
  p_idempotency_key text,
  p_payload         jsonb       DEFAULT '{}',
  p_entity_type     text        DEFAULT NULL,
  p_entity_id       uuid        DEFAULT NULL,
  p_project_id      uuid        DEFAULT NULL,
  p_run_at          timestamptz DEFAULT now(),
  p_max_attempts    integer     DEFAULT 3
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_id uuid;
BEGIN
  INSERT INTO public.jobs (
    project_id, job_type, entity_type, entity_id,
    payload, idempotency_key, run_at, max_attempts
  ) VALUES (
    p_project_id, p_job_type, p_entity_type, p_entity_id,
    p_payload, p_idempotency_key, p_run_at, p_max_attempts
  )
  ON CONFLICT (idempotency_key) DO NOTHING
  RETURNING id INTO v_id;

  -- [P0.4] return the existing job ID on idempotency conflict
  IF v_id IS NULL THEN
    SELECT id INTO v_id FROM public.jobs WHERE idempotency_key = p_idempotency_key;
  END IF;

  RETURN v_id;
END;
$$;

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- [SEC] jobs: no authenticated SELECT (payloads + errors are service-internal)
-- ---------------------------------------------------------------------------
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
-- No SELECT policy for authenticated; FastAPI exposes safe progress aggregates.

-- ---------------------------------------------------------------------------
-- [P0.7] Revoke functions from PUBLIC, anon, authenticated; grant to service_role
-- ---------------------------------------------------------------------------
REVOKE ALL ON FUNCTION claim_job(text, text[], integer)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION complete_job(uuid, text, jsonb)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION fail_job(uuid, text, text, interval)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION extend_job_lease(uuid, text, integer)
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION enqueue_job(text, text, jsonb, text, uuid, uuid, timestamptz, integer)
  FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION claim_job(text, text[], integer)                              TO service_role;
GRANT EXECUTE ON FUNCTION complete_job(uuid, text, jsonb)                               TO service_role;
GRANT EXECUTE ON FUNCTION fail_job(uuid, text, text, interval)                          TO service_role;
GRANT EXECUTE ON FUNCTION extend_job_lease(uuid, text, integer)                         TO service_role;
GRANT EXECUTE ON FUNCTION enqueue_job(text, text, jsonb, text, uuid, uuid, timestamptz, integer) TO service_role;

COMMENT ON TABLE jobs IS
  'Durable background job queue. Claimed with SELECT ... FOR UPDATE SKIP LOCKED. '
  'claim_job reaps crashed final-attempt jobs before claiming. '
  'complete_job / fail_job / extend_job_lease require the claiming worker_id. '
  'enqueue_job is idempotent: returns existing ID on key conflict. '
  'All functions restricted to service_role.';
