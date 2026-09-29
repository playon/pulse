# Plan — Scoreboard Self-Healing + VPU Manager Integration

Status: **Phase 0 discovery COMPLETE** (VPU2, 2026-08-11). Design below is now
grounded in real VPU state, not inference.
Owner: Ian.

## The field problem

VPUs resolve scoreboard data through a fallback chain:

```
Sportzcast (ScoreConnect)  →  OCR camera  →  CHUPIP (full-PiP from main heads)
```

CHUPIP crops the scoreboard out of a wide main-camera frame — far away, often
behind fencing, badly blurred. It is technically "working" (a stream goes out
with a scoreboard box), which is why it survives unnoticed.

---

# Part 1 — Discovery findings (VPU2, verified)

## 1.1 The scoreboard mode is a plain file read

`C:\Pixellot\Data\Configuration\graphics.cfg`, INI-style, `[GENERAL]` section:

```
TYPE, string, WEB    // options WEB,SPORTZCAST,DAKTRONICS,OUTFITTERS,OCR,NEVCO
```

**This is the "scoreboard set to WEB / OFF / MANUAL" field.** No VPU Manager
API call needed — `Get-Content` + the INI parser pattern already in
`Get-PixellotConfig.ps1`. PS 5.1-safe, zero new transport, zero risk.

Other useful `graphics.cfg` keys observed:

| Key | VPU2 value | Why Pulse wants it |
|---|---|---|
| `TYPE` | `WEB` | configured scoreboard source |
| `BOT_NUMBER` | `02130` | **authoritative bot number** — SC III's is documented as "notoriously stale" (`Get-ScoreConnectStatus.ps1:~442`). Cross-check the two and flag mismatches. |
| `GRAPHICS_MODE_ON_INIT` | `LOGOS_ONLY` | `LOGOS_ONLY` / `LOGOS_SCOREBUG` / `CLEAN`. **`LOGOS_ONLY` means no scorebug is drawn at all** — a silent "why is there no score on my broadcast" cause. |
| `VENUE_ID` | `YOUR_VENUE_ID` | literal placeholder = **venue never provisioned**. Straight finding. |
| `PORT` | `1402` | Sportzcast listener (matches the observed listening port) |
| `SHOT_CLOCK_ENABLE`, `NUMBER_OF_PERIODS` | `true`, `4` | sport-config sanity |
| `HTML_GRAPHICS_URL` | `127.0.0.1:1888/graphicsClient.html` | local graphics client (event-time only) |
| `LIGR_ENABLED`, `[SINGULAR] TYPE` | `false`, `FLOW` | third-party graphics provider wiring |
| `DO_NOT_DOWNLOAD_HTML_FILES_FROM_CLOUD` | `true` | explains stale graphics assets |
| `AUTHENTICATION` | (blank) | Nevco-only credential slot |

## 1.2 CHUPIP fallback has an explicit on-disk flag

`C:\Pixellot\Data\Configuration\PiP.cfg`:

```
[PIP]
IS_AUTO_OCR_TO_FULL_PIP_FALLBACK, bool, false
    //Indicates that PiP process started after fallback from OCR to full PiP

[DEEP_OCR]
FULL_PIP_AUTO_FALLBACK_GRACE_TIME_SEC, int, 300
MAX_ALLOWED_CONTINUOUS_FAILURES_PERCENTAGE, int, 80
MAX_ALLOWED_CONTINUOUS_FAILURES_TIME_SEC,   int, 60
ENHANCED_PIP, bool, false    //Enable in order to use PIP scoreboard overlays
DO_DEEP_OCR,  bool, false
```

**`IS_AUTO_OCR_TO_FULL_PIP_FALLBACK` is the CHUPIP detector.** True = this box
fell back to the blurry main-head scoreboard. The three `DEEP_OCR` thresholds
are the exact fallback policy (80% failures over 60s, 300s grace) — so Pulse
can explain *why* it fell back, not just that it did.

`ENHANCED_PIP` here mirrors the `Graphics\pipdesign\enhanced_pip.txt` presence
check already in `Get-PixellotConfig.ps1:125-144` — cross-check them; a
disagreement is itself a finding.

Also in `[PIP]`:

| Key | VPU2 value | Use |
|---|---|---|
| `CAMERA_URL` | `rtsp://10.0.0.151/h264` | **the OCR camera's actual address** per Pixellot |
| `LAST_PAIRED_IP` / `_MAC_ADDRESS` / `_STATUS` / `_UTC_TIMESTAMP` | blank / blank / `false` / `0` | **OCR camera has never successfully paired** on this box |
| `BRIGHTNESS` `EXPOSURE` `GAIN` `IRIS` `EXPOSURE_MODE` `SATURATION` | 60 / 20000 / 4 / 2 / `MANUAL` / 10 | Pixellot's *intended* OCR picture settings — compare against what the camera actually reports (the black-frame work) |
| `CONNECTION_TYPE` | (blank) | `LAN` / `DIRECT` |
| `AUTO_CAMERA_SETUP` | `false` | one-shot post-install camera setup |

