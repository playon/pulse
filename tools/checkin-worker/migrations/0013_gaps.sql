-- What the 6493 test event (2026-10-14) showed was missing from the views.
-- Each view is its previous body (0010 unit_status, 0012 events) wrapped,
-- with new columns appended; every existing column stays, so Vitals keeps
-- working unchanged (playon/pulse-vitals docs/contract.md, rule 3).
--
-- unit_status: telemetry.scoreboard.ok means "ScoreConnect is running" when
-- there's no OCR camera, and read true all event with 6493's ScoreLink
-- missing. The pass now also reports whether the ScoreLink is connected,
-- whether score data is arriving, and the sport ScoreConnect decodes.
--
-- events: the in-event reader now logs the event's name, NFHS game key and
-- schedule (VPU.exe's own "Start Reason" line), time off air inside the event
-- (outages and VPU.exe restarts), and warnings, led by a scoreboard set to
-- the wrong sport for the game.
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
  )
) s;

DROP VIEW events;
CREATE VIEW events AS
SELECT v.*,
       json_extract(v.event, '$.eventName') AS event_name,
       json_extract(v.event, '$.nfhsGameKey') AS nfhs_game_key,
       json_extract(v.event, '$.scheduledStart') AS scheduled_start,
       json_extract(v.event, '$.scheduledEnd') AS scheduled_end,
       json_extract(v.event, '$.offAirSeconds') AS off_air_seconds,
       json_extract(v.event, '$.path') AS path,
       json_extract(v.event, '$.kind') AS kind,
       json_extract(v.event, '$.scoreboard.sportMatch') AS scoreboard_sport_match,
       json_extract(v.event, '$.scoreboard.scoreConnectSport') AS scoreconnect_sport,
       json_extract(v.event, '$.warnings') AS warnings
FROM (
  WITH e AS (
    SELECT *,
           COALESCE(venue_id, vpu_name, hostname, serial_number) AS unit_key,
           ROW_NUMBER() OVER (PARTITION BY COALESCE(venue_id, vpu_name, hostname, serial_number), event_id
                              ORDER BY COALESCE(sent_at, received_at) DESC, id DESC) AS rn,
           MIN(COALESCE(sent_at, received_at)) OVER (PARTITION BY COALESCE(venue_id, vpu_name, hostname, serial_number), event_id) AS first_at
    FROM checkins
    WHERE event_id IS NOT NULL
  )
  SELECT unit_key, venue_id, vpu_name, event_id,
         first_at AS started_at,
         COALESCE(sent_at, received_at) AS updated_at,
         reason AS last_kind,
         event_state AS state,
         event_on_air AS went_on_air,
         event_reason AS why_not_on_air,
         json_extract(event, '$.onAirSeconds') AS on_air_seconds,
         json_extract(event, '$.fails') AS fails,
         json_extract(event, '$.restarts') AS restarts,
         json_extract(event, '$.drops') AS drops,
         json_extract(event, '$.camerasDown') AS cameras_down,
         json_extract(event, '$.lastFailUrl') AS last_fail_url,
         json_extract(event, '$.closeReason') AS close_reason,
         event
  FROM e
  WHERE rn = 1
) v;
