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