> ⚠️ `PiP.cfg [CAM_CREDENTIALS]` holds a **cleartext camera username/password**.
> Any collector that reads this file must drop that section before it reaches
> the payload — do not surface, log, or export it. Add the key names to
> `tools/vpu-smoke/redact.py` as well.

## 1.3 VPU Manager is real, unauthenticated, and message-driven

- `http://localhost:32323/` → **200**, a Vite/Vue SPA titled "VPU Manager",
  served by `Microsoft-HTTPAPI/2.0` (http.sys, `HTTP://*:32323/` reservation).
  **No auth on the root.**
- Bundle `/assets/index.3d61003e.js` is ~11 MB and contains **121 distinct
  `*Message` types** — the app is a message-bus client, not a REST client.
  Only outbound REST found: `abe[.dev|.stage].pixellot.tv/api/v3/auth/keys`.
- ScoreConnectIII (PID 5988) owns ports **1402, 1883 (MQTT), 5000, 8083**
  (8083 = MQTT-over-WebSocket by convention). So an MQTT broker is already
  running locally, shipped by Sportzcast.
- **Transport still unconfirmed.** Port `42424` answers HTTP but 404s on `/`
  (so something is listening at a sub-path); `9001` is another http.sys
  reservation. Nailing the exact bus endpoint is the one open discovery item.
- Event-time-only services, **not listening while idle**: `33337`
  (`PiP.cfg [STATUSREPORTER] LISTEN_PORT`, `PIP_REPORT_INTERVAL_MSEC = 1000`)
  and `1888` (graphics client). These come up during an event.

### Message catalogue highlights (all 121 observed)

| Message | Opportunity for Pulse |
|---|---|
| `VenueSelfTestProgressMessage` | **Pixellot ships its own venue self-test.** Pulse could trigger and surface it. |
| `StartChuOcrValidationMessage` / `...ResponseMessage` | on-demand validation of the CHU/OCR scoreboard path |
| `SetChuFeedModeMessage`, `PipScoreboardModeMessage`, `OcrModeMessage` | the write side of the scoreboard source |
| `CameraFramesRequestMessage` / `ReplyMessage` / `FailureReplyMessage` | **live camera frames without touching RTSP** — feeds the black-frame diagnostic |
| `PipFrameStreamMessage`, `StartPipFramesStreamRequest` | live PiP/OCR frame stream (see what the scorebug crop actually looks like) |
| `RequestChuOcrFrameMessage`, `ChuOcrFrameMessage` | single CHU OCR frame grab |
| `CamerasParametersRequest/Reply`, `...MinMaxValuesRequest/Reply` | authoritative camera picture settings **and their valid ranges** |
| `SimplifiedCalibration*` (sport types, ground points) | calibration state + supported sports, live |
| `ScoreboardStatusMessage`, `ScoreBoardDataMessage`, `OcrDataMessage` | live scoreboard/OCR data state |
| `ScoreboardCalibrationDataMessage`, `ApplyScoreboardCalibration*` | scoreboard calibration read/apply |
| `LocalLicenseInfoMessage` | **licensing** — currently a blind spot in Pulse |
| `ChuUpgradeStatusMessage`, `CcuUpdateMessage`, `VersionMessage` | camera-head firmware/upgrade state — the open TBD in the calibration/firmware memory |
| `UploadStatusMessage`, `PostProcessStatusMessage`, `RawUploadStatusMessage` | event upload / post-process backlog |
| `RealtimeInformationMessage`, `StatusInformationMessage`, `StaticInformationMessage` | general live telemetry |
| `PoeRequestMessage` | **PoE control on camera ports** — remote camera power-cycle |
| `AudioValueMessage`, `AudioEnabledMessage` | cross-check the audio lane |
| `TunnelControlMessage` | Pixellot's own remote-access tunnel |

---

# Part 2 — What to build

## Phase 1 — Scoreboard Source panel (read-only, no new transport)

Ships entirely off the two config files + what Pulse already collects. This is
now a small, low-risk change — no message bus, no writes.

New collector reads `graphics.cfg` + `PiP.cfg` (reusing the INI parse pattern
in `Get-PixellotConfig.ps1:31-87`, minus `[CAM_CREDENTIALS]`), joins with the
existing SC III status and OCR calibration, and renders one verdict:

| Condition | Verdict |
|---|---|
| `IS_AUTO_OCR_TO_FULL_PIP_FALLBACK = true` | 🔴 **On CHUPIP — broadcast scoreboard is blurry.** Fell back after 80% OCR failures / 60s, 300s grace. |
| `TYPE = SPORTZCAST` + SC III data flowing | ✅ healthy |
| `TYPE = SPORTZCAST` + no data | ⚠️ Sportzcast configured but silent → offer the sweep (Phase 2) |
| `TYPE = OCR` + OCR not calibrated **or** `LAST_PAIRED_STATUS = false` | 🔴 OCR selected but never paired/calibrated — CHUPIP is imminent |
| `TYPE = WEB` | ℹ️ scoreboard comes from the cloud, not this box — local SC/OCR findings are expected, not faults |
| `GRAPHICS_MODE_ON_INIT = LOGOS_ONLY` | ⚠️ **no scorebug will render at all**, whatever the source |
| `VENUE_ID = YOUR_VENUE_ID` | 🔴 venue never provisioned |
| `graphics.cfg BOT_NUMBER ≠ SC III botNumber` | ⚠️ stale bot registration |

