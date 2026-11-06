-- Two lessons from Canopy Leaf's rollout (#leaf-deploy-coordination, 2026-10-14):
--
-- 1. Leaf leaked memory on VPUs for months before anyone saw it. The monitor
--    now reports the peak memory each pass held, stored beside its CPU cost.
-- 2. Finding that leak meant editing cron jobs by hand for four months. One row
--    here now switches the scheduled monitor off, or skips named collectors,
--    for one unit or the whole fleet. The ingest Worker returns it in every
--    reply. scope is 'fleet' or a unit key (venue id, else VPU name); a unit's
--    own row decides its mode, and skip lists add up. mode 'off' leaves only
--    an hourly identity-only check-in with reason 'paused'.
--
--   -- stop the monitor everywhere:
--   UPDATE monitor_control SET mode = 'off', note = '…', updated_at = datetime('now') WHERE scope = 'fleet';
--   -- stop one collector everywhere:
--   UPDATE monitor_control SET skip = '["Get-S1Cameras.ps1"]' WHERE scope = 'fleet';
--   -- stop it on one unit:
--   INSERT INTO monitor_control (scope, mode, note, updated_at) VALUES ('<venue id>', 'off', '…', datetime('now'));
ALTER TABLE checkins ADD COLUMN monitor_memory_peak_mb REAL;

CREATE TABLE monitor_control (
  scope      TEXT PRIMARY KEY,
  mode       TEXT NOT NULL DEFAULT 'on' CHECK (mode IN ('on', 'off')),
  skip       TEXT NOT NULL DEFAULT '[]',
  note       TEXT,
  updated_at TEXT
);
INSERT INTO monitor_control (scope, mode, skip, note, updated_at)
VALUES ('fleet', 'on', '[]', 'default', datetime('now'));
