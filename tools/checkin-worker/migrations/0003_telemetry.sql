-- pulse.telemetry/v1 from the fleet monitor (Pulse.Web/app/main.py
-- _build_telemetry). Tier 1 (the summary a fleet grid shows) as columns so it
-- sorts and filters; tier 2 (the detail behind it) as one JSON document,
-- readable with json_extract. NULL on launch check-ins and older builds.
ALTER TABLE checkins ADD COLUMN tel_status          TEXT;     -- PASS | WARN | FAIL
ALTER TABLE checkins ADD COLUMN tel_status_since    TEXT;     -- when the verdict last changed
ALTER TABLE checkins ADD COLUMN tel_headline        TEXT;     -- top blocker, else top risk
ALTER TABLE checkins ADD COLUMN tel_blocker_count   INTEGER;
ALTER TABLE checkins ADD COLUMN tel_risk_count      INTEGER;
ALTER TABLE checkins ADD COLUMN tel_pixellot_version TEXT;
ALTER TABLE checkins ADD COLUMN tel_cameras_expected INTEGER;
ALTER TABLE checkins ADD COLUMN tel_cameras_detected INTEGER;
ALTER TABLE checkins ADD COLUMN tel_streaming_path  TEXT;     -- zixi-2088 | zixi-443 | rtmp-1935 | blocked
ALTER TABLE checkins ADD COLUMN telemetry           TEXT;     -- full tier 1 + 2 JSON

-- The latest telemetry per unit: what a fleet grid (or NFHS Console) shows.
CREATE VIEW unit_status AS
WITH latest AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY COALESCE(serial_number, ''), COALESCE(hostname, '')
           ORDER BY COALESCE(sent_at, received_at) DESC, id DESC) AS rn
  FROM checkins
  WHERE telemetry IS NOT NULL
)
SELECT venue_id, vpu_name, hostname, serial_number,
       COALESCE(sent_at, received_at) AS last_seen,
       tel_status AS status, tel_status_since AS status_since,
       tel_headline AS headline, tel_blocker_count AS blockers, tel_risk_count AS risks,
       event_live, tel_streaming_path AS streaming_path,
       tel_cameras_detected AS cameras_detected, tel_cameras_expected AS cameras_expected,
       tel_pixellot_version AS pixellot_version, pulse_version,
       telemetry
FROM latest
WHERE rn = 1;
