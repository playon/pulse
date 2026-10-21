-- The agent build each unit should run, and who set it (PV-85).
--
-- Pulse Vitals moves the fleet's agent build through POST /agent-target on
-- the admin Worker (src/agent-target.js), never by writing this database: it
-- stays read-only against pulse-checkins. The Worker checks the version and
-- hash against the published agent-v* release, then writes the pin below
-- with the Access identity that asked for it.
--
-- Pins get their own table, apart from monitor_control. A unit row in
-- monitor_control decides that unit's mode (0011), so creating one just to
-- pin a build turned a unit's monitor back on while the fleet was off. Here a
-- row is a pin and nothing else: scope 'fleet' or a unit key (venue id, else
-- VPU name); a unit's own row wins over the fleet's. Clearing deletes the row.
-- The ingest reads mode and skip from monitor_control and the pin from here.
--
-- monitor_control.agent_version / agent_sha256 (0017) are retired: any pin
-- set by hand there moves here, and the columns are emptied so nothing reads
-- a stale copy. (SQLite can't drop a column with a CHECK, so they stay, unused.)
--
-- agent_target_log keeps every change, set or clear, with what it replaced.
--
-- Additive for the views Vitals reads. Apply before deploying the Workers
-- that read and write agent_target.

CREATE TABLE agent_target (
  scope   TEXT PRIMARY KEY,
  version TEXT NOT NULL CHECK (version GLOB '[0-9]*.[0-9]*.[0-9]*' AND version NOT GLOB '*[^0-9.]*'),
  sha256  TEXT NOT NULL CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  note    TEXT,
  set_by  TEXT,                          -- NULL: set by hand
  set_at  TEXT NOT NULL
);

INSERT INTO agent_target (scope, version, sha256, note, set_by, set_at)
SELECT scope, agent_version, agent_sha256, 'moved from monitor_control', NULL,
       COALESCE(updated_at, datetime('now'))
FROM monitor_control
WHERE agent_version IS NOT NULL AND agent_sha256 IS NOT NULL;

UPDATE monitor_control SET agent_version = NULL, agent_sha256 = NULL
WHERE agent_version IS NOT NULL OR agent_sha256 IS NOT NULL;

CREATE TABLE agent_target_log (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  at               TEXT NOT NULL,
  scope            TEXT NOT NULL,
  version          TEXT,                  -- NULL: the target was cleared
  sha256           TEXT,
  previous_version TEXT,
  previous_sha256  TEXT,
  set_by           TEXT NOT NULL,
  note             TEXT
);
CREATE INDEX agent_target_log_scope_at ON agent_target_log (scope, at);
