# How to Use Pulse

**Pulse** is a Pixellot VPU diagnostic tool. It runs in your web browser and tells you what's wrong with a VPU at a glance — no guesswork, no manual log digging, no memorizing PowerShell commands.

This guide has two parts:

- **Part 1: Everyday Use** — what every tester needs to know to start using Pulse.
- **Part 2: Advanced Reference** — for techs who want to understand what's happening under the hood.

If you only have 5 minutes, read Part 1 and the **Common Scenarios** section.

---

## Part 1: Everyday Use

### What Pulse does

When something is wrong with a VPU — a stream won't go live, a camera is offline, the score isn't showing up — Pulse runs a battery of checks against the unit and shows you:

- **What's broken** (findings, color-coded by severity)
- **Where to look** (the relevant tab to drill in)
- **How to fix it** (recommendations and one-click actions)

Pulse runs *on* the VPU itself. You access it through Chrome on the VPU, or remotely via LogMeIn / RDP.

### Launching Pulse

You'll get one of these `.bat` files from the team:

| File | When to use it |
|------|----------------|
| `run_pulse.bat` | Production. Stable, validated builds. Use this 95% of the time. |
| `run_pulse_beta.bat` | Beta testing. What you'll be running during this test program. |
| `run_pulse_dev.bat` | Bleeding-edge dev builds (latest `dev` commit). Only use if asked. |

**Steps:**

1. Copy the `.bat` file to the VPU (Desktop is fine).
2. Double-click it.
3. A black console window opens showing the PULSE logo and a series of `[INFO]` lines as it sets itself up. **Leave that window open** — it's the server.
4. Chrome opens automatically to `http://localhost:8765` after about 5–10 seconds.

**The first launch takes longer** (1–2 minutes). Pulse downloads its own private copy of Python so it doesn't interfere with anything else on the VPU. Subsequent launches are nearly instant.

**If the console closes immediately:** copy down what's on screen (a screenshot is best) and send it to the team — that's a Pulse bug, not a VPU problem.

### The loading screen

When Pulse first opens you'll see the Pulse logo and a progress bar. This is the tool talking to the VPU to pull every diagnostic at once.

- Bar fills 0% → 100%
- The line under the logo tells you which area is being checked (Network, Camera Connectivity, etc.)
- The whole thing usually takes 5–15 seconds. On a struggling VPU it can take 30+

**Don't click around while this is loading.** Let it finish. You'll get a complete picture instead of half-loaded data.

### The Dashboard at a glance

Once loaded, the **Dashboard** is the home page. It's a summary view designed to answer "is this VPU healthy?" in five seconds.

What you'll see, top to bottom:

| Section | What it tells you |
|---------|---------------|
| **Command Center** | Overall health: "All Clear", "1 Warning", "2 Critical" |
| **Top Findings** | Up to 3 most important issues, clickable to drill in |
| **Subsystems** | Six tiles (System / Network / Cameras / Services / Disk / Events) each colored by health |
| **Active Findings** | Full list of issues if there are more than 3 |
| **VPU Identity** | Which VPU this is — model, hostname, serial |
| **Pixellot Software** | Installed version + image version |
| **System Status** | CPU, Memory, Disk, Temperature gauges + Uptime and Internet |
| **NIC Connections** | Live view of the 4 network ports and what's plugged into each |
| **Network** | IP, gateway, DNS, NTP at a glance |
| **Storage** | Disk usage per drive |
| **Pixellot Services** | Are the Pixellot services (Agent, Encoder, Watchdog) running? |

### Reading the colors

Pulse uses three colors consistently across the whole tool:

| Color | Meaning |
|-------|---------|
| **Green** | Healthy / passing / OK |
| **Amber / Yellow** | Warning — something is off but the VPU is still working |
| **Red** | Critical — actively broken or about to break |

A green dashboard with "All Clear" means the VPU is in good shape.

### "I see a problem — what do I do?"

The basic flow:

1. **Look at the Dashboard.** Findings tell you what's wrong.
2. **Click the finding.** It jumps you to the relevant tab with more detail.
3. **Read the recommendation.** Most findings include a suggested fix.
4. **Try the recommendation.** If it works, great. If not, capture a Support Bundle (top-right button) and escalate.

