# Pulse telemetry v1 — data contract

> **The canonical contract is `docs/contract.md` in `playon/pulse-vitals`.**
> This page is the summary for DevOps and the NFHS Console team. Where they
> differ, the Vitals contract and the ingest Worker win.

**Status:** draft for DevOps and the NFHS Console (Oracle) team. Proof of
concept running on one bench VPU since 2026-10-12.
**Owner:** Ian Moore (Pulse). **Schema id:** `pulse.telemetry/v1`.
**Scope:** the utilitarian payload (fields chosen 2026-10-13). A
troubleshooting tier (full finding copy, every adapter, clock drift, PoE,
GPUs, disks, recordings) comes later and will be additive.

## What this is

Pulse runs on Windows VPUs. A scheduled task checks the unit and reports
whether it is ready to stream, and if not, why. This document describes what
it sends, so NFHS Console can show it beside the Pixellot metrics Oracle
already displays.

Pixellot's own monitoring (via Unity `pixellot_monitoring`) reports symptoms:
CPU, bandwidth, dark court. Pulse reports causes Pixellot can't see from
outside the box: a venue firewall blocking UDP 2088, a camera port at
100 Mbps, ScoreConnect stopped, an unexpected power loss.

## When the VPU checks, and when it posts

Checking and posting are separate. The task ticks every 5 minutes; most ticks
do nothing.

| Situation | Readiness check | Post |
|---|---|---|
| Event live (vpu.exe running) | **none** | **none** |
| Healthy (PASS) | every 20 min | one-line **heartbeat** once an hour |
| WARN (streams, with a problem) | every 15 min | full report every 30 min |
| FAIL (will not stream) | every 15 min | full report every 15 min |
| A finding seen once, awaiting confirmation | next tick (5 min) | nothing until confirmed |
| **Anything changes** | | **full report at once** |

"Changes" means any field in the payload below, or any blocker/risk opening
or resolving. A finding counts only after two checks in a row see it, and
clears only after two in a row don't, so a flapping link doesn't post every
check. Info-only findings never speed checks up.

**Consequence for consumers:** silence is normal. A healthy unit posts once an
hour; a unit mid-event posts nothing for the length of the game. "Last seen"
older than ~70 minutes outside an event means powered off, offline, or the
monitor isn't installed. The data can't tell those apart.

## Transport today, and what we need from DevOps

Today the VPU POSTs to a Cloudflare Worker (`tools/checkin-worker/`), which
stores each check-in in a D1 (SQLite) database. That is the proof of concept,
not the destination; the same JSON is what a Console ingest endpoint would
receive.

```
POST https://pulse-checkin.pulse-checkin-worker.workers.dev/checkin
{ "secret": "...", "checkins": [ <check-in>, ... ] }        <- up to 3 per request
-> 200 { "ok": true, "results": [{ "checkinId": "...", "status": "inserted" | "duplicate" | "invalid" }] }
```

The VPU queues every check-in on disk and deletes it only when the sink
answers for it, so a dead or blocked endpoint delays data rather than losing
it. Replays carry their original `sentAt`. `checkinId` is a UUID; the sink
must treat a repeat as a duplicate.

**Open questions for DevOps:**

1. **Endpoint.** A new Unity route, or a separate ingest service Console reads from?
2. **Auth.** The plan is a token held as an AWS secret and injected at build time, shipped inside an executable. Any token inside a publicly downloadable executable can be extracted. Options: a write-only token scoped to this one route plus server validation and rate limits; per-unit tokens issued at install; or a short-lived token from Unity's existing `GET /v2/pixellot_auth_token`.
3. **Volume.** See sizing below.
4. **Retention.** Console probably needs the latest reading per unit plus a 30-90 day transition log, not every post.
5. **Reachability.** School web filters may block `workers.dev`; a playonsports/nfhsnetwork domain is less likely to be.

## Sizing

| | Value |
|---|---|
| Full report | ~2 KB |
| Heartbeat | ~200 bytes |
| Healthy unit, per day | 24 heartbeats, ~5 KB |
| Full fleet (~14,000 Windows VPUs), mostly healthy | ~340,000 heartbeats/day plus full reports on change, roughly 0.1 GB/day |

The monitor's own cost is reported in every full report (`monitor.cpuSeconds`,
`monitor.processes`, `monitor.cpuPercent`). Measured on a bench VPU (6
threads): a check uses ~8 CPU-seconds, ~7% of the machine for ~20 s; an idle
tick 0.14 s.

## Check-in types

**Heartbeat** — an unchanged PASS, hourly. The whole message:

```json
{ "checkinId": "…", "sentAt": "2026-10-13T21:00:00Z", "reason": "heartbeat",
  "venueId": "5d6bdbe845b8870789141191", "vpuName": "PXLS2_6493 …", "status": "PASS" }
```

**Full report** — on any change (`reason: "state-change"`) or an unchanged
FAIL/WARN on schedule (`reason: "periodic"`):

