-- The monitor's measured cost per check (job-object CPU time of the check and
-- every process it started), so the pilot can show it stays light.
ALTER TABLE checkins ADD COLUMN monitor_cpu_seconds REAL;
ALTER TABLE checkins ADD COLUMN monitor_cpu_percent REAL;   -- share of the whole machine over the check
ALTER TABLE checkins ADD COLUMN monitor_processes   INTEGER;