### The tabs

Pulse is organized by what you're investigating, not by data type. Pick the tab that matches your question.

| Tab | Use it when... |
|-----|----------------|
| **Dashboard** | First stop. Triage everything from here. |
| **Network** | The VPU can't reach the internet, NTP is drifting, DNS lookups fail, or you need to run a speed test. |
| **Camera Connectivity** | A camera is missing, the score camera isn't showing up, or a NIC port is showing the wrong speed. |
| **Score Connect** | Score data isn't appearing in the broadcast. ScoreConnect III configuration / service. |
| **Audio** | Play-by-play / announcer audio is missing or distorted. |
| **System Overview** | Need hardware details, installed software list, OS info, Pixellot version. |
| **Pixellot Services** | Agent / encoder / watchdog is stopped or crashed. |
| **Disk & System Health** | Disk is full, SMART warnings, or you need to free space. |
| **Event Viewer** | Looking for the last error or crash. Filtered to Pixellot-relevant Windows events. |
| **Reports** | Export a Support Bundle to share with engineering. |
| **Settings** | Adjust Pulse's behavior. ScoreConnect URL, poll intervals. |
| **About** | Pulse version, what it's based on, where to file bugs. |

### The buttons on the Dashboard

| Button | What it does |
|--------|--------------|
| **Run All Diagnostics** | Re-runs every check from scratch. Use this after you've made a change (restarted a service, plugged a cable) to see if it fixed things. The splash screen reappears with progress. |
| **Support Bundle** | Generates a downloadable zip with everything Pulse saw. Attach to your escalation. |
| **Refresh Dashboard** | Lightweight refresh of just the dashboard. Cheaper than Run All. |

### Common scenarios

#### "The stream won't start"

1. **Dashboard → Top Findings**. Look for anything mentioning Agent, Encoder, or Services.
2. If Agent or Encoder is **Stopped**, click into **Pixellot Services** and try the *Restart Agent + Coordinator* button.
3. If services look fine but stream still won't start, check **Network → Internet**. The VPU needs to reach the Pixellot cloud.
4. Capture a Support Bundle if you can't resolve in 2–3 minutes.

#### "A camera is missing or shows the wrong thing"

1. **Camera Connectivity** tab.
2. Look at the NIC port diagram. Each Pixellot camera should show up on a specific port with a green status.
3. A port showing "Down" with no cameras detected = unplugged cable or dead camera.
4. A port showing 100 Mbps where it should be 1 Gbps = bad cable or NIC issue.
5. The **Fault Isolator** walks you through narrowing it down step by step.

#### "Score data isn't appearing"

1. **Score Connect** tab.
2. Check that ScoreConnect III service is running.
3. Verify the configured URL matches what's expected.
4. If ScoreConnect III is healthy, the issue is more likely the OCR camera. Switch to **Camera Connectivity** and look at the OCR port.

#### "VPU feels slow"

1. **Dashboard → System Status**. Check CPU, Memory, Disk gauges.
2. CPU >90% sustained = something is running away. **System Overview → Installed Software** for context.
3. Memory >90% = restart will help. Consider a reboot.
4. Disk >90% = free space immediately. **Disk & System Health** has cleanup options.

#### "Audio is missing or distorted"

1. **Audio** tab.
2. Verify the announcer device is listed and showing signal.
3. Confirm volume levels aren't muted or set to zero.

### When to escalate

Escalate to engineering when:

- A finding is **critical (red)** and you can't resolve it
- You see **"Unsupported security software detected"** — this needs an RMA
- The VPU is reporting **hardware errors** (disk SMART warnings, temperature critical)
- Pulse itself crashes or shows incorrect data

**Before you escalate, always:**

1. Click **Support Bundle** on the Dashboard — this captures everything Pulse saw.
2. Note the **Pulse version** (bottom-left of sidebar, like `dev-1a2b3c4`).
3. Note the **VPU name and serial** (Dashboard → VPU Identity).
4. Note **what you tried** and what the result was.

---

## Part 2: Advanced Reference

This section assumes Windows admin comfort, PowerShell familiarity, and some Pulse internals knowledge.

### How Pulse works

Pulse is a small web server that runs locally on the VPU:

