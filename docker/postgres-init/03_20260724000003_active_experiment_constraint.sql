-- =============================================================================
-- 003_active_experiment_constraint.sql
-- Enforce at most one active Experiment per Project.
-- An Experiment is active when its status is ready, in_progress,
-- tracking, or analyzing. Only one such experiment may exist per project
-- at any time — completed and cancelled experiments are excluded.
-- =============================================================================

CREATE UNIQUE INDEX one_active_experiment_per_project
  ON experiments (project_id)
  WHERE status IN ('ready', 'in_progress', 'tracking', 'analyzing');
