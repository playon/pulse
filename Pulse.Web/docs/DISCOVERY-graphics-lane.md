# Discovery — Graphics / Scorebug lane

Status: **on-box discovery COMPLETE** (vpu-home, Win10 LTSC 17763, 2026-09-14).
The box was on 5.27.6 when discovery started and the prod cloud upgraded it to **GA 5.37.1**
mid-session (`InstallationStage INSTALL_SUCCESS` 15:44, CHU firmware upgraded, agent reported
`softwareVersion: 5.37.1` at 16:29). Everything below was re-verified after the upgrade.
Origin: the Tanque Verde review (2026-09-14) — two units broadcast a full event with no
scorebug and passed every Pulse check. Pulse has zero on-box graphics visibility today;
its whole graphics surface is external reachability to `singular.live`
(`Test-NetworkPorts.ps1:59`, `Test-TlsInspection.ps1:146`).

Every path, filename, log format and field below was read off vpu-home over ssh, not inferred.

---

## 1. Where the evidence lives

| What | Path | Notes |
|---|---|---|
| Log root | `C:\Pixellot\Data\Log\` | plus an `archive\` subdir |
| Graphics log | `GraphicsManager_vpu_YYYYMMDD_HHMMSS.log` | named per day, but **appends across process restarts** — one file holds many `START NEW LOG SESSION` blocks |
| Agent log | `agent_vpu_YYYYMMDD_HHMMSS.log` | 13-15 MB/day on an idle box |
| Graphics config | `C:\Pixellot\Data\Configuration\graphics.cfg` | INI-style, same shape `Get-PixellotConfig.ps1` already parses |
| PiP config | `C:\Pixellot\Data\Configuration\PiP.cfg` | |

**Size guard is mandatory.** Idle GraphicsManager log = 713 bytes. The failing Tanque Verde
unit's was **17 MB** (inflated by a Sportzcast reconnect storm). Read the tail, never the file.

## 2. The healthy baseline — and why "servers are up" proves nothing

vpu-home's GraphicsManager starts clean every boot, line-for-line matching what the *failing*
603b752c logged after its restart:

```
Starting graphics overlay server
Starting http server
Graphics overlay server started
Starting Graphics Events Server grpcAddress=127.0.0.1:61014
ScoreProviderWatcher created maxSleepTime=5m0s minSleepTime=5s
Serving gRPC grpcAddress=127.0.0.1:61014
recoverLiveEventsFromBackup | No events to recover from event queue
Successfully started Graphics Events Server port=61014
```

So a healthy startup block is **not** a health signal. The only positive signature is
`Successfully sent graphics client URL to VPU`; its absence, with
`Failed to send graphics client` climbing, is the fault. One failure per event is normal
(CEF takes ~6 s against a 5 s client deadline). Hundreds is not.

## 3. Benign-on-idle error — do not report it

A healthy idle box logs this at every start:

```
ERROR | graphicseventsserver.go(1149) | recoverScoreProviderFromBackup |
Failed to read score provider backup file backupPath=C:\Pixellot\Data\scoreProvider.txt
```

vpu-home is fully healthy and logs it on every boot. Any "GraphicsManager has ERRORs" rule
would fire on every unit in the fleet. Excluded.

## 4. Idle state is NOT_EVALUATED, not FAIL

With no event running, **nothing** listens on 1402 (Sportzcast), 5000 (ScoreConnect), 1888
(graphics client), 8081 (LGEP) or 49741 (overlay). The gRPC map is also different: idle,
`Coordinator.exe` owns 61003/61004/61007/61017 and `graphicsmanager.exe` owns its overlay
listener; `VPU.exe` isn't even running, so **61011 does not exist between events**.

Consequence: every reachability check in this lane must report NOT_EVALUATED when no event is
registered. A lane that tests these ports on an idle box would fail every VPU in the fleet.

## 5. Config findings available with no event at all

vpu-home's own `graphics.cfg` is a live positive specimen for three findings:

| Key | vpu-home value | Finding |
|---|---|---|
| `GRAPHICS_MODE_ON_INIT` | `LOGOS_ONLY` | **no scorebug is drawn at all** — silent "why is there no score on my broadcast" |
| `VENUE_ID` | `YOUR_VENUE_ID` | literal placeholder = venue never provisioned |
| `TYPE` | `OCR` | configured scoreboard source; cross-check against what's actually reachable |
| `BOT_NUMBER` | `02130` | authoritative bot number — cross-check SC III's, which is documented as stale |
| `[SINGULAR] REMOTE_PIXELLOT_FILE_URL` | `graphics-clients-**stage**.pixellot.tv` | staging asset host on a production box |
| `[SINGULAR] GRAPHICS_APP_ID` | empty | |
| `HOME_TEAM` / `AWAY_TEAM` | `Garretson` / `B/E HS` | stale team names from a previous venue |

### Parsing gotcha — `//` in values

