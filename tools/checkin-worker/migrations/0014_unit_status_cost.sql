-- unit_status read about 600,000 rows per query (2026-10-14: ~600 units x
-- ~1,100 check-ins): its last_kind was a correlated subquery that rescanned
-- every check-in once per unit. Local Vitals refreshing every minute against
-- the live database spent the free tier's 5M daily row reads in under an
-- hour. Same columns and values as 0013; last_kind now comes from one ranked
-- pass, so a read scans the table a fixed number of times.
DROP VIEW unit_status;
CREATE VIEW unit_status AS
SELECT s.*,
       json_extract(s.telemetry, '$.scoreboard.scoreLinkConnected') AS score_link_connected,
       json_extract(s.telemetry, '$.scoreboard.dataFlowing') AS scoreboard_data_flowing,
       json_extract(s.telemetry, '$.scoreboard.sport') AS scoreconnect_sport
FROM (
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
    ), newest AS (
      -- each unit's newest check-in of any kind, in one ranked pass
      SELECT unit_key, reason,
             ROW_NUMBER() OVER (PARTITION BY unit_key ORDER BY seen_at DESC, id DESC) AS rn
      FROM keyed
    ), heard AS (
      SELECT k.unit_key, MAX(k.heard_at) AS last_seen, n.reason AS last_kind
      FROM keyed k
      JOIN newest n ON n.unit_key = k.unit_key AND n.rn = 1
      GROUP BY k.unit_key
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
  )
) s;
