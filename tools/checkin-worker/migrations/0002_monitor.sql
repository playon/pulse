-- Fleet-monitor check-ins (Pulse.Web/app/monitor_once.py). A launch check-in
-- leaves every column below NULL except reason ('startup', or NULL from builds
-- that predate the field).
ALTER TABLE checkins ADD COLUMN reason            TEXT;     -- startup | periodic | state-change
ALTER TABLE checkins ADD COLUMN os_build          TEXT;
ALTER TABLE checkins ADD COLUMN ubr               TEXT;
ALTER TABLE checkins ADD COLUMN delta_status      TEXT;     -- verdict after this pass
ALTER TABLE checkins ADD COLUMN delta_prev_status TEXT;
ALTER TABLE checkins ADD COLUMN delta_opened      TEXT;     -- JSON [{code,class,title,since}]
ALTER TABLE checkins ADD COLUMN delta_resolved    TEXT;     -- JSON [{code,class,title,since}]
ALTER TABLE checkins ADD COLUMN monitor_pass      TEXT;     -- full | partial
ALTER TABLE checkins ADD COLUMN monitor_seconds   REAL;     -- the pass's own wall time
ALTER TABLE checkins ADD COLUMN monitor_ps_runs   INTEGER;  -- PowerShell processes it started
ALTER TABLE checkins ADD COLUMN event_live        INTEGER;  -- 1 if vpu.exe was running

CREATE INDEX idx_checkins_reason ON checkins (reason, received_at);

-- Every finding that opened or resolved on a monitored unit, one row each.
-- This is the "caught before the event" ledger the pilot is measured on.
CREATE VIEW transitions AS
SELECT c.hostname, c.serial_number, c.vpu_name, c.venue_id,
       COALESCE(c.sent_at, c.received_at) AS at,
       'opened' AS kind,
       json_extract(e.value, '$.code')  AS code,
       json_extract(e.value, '$.class') AS class,
       json_extract(e.value, '$.title') AS title,
       json_extract(e.value, '$.since') AS since,
       c.event_live, c.delta_status AS status_after
FROM checkins c, json_each(c.delta_opened) e
WHERE c.delta_opened IS NOT NULL
UNION ALL
SELECT c.hostname, c.serial_number, c.vpu_name, c.venue_id,
       COALESCE(c.sent_at, c.received_at),
       'resolved',
       json_extract(e.value, '$.code'),
       json_extract(e.value, '$.class'),
       json_extract(e.value, '$.title'),
       json_extract(e.value, '$.since'),
       c.event_live, c.delta_status
FROM checkins c, json_each(c.delta_resolved) e
WHERE c.delta_resolved IS NOT NULL;
