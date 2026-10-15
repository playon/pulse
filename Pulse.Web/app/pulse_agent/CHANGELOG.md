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

## [0.1.0] - 2026-10-15

### Added
- The agent has its own version. Every check-in it posts (full report,
  heartbeat, paused line and in-event posts) carries `agentVersion`, beside
  `pulseVersion`. A Pulse Diagnostics launch check-in doesn't carry it.

### Changed
- The monitor, its check-in queue and the telemetry builder moved from
  `Pulse.Web/app` into `Pulse.Web/app/pulse_agent`. What the agent collects
  and posts is unchanged.
