-- units: one line per unit, like the old sheet's Runs tab (Ian, 2026-10-14).
-- run_count counted every check-in, so the fleet monitor's heartbeats and
-- re-posts inflated it (vpu-home read 295 "runs"), and a unit imported from
-- the sheet counted as 1 however many runs the sheet had recorded. Now:
--   run_count      = launches of Pulse: the sheet's recorded count for an
--                    imported unit, plus every launch check-in since
--   monitor_posts  = the scheduled monitor's reports, counted apart
--   first_seen     = the sheet's First Seen for an imported unit
--   last_launch    = the newest launch check-in
-- Version, channel and readiness come from the newest check-in that carries
-- them, so a heartbeat (identity + status only) never blanks them.
DROP VIEW units;
CREATE VIEW units AS
WITH c AS (
  SELECT *,
         COALESCE(venue_id, vpu_name, hostname, serial_number) AS unit_key,
         COALESCE(sent_at, received_at) AS seen_at,
         CASE
           WHEN source = 'sheet-import' THEN COALESCE(CAST(json_extract(raw, '$.runCount') AS INTEGER), 1)
           WHEN telemetry IS NULL AND (reason IS NULL OR reason = 'startup') THEN 1
           ELSE 0
         END AS launches,
         CASE WHEN reason IN ('periodic', 'state-change', 'heartbeat') THEN 1 ELSE 0 END AS monitor_post,
         CASE WHEN source = 'sheet-import' THEN json_extract(raw, '$.firstSeen')
              ELSE COALESCE(sent_at, received_at) END AS first_at
  FROM checkins
), agg AS (
  SELECT unit_key,
         SUM(launches)     AS run_count,
         SUM(monitor_post) AS monitor_posts,
         MIN(first_at)     AS first_seen,
         MAX(seen_at)      AS last_seen,
         MAX(CASE WHEN launches > 0 THEN seen_at END) AS last_launch
  FROM c
  GROUP BY unit_key
), detail AS (
  -- newest row that carries a version (every kind except the heartbeat)
  SELECT *, ROW_NUMBER() OVER (PARTITION BY unit_key ORDER BY seen_at DESC, id DESC) AS rn
  FROM c
  WHERE pulse_version IS NOT NULL
), verdict AS (
  -- newest readiness verdict: a launch's readiness block or a monitor report
  SELECT unit_key, COALESCE(tel_status, readiness_status) AS status,
         readiness_blockers, readiness_risks,
         ROW_NUMBER() OVER (PARTITION BY unit_key ORDER BY seen_at DESC, id DESC) AS rn
  FROM c
  WHERE COALESCE(tel_status, readiness_status) IS NOT NULL AND reason IS NOT 'heartbeat'
)
SELECT d.venue_id, d.vpu_name, d.model, d.pulse_version, d.channel,
       v.status AS readiness_status, v.readiness_blockers, v.readiness_risks,
       a.first_seen, a.last_seen, a.run_count, a.monitor_posts, a.last_launch
FROM agg a
LEFT JOIN detail  d ON d.unit_key = a.unit_key AND d.rn = 1
LEFT JOIN verdict v ON v.unit_key = a.unit_key AND v.rn = 1
WHERE a.unit_key IS NOT NULL;
