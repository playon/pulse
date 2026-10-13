-- MAC addresses (Ian, 2026-10-13: needed for triage and Pixellot RMA lookups).
-- tel_mac is the internet adapter's; tel_camera_macs lists every connected
-- camera's, so a camera can be found by MAC across the fleet:
--   SELECT vpu_name FROM unit_status WHERE camera_macs LIKE '%00:0E:53:AA:01:01%';
-- Every adapter's and camera port's MAC is in the telemetry JSON.
ALTER TABLE checkins ADD COLUMN tel_mac         TEXT;  -- AA:BB:CC:DD:EE:FF
ALTER TABLE checkins ADD COLUMN tel_camera_macs TEXT;  -- JSON ["AA:BB:CC:DD:EE:FF"]

DROP VIEW unit_status;
CREATE VIEW unit_status AS
WITH latest AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY COALESCE(serial_number, ''), COALESCE(hostname, '')
           ORDER BY COALESCE(sent_at, received_at) DESC, id DESC) AS rn
  FROM checkins
  WHERE telemetry IS NOT NULL
)
SELECT vpu_name, venue_id, hostname,
       COALESCE(sent_at, received_at) AS last_seen,
       tel_status AS status, tel_status_since AS status_since,
       tel_headline AS headline, tel_blocker_count AS blocker_count, tel_blockers AS blockers,
       tel_risk_count AS risk_count,
       tel_streaming_path AS streaming_path, tel_ports_failed AS ports_failed,
       tel_system_type AS system_type,
       tel_cameras_detected AS cameras_detected, tel_cameras_expected AS cameras_expected,
       tel_cameras_slow AS cameras_slow,
       tel_pixellot_version AS pixellot_version,
       tel_ip AS ip, tel_subnet_mask AS subnet_mask, tel_gateway AS gateway,
       tel_dns1 AS dns1, tel_dns2 AS dns2, tel_dhcp AS dhcp, tel_mac AS mac,
       tel_camera_macs AS camera_macs,
       tel_services_down AS services_down,
       tel_scoreboard_source AS scoreboard_source, tel_scoreboard_ok AS scoreboard_ok,
       tel_last_boot AS last_boot, tel_unexpected_7d AS unexpected_shutdowns_7d,
       tel_reboot_pending AS reboot_pending, tel_poe_draw_w AS poe_draw_w,
       tel_clock_offset_s AS clock_offset_s,
       event_live, pulse_version, serial_number,
       telemetry
FROM latest
WHERE rn = 1;