- **Backend:** Python 3.12 (downloaded fresh on first launch into `app/python/`), FastAPI + Uvicorn, serving on `localhost:8765`.
- **Frontend:** Vanilla JavaScript SPA. No build step, no framework — it just edits the DOM directly.
- **Data sources:** PowerShell scripts in `Pulse.Web/scripts/` that wrap WMI/CIM queries, registry reads, log parsing, and network probes. Output is JSON. Capped at 4 concurrent PowerShell processes so the VPU isn't CPU-starved.

The browser polls the backend via HTTP, plus there's a WebSocket on `/ws` that streams CPU / Memory / Disk / NIC stats every few seconds so the dashboard feels live.

### File locations on the VPU

All channels install to the same directory — **`C:\Pulse`** — one channel at a
time (the `CHANNEL` file records which). Re-running a different channel's
launcher swaps the install in place.

| Path | What it contains |
|------|------------------|
| `C:\Pulse\` | The install (whichever channel was last launched) |
| `C:\Pulse\Pulse.bat` | The launcher, self-copied here (the Start Menu shortcut points at it) |
| `C:\Pulse\app\python\` | Embedded Python (downloaded on first run) |
| `C:\Pulse\app\static\` | HTML / JS / CSS |
| `C:\Pulse\scripts\` | PowerShell scripts run for diagnostics |
| `C:\Pulse\pulse-server.log` | Server log file (truncated each launch) |
| `C:\Pulse\pulse-settings.json` | User settings (poll interval, ScoreConnect URL) |
| `C:\Pulse\VERSION` | The installed release tag / commit |
| `C:\Pulse\CHANNEL` | Which channel is installed (production / beta / dev) |

### The log panel (bottom of every page)

There's a collapsed log bar at the bottom of every Pulse page. Click the chevron or a tab to expand it.

**Script Log** — every PowerShell script Pulse runs:

```
07:23:04.103   Get-SystemIdentity.ps1   2,341ms   4.1 KB   ok      demo mode
07:23:04.198   Get-Performance.ps1        892ms   1.2 KB   ok      demo mode
07:23:09.502   Test-NetworkPorts.ps1   45,000ms          timeout   after 45s
```

Useful for figuring out *why* a tab is empty or slow. If a script consistently times out, you've found the issue.

**Server Log** — uvicorn requests, Python exceptions, app lifecycle:

```
2026-05-27 16:19:32 [INFO] pulse: Pulse Web 0.1.0-dev starting
2026-05-27 16:19:32 [INFO] uvicorn.error: Application startup complete.
2026-05-27 16:19:33 [INFO] uvicorn.access: 127.0.0.1:55432 - "GET /api/dashboard HTTP/1.1" 200
2026-05-27 16:19:33 [INFO] pulse.ps: Get-SystemIdentity.ps1 2341ms [ok] (4096B) demo mode
```

Auto-refreshes every 2 seconds while you're looking at it. Stops polling when you close the pane or switch tabs.

### Channels and version stamps

The bottom-left of the sidebar shows the installed version, like `dev-1a2b3c4` or `beta-v0.2.0`.

| Format | Channel |
|--------|---------|
| `web-v0.X.Y` | Production (main) |
| `beta-v0.X.Y` | Beta |
| `dev-<sha>` or `dev-v0.X.Y-dev-<sha>` | Dev |

To check what's actually on disk: `type %LOCALAPPDATA%\PulseWeb-beta\VERSION`.

### Forcing a fresh install

If something is misbehaving and you suspect cached / stale files:

```cmd
:: Kill any running Pulse
taskkill /IM python.exe /F
taskkill /IM pythonw.exe /F

:: Nuke the install dir
rd /s /q "C:\Pulse"

