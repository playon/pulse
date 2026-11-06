-- unit_latest.ev_type (PV-51): whether the unit's newest event is a game
-- ('event') or Pixellot's daily test ('daily-test'), so Vitals can keep the
-- two apart without guessing from the event id. Additive: no existing column
-- changes. Ingest and the daily rebuild fill it from src/latest.js.
ALTER TABLE unit_latest ADD COLUMN ev_type TEXT;

-- Backfill: the event each row already points at (ev_row is the check-in id).
UPDATE unit_latest
SET ev_type = (SELECT CASE WHEN json_extract(c.event, '$.kind') = 'daily-test' THEN 'daily-test' ELSE 'event' END
               FROM checkins c WHERE c.id = unit_latest.ev_row)
WHERE ev_row IS NOT NULL;
