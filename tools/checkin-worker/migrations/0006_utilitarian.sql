-- The utilitarian payload (Ian, 2026-10-13). Check-ins no longer carry
-- hostname or BIOS serial, so a unit is its Pixellot venue id, falling back to
-- the VPU name, then (for rows from before this change) hostname and serial.
-- The monitor now posts only on change or schedule, and an unchanged PASS is a
-- one-line "heartbeat", so last_seen comes from the newest check-in of any
-- kind while the readings come from the newest full one.
ALTER TABLE checkins ADD COLUMN tel_internet_reachable INTEGER;

DROP VIEW units;
CREATE VIEW units AS
WITH seen AS (
  SELECT *,
         COALESCE(venue_id, vpu_name, hostname, serial_number) AS unit_key,
         COALESCE(sent_at, received_at) AS seen_at
  FROM checkins
), ranked AS (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY unit_key ORDER BY seen_at DESC, id DESC) AS rn,
         COUNT(*)     OVER (PARTITION BY unit_key) AS run_count,
         MIN(seen_at) OVER (PARTITION BY unit_key) AS first_seen
  FROM seen
)
SELECT venue_id, vpu_name, model, pulse_version, channel,
       readiness_status, readiness_blockers, readiness_risks,
       first_seen, seen_at AS last_seen, run_count
FROM ranked
WHERE rn = 1;

DROP VIEW unit_status;
CREATE VIEW unit_status AS
WITH keyed AS (
  SELECT *,
         COALESCE(venue_id, vpu_name, hostname, serial_number) AS unit_key,
         COALESCE(sent_at, received_at) AS seen_at
  FROM checkins
), latest AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY unit_key ORDER BY seen_at DESC, id DESC) AS rn
  FROM keyed
  WHERE telemetry IS NOT NULL
), heard AS (
  SELECT unit_key, MAX(seen_at) AS last_seen,
         (SELECT reason FROM keyed k2 WHERE k2.unit_key = keyed.unit_key
          ORDER BY seen_at DESC, id DESC LIMIT 1) AS last_kind
  FROM keyed
  GROUP BY unit_key
)
SELECT l.vpu_name, l.venue_id, l.model,
       h.last_seen, h.last_kind, l.seen_at AS last_full_report,
       l.tel_status AS status, l.tel_status_since AS status_since,
       l.tel_headline AS headline, l.tel_blockers AS blockers,
       l.tel_internet_reachable AS internet_reachable,
       l.tel_streaming_path AS streaming_path, l.tel_ports_failed AS ports_failed,
       l.tel_ip AS ip, l.tel_subnet_mask AS subnet_mask, l.tel_gateway AS gateway,
       l.tel_dns1 AS dns1, l.tel_dns2 AS dns2, l.tel_dhcp AS dhcp, l.tel_mac AS mac,
       l.tel_system_type AS system_type,
       l.tel_cameras_detected AS cameras_detected, l.tel_cameras_expected AS cameras_expected,
       l.tel_cameras_slow AS cameras_slow,
       l.tel_services_down AS services_down,
       l.tel_scoreboard_source AS scoreboard_source, l.tel_scoreboard_ok AS scoreboard_ok,
       l.tel_last_boot AS last_boot, l.tel_unexpected_7d AS unexpected_shutdowns_7d,
       l.tel_pixellot_version AS pixellot_version, l.pulse_version,
       l.telemetry
FROM latest l
JOIN heard h ON h.unit_key = l.unit_key
WHERE l.rn = 1;

DROP VIEW transitions;
CREATE VIEW transitions AS
SELECT c.vpu_name, c.venue_id,
       COALESCE(c.sent_at, c.received_at) AS at,
       'opened' AS kind,
       json_extract(e.value, '$.code')  AS code,
       json_extract(e.value, '$.class') AS class,
       json_extract(e.value, '$.title') AS title,
       json_extract(e.value, '$.since') AS since,
       c.delta_status AS status_after
FROM checkins c, json_each(c.delta_opened) e
WHERE c.delta_opened IS NOT NULL
UNION ALL
SELECT c.vpu_name, c.venue_id,
       COALESCE(c.sent_at, c.received_at),
       'resolved',
       json_extract(e.value, '$.code'),
       json_extract(e.value, '$.class'),
       json_extract(e.value, '$.title'),
       json_extract(e.value, '$.since'),
       c.delta_status
FROM checkins c, json_each(c.delta_resolved) e
WHERE c.delta_resolved IS NOT NULL;
