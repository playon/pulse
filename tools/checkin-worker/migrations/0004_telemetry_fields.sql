-- More of pulse.telemetry/v1 as columns (Ian, 2026-10-13), so a fleet grid can
-- show and filter them without json_extract. The JSON `telemetry` column
-- still holds everything, including the per-adapter and per-port detail.
ALTER TABLE checkins ADD COLUMN tel_system_type      TEXT;     -- S1 | S2 | S2S
ALTER TABLE checkins ADD COLUMN tel_blockers         TEXT;     -- JSON [title]
ALTER TABLE checkins ADD COLUMN tel_cameras_slow     INTEGER;  -- camera ports below expected link speed
ALTER TABLE checkins ADD COLUMN tel_ports_failed     TEXT;     -- JSON ["Streaming (Zixi primary) (UDP 2088)"]
ALTER TABLE checkins ADD COLUMN tel_services_down    TEXT;     -- JSON [service name]
ALTER TABLE checkins ADD COLUMN tel_scoreboard_source TEXT;    -- ocr | scoreconnect
ALTER TABLE checkins ADD COLUMN tel_scoreboard_ok    INTEGER;
ALTER TABLE checkins ADD COLUMN tel_ip               TEXT;     -- the internet adapter's IPv4 setup
ALTER TABLE checkins ADD COLUMN tel_subnet_mask      TEXT;
ALTER TABLE checkins ADD COLUMN tel_gateway          TEXT;
ALTER TABLE checkins ADD COLUMN tel_dns1             TEXT;
ALTER TABLE checkins ADD COLUMN tel_dns2             TEXT;
ALTER TABLE checkins ADD COLUMN tel_dhcp             INTEGER;
ALTER TABLE checkins ADD COLUMN tel_last_boot        TEXT;
ALTER TABLE checkins ADD COLUMN tel_unexpected_7d    INTEGER;  -- unexpected shutdowns / power loss, 7 days
ALTER TABLE checkins ADD COLUMN tel_reboot_pending   INTEGER;
ALTER TABLE checkins ADD COLUMN tel_poe_draw_w       REAL;
ALTER TABLE checkins ADD COLUMN tel_clock_offset_s   REAL;

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
       tel_dns1 AS dns1, tel_dns2 AS dns2, tel_dhcp AS dhcp,
       tel_services_down AS services_down,
       tel_scoreboard_source AS scoreboard_source, tel_scoreboard_ok AS scoreboard_ok,
       tel_last_boot AS last_boot, tel_unexpected_7d AS unexpected_shutdowns_7d,
       tel_reboot_pending AS reboot_pending, tel_poe_draw_w AS poe_draw_w,
       tel_clock_offset_s AS clock_offset_s,
       event_live, pulse_version, serial_number,
       telemetry
FROM latest
WHERE rn = 1;
