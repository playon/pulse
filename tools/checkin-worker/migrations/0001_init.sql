-- One row per check-in, never updated. Everything else is derived.
-- Timestamps are ISO 8601 UTC with a trailing Z so string order is time order.
CREATE TABLE checkins (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  checkin_id         TEXT    NOT NULL UNIQUE,
  received_at        TEXT    NOT NULL,
  sent_at            TEXT,
  hostname           TEXT,
  serial_number      TEXT,
  venue_id           TEXT,
  vpu_name           TEXT,
  model              TEXT,
  pulse_version      TEXT,
  channel            TEXT,
  readiness_status   TEXT,
  readiness_policy   TEXT,
  readiness_blockers TEXT,  -- JSON array of codes
  readiness_risks    TEXT,  -- JSON array of codes
  country            TEXT,
  source             TEXT    NOT NULL DEFAULT 'pulse',
  raw                TEXT    NOT NULL
);

CREATE INDEX idx_checkins_unit     ON checkins (serial_number, hostname);
CREATE INDEX idx_checkins_received ON checkins (received_at);

-- Replaces the old sheet's one-row-per-unit upsert. A unit is (serial, hostname):
-- some boards report junk BIOS serials, so serial alone can merge distinct units.
CREATE VIEW units AS
WITH seen AS (
  SELECT *,
         COALESCE(sent_at, received_at) AS seen_at,
         ROW_NUMBER() OVER unit_recent AS rn,
         COUNT(*)     OVER unit_all    AS run_count,
         MIN(COALESCE(sent_at, received_at)) OVER unit_all AS first_seen
  FROM checkins
  WINDOW unit_all    AS (PARTITION BY COALESCE(serial_number, ''), COALESCE(hostname, '')),
         unit_recent AS (PARTITION BY COALESCE(serial_number, ''), COALESCE(hostname, '')
                         ORDER BY COALESCE(sent_at, received_at) DESC, id DESC)
)
SELECT hostname, serial_number, venue_id, vpu_name, model, pulse_version, channel,
       readiness_status, readiness_blockers, readiness_risks,
       first_seen, seen_at AS last_seen, run_count
FROM seen
WHERE rn = 1;
