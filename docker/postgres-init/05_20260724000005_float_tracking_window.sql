-- Migration 005: change tracking_window_hours from integer to real (float4)
-- This allows accelerated test runs to use sub-hour windows (e.g. 2 minutes = 0.0333).
-- All existing 72-hour values are preserved exactly.

ALTER TABLE experiments
  ALTER COLUMN tracking_window_hours TYPE real
  USING tracking_window_hours::real;

-- Ensure the default still works
ALTER TABLE experiments
  ALTER COLUMN tracking_window_hours SET DEFAULT 72;

COMMENT ON COLUMN experiments.tracking_window_hours IS
  'Tracking window duration in hours. Accepts fractional values (e.g. 0.0333 = 2 min) for accelerated tests.';
