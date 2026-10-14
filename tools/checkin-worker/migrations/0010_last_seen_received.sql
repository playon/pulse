-- last_seen is when the Worker last heard from the unit (received_at), not the
-- VPU's own clock (Ian, 2026-10-14). sent_at is rejected only when it is in the
-- future, so a unit whose clock runs days slow (a venue that blocks NTP on
-- UDP 123 is one of Pulse's own findings) read as offline while still posting.
-- A replayed backlog now counts as "heard just now", which is true: the unit
-- reached the Worker. A sheet-imported row keeps sent_at, because its
-- received_at is the import date, not a sighting.
-- Everything that orders check-ins (newest reading, last_kind, last_launch,
-- first_seen) still uses sent_at, so a replay never outranks a newer report.
-- The view bodies are the 0009 ones with only last_seen changed.

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
           CASE WHEN source = 'sheet-import' THEN COALESCE(sent_at, received_at) ELSE received_at END AS heard_at,
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
           MAX(heard_at)     AS last_seen,
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
           COALESCE(sent_at, received_at) AS seen_at,
           CASE WHEN source = 'sheet-import' THEN COALESCE(sent_at, received_at) ELSE received_at END AS heard_at
    FROM checkins
  ), latest AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY unit_key ORDER BY seen_at DESC, id DESC) AS rn
    FROM keyed
    WHERE telemetry IS NOT NULL
  ), heard AS (
    SELECT unit_key, MAX(heard_at) AS last_seen,
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
