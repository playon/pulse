# Pulse check-in Worker

Where Pulse's launch check-in lands. It replaced the Google Apps Script sheet
after a lapsed personal subscription silently dropped four days of check-ins.

Two Workers, one D1 database (`pulse-checkins`, id `30ea63a8-dbec-494c-827b-ddb48e6dbaac`),
on the ian.moore@playonsports.com Cloudflare account:

| Worker | Who calls it | What it does |
|---|---|---|
| `pulse-checkin` — https://pulse-checkin.pulse-checkin-worker.workers.dev | VPUs (public) | `POST /checkin` stores check-ins; `GET /health`; daily cron posts to Slack when too few arrived |
| `pulse-checkin-admin` — https://pulse-checkin-admin.pulse-checkin-worker.workers.dev | People, behind Cloudflare Access | `/` unit table, `/units.csv`, `/checkins.csv?days=30` |

They are separate Workers because Cloudflare Access on a `workers.dev`
hostname covers the whole hostname, and VPUs have to POST without logging in.

### Sheet relay

When a VPU can't reach this Worker (usually a school filter blocking
`workers.dev`), Pulse posts the check-in to the old Apps Script sheet instead.
That script (in Ian's Google account, not in this repo) writes its row, then
forwards the check-in here with the sheet's key removed and the header
`X-Pulse-Relay: sheet`. Those rows get `source = 'sheet-relay'` and an empty
`country`, because the request comes from Google, not from the school. The VPU
keeps the check-in queued and retries later; that copy lands as a duplicate,
because the checkinId matches. The header is only a label and grants nothing.

## Ingest contract

```json
POST /checkin
{
  "checkins": [
    { "checkinId": "uuid", "sentAt": "2026-09-23T14:00:00Z",
      "venueId": "...", "vpuName": "...",
      "model": "...", "pulseVersion": "...", "channel": "...",
      "readiness": { "status": "PASS", "policyVersion": "1", "blockers": [], "risks": [] } }
  ]
}
```

The response is `{"ok": true, "results": [{"checkinId": "...", "status": "inserted" | "duplicate" | "invalid"}]}`.
A client should drop an entry from its queue on any of those three statuses and
keep it on anything else: a non-200 response, `ok` not true, or a network error.
Limits are 50 check-ins or 64 KB per request, and 30 requests per minute per IP.

Check-ins from the fleet monitor (`Pulse.Web/app/monitor_once.py`) add optional
fields, stored by migration `0002_monitor.sql`:

```json
{ "reason": "periodic" | "state-change",   // "startup" from an interactive launch
  "osBuild": "17763", "ubr": 253,
  "delta": { "status": "FAIL", "prevStatus": "PASS",
             "opened":   [{ "code": "...", "class": "blocker", "title": "...", "since": "..." }],
             "resolved": [] },
  "monitor": { "pass": "full" | "partial", "seconds": 41.5, "psRuns": 9, "eventLive": false } }
```

The `transitions` view gives one row per finding opened or resolved, which is
what the pilot is measured on. The monitor sends 3 check-ins per request, so a
replayed queue stays under the 64 KB cap.

There is no write key. Pulse ships from a public repo, so a key in it was
readable by anyone and only looked like protection. The protection is the
per-IP rate limit, the size caps and field-by-field validation, and the ingest
Worker can't read anything back. Older builds still send a `secret` field; it
is ignored and never stored. Real per-unit auth comes with the Unity transport.

## One-time setup

Run everything from this folder.

1. **Log in:** `npx wrangler login`. Use the ian.moore@playonsports.com Cloudflare account.
2. **Create the database:** `npx wrangler d1 create pulse-checkins`. Paste the
   `database_id` it prints into **both** `database_id` lines in `wrangler.toml`.
3. **Apply the schema:** `npm run migrate:remote`
4. **Set the Slack webhook.** Create an app at api.slack.com/apps, then Incoming
   Webhooks, then add one to the target channel. Then run
   `npx wrangler secret put SLACK_WEBHOOK_URL`.
5. **Deploy:** `npm run deploy`. This deploys both Workers.
7. **Put Access in front of the admin Worker.** In the dashboard, open Workers &
   Pages, then `pulse-checkin-admin`, Settings, Domains & Routes, and turn on
   Cloudflare Access for the workers.dev route. In Zero Trust, open Access,
   Applications, then that app, and add a policy: *Allow* where *Emails
   ending in* is `@playonsports.com`. Copy the team domain and the
   Application Audience (AUD) tag into `ACCESS_TEAM_DOMAIN` and `ACCESS_AUD`
   under `[env.admin.vars]`, then run `npx wrangler deploy --env admin` again.
   Until both are set, the admin Worker answers 403 to everyone.
8. **Add a second admin:** Manage Account, then Members. This keeps the sink
   from depending on one person.

Don't turn on Access for `pulse-checkin`. That would lock out every VPU.

## Checking it

```bash
curl -s https://pulse-checkin.pulse-checkin-worker.workers.dev/health
```

The alert runs daily at 13:00 UTC. `ALERT_WINDOW_HOURS` (default 24) and
`ALERT_MIN_CHECKINS` (default 1) in `wrangler.toml` tune it. Past runs are
under the Worker's Cron Triggers tab in the dashboard.

## Local development

```bash
npm install
printf 'DEV_ALLOW_UNAUTHENTICATED=true\n' > .dev.vars.admin   # local only, never in the dashboard
npm run migrate:local
npm run dev          # ingest on :8787
npm run dev:admin    # admin on :8788, sharing the same local database
npm test             # node:test against the real migrations via node:sqlite
```

To fire the cron by hand, run `npx wrangler dev --local --test-scheduled`, then
`curl "localhost:8787/__scheduled?cron=0+13+*+*+*"`.

## Backups

D1 Time Travel restores to any point in the last 7 days on the free plan
(`npx wrangler d1 time-travel restore pulse-checkins --timestamp=...`).
For a copy you hold yourself, run `npx wrangler d1 export pulse-checkins --remote --output=backup.sql`.