| Field | Notes |
|---|---|
| `checkinId`, `sentAt` | UUID (idempotency key); ISO 8601 UTC creation time |
| `reason` | `state-change` \| `periodic` (monitor); `startup` = a tech opened Pulse |
| `venueId` | Pixellot venue id: **the unit's identity and the join key to Unity, EQS and Pixellot Club** |
| `vpuName` | e.g. `PXLS2_6493 PlayOn Lab - …` |
| `model` | PC model |
| `pulseVersion` | Pulse build |
| `delta` | `{status, prevStatus, opened:[{code,class,title,since}], resolved:[…]}`: what changed |
| `monitor` | `{pass, seconds, psRuns, cpuSeconds, processes, cpuPercent}`: the check's own cost (pilot) |
| `telemetry` | below |

No hostname or BIOS serial is sent.

## `telemetry`

```json
{
  "schema": "pulse.telemetry/v1",
  "status": "FAIL",
  "statusSince": "2026-10-13T19:20:00Z",
  "headline": "The venue network is blocking clock sync",
  "blockers": ["The venue network is blocking clock sync"],
  "checkedAt": "2026-10-13T19:34:30Z",
  "pixellotVersion": "5.37.3",
  "runnerVersion": "2",
  "network": {
    "internetReachable": true,
    "streamingPath": "rtmp-1935",
    "portsFailed": ["Clock sync (UDP 123)"],
    "internet": { "adapter": "Internet", "mac": "C8:D9:D2:1C:29:2A", "ip": "192.168.111.251",
                  "subnetMask": "255.255.254.0", "gateway": "192.168.110.1",
                  "dns1": "192.168.110.1", "dns2": null, "dhcp": false }
  },
  "cameras": {
    "systemType": "S2", "expected": 2, "detected": 2, "slow": 0,
    "ports": [
      { "port": "Port 1", "portMac": "00:30:64:36:73:AA", "state": "camera",
        "linkMbps": 1000, "expectedMbps": 1000, "slow": false,
        "cameraModel": "4K Bullet Outdoor 3-8mm", "cameraMac": "00:D0:89:19:71:57",
        "cameraFirmware": "…" }
    ]
  },
  "servicesDown": [],
  "scoreboard": { "source": "scoreconnect", "ok": true },
  "power": { "lastBoot": "2026-10-13T14:48:23-04:00", "unexpectedShutdowns7d": 4 }
}
```

| Field | Meaning |
|---|---|
| `status` | `PASS` \| `WARN` \| `FAIL`, settled over two checks. FAIL = will not stream; WARN = streams with a problem |
| `statusSince` | when `status` last changed ("FAIL for 3 h") |
| `headline` | the top confirmed blocker, else the top risk, else null |
| `blockers` | confirmed blocker titles |
| `runnerVersion` | the agent runner's own version (`RUNNER_VERSION` in `pulse_agent/runner.py`). An agent update never replaces the runner, so this shows which units need enrolling again for a runner fix. null: a runner from before PV-85's review fixes (re-enroll it), or a monitor not run by the runner |
| `network.streamingPath` | which rung of the failover chain a stream would use now: `zixi-2088` → `zixi-443` → `rtmp-1935`, or `blocked` |
| `network.portsFailed` | required outbound rules that failed |
| `network.internet` | the internet adapter's IPv4 setup and MAC (`AA:BB:CC:DD:EE:FF`) |
| `cameras.systemType` | `S1` \| `S2` \| `S2S` |
| `cameras.ports[].state` | `camera`, `scoreboard camera`, `no link`, `linked, no camera answering`, or `internet cable` (miswired) |
| `cameras.ports[].slow` | linked below its expected speed |
| `servicesDown` | services that should run and don't (vpu.exe is never listed: it runs only during events; ScoreConnect only when it is the score source) |
| `scoreboard.source` | `ocr` (a scoreboard camera reads the score) or `scoreconnect` |
| `power.unexpectedShutdowns7d` | power cuts and hard crashes in 7 days |

## Rules for consumers

- **null means "not known", never "fine".** A collector that failed leaves its part null.
- **Silence is expected.** See the posting table; use "last seen", don't guess.
- **Escape everything on display.** Text comes from the VPU.
- **Join on `venueId`.**

## Privacy

Sent: the internet adapter's IPv4 setup and MAC, each camera port's NIC and
camera MAC, VPU name, venue id, PC model. Never sent: hostname, BIOS serial,
camera serials, user names, public IP (the sink sees the connecting IP but
stores only the country).

## Versioning

New fields are additive and keep the schema id. Renaming or removing a field,
or changing a meaning, becomes `pulse.telemetry/v2`, sent alongside v1 for a
release.

## Proof of concept: where to look

D1 database `pulse-checkins` (Cloudflare account ian.moore@playonsports.com):

- `unit_status`: one row per unit, the fields above as columns, `last_seen` from the newest check-in of any kind, the full document in `telemetry`
- `transitions`: every finding opened or resolved
- `checkins`: every check-in

Source: `Pulse.Web/app/pulse_agent/telemetry.py` (`_build_telemetry`),
`Pulse.Web/app/pulse_agent/monitor.py` (`plan_tick`, `plan_post`),
`Pulse.Web/app/monitor_once.py`,
`tools/checkin-worker/` (ingest and migrations).
