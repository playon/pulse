# Pulse — Pixellot VPU Diagnostic Tool

Diagnostic tools for Pixellot VPU field support. Covers camera-NIC and cable
health, network connectivity, Pixellot services, system overview
hardware/peripherals, disk health, audio, the Windows event log, and a Reports
panel with support bundles — all live, with plain-language next-step guidance
and per-panel Recommended Actions. Pulse also **updates itself in place**, can
**share a diagnostic snapshot to another Pulse over the LAN**, and includes a
guided **Fault Isolator** wizard that pinpoints a camera fault to the NIC port,
cable, or camera.

**Pulse.Web** (`Pulse.Web/`) is the active product — a self-contained,
browser-based diagnostic tool (Python + vanilla JS). No Node.js, npm, or
.NET required; double-click a launcher and it bootstraps everything.

> `Pulse.WPF/` (the original C#/WPF desktop app) is **deprecated** in favor of
> Pulse.Web. Its source remains for reference but is no longer built or shipped.

## Install on a VPU

One launcher per channel — drop it on the VPU (or, after the first run, launch
from the **Start Menu**: press **Win**, type "pulse", Enter). Each self-elevates
(UAC), installs to `C:\Pulse`, adds a Start Menu entry, and auto-updates every
launch.

| Launcher | Channel | Pulls |
|---|---|---|
| [`run_pulse.bat`](https://raw.githubusercontent.com/playon/pulse/main/runners/run_pulse.bat) | **Production** | latest `web-v*` release |
| [`run_pulse_dev.bat`](https://raw.githubusercontent.com/playon/pulse/main/runners/run_pulse_dev.bat) | **Dev** | latest commit on the `dev` branch |

Both install to `C:\Pulse` (one channel at a time), so run the launcher for the
channel you want. Field VPUs use **`run_pulse.bat`**; internal testing and
field validation use **`run_pulse_dev.bat`**. Once installed, Pulse can update
itself from **Settings → Check for Update** (no need to re-run the launcher).

The beta channel was retired on 2026-09-21 — validation happens on `dev`, whose
launcher tracks the branch tip.

On first launch, the embedded `run.bat`:
1. Downloads embedded Python 3.12.8 from python.org
2. Installs pip and dependencies (FastAPI, Uvicorn)
3. Starts the server at **http://localhost:8765**
4. Opens the browser automatically

Subsequent launches skip the Python setup and start in seconds. Falls back to a
cached version if the VPU is offline.

### How it works

```
Pulse.Web/
├── run.bat                  — Windows launcher (bootstraps embedded Python)
├── VERSION                  — semver source of truth for the build
├── CHANGELOG.md             — per-release "what's new" (shown on update)
├── app/
│   ├── main.py              — FastAPI server (REST + WebSocket)
│   ├── powershell.py        — async PowerShell subprocess runner
│   ├── demo_data.py         — synthetic data for non-Windows demo mode
│   ├── requirements.txt     — fastapi, uvicorn
│   └── static/
│       ├── index.html       — SPA shell
│       ├── app.js           — client-side hash router + page renderers
│       ├── tailwind-min.css — self-hosted Tailwind utilities (no CDN)
│       └── style.css        — dark theme styles
└── scripts/                 — 40+ PowerShell scripts: data collection (Get-*),
                               connectivity tests (Test-*), and actions
                               (Restart-*, Install-*, Set-*, Invoke-*)
```

The backend runs PowerShell scripts to collect WMI/CIM data and returns JSON
over REST + WebSocket. The frontend is a vanilla JS single-page app with hash
routing — **no build step, no bundler, no CDN dependencies.**

### Pages

| Page | Description |
|------|-------------|
| Dashboard | Live CPU / Memory / Disk / Temp gauges, VPU identity, prioritized findings |
| Network | IP config, internet reachability, DNS, port + domain tests, NTP |
| Camera Connectivity | Camera-NIC ports, link/speed, Pixellot camera + OCR detection; launches the Fault Isolator |
| Score Connect | ScoreConnect service + scoreboard-camera checks |
| Audio | Audio device detection, signal, and volume |
| System Overview | OS, CPU, RAM, GPU, disks, installed software, Pixellot version compatibility |
| Pixellot Services | Pixellot service status with restart controls |
| Disk & System Health | Logical/physical disks, disk events, Pixellot directory sizes |
| Event Viewer | Filterable Windows event log (hours, severity) |
| Reports | Full diagnostic JSON export / support bundle |
| Share over LAN | Send or receive a diagnostic snapshot to another Pulse on the same network |
| Settings | ScoreConnect URL, poll interval, Check for Update |
| About | Version and technology info |

The **Fault Isolator** (opened from Camera Connectivity) is a guided swap-test
wizard — **Baseline → NIC Port → Cable → Camera → Verdict** — that isolates a
camera fault to the NIC port, the cable, or the camera (CHU).

### Run on macOS (demo mode)

On non-Windows systems Pulse runs in **demo mode** with synthetic data (the
PowerShell scripts are stubbed via `demo_data.py`). Useful for UI development.

```bash
brew install python3
pip3 install fastapi 'uvicorn[standard]'
cd Pulse.Web/app
python3 main.py
```

Then open **http://localhost:8765** in your browser.

### Requirements

- **VPU (production):** Windows 10+ (for PowerShell + WMI), internet on first run
- **macOS/Linux (dev):** Python 3.10+, pip

## Release channels

Code flows **`dev` → `main`**, each with its own release channel and launcher
(above). Versions follow semver — the source of truth is `Pulse.Web/VERSION`,
and the per-release "what's new" notes (shown by the in-app **Check for
Update**) live in `Pulse.Web/CHANGELOG.md`. Pushing a production tag (`web-v*`)
builds and publishes the release the launcher pulls; `dev` auto-tags on push.

The `beta` branch is frozen rather than deleted — testers' share-once launcher
fetches from a URL on that branch, so removing it would break them. See
`CLAUDE.md`.

---

## Pulse WPF (Desktop) — deprecated

The original C#/WPF desktop app lives under `Pulse.WPF/`. It is **no longer
built, shipped, or supported** — Pulse.Web replaced it. The source is kept for
reference and history; its CI and channel launchers have been removed. Don't
build on it without first deciding to revive the line.