:: Re-run the launcher
run_pulse_beta.bat
```

The launcher will redownload everything from GitHub.

### Browser cache

If you see the wrong UI (old layout, missing features) after a fresh install, your browser is serving cached JS/CSS. Hard-refresh with **Ctrl + Shift + R** or **Shift + F5**.

Pulse uses cache-busting query strings tied to the boot timestamp, so this usually isn't needed — but it's the first thing to try if the UI looks stale.

### Running PowerShell scripts directly

Every diagnostic Pulse runs is a `.ps1` file in `<install_dir>\scripts\`. You can run them yourself for testing:

```powershell
cd %LOCALAPPDATA%\PulseWeb-beta\scripts
powershell -ExecutionPolicy Bypass -File Get-SystemIdentity.ps1
```

Output is always JSON. Useful for grabbing a single piece of data without firing up Pulse.

### Hidden: Windows build revision (UBR)

On the **About** tab, type `jessejessejesse` (no text box; just type it while the page is open). A modal opens showing the Windows Update Build Revision, read from:

```powershell
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR
```

Nothing in the UI points to it on purpose. It is backed by `scripts/Get-WindowsUbr.ps1` and `GET /api/system/ubr`. Why it matters: `17763` alone doesn't tell you which pktmon a unit has. `17763.253` is the unpatched 1809 RTM build, and packet capture is impossible there; a patched unit reads something like `17763.8880`. Esc or a click outside closes the modal.

### Demo mode

If you run Pulse on a non-Windows machine (Mac or Linux), it boots in **DEMO_MODE**. PowerShell calls return canned data from `app/demo_data.py` instead of erroring out. A yellow "DEMO DATA" banner appears in the sidebar so you know.

This is meant for development and screenshots, not production support. Don't use Pulse on a non-VPU and expect meaningful diagnostics.

### Manual Pixellot remediation (without Pulse)

Pulse exposes one-click versions of these, but here they are direct:

| Action | Command |
|--------|---------|
| Restart Pixellot agent + coordinator | `c:\pixellot\bin\keepagentup.exe` |
| Reinstall Pixellot dependencies | Download + run `https://software.pixellot.tv/apps/Pixellot-Installer-Dependencies-5.0.0.exe` |
| Check NTP peers | `w32tm /query /peers` |
| Check NTP status | `w32tm /query /status` |
| DNS sanity check | `nslookup www.pixellot.tv 8.8.8.8` |
| Find recent VPU errors | Search `c:\pixellot\data\log\vpu*.log` for `error`, `fatal`, `start new log` |
| Windows system file check | `sfc /scannow` |
| Windows image health | `dism /online /cleanup-image /checkhealth` |
| Windows image repair | `dism /online /cleanup-image /restorehealth` |

The PDF *Various VPU Troubleshooting Tips 2.0* is the source for all of these — keep a copy handy.

### Auto-shutdown

Pulse will shut itself down 60 seconds after the last browser tab closes. This avoids leaving an idle server running on the VPU after you finish a session.

If you want to keep it running unattended, leave a Chrome tab open pointed at `http://localhost:8765`.

### Reporting bugs

When Pulse itself is misbehaving:

1. Open the **Server Log** tab in the log panel and capture the last screen of output.
2. Open the **Script Log** tab and look for `error` or `timeout` rows.
3. Note the version from the sidebar footer.
4. Note the channel you launched from (`beta`, `dev`, etc.).
5. Click **Support Bundle** to capture the full state.

Send all four to the team along with what you were doing when it broke.

### Where to file feedback during beta

Anything you find — bugs, confusing UX, missing data, false positives — file in the team's JIRA project (PULSEDEV) or send to the team channel. Screenshots and the Support Bundle make every bug report 10x more useful.

---

## Quick reference card

Print this page and tape it to your monitor.

**Launch:** Double-click `run_pulse_beta.bat` (or Start Menu → type "pulse") → Chrome opens automatically

**Triage flow:** Dashboard → Click a finding → Read recommendation → Try fix → Run All Diagnostics

**Common fixes:**
- Service stopped → Pixellot Services tab → Restart Agent
- Camera missing → Camera Connectivity → check NIC port
- Score missing → Score Connect tab → check service + OCR camera
- Slow VPU → System Status gauges → check what's >90%
- Audio missing → Audio tab → check device + signal

**Escalation kit:**
- Support Bundle (Dashboard button)
- Pulse version (sidebar footer)
- VPU name + serial (Dashboard → VPU Identity)
- What you tried + result

**If Pulse misbehaves:**
- Hard refresh: `Ctrl + Shift + R`
- Nuke install: `rd /s /q "%LOCALAPPDATA%\PulseWeb-beta"` then re-launch

---

*Beta release · See the team channel for the latest build.*
