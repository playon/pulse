-- The fleet agent's own version, and the target it's pinned to (PV-49).
--
-- The agent (the scheduled monitor) now versions apart from Pulse Diagnostics
-- and sends agentVersion on every post; agentUpdate reports how its last
-- update went. Fleet control gains a target: the agent version a unit should
-- run and the SHA-256 of that release's zip. The reply carries it as
-- control.agent; the agent builds the download URL itself from the version
-- (playon/pulse releases, agent-v{version}) and refuses a zip whose hash
-- differs, so this table can only choose among published releases.
--
--   -- pin the fleet:
--   UPDATE monitor_control SET agent_version = '0.2.0', agent_sha256 = '<64 hex>',
--          note = '…', updated_at = datetime('now') WHERE scope = 'fleet';
--   -- a canary, or hold one unit back (its own row wins when it sets a version):
--   INSERT INTO monitor_control (scope, agent_version, agent_sha256, note, updated_at)
--   VALUES ('<venue id>', '0.2.0', '<64 hex>', '…', datetime('now'))
--   ON CONFLICT (scope) DO UPDATE SET agent_version = excluded.agent_version,
--          agent_sha256 = excluded.agent_sha256, note = excluded.note, updated_at = excluded.updated_at;
--   -- stop moving the fleet (units stay on what they run):
--   UPDATE monitor_control SET agent_version = NULL, agent_sha256 = NULL WHERE scope = 'fleet';
--
-- Additive: no existing column changes. Apply before deploying the Worker
-- that writes these columns. Nothing to backfill: until now the Worker
-- dropped agentVersion.

ALTER TABLE checkins ADD COLUMN agent_version TEXT;
ALTER TABLE checkins ADD COLUMN agent_update_status TEXT;
ALTER TABLE checkins ADD COLUMN agent_update_version TEXT;
ALTER TABLE checkins ADD COLUMN agent_update_error TEXT;

-- A typo in a hand-written UPDATE fails here, loudly, instead of the Worker
-- quietly leaving the target out of every reply.
ALTER TABLE monitor_control ADD COLUMN agent_version TEXT
  CHECK (agent_version IS NULL OR (agent_version GLOB '[0-9]*.[0-9]*.[0-9]*'
                                   AND agent_version NOT GLOB '*[^0-9.]*'));
ALTER TABLE monitor_control ADD COLUMN agent_sha256 TEXT
  CHECK (agent_sha256 IS NULL OR (length(agent_sha256) = 64 AND agent_sha256 NOT GLOB '*[^0-9a-f]*'));

-- unit_latest: the version the unit's agent last reported, and its newest
-- update outcome. Each group keeps the (time, id) of its check-in, like the
-- others (src/latest.js).
ALTER TABLE unit_latest ADD COLUMN agent_at TEXT;
ALTER TABLE unit_latest ADD COLUMN agent_row INTEGER;
ALTER TABLE unit_latest ADD COLUMN agent_version TEXT;
ALTER TABLE unit_latest ADD COLUMN agent_update_at TEXT;
ALTER TABLE unit_latest ADD COLUMN agent_update_row INTEGER;
ALTER TABLE unit_latest ADD COLUMN agent_update_status TEXT;
ALTER TABLE unit_latest ADD COLUMN agent_update_version TEXT;
ALTER TABLE unit_latest ADD COLUMN agent_update_error TEXT;
