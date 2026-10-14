-- Eastern-time copies of the timestamps people read (Ian, 2026-10-14), so
-- DataGrip and the CSVs need no UTC conversion. Each *_et column sits next to
-- its UTC original, which stays the value the code sorts and compares on.
-- Values read like "2026-10-14 10:33:34 EDT": EDT from the second Sunday of
-- March to the first Sunday of November (US rules since 2007), EST otherwise.
-- SQLite has no time zones, so the switch is worked out here. The view bodies
-- are the 0008 / 0006 ones unchanged, wrapped in an outer select.

DROP VIEW units;
CREATE VIEW units AS
SELECT
  venue_id,
  vpu_name,
  model,
  pulse_version,
  channel,
  readiness_status,
  readiness_blockers,
  readiness_risks,
  first_seen,
  CASE WHEN datetime(first_seen) IS NULL THEN NULL WHEN datetime(first_seen) >= datetime(strftime('%Y', first_seen) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(first_seen) < datetime(strftime('%Y', first_seen) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', first_seen, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', first_seen, '-5 hours') || ' EST' END AS first_seen_et,
  last_seen,
  CASE WHEN datetime(last_seen) IS NULL THEN NULL WHEN datetime(last_seen) >= datetime(strftime('%Y', last_seen) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(last_seen) < datetime(strftime('%Y', last_seen) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', last_seen, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', last_seen, '-5 hours') || ' EST' END AS last_seen_et,
  run_count,
  monitor_posts,
  last_launch,
  CASE WHEN datetime(last_launch) IS NULL THEN NULL WHEN datetime(last_launch) >= datetime(strftime('%Y', last_launch) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(last_launch) < datetime(strftime('%Y', last_launch) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', last_launch, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', last_launch, '-5 hours') || ' EST' END AS last_launch_et
FROM (
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
  WHERE a.unit_key IS NOT NULL
);

DROP VIEW unit_status;
CREATE VIEW unit_status AS
SELECT
  vpu_name,
  venue_id,
  model,
  last_seen,
  CASE WHEN datetime(last_seen) IS NULL THEN NULL WHEN datetime(last_seen) >= datetime(strftime('%Y', last_seen) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(last_seen) < datetime(strftime('%Y', last_seen) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', last_seen, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', last_seen, '-5 hours') || ' EST' END AS last_seen_et,
  last_kind,
  last_full_report,
  CASE WHEN datetime(last_full_report) IS NULL THEN NULL WHEN datetime(last_full_report) >= datetime(strftime('%Y', last_full_report) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(last_full_report) < datetime(strftime('%Y', last_full_report) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', last_full_report, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', last_full_report, '-5 hours') || ' EST' END AS last_full_report_et,
  status,
  status_since,
  CASE WHEN datetime(status_since) IS NULL THEN NULL WHEN datetime(status_since) >= datetime(strftime('%Y', status_since) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(status_since) < datetime(strftime('%Y', status_since) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', status_since, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', status_since, '-5 hours') || ' EST' END AS status_since_et,
  headline,
  blockers,
  internet_reachable,
  streaming_path,
  ports_failed,
  ip,
  subnet_mask,
  gateway,
  dns1,
  dns2,
  dhcp,
  mac,
  system_type,
  cameras_detected,
  cameras_expected,
  cameras_slow,
  services_down,
  scoreboard_source,
  scoreboard_ok,
  last_boot,
  CASE WHEN datetime(last_boot) IS NULL THEN NULL WHEN datetime(last_boot) >= datetime(strftime('%Y', last_boot) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(last_boot) < datetime(strftime('%Y', last_boot) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', last_boot, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', last_boot, '-5 hours') || ' EST' END AS last_boot_et,
  unexpected_shutdowns_7d,
  pixellot_version,
  pulse_version,
  telemetry
FROM (
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
  WHERE l.rn = 1
);

DROP VIEW transitions;
CREATE VIEW transitions AS
SELECT
  vpu_name,
  venue_id,
  at,
  CASE WHEN datetime(at) IS NULL THEN NULL WHEN datetime(at) >= datetime(strftime('%Y', at) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(at) < datetime(strftime('%Y', at) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', at, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', at, '-5 hours') || ' EST' END AS at_et,
  kind,
  code,
  class,
  title,
  since,
  CASE WHEN datetime(since) IS NULL THEN NULL WHEN datetime(since) >= datetime(strftime('%Y', since) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(since) < datetime(strftime('%Y', since) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', since, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', since, '-5 hours') || ' EST' END AS since_et,
  status_after
FROM (
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
  WHERE c.delta_resolved IS NOT NULL
);

-- The raw table with its two timestamps in Eastern time, for browsing.
CREATE VIEW checkins_et AS
SELECT CASE WHEN datetime(received_at) IS NULL THEN NULL WHEN datetime(received_at) >= datetime(strftime('%Y', received_at) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(received_at) < datetime(strftime('%Y', received_at) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', received_at, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', received_at, '-5 hours') || ' EST' END AS received_at_et,
       CASE WHEN datetime(sent_at) IS NULL THEN NULL WHEN datetime(sent_at) >= datetime(strftime('%Y', sent_at) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(sent_at) < datetime(strftime('%Y', sent_at) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', sent_at, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', sent_at, '-5 hours') || ' EST' END AS sent_at_et,
       *
FROM checkins;