The file stores URLs with doubled slashes so its own `//` comment convention survives:

```
HTML_GRAPHICS_URL, string, http:////127.0.0.1:1888/graphicsClient.html?master=1
LGEP_ADDRESS, string, http:////127.0.0.1:8081
```

A naive comment strip on `//` truncates `http://` to `http:`. Strip a comment only when `//`
is preceded by whitespace, then collapse `////` to `//` in the value.

### The cfg files are never migrated on upgrade — key presence is NOT a version signal

vpu-home went 5.27.6 -> 5.37.1 and **`graphics.cfg` and `PiP.cfg` both still carry an
mtime of 2021-01-26**. The upgrade rewrote neither. So:

- `PiP.cfg` has `DECODER_TYPE, string, QSV` and **no** `IS_AUTO_OCR_TO_FULL_PIP_FALLBACK` /
  `FULL_PIP_AUTO_FALLBACK_GRACE_TIME_SEC` (those were read on VPU2).
- `graphics.cfg` has **no** `/GENERAL/GraphicEngineType` and no `DISABLE_GRAPHICS_PROXY`,
  on GA 5.37.1.

An earlier read of these as "5.37-only keys" was wrong — presence reflects when the file was
last written, not the venue version. Never infer version from key presence; absent stays
NOT_EVALUATED.

**This makes vpu-home a candidate reproduction box.** On GA 5.37.1 its config shape matches
the three FAILING Tanque Verde units (no `GraphicEngineType`) and differs from the working
control `5fb394c2`, which has it. If vpu-home runs an event with graphics and fails the same
way, the leading hypothesis (GraphicsManager's VPU gRPC target resolving empty) gets a bench
repro instead of four bundles.

## 6. PiP watchdog-kill detection is implementable

The agent log carries both halves of the PiP keep-alive bug on 5.27.6, with no event needed to
confirm the format (35 and 47 hits respectively on an idle day):

```
Info | PiP_WatchdogTiming | WatchdogMonitor.cs(387) | WatchdogShouldBeActive |
      WatchdogShouldBeActive - GetKeepStandAloneApplicationUp False
Info | Initializer | DotNetUtilities.cs(1306) | Set |
      setting param _keepStandAloneApplicationUp PiP to True
Info | Initializer | ApplicationManager.cs(823) | AppProcessIsRunning |
      PiP ProcessIsRunning: False. Found by: name
```

Tab-separated, `|`-delimited fields. So Pulse can reconstruct keep-alive flag state per app and
whether PiP is running — the frozen/black-PiP signature — from the agent log alone.

## 7. Dynamic-port-range gap (fleet image, read-only check)

```
netsh int ipv4 show dynamicport tcp   -> Start 49152, 16384 ports  (49152-65535)
netsh int ipv4 show excludedportrange -> 5357, 9001, 32323, 42424 only
```

Pixellot's gRPC ports **61001-61019 sit inside the ephemeral range with no reservation**, as
does graphicsmanager's overlay listener (49846 on vpu-home). Any process making outbound
connections can be handed one before Pixellot binds it. This was *not* the cause at Tanque
Verde (PID 9456 there was genuinely `C:\Pixellot\Bin\VPU.exe`), but the missing reservation is
a real fleet-image fragility and costs one read-only command to report.

## 8. Binary version quirk

`graphicsmanager.exe` and `PiP.exe` carry **no FileVersion** (blank); `VPU.exe` reports
`5.27.6`. A "graphics stack present + version" card must read VPU.exe, not the graphics
binaries.

---

## What vpu-home cannot validate

It has never run an event, so the failing state itself can't be reproduced there: no
`RegisterEvent` / `DisableChuPip` lines, no `SendGraphicsInfo`, no live listeners. Those
assertions stay grounded in the four Tanque Verde bundles (A 603df7cb 9/14, B 603b752c 9/14,
C 603b752c 9/12, D 5fb394c2 9/08 working control). vpu-home validates collection paths, log
formats, config keys and PS 5.1 behavior — which is what the collector needs.

Related: `PLAN-scoreboard-self-healing.md` (VPU2 config discovery), memory
`project-pip-killed-on-overlapping-events`, `project-scoreboard-cg-parser`.
