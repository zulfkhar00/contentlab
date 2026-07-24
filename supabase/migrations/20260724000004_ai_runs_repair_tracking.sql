-- =============================================================================
-- 004_ai_runs_repair_tracking.sql
-- Sprint 6B: track multi-attempt provider invocations.
-- Each repair call creates a new ai_run (append-only), not an update.
-- request_group_id ties the logical operation across attempts.
-- parent_ai_run_id on attempt 2+ points to attempt 1.
-- =============================================================================

ALTER TABLE ai_runs
  ADD COLUMN IF NOT EXISTS request_group_id  uuid,
  ADD COLUMN IF NOT EXISTS attempt_number    integer NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS parent_ai_run_id  uuid REFERENCES ai_runs(id),
  ADD COLUMN IF NOT EXISTS error_detail      text;

-- Index for looking up all attempts in a group
CREATE INDEX IF NOT EXISTS ai_runs_request_group
  ON ai_runs (request_group_id)
  WHERE request_group_id IS NOT NULL;

COMMENT ON COLUMN ai_runs.request_group_id IS
  'Groups all ai_run rows belonging to one logical operation (initial + repairs).';
COMMENT ON COLUMN ai_runs.attempt_number IS
  '1 for the initial call; 2 for the first repair; etc.';
COMMENT ON COLUMN ai_runs.parent_ai_run_id IS
  'Points to attempt_number=1 for repair rows. NULL on the initial attempt.';
COMMENT ON COLUMN ai_runs.error_detail IS
  'Validation error message or exception string when status != success.';