The `TYPE = WEB` row matters more than it looks: it stops techs chasing a dead
Sportzcast on a box that was never meant to use it.

## Phase 2 — Sportzcast profile sweep (guarded write)

Unchanged in design, and still worth building — but note Phase 1 now correctly
*scopes* it: only offer the sweep when `TYPE = SPORTZCAST`.

SC III exposes the whole tree (mapped in `Pulse.WPF/.../ScoreConnectService.cs`):
`get-vendor-list` → `get-vendor-sports/{vendorId}` →
`get-vendor-configurations/{vendorSportId}` → `set-scoreconnect-configuration`
(PUT-first, POST fallback).

**Candidate set:** every `(vendorId, vendorSportId, configurationId)` whose
sport matches the configured sport, across vendors.

**Per candidate:** apply → dwell N sec → sample `get-status` twice ~2s apart.
**Oracle:** `scoreBoardData.description` says present AND raw `data` non-empty
AND the two samples *differ* — a stale non-empty buffer would otherwise read as
a win.

**Guardrails:** refuse if data already present; refuse (or loudly confirm)
during an active event; snapshot original config first and abort if that read
fails; restore-on-exit finally-blocked, then re-read to verify the restore took;
hard runtime cap + working cancel; report every candidate tried.

**No-winner is a real result:** "swept 14 profiles for Basketball, none produced
data" is strong evidence of a cabling / controller-power / ScoreLink fault
rather than configuration.

Still needs from discovery: the **settle time** after a profile change, and the
real size of a `get-vendor-configurations` list (sets the runtime cap). Both
need a bench box with a live controller — VPU2 has none attached.

## Phase 3 — VPU Manager as a Pulse data source

Ordered by value-to-effort. **Read-only throughout** — see the caution below.

1. **Confirm the transport.** Probe `42424` sub-paths and the MQTT broker on
   `1883`/`8083`; watch what the SPA does with DevTools open on the VPU. One
   session. Everything else is gated on this.
2. **Venue self-test passthrough** (`VenueSelfTestProgressMessage`) — Pixellot's
   own acceptance test, surfaced in Pulse alongside Stream Readiness. Highest
   single payoff: it is Pixellot's definition of "this venue is good."
3. **Live camera frames** (`CameraFramesRequestMessage`, `RequestChuOcrFrameMessage`)
   — replaces/augments the RTSP path in the black-frame diagnostic and works for
   the CHU/OCR head specifically.
4. **Camera parameters + min/max** — the black-frame work currently compares
   same-room settings; this gives authoritative values *and legal ranges*.
5. **Licensing + CHU firmware** (`LocalLicenseInfoMessage`, `ChuUpgradeStatusMessage`,
   `VersionMessage`) — closes two known Pulse blind spots, including the firmware
   location TBD.
6. **Upload / post-process backlog** (`UploadStatusMessage`, `PostProcessStatusMessage`)
   — "the game recorded but never showed up" tickets.
7. **Event-time PiP status feed** on `:33337` (1 Hz) — live OCR health *during*
   a game, which nothing in Pulse can see today.

### Caution on writes

The bus is Pixellot's own control plane (`PoeRequestMessage`, camera control,
`SetChuFeedMode`, calibration apply, `TunnelControlMessage`). Pulse writing to
it is a materially bigger step than anything Pulse does now — reversible-looking
messages can strand a camera mid-event. **Read-only until there's a specific
ticket-driven case, and treat any write as Repair-Tools-gated.**

Also: 32323 is unauthenticated on localhost. That is Pixellot's design decision,
not ours, but Pulse's remote-access work (Cloudflare Tunnel) should never expose
it — worth an explicit note in that project.

---

## Open decisions for Ian

1. **Phase 1 scope** — ship the config-file panel on its own? It's small,
   read-only, and independently useful. Recommendation: yes, now.
2. **On a winning sweep profile — apply-and-keep, or restore and let the tech
   apply?** Recommendation: apply-and-keep behind an opt-in checkbox that
   defaults off in v1.
3. **Sweep during a live event** — hard block or warn-and-allow? Techs are
   usually calling *because* a game is on. Recommendation: warn-and-allow with a
   loud confirmation.
4. **How far into VPU Manager do we go?** Phase 3 items 2–4 are a real feature
   line, not a weekend. Worth a PULSEDEV epic if we commit.
5. **Sportzcast heads-up** before Pulse starts POSTing configuration changes to
   their service across the fleet?
