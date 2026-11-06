# Agent runner: checks on a real VPU (PV-85)

`Pulse.Web/tests/test_agent_runner.py` runs real ticks from real zips over local
HTTP, but on macOS or Linux. Some of what the runner does exists only on the
fleet image (Windows 10 LTSC 1809, SYSTEM, the scheduled task, antivirus, the
embedded Python). No automated test covers these. Before the first fleet pin
of a release, and after any change to `pulse_agent/runner.py`, go through this
list on one dev VPU and record the result in the PV ticket.

`tools/vpu-smoke/` is the collector sweep. It does not test the runner.

## Setup

1. Enroll the VPU from Settings on a dev build that has the runner change.
2. Confirm `C:\PulseFleetMonitor\agent_runner.py` is the new runner and the next
   check-in reports `telemetry.runnerVersion` (Vitals, or `unit_latest` /
   `checkins.telemetry`).
3. Keep `C:\PulseFleetMonitor\agent-runner.log` and `agent-slots.json` open in a
   second window to watch them.

## Checks

| # | Check | How | Pass |
|---|---|---|---|
| 1 | Embedded Python runs the runner | Wait for one scheduled tick. | `agent-runner.log` has no `runner error`; a check-in arrives. |
| 2 | A tick over time is killed with its children (`taskkill /T`) | Temporarily set `TICK_TIMEOUT_SECONDS = 20` in `agent_runner.py`, add a long `Start-Sleep` to a collector in the active slot, and run the task. | After the tick, no `powershell.exe` started by the tick is left (`Get-CimInstance Win32_Process` by ParentProcessId). Restore both files. |
| 3 | The task's 5-minute limit stops a slow download, and the try still counts | Pin a build on a unit whose link you throttle (or point the hosts file at a slow mirror), so the download can't finish. | `agent-slots.json` shows `tries` going 1, 2, … before each download. After five, `agentUpdate.error` starts "gave up after 5 failed tries". |
| 4 | A rename blocked by antivirus or an open file leaves a whole slot | During an update, hold a file in the other slot open (`notepad slots\b\app\main.py`) or let Defender scan it. | The update fails and is retried later; `slots\b` is whole (the old build or the new one, never half); the next tick sweeps `slots\b.new` / `slots\b.old`. |
| 5 | Rollback finishes inside the 5-minute limit | Pin a build whose `monitor_once.py` exits 1. | The next tick rolls back (`agentUpdate.status` `rolled-back`); the task never shows "terminated" for that run in Task Scheduler history. |
| 6 | No update or forced pass during an event | Start VPU.exe (or a test event), then pin a new build. | No download until VPU.exe exits. If an event starts during a download, the build waits in the other slot and is switched to after the event. |
| 7 | Enrol hash | Enroll from exactly a released build's tree, then pin that release. | No download: `agent-runner.log` shows no `downloading`. |

## Recording

Write the VPU, the build, the date and a pass or fail for each row in the PV
ticket. A failure blocks the fleet pin.
