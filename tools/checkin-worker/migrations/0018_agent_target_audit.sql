-- Who set each agent target, and when (PV-85).
--
-- Pulse Vitals moves the fleet's agent build through POST /agent-target on
-- the admin Worker (src/agent-target.js), never by writing this database: it
-- stays read-only against pulse-checkins. The Worker checks the version and
-- hash against the published agent-v* release, then writes the pair below
-- with the Access identity that asked for it.
--
-- agent_note / agent_set_by / agent_set_at describe the current target on
-- each monitor_control row (note stays the row's mode note). agent_target_log
-- keeps every change, set or clear, with what it replaced.
--
-- Additive: no existing column or view changes. Apply before deploying the
-- admin Worker that writes these columns.

ALTER TABLE monitor_control ADD COLUMN agent_note TEXT;
ALTER TABLE monitor_control ADD COLUMN agent_set_by TEXT;
ALTER TABLE monitor_control ADD COLUMN agent_set_at TEXT;

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
