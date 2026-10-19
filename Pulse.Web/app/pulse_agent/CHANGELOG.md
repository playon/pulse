# Pulse fleet agent — Changelog

Changes to the fleet agent: the scheduled monitor, its check-in and its
`pulse.telemetry/v1` report. Newest first. Versions track
`Pulse.Web/app/pulse_agent/VERSION`, not `Pulse.Web/VERSION`: the agent
versions on its own so the fleet can be pinned to an agent build (PV-49).

**How this is maintained:**
- Any change that alters what the agent collects, decides or posts goes under
  `## [Unreleased]`, written for whoever reads Pulse Vitals. That includes an
  engine change in `main.py` (collectors, findings, readiness), which still
  ships inside the agent.
- Bump `VERSION` when you cut an agent release. A released version's files
  never change.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- The check-in carries what Vitals' unit tabs show (PV-65 to PV-76). Each part
  is null when its read failed, never a healthy-looking default.
  - `cameras.nic`: the camera card's chip, its family name (`GIE74 series`,
    `GIE64 series`, `GIE74P-AN`, or null for a chip Pulse doesn't know), its
    port count, whether it can report PoE, and `poe`: the card's budget,
    temperature, the Molex flag and each port's volts, amps and watts. Only an
    I210/I211 card loads SmartPoE.dll, at most once an hour, behind the
    collector's crash sentinel.
  - `power`: pending reboot, BIOS After Power Loss, when the device-install
    reboot task last ran, and up to 20 restarts and shutdowns from the last 7
    days (time, planned or unexpected, by Pulse or not, source, reason). No
    process path, user, comment or message: they carry the computer name.
  - `hardware.volumes` (free space per fixed disk), each `hardware.disks[]`
    drive's health, wear, power-on hours and uncorrected errors, and
    `hardware.predictFailure`.
  - `services` (each streaming component's state) beside `servicesDown`, and
    `applications` (installed software, Pixellot first) with
    `applicationsTotal`.
  - `programs`: whether VPU.exe, Agent.exe and Coordinator.exe can start, by the
    rule the pixellot-dll-missing and pixellot-start-error blockers use.
  - `environment`: Windows name, build and patch level, the time zone and
    whether it is a US one (the tz-non-us rule), and clock drift.
- The monitor reads the Windows patch level (6 h cache), clock drift (1 h
  cache) and PoE (1 h cache) on full passes.

### Changed
- Readings that move on every read no longer post a full check-in by
  themselves: clock drift counts in whole seconds, disk space in whole percent,
  PoE as each port on or off, and power-on hours not at all. Each post still
  carries the exact values.
- A telemetry document is kept under 15 KB by cutting the application list,
  then the oldest restart rows, from the end. The check-in Worker drops one
  over 16 KB whole.

## [0.2.1] - 2026-10-16

### Added
- The check-in's `scoreboard` block now says more about the score source
  (PV-59). `ocr` is `{configured, issue}` for the scoreboard camera, or null
  when the adapters or the Pixellot config couldn't be read. `scoreConnect`
  carries the ScoreConnect III version, console firmware, ScoreLink model and
  port, serial port, event type and bot number, each null when unknown. It is
  null only when the ScoreConnect check itself failed or didn't run. When
  ScoreConnect III isn't answering, the block is still sent: `version` and the
  ScoreLink model and port can be set, and the rest are null. It is sent
  whichever source is in use. `firmware`, `serialPort` and `eventType` are
  unverified: not yet seen populated on a unit with live score data, and null
  when ScoreConnect III does not report them. `source` and `ok` are unchanged.
  A change in any of these posts on the next full pass.
- Each full report now carries `telemetry.calibration`: the primary sport,
  each calibrated sport with when it was calibrated (newest first, at most
  20), and whether the scoreboard (OCR) camera is calibrated. It is read from
  the Pixellot calibration folders by a new local collector,
  `Get-CalibrationStatus.ps1`; no camera is probed. The monitor keeps its
  answer for 6 hours, like the hardware inventory, so most passes start no
  PowerShell for it. A recalibration shows up within 6 hours; an unchanged
  unit posts nothing extra. A read that fails is retried on the next pass.
  `calibration` is null when the calibration folder can't be read, and
  `sports: []` means it was read and no sport is calibrated (PV-57).
- Telemetry carries a `hardware` block (PV-64): PC model, processor (name,
  cores, threads), memory in GB, up to 8 disks (model, size, NVMe/SSD/HDD/USB),
  up to 4 graphics cards (name, driver, memory) and the BIOS version and date.
  It reuses what the pass already collects (Get-Hardware comes from the 6 h
  cache), so a pass costs no more, and it is posted again only when it
  changes. A part that couldn't be read is null. No serial number, asset tag
  or hostname, from the BIOS or any disk.
- Get-Hardware reports a graphics card's real memory (`vramMB`, from the
  driver's registry key: WMI tops out at 4095 MB) and each disk's media type
  (`mediaType`, SSD or HDD).

### Fixed
- A unit whose Pixellot dependency folders are on its user's PATH no longer
  reads FAIL with "VPU.exe can't start because ... are missing". The DLL
  check runs as SYSTEM in the agent, and SYSTEM's user PATH is empty, so every
  DLL found only through the user's PATH read as missing (De La Salle, CA:
  22 of them, on a VPU that ran its daily test that morning). As SYSTEM it
  now also searches the PATH of each user logged in. If no user is logged in,
  the finding says that no user's PATH could be searched.

## [0.2.0] - 2026-10-15

### Added
- The agent can update itself. On a unit enrolled from Pulse Settings, the
  scheduled task runs a small runner (`agent_runner.py`) that keeps two copies
  of the agent and runs one. When fleet control pins a build, the runner
  downloads that `agent-v*` release, checks its SHA-256 against the pin and
  switches to it between events. A new build is on probation: its first tick
  posts a full report, and three clean ticks commit it. If one fails, crashes
  or hangs, the unit goes back to the build it had, and that build isn't tried
  again until the pin changes.
- Posts carry `agentUpdate` (`applied`, `failed` or `rolled-back`, with the
  version and any error) for a day after an update attempt.

### Changed
- The monitor keeps its state, queue, cache and logs in the folder the runner
  gives it (`PULSE_MONITOR_DATA`), so they outlive an update. Without one they
  stay beside the code, as before.
- Opting in installs the runner layout, and a dev launch moves a unit on the
  older layout to it. After that a dev launch no longer copies its build into
  the monitor: fleet control decides which build runs.

## [0.1.0] - 2026-10-15

### Added
- The agent has its own version. Every check-in it posts (full report,
  heartbeat, paused line and in-event posts) carries `agentVersion`, beside
  `pulseVersion`. A Pulse Diagnostics launch check-in doesn't carry it.

### Changed
- The monitor, its check-in queue and the telemetry builder moved from
  `Pulse.Web/app` into `Pulse.Web/app/pulse_agent`. What the agent collects
  and posts is unchanged.
