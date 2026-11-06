-- The monitor's in-event reader (Pulse.Web/app/event_watch.py, 2026-10-14).
-- While VPU.exe runs it reads only the files Pixellot already writes (the VPU
-- log's new lines, the AgentBenchmarks tail, the recorded-event folder name)
-- and posts at an event's start, on a confirmed change, and at its end:
-- reason 'event-start' / 'event-update' / 'event-end', with an `event`
-- document (pulse.event/v1) stored whole. event_id is the Pixellot event id;
-- Unity's GET /v2/pixellots/broadcasts/<id> (no auth) resolves it to the NFHS
-- game key, broadcast key and air status.
ALTER TABLE checkins ADD COLUMN event_id TEXT;
ALTER TABLE checkins ADD COLUMN event_state TEXT;     -- on-air, connecting, stream-failing, restart-loop, camera-link-down, ended
ALTER TABLE checkins ADD COLUMN event_reason TEXT;    -- on 'event-end' when it never aired: why
ALTER TABLE checkins ADD COLUMN event_on_air INTEGER; -- 1 if the stream connected at any point
ALTER TABLE checkins ADD COLUMN event TEXT;           -- the pulse.event/v1 document

CREATE INDEX IF NOT EXISTS checkins_event_id ON checkins (event_id);

-- One row per (unit, event): its newest event post. `ended` = an event-end
-- arrived; otherwise the event is live (or its end hasn't been posted yet).
CREATE VIEW events AS
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
WHERE rn = 1;
