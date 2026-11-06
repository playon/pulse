-- PV-19: five telemetry columns have never been filled. The Worker binds
-- tel.risks, rebootPending, poeDrawW, clockOffsetS and cameraMacs, but
-- telemetry() never sets them and the agent doesn't send them (the
-- "troubleshooting tier", not built). unit_status already stopped selecting
-- them in 0006; checkins_et was the last view still exposing them, through
-- SELECT *. SQLite can't exclude columns from *, so the list is explicit.
-- Adding a column to checkins now means adding it here too (a test checks).
-- The base-table columns stay: dropping them buys nothing and the ingest
-- INSERT still binds them. Revisit when that tier ships.
DROP VIEW checkins_et;
CREATE VIEW checkins_et AS
SELECT CASE WHEN datetime(received_at) IS NULL THEN NULL WHEN datetime(received_at) >= datetime(strftime('%Y', received_at) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(received_at) < datetime(strftime('%Y', received_at) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', received_at, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', received_at, '-5 hours') || ' EST' END AS received_at_et,
       CASE WHEN datetime(sent_at) IS NULL THEN NULL WHEN datetime(sent_at) >= datetime(strftime('%Y', sent_at) || '-03-01', 'weekday 0', '+7 days', '+7 hours') AND datetime(sent_at) < datetime(strftime('%Y', sent_at) || '-11-01', 'weekday 0', '+6 hours') THEN strftime('%Y-%m-%d %H:%M:%S', sent_at, '-4 hours') || ' EDT' ELSE strftime('%Y-%m-%d %H:%M:%S', sent_at, '-5 hours') || ' EST' END AS sent_at_et,
       id, checkin_id, received_at, sent_at,
       hostname, serial_number, venue_id, vpu_name,
       model, pulse_version, channel, readiness_status,
       readiness_policy, readiness_blockers, readiness_risks, country,
       source, raw, reason, os_build,
       ubr, delta_status, delta_prev_status, delta_opened,
       delta_resolved, monitor_pass, monitor_seconds, monitor_ps_runs,
       event_live, tel_status, tel_status_since, tel_headline,
       tel_blocker_count, tel_pixellot_version, tel_cameras_expected, tel_cameras_detected,
       tel_streaming_path, telemetry, tel_system_type, tel_blockers,
       tel_cameras_slow, tel_ports_failed, tel_services_down, tel_scoreboard_source,
       tel_scoreboard_ok, tel_ip, tel_subnet_mask, tel_gateway,
       tel_dns1, tel_dns2, tel_dhcp, tel_last_boot,
       tel_unexpected_7d, tel_mac, tel_internet_reachable, monitor_cpu_seconds,
       monitor_cpu_percent, monitor_processes, monitor_memory_peak_mb, event_id,
       event_state, event_reason, event_on_air, event,
       agent_version, agent_update_status, agent_update_version, agent_update_error
FROM checkins;
