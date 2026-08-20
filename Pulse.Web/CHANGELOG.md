# Pulse.Web — Changelog

User-facing changes to Pulse.Web, newest first. This is the source the update
flow shows testers when a new build is available.

**How this is maintained (read before editing):**
- When you ship a change a tester would notice (feature, fix, or visible
  change), add a one-line bullet under `## [Unreleased]`, grouped under
  **Added**, **Changed**, or **Fixed**. Write it for a field tech, not a
  developer — "Fixed false low-speed warning on OCR camera ports", not the
  commit subject.
- At a beta/main promotion, rename `[Unreleased]` to the released version
  (e.g. `## [0.2.0] — 2026-06-15`) and start a fresh empty `[Unreleased]`.
  That version's section becomes the GitHub release notes the update flow
  displays.
- Dev auto-tags don't use this file — they get notes generated from commit
  messages automatically. Curate here for the builds testers and the fleet
  actually read (beta / main).

Format follows [Keep a Changelog](https://keepachangelog.com/). Versions track
`Pulse.Web/VERSION`.

## [Unreleased]

## [1.2.1] - 2026-08-20

### Added
- Network Test now checks TCP 1935, the RTMP fallback the VPU streams over when both UDP streaming ports are blocked — it's a required port, and it isn't testable in VPU Manager.
- Pulse now names the venue's web filter when it blocks Pixellot services. If the filter kills the secure connection to Singular, pixellot.tv or NFHS (a blocked-category block, not SSL inspection), the Network tab identifies the product — Linewize, Zscaler, iboss, Securly, Lightspeed, GoGuardian and others — and shows the block-page link you can send to venue IT.

### Changed
- The streaming verdict now matches how the VPU actually fails over (UDP 2088 → UDP 443 → TCP 1935): "can't broadcast" only appears when every path is blocked. Both UDP ports blocked with 1935 open now reads "Streaming is degraded — running on the emergency fallback" (games air ~4 minutes late with no loss protection), and a healthy stream with blocked backup paths shows a resiliency warning instead of a false alarm.
- Network Test: the optional SportzCast TCP 1935 tile is gone — two 1935 tiles with different results was confusing, and SportzCast connectivity is already covered by the Scorebot 1400–1405 tiles and the sportzcast.net service check.
- Stream Readiness now FAILS when a venue web filter is blocking Pixellot services. It used to report a green PASS ("game-ready") while graphics, scheduling and updates were all cut off, because the block left the certificates untouched — the wording was a vague "possible SSL inspection" note buried on the Network tab.

### Fixed
- Release notes now actually show up. The "what's new" list in Check for Update was showing install instructions instead of the changes in the build — every release on every channel had been publishing boilerplate only.

## [1.2.0] - 2026-08-17

### Added
- Disks: when the recordings drive (D:) reaches 90% full, a Storage Cleanup card can free space — it deletes daily test clips older than 90 days and game recordings older than 1 year, after showing exactly which folders (with counts and sizes) will be removed. Nothing from the last 90 days is ever touched.
- Pulse now closes itself (server and browser window) 5 minutes after the LogMeIn session that opened it ends — no more Pulse left running on the VPU after you disconnect. A banner at the top of the page shows the live countdown, and reconnecting within those 5 minutes cancels it automatically; opening Pulse at the console or over another remote tool is unaffected.
- Camera Connectivity now marks the exact port when the venue's internet cable is plugged into the camera card — a red "Internet Uplink — wrong port" tile tells you which cable to move to the motherboard network port.
- Splashtop Streamer is now removed automatically in the background — it was installed on VPUs as part of the retired Canopy deployment, alongside the Leaf agent Pulse already cleans up. Heads up: if you are connected to a VPU over Splashtop, the first Pulse launch will end that session; use LogMeIn, the supported remote tool.
- Camera Connectivity now shows live PoE power draw for each camera port — watts, volts and amps per port plus the card's total budget, free power and temperature, refreshing every few seconds. It flags a disconnected Molex power lead on the camera card (the same fault VPU Manager reports as a failed POE Power Test) and tells you to reseat it. Only the newer camera cards (Intel I210/I211) can report power; on an older 82574L card the section says so plainly instead of sitting empty.

### Changed
- Storage alerts are now critical-only: the amber "space low" warning at 80% full is gone everywhere (findings, readiness, Disks page, dashboard bars). Drives alert only when they actually matter — over 90% full — which is also the moment the Storage Cleanup card appears with the fix.
- Pulse now cleans up the retired Canopy/Leaf software automatically. The old Banyan Hills agent (no longer used by PlayOn) is uninstalled in the background the first time Pulse runs on a VPU, and the leftover C:\Banyan folder is removed — no action needed from techs.
- Splashtop Streamer is now removed automatically too — it was installed as part of the same retired Canopy deployment. Heads up: if you are connected to a VPU over Splashtop, the first Pulse launch will end that session; use LogMeIn, the supported remote tool.
- New standalone script `scripts/Get-WindowsPatchStatus.ps1`: run it on a VPU to see the real Windows patch level (build number, hotfixes, servicing history, pending reboot) even though Windows Update is disabled on the fleet image.

### Changed
- Network Test: AWS S3 (s3.amazonaws.com) is no longer tested anywhere — removed from the port, service reachability, name lookup, and secure-connection checks. It is no longer required for streaming, so a venue firewall blocking it won't show a failure anymore.
- The "Windows support ends within a year" warning now reassures instead of alarming when the VPU still has years of security updates left: it explains the unit is covered until the true end-of-servicing date (e.g. 2032 for LTSC 2021) and that no action is needed.
- The blocked-backup-streaming warning no longer says "the broadcast still works" — the title and description now just state what's blocked and what to ask venue IT to open.

### Fixed
- ScoreConnect: the scoreboard could show the wrong quarter on non-Daktronics boards — an Electro-Mech football board sitting on Q2 read as "Q7" even though the score, clock and down & distance on the same screen were all correct. Pulse now reads the quarter from its own fixed spot in the scoreboard data instead of taking the last digit it finds. It also won't show a quarter that can't be real for the sport any more: a football board reporting Q7 leaves the quarter blank rather than showing a wrong one you might pass on to a school.
- Stream Readiness now correctly reports FAIL (not WARNING) when a venue firewall is intercepting secure connections — the dashboard verdict was silently ignoring this case.
- Network: the packet capture never ran on a real VPU — it failed instantly with no result. It now runs and reports normally. (A stray dash character in the script stopped Windows from reading the file at all; it worked in testing and failed on every actual unit.)
- Cleaned up garbled punctuation in diagnostic messages on real VPUs — the ScoreConnect "software is out of date" notice and truncated camera error text were showing stray characters where a dash or "..." belonged.

## [1.1.2] - 2026-08-07

### Fixed
- Event Streaming: the page could fail to load on real VPUs when the box had recent shutdown or Pixellot process-restart history (a time-zone comparison error found during release verification).

## [1.1.1] - 2026-08-07

### Added
- Event Streaming: failed events now show what was wrong on the box while the event was running — unit off or rebooted mid-event, graphics driver faults, Pixellot service (Agent/Coordinator/KeepAgentUp) failures, or software crashes — pulled from the Windows event logs and matched to each event's time window. Also calls out "recorded but nothing uploaded" as a likely network block.
- Event Streaming: cleaner layout (named panels with icons, single-line status pills, compact evidence wording) and a clearer identity card showing the unit's full cloud name, school and pixellot keys, NFHS broadcasting status, and quality average.
- Event Streaming: units that were installed but never activated for NFHS now get a clear finding ("confirm this unit is activated in the NFHS Console") instead of an empty page, and the quality chip no longer shows a misleading 0% when no events were ever scored.

## [1.1.0] - 2026-08-05

### Added
- New "Event Streaming" page under Triage: shows this VPU's recent events as the NFHS cloud sees them — which ones streamed, which didn't, and the evidence for why (cloud camera/health indicators, whether the box recorded video locally, quality scores). Works with no login; if the school network blocks the cloud, the page says so and still shows the box's local recording history.
- When the launcher can't download Pulse, it now explains why instead of just saying "check the internet connection": it shows the actual download error, tests each GitHub server Pulse needs one by one, and prints exactly which ones the venue's network is blocking (with the allow-list to hand to the school's IT). Catches the common case where github.com opens fine in a browser but the download servers are filtered, and flags networks that intercept HTTPS. The report is also saved to a file support can ask for.
- Pulse now cleans up the retired Canopy/Leaf software automatically. The old Banyan Hills agent (no longer used by PlayOn) is uninstalled in the background the first time Pulse runs on a VPU, and the leftover C:\Banyan folder is removed — no action needed from techs.
- New standalone script `scripts/Get-WindowsPatchStatus.ps1`: run it on a VPU to see the real Windows patch level (build number, hotfixes, servicing history, pending reboot) even though Windows Update is disabled on the fleet image.

### Changed
- Status labels now look the same on every page: rounded pill shape, all-caps text (PASS, WARN, RUNNING), and count bubbles are gray instead of orange so a tally no longer looks like a warning.
- Status words now match everywhere: "Healthy" and "Attention" chips read OK and WARNING like the rest of the app, and ScoreConnect's cloud link shows CONNECTED / NOT CONNECTED instead of Yes / No.
- Network Test: port tiles now use the same PASS / FAIL pills as the service list next to them, and the ? icon sits right after the port number where it's easier to spot.
- Camera Connectivity: port cards now show link state as the same style of pill (LINKED / DEGRADED / NO LINK) used across the app, always in the top-right corner of the card; the camera role label (OCR / MAIN CAMERA) sits on its own line below the port number.
### Fixed
- Every bit of text in Pulse is now readable in both light and dark mode, checked page by page including the sidebar. Faint grey text (log timestamps, the small print under the dashboard gauges, card headings like FINDINGS and VPU IDENTITY, and the sidebar's group labels like TRIAGE and TROUBLESHOOTING) was washed out against the background — worst on a laptop screen in daylight. The coloured status words were the other half of it: PASS / FAIL / WARNING chips, the red [CRITICAL] tags, the amber WARNING pills, the teal MAIN CAMERA badge and the highlighted sidebar item were all too pale against their backgrounds, especially where a chip sat inside an already-tinted row.
- The scoreboard's LIVE / STALE / NO SIGNAL indicator was nearly invisible in light mode — it was using the light theme's dark green on the near-black scoreboard. The scoreboard now keeps its own colours in both modes, so it reads the same whichever mode you're in. Team names and the raw-data label on the scoreboard are clearer too.
- The loading screen no longer says "this can take a moment" after it has already finished; it now reads "All checks complete." on the last frame.
- A Pulse run from a source checkout no longer reports itself as the latest production release — it now shows the version it actually is.
- Stream Readiness now reports FAIL when the venue firewall is intercepting secure connections (SSL inspection). It used to read WARNING — "will likely stream" — on a VPU whose graphics, uploads and Pixellot updates were all cut off. The finding text no longer suggests video keeps streaming either; it says plainly not to expect a clean broadcast until venue IT exempts the domains from decryption.
- Pulse now actually exits a minute after the last browser tab closes, as designed — a hidden crash in the shutdown step had been leaving the server running in the background until reboot.
- Network Test no longer shows a wall of false "blocked (TCP/443)" warnings right after Pulse opens. On slower VPUs the checks could time out while Pulse was still busy collecting data, making a healthy network look blocked; any check that fails now gets an automatic second attempt once the rush is over.
- The dashboard no longer warns "CPU usage elevated" just because Pulse itself was busy collecting data at that moment. An elevated reading is now double-checked with a follow-up sample before the warning shows.
- Uptime no longer shows an extra day (a VPU up 16 hours used to read "1d 16h").
- The Z4SF-5 main camera head is now recognized by name on Camera Connectivity instead of showing as a generic "IP Camera".
- Launcher no longer needs a second run when Chrome starts but no window appears (typically the first Chrome start after it self-updated): Pulse now waits until a Chrome window is actually visible and relaunches Chrome itself if one doesn't show up.
- Camera Connectivity heading no longer reads "1 finding need attention" when there is a single finding.
- Network Test: the port tiles and service ? icons now show a clear "If blocked on the school's network" pop-up on hover, tap, or keyboard focus (the old tooltips were slow and easy to miss), each column explains what the pop-ups are for, and a failed service now shows what it breaks right on the row — so it's in the screenshot you send to school IT.
- Network Test: port tiles now carry the same ? icon as the service rows, so it's obvious each tile has an impact pop-up.

### Removed
- Network Test no longer checks the retired leaf-uploads/leaf-downloads addresses (old Canopy buckets) — schools don't need to allow them anymore.
- **Share over LAN is hidden for now.** The tab is removed from the sidebar while the feature is on hold — use Exports to download reports instead.

## [1.0.5] - 2026-08-04

### Added
- ScoreConnect: new "Previous Configurations" panel. Pulse now remembers each scoreboard setup this VPU has run (vendor, sport, connection type, bot number, ScoreLink) — recorded only while scoreboard data is confirmed flowing — so after a reconfigure or bot reassignment you can see exactly what it was set to before, and when it changed.

## [1.0.4] - 2026-08-03

### Fixed
- Network Test: the Wired Ports table now lists the motherboard uplink first, then the camera ports in order — the uplink no longer appears in the middle of the camera NIC's four ports.

## [1.0.3] - 2026-07-31

### Changed
- Sidebar: Audio now sits above Service Status under Troubleshooting.

## [1.0.2] - 2026-07-28

### Fixed
- The dashboard no longer shows a false "No main cameras detected" alarm (or a false "port running slow" warning on the scoreboard camera port) in the first minute after Pulse starts. Camera detection now asks the cameras directly instead of trusting a network cache that can be empty right after launch — cameras that are genuinely unplugged still alarm immediately.

## [1.0.1] - 2026-07-20

### Fixed
- **The disk-space alert now checks each drive separately.** A nearly full C:
  or D: used to hide behind the combined free space of all drives, so the
  "disk almost full" warning never appeared on VPUs with a large recordings
  drive. Each drive is now checked on its own, and the alert says which drive
  is full and what to do — free up the system drive (C:) or clear old
  recordings (D:).

## [1.0.0] - 2026-07-17

### Added
- **The Network tab now catches firewalls that intercept secure traffic (SSL
  inspection).** When a school firewall decrypts HTTPS and swaps in its own
  certificate — the "video streams but graphics never load" failure — Pulse
  now names the intercepting device, lists exactly which domains are affected
  (including the full singular.live family the graphics run on), and spells
  out the fix for the district's IT team: exempt the domains from SSL
  decryption, a URL allowlist is not enough. Shows on the Dashboard, the
  Network tab, and in exported reports.
- **The Audio tab is back.** Audio device diagnostics — inputs, outputs,
  volume, and live signal activity — are available again under
  Troubleshooting while we continue building the lane out.
- **Camera Frames now spots a black picture and tells you why.** When a camera
  grabs a frame but the picture comes back black (the OCR/scoreboard symptom),
  Pulse flags it as "Black picture" instead of a green "Active", explains it in
  plain terms — usually the camera darkening everything to cope with a bright
  scoreboard, or its picture set too dark — and notes when the other cameras
  prove the room lights are on, so you know it's a camera setting, not the venue.
- **The installer now explains itself when a school firewall breaks the
  download.** If the first-run Python/pip download fails because the network is
  intercepting secure connections (SSL inspection substituting certificates),
  the install window now says exactly that — naming the intercepting device and
  telling the venue's IT team which domains to exempt from SSL decryption —
  instead of a cryptic certificate error.

### Changed
- **The startup screen now shows what Pulse is checking.** As Pulse loads it
  lists each diagnostic and ticks it off in a fixed top-to-bottom order, with
  an "X of 12 systems" counter and a note that the full sweep can take a
  moment — so a slower first load reads as steady progress, not a hang. If a
  critical or warning issue is detected it's flagged right on the loading
  screen, and on a genuinely slow unit the note switches to a "still working"
  message instead of looking stuck.
- **Service Status now lists Pixellot programs and Windows services in separate
  areas.** The tab is split into "Pixellot Core Processes" (Agent, Coordinator,
  VPU, and the KeepAgentUp watchdog) and "Windows Services" (ScoreConnect,
  LogMeIn), so it's clear at a glance which is a background program and which is
  a Windows service — and a service that's missing no longer reads like a
  stopped program.
- **The Secure Connections check moved under Advanced Diagnostics.** On the
  Network Test tab it now lives inside the collapsible Advanced Diagnostics
  section instead of taking a full panel at the top of the page; any
  intercepted or failing service still surfaces in the findings banner.
- **Audio signal meters now move in near real time.** Meter readings were
  stuck behind a 25-second cache and a per-poll compile step; levels now
  refresh about every 2 seconds, and repeated volume changes always take
  effect instead of being skipped.
- **The Audio tab shows only devices that matter.** The main lists now show
  just the active input and output devices; unplugged or disabled hardware
  sits in a collapsed "inactive devices" list, and devices Windows merely
  remembers from the past (often dozens on a long-lived VPU) are hidden
  entirely.
- **Removed the duplicate "Restart Agent + Coordinator" button from the Pixellot
  Software tab.** The same action lives on the Service Status tab; it now appears
  in just one place.
- Settings now puts "Restart Pulse App" and "Reboot VPU" in separate panels, so
  the low-risk app restart isn't visually grouped with the full Windows reboot.
- **Pulse now keeps its installer tooling current.** Each launch quietly
  updates the bundled Python's package installer (pip) so upstream security
  fixes arrive on their own — skipped harmlessly when the VPU is offline.

### Removed
- Dropped the redundant "Network Errors (this adapter)" counters from the
  Internet Adapter card on the Network Test page. The same RX/TX error and
  discard counts are already shown per port under Wired Ports.

### Fixed
- **The Secure Connections check no longer reports false failures on VPUs.**
  The TLS test was offering only an outdated protocol version (TLS 1.0) that
  most services reject, so 8 of its 11 checks failed on real hardware even on
  a healthy network; it now negotiates TLS 1.2 and passes cleanly.
- **The Audio tab now reads real device info on VPUs.** It was silently
  falling back to a limited view (no volume, mute, or signal meters) on
  every real VPU; devices now show live levels, volume control works, and
  the Windows default recording/playback device is marked with a "Default"
  badge.
- **"Restart Agent + Coordinator" now says when nothing was restarted.** On
  most VPUs the keepagentup watchdog is already running, so the restart
  command exits without doing anything; Pulse now shows an amber "Not
  restarted — watchdog already running" notice instead of a green Success,
  and the agent/coordinator status lines recognize them running as bare
  processes instead of reporting "NotFound".
- **The loading screen no longer freezes when a partner service is down.**
  Port checks probed each internet service one at a time, so a few
  unreachable servers (e.g. a Sportzcast outage) could stall the startup
  checklist for 20+ seconds; all services are now probed at once, and the
  port sweep no longer runs twice on every startup.
- **The startup checklist now ticks through every check steadily.** Quick
  checks appear first and the Dashboard summary last, matching how fast each
  one really finishes; previously the list could sit idle and then flash all
  twelve checks in one instant.
- **The System tab now lists all installed software.** On real VPUs the list
  collapsed to a single program; the full inventory (with publisher and
  install date) now comes through.
- **Check for Update works on dev builds and reports failures honestly.** Dev
  builds now publish releases for the updater to find, and when no release
  exists for a channel the message says so instead of blaming the VPU's
  internet connection.
- **ScoreConnect no longer shows "Not Found" on Service Status when it's
  actually running.** Newer ScoreConnect (III) registers under a different
  Windows service name; the tab now detects ScoreConnect I, II, or III, shows
  its real status, and its Restart button works for every version.

## [0.4.3] - 2026-06-30

### Fixed
- **Pulse no longer needs two launches to open on a freshly set-up VPU.** On a
  new unit the first launch would start the server, say "Pulse is running," and
  close — but no browser window appeared, so you had to run it again. The cold
  Chrome profile was eating the first open; Pulse now opens straight to the page
  on the first try.
- **ScoreConnect tab no longer shows "Failed to load data" on VPUs running an
  older ScoreConnect.** On a unit running ScoreConnect I or II (not III) — for
  example one with several versions installed — the tab failed outright instead
  of showing the version it found. It now displays the detected ScoreConnect I/II
  configuration, and a genuine probe failure shows the real reason rather than
  the generic message.

## [0.4.2] - 2026-06-24

### Fixed
- **ScoreConnect tab no longer shows an "Invalid JSON" error on some VPUs.** The
  scoreboard's raw data feed — and bot numbers read from older ScoreConnect logs
  — can carry hidden control characters that broke the data hand-off, so the tab
  failed with a raw `Invalid JSON from Get-ScoreConnectStatus.ps1` message and no
  data. Pulse now handles those characters, so the ScoreConnect tab loads
  normally.
- **No more "Missing Shortcut" when opening Pulse from the Start menu.** The
  launcher now repairs its own Start-menu target on every launch and won't
  leave a dead shortcut behind if a step fails — search "pulse" and hit Enter
  and it just opens.
- **Peripherals panel on the Environment tab no longer hangs on "Loading…".**
  On a real VPU with a single mouse or keyboard the panel would spin forever; it
  now shows the connected mouse, keyboard, and monitor (with device names).

## [0.4.1] - 2026-06-23

### Fixed
- **Camera Frames now works with cameras that use a different stream path.**
  Some cameras serve their video on a different RTSP path than the usual one,
  so Camera Frames showed "No frame" even though the camera was online and
  viewable in a browser. Pulse now tries the common stream paths and uses
  whichever one the camera answers on, and when none work it lists the paths it
  tried so the camera can be flagged.

## [0.4.0] - 2026-06-23

### Added
- **New "Inspection Report" tab (under Triage) — the fleet-audit fields on one screen.**
  Pools the details you'd otherwise hunt for across the Hardware, Network, Camera and
  ScoreConnect tabs — LMI name, camera type, OS / VPU type, the uplink's IP, MAC,
  static-vs-DHCP, subnet mask and gateway, the network port test with an overall
  Pass/Warning/Fail result, the scoreboard's sport / vendor / ScoreLink status, and a
  live frame grab from every connected camera. Unlike the Camera tab, it captures
  frames even while the VPU is recording. Built for working through a large fleet audit
  one VPU at a time.
- **New "Power Events" tab — see why a VPU restarted, and whether one is pending.**
  Under System Information, Power Events shows the recent restart/shutdown history
  with the cause of each (planned vs. unexpected, who triggered it, and the
  reason), plus an up-front "reboot pending" banner and uptime. Reboots Pulse
  itself triggered are clearly labeled, so you can tell at a glance that an
  "unprovoked" restart came from Windows, a driver install, or an update — not
  from Pulse. Answers the "the box rebooted on its own" ticket in one click.
- **Pulse now catches the internet being plugged into a camera port.** On a VPU
  the internet/venue cable must go to the motherboard network port — the 4-port
  NIC is cameras-only. If the uplink is found on a camera-NIC port instead,
  Pulse raises a CRITICAL with the fix (move the cable to the motherboard port,
  enable it; the Wi-Fi card is for the Pixellot Connect app and stays enabled),
  and notes if the motherboard port is disabled or unplugged. It tells the
  motherboard port apart from the camera card by its hardware (PCI) location, so
  it works even when both use the same Intel chipset.
- **Pulse now flags a disabled Wi-Fi card.** The Wi-Fi card is how the Pixellot
  Connect app reaches the VPU. If it's been disabled in Windows, Pulse raises a
  warning with how to turn it back on — so a unit that's invisible to Connect is
  easy to spot. (Units without a Wi-Fi card aren't flagged.)
- **Refresh camera stills one at a time.** The Camera Frames panel now has a
  "Refresh all cameras" button plus a "Refresh" on each camera card, so you can
  grab a new still from just the camera you're working on instead of re-pulling
  every camera.
- **Restart Pulse or reboot the VPU from Settings.** The Settings page has a new
  Reboot Pulse panel. "Restart Pulse app" relaunches Pulse if the page is stuck
  or acting up — the VPU and any recording keep running, and the page reloads
  itself once Pulse is back. "Reboot VPU" restarts Windows on the unit; it
  interrupts any active recording, so it asks you to confirm first.
- **Disks now shows real drive wear and SMART health, not just Healthy/Unhealthy.**
  Each physical drive lists its SSD wear (percent of rated write-life used),
  temperature, and power-on hours next to the health badge. Pulse raises a
  warning when a drive crosses 80% wear, and a critical when a drive reports a
  SMART pre-failure or uncorrectable errors — so you can swap a dying SSD before
  it quits mid-game instead of after.
- **Network Test now lists every wired port, not just the internet uplink.** A new
  "Wired Ports" table shows each Ethernet port — the motherboard uplink and each
  camera-NIC port — with its link state, speed, and error/discard counts, so a
  bad cable or dirty switch port on a non-uplink port is no longer invisible. The
  live network monitor also gained a per-interface table (queue depth, errors,
  and packet rates per NIC).

### Removed
- **Removed the "Reinstall Pixellot Dependencies" button.** Reinstalling the
  Pixellot video dependencies pauses recording for several minutes and is a
  last-resort step, so it's no longer something Pulse can trigger. When the logs
  show a CUDNN/TensorFlow dependency error, Pulse now points you to capture an
  export and escalate to Pixellot support instead. The installed dependency
  version still shows on the Service Status tab.

### Changed
- **Renamed the "Fault Isolator" tool to "Camera Connection Troubleshooting".**
  The swap-test tool on the Camera Connectivity tab (and the button that opens it)
  now uses a plainer name — same step-by-step test, clearer label.
- **Camera Frames now show the camera type, model, and firmware.** Each
  captured still lists the system type (S1/S2/S2S), IP address, camera model,
  and firmware version, and is clearly marked as a point-in-time snapshot — not
  a live stream. The status now reads "Active" instead of "Streaming".
- **"Disk & Driver Errors" now catches filesystem corruption.** The disk-events
  panel used to watch only the disk / NVMe / storage-controller logs; it now also
  includes NTFS and volume-manager events (the "run chkdsk — the file system is
  corrupt" kind), which are the ones that usually come right before data loss.
- **Clearer Stream Readiness wording.** The middle verdict now reads "WARNING"
  instead of "WARN", and its summary explains it plainly: "Will likely stream,
  but there are issues found that should be addressed to improve the system's
  reliability."
- **Slimmed down the Settings page.** Settings now shows just Software Update and
  the new Reboot Pulse panel. The ScoreConnect URL, live-metrics interval, log
  file paths, and the Run All Diagnostics button were removed to keep the page
  focused. (Generating a report from **Exports** still re-runs every check.)
- **Reorganized the sidebar into six clearer groups.** Tabs are now grouped as
  Triage, Troubleshooting, Pixellot Configuration, System Information, Data
  Logs, and Pulse. A few tabs were renamed to say what they do —
  "Network Test", "ScoreConnect", "Service Status", "Disks",
  "Windows Events", and "Exports". Nothing moved out of reach; bookmarks/links
  still work.
- **Split the big "System Overview" tab into focused tabs.** Hardware (CPU,
  memory, graphics, storage), Applications (installed software + concern
  flags), and Environment (Windows OS, locale, uptime, users, peripherals) are
  now separate tabs, and Pixellot version + hardware-compatibility moved to a
  new Pixellot Software tab. Old "System Overview" links open Hardware.
- **Split the Pixellot Configuration tab into three.** Pixellot Software
  (version, install/agent, registry, and the Restart Agent button), Camera
  Hardware (per-camera role / IP / MAC / firmware / TV mode / serial), and
  Camera Calibrations (multisport + OCR scoreboard status) are now separate
  tabs. Old "Pixellot Configuration" links open Pixellot Software.
- **The Camera Hardware tab now shows each camera's full details.** Every
  camera's complete probe — device identity, network settings, stream encoding,
  and image-sensor tuning — now appears on the Camera Hardware tab. Before, this
  lived only inside a per-port "Details" drop-down on Camera Connectivity, which
  now links straight to the tab and flags ports with more than one camera.
- **New Data Logs tabs.** Pixellot Logs (the Pixellot log-directory scan, moved
  off Windows Events into its own tab) and Pulse Logs (Pulse's own script-call
  and server logs) now live under Data Logs. The old slide-up log drawer at the
  bottom of the window is gone — its script + server logs are now the full-page
  Pulse Logs tab.
- **New Help tab.** A plain-English page covering what Pulse is, how to read the
  Dashboard, and the first things to try in the field, under the Pulse group.
- **The Wi-Fi warning now explains Wi-Fi's real job.** When the VPU is running
  its internet over Wi-Fi, the message now notes the Wi-Fi card is meant for the
  Pixellot Connect app — move the internet to the motherboard Ethernet port.
- **New Stream Readiness check.** Pulse now rolls every diagnostic into one
  PASS / WARNING / FAIL call on whether the VPU can stream tonight's game, shown
  at the top of the Dashboard with the exact blockers and risks behind the
  verdict. FAIL means "don't expect a clean broadcast tonight."
- **Clearer wording across Pulse.** Findings and panels now lead with plain
  language and the fix — fewer unexplained acronyms up front, with the technical
  detail (exact values, commands, port numbers) still right there in the detail.
- **Port Connectivity tiles now list in numeric order, two per row.** Within
  Required and within Optional, ports run ascending (53, 123, 443…) and wrap in
  pairs, so a given port is easy to find at a glance.
- **Tidied the Dashboard's System Status gauges.** The status rings and their
  labels now line up evenly across the row, and the "Live" dot only shows up
  when the live connection drops (Connecting…/Reconnecting…) instead of sitting
  on screen at all times.
- The Audio tab is temporarily hidden while audio diagnostics are being
  finished. No loss of function — audio checks were not yet in field use.

### Fixed
- **Error tabs no longer spin forever.** When a check can't run, Camera
  Connectivity, ScoreConnect, the Camera Fault Isolator, and Windows Events now
  show a clear error message instead of an endless loading spinner.
- **Cleaner light mode.** A few dashboard elements (the storage bars, the
  temperature gauge, and some status colors) were using dark-theme shades while
  in light mode; they now match the rest of the page in both light and dark.
- **Received report sizes now read correctly.** In Share over LAN, a
  multi-gigabyte snapshot showed an oversized "MB" figure in the received list;
  it now displays in GB.
- **No more false "can't reach gateway" alarm when the gateway just ignores
  pings.** Plenty of routers and firewalls are set to drop pings (ICMP) to
  themselves while still routing traffic perfectly. Pulse used to read that as a
  CRITICAL "VPU can't reach its gateway — check the cable/switch/VLAN," sending
  techs to chase a fault that isn't there. Now, when the VPU is already reaching
  the internet, an unanswered gateway ping is shown as an informational note
  ("gateway doesn't answer ping, but traffic is routing normally") instead of a
  critical. A real dead gateway — where the internet is also unreachable — still
  raises the critical.
- **No more false "DNS blocked / can't resolve any hostname" alarm.** The DNS
  check was probing whatever resolver it found first across *all* network
  adapters — so a stale resolver on a disconnected or secondary adapter (e.g. a
  camera NIC) could be tested instead of the one the VPU actually uses, fail,
  and raise a critical while every domain on the same screen was resolving fine.
  Pulse now tests the resolver on the active internet uplink, and never reports
  DNS as blocked when name resolution is demonstrably working.
- **No more false "DNS server unreachable" warning when the server just ignores
  ping.** Many venue firewalls block ICMP (ping) to the DNS server while it
  still answers real lookups. Pulse used to read the dead ping as a warning even
  though domains were resolving fine. When name resolution is demonstrably
  working, that 100%-loss ping is now reported as an INFO note ("isn't answering
  pings, but name resolution is working — no action needed") instead of a
  warning, and the DNS Server tile in Local Network Health turns blue/INFO with
  a "ICMP ping blocked by firewall — name resolution is working" note instead of
  showing red.
- **Gateway, DNS, and uplink readings now follow the active internet connection.**
  On a VPU with more than one network connection (the camera NIC plus the
  internet uplink, or a VPN), the Network Test could ping the gateway and DNS —
  and read link speed and error counts — off the wrong adapter, making a healthy
  uplink look bad or a stale one look fine. These checks now lock onto the
  connection that actually carries the VPU's internet traffic.
- **Dropped two dead addresses from the domain-resolution check.** Two storage
  hostnames from a retired backend were still in the name-lookup list; they no
  longer resolve, so they showed as meaningless red failures. Removed.
- **The Network panel no longer comes up blank / "no internet" on some VPUs.**
  The new adapter-role check was scanning every network device Windows has ever
  seen (VPUs accumulate dozens of stale ones), which could time out the whole
  network check — leaving the panel empty and falsely reporting "VPU has no
  internet connection." It now reads hardware location only for the adapters
  actually present, and a network-check hiccup no longer masquerades as "no
  internet" (Pulse says a check couldn't complete instead).
- **Pulse now opens directly in Chrome on launch.** On VPUs with no default
  browser set, Windows used to pop a "How do you want to open this?" picker
  (with Internet Explorer as the first option) instead of opening Pulse. The
  launcher now opens Chrome explicitly — no dialog, no IE.
- **The launcher no longer looks frozen while starting.** It used to run the
  server in the foreground window (a debug aid), so the window sat there
  showing the live server log and seemed stuck until you pressed Ctrl+C. It now
  starts the server in the background, opens the browser, and closes the window.
  Launch failures still stop and show the error, and everything is logged.
- **A blocked Zixi streaming port (UDP/2088) is now flagged as a real outage.**
  Pulse used to treat UDP/2088 as one of three interchangeable streaming paths,
  so blocking it only showed a yellow "no failover" note. In the field the
  live broadcast rides UDP/2088 with no failover — so a block there now reads as
  a red "Streaming is blocked — the VPU can't broadcast." The failover/"backup
  connection" wording now applies only to the two port-443 paths (UDP/443 and
  the TCP/443 tunnel), which do back each other up.
- Fixed an error that could appear on the Audio screen and during full
  diagnostic collection (the audio device check failed to return results on
  some VPUs).

## [0.3.5] - 2026-06-23

### Fixed
- **No more false "DNS server unreachable" warning when the server just ignores
  ping.** Many venue firewalls block ICMP (ping) to the DNS server while it
  still answers real lookups. Pulse used to read the dead ping as a warning even
  though domains were resolving fine. When name resolution is demonstrably
  working, that 100%-loss ping is now reported as an INFO note ("isn't answering
  pings, but name resolution is working — no action needed") instead of a
  warning, and the DNS Server tile in Local Network Health turns blue/INFO with
  a "ICMP ping blocked by firewall — name resolution is working" note instead of
  showing red.

## [0.3.4] - 2026-06-18

### Fixed
- **No more false "DNS blocked — can't resolve any hostname" alarm.** The DNS
  check was probing whatever resolver it found first across *all* network
  adapters, so a stale resolver on a disconnected or secondary adapter (e.g. a
  camera NIC or VPN) could get tested instead of the one the VPU actually uses —
  it failed, and Pulse raised a critical even though every domain was resolving
  fine. Pulse now tests the resolver on the active internet uplink.

## [0.3.3] - 2026-06-15

### Fixed
- **Pulse now opens directly in Chrome on launch.** On VPUs with no default
  browser set, Windows used to pop a "How do you want to open this?" picker
  (Internet Explorer first) instead of opening Pulse. The launcher now opens
  Chrome explicitly — no dialog, no IE.
- **The launcher no longer looks frozen while starting.** It was running the
  server in the foreground window, so it sat showing the live log and seemed
  stuck until you pressed Ctrl+C. It now starts the server in the background,
  opens the browser, and closes the window. Launch failures still stop and show
  the error, and everything is logged.

## [0.3.2] - 2026-06-12

### Fixed
- **Port Connectivity no longer warns that streaming will fail when it won't.**
  Pixellot can broadcast over any of three paths (UDP/2088, UDP/443, or the
  TCP/443 tunnel), so one blocked path now shows a yellow "no failover" note
  instead of a red failure — it only flags a real "stream can't broadcast" when
  all three are blocked. (The UDP/443 row is also renamed from the misleading
  "Zixi QUIC" to "Zixi Backup".)

### Changed
- **Network checks combined into one panel.** Port Connectivity (left) and
  Domain Reachability (right) now share a single card. Port tiles lead with the
  port number and protocol — no hostnames; the domain detail is all in the
  right-hand column. The Internet Adapter card lays its sections side by side so
  it takes less vertical space.

## [0.3.1] - 2026-06-11

### Changed
- The Audio tab is temporarily hidden while audio diagnostics are being
  finished. No loss of function — audio checks were not yet in field use.

### Fixed
- Fixed an error that could appear on the Audio screen and during full
  diagnostic collection (the audio device check failed to return results on
  some VPUs).

## [0.3.0] - 2026-06-11

### Added
- **Pulse records which VPUs it's run on.** On launch Pulse sends a small
  identity-only check-in — hostname, serial, venue, model, version — so we can
  see which units Pulse has been used on. It never runs on demo/dev machines and
  fails silently if the network blocks it; Pulse works exactly the same either way.
- **Share a report to another Pulse over the LAN.** A new **Share over LAN**
  page lets you send this VPU's full diagnostic snapshot straight to another
  Pulse on the same network — no USB or file copy. On the receiving machine,
  turn on **Receive over LAN** and read off its five-word pairing code (e.g.
  "tiger maple river copper dust"); on the sending machine, type those words
  and hit **Send**. On a VPU with more than one network, pick which one to
  share from the dropdown (so the other machine can actually reach it), and
  Pulse opens the Windows firewall for the share port automatically (one
  approval prompt). Received reports show up in an
  in-app inbox you can view, download, or delete. Receiving is off by default,
  so Pulse only opens to the network when you ask it to (Windows may prompt to
  allow access the first time).
- **Every port and domain Pulse tests now explains what happens if it's
  blocked.** Hover an entry in Port Connectivity or Domain Reachability — or
  open the matching issue — to see the real-world impact (e.g. the game won't
  stream, or scoreboard data won't come through). Makes it obvious which
  blocked endpoints actually matter at a given venue and which are harmless.

### Changed
- **Fixed the System Disk gauge reading the wrong number.** The dashboard donut
  was showing a whole-machine average across all drives, so a large near-empty
  D: dragged it down (e.g. **9%** when the C: system drive was really ~50% full).
  It now shows the **C: (system) drive's own usage**, matching the "free of"
  figure beneath it. The storage card also labels both drives by role —
  **System (C:) — OS & Pixellot** and **Recordings (D:) — local VOD storage** —
  so you can watch the recordings drive fill up.
- **System Overview cleanups (UX audit).** Install date shows as a plain date
  instead of a raw timestamp; the install-date and locale fields are now
  populated; blank hardware values show "—" instead of "null GB"; GPU cards
  label each adapter **Dedicated**/**Integrated** (not color-only); the
  hardware-compatibility note reads in plain language; and the software filter
  shows a "no matches" message. Wide tables now scroll on narrow screens instead
  of squashing the page. (Also fixes a stray "undefined GB free" on Disk &
  System Health.)
- **The build version now shows on the loading screen**, right under the Pulse
  logo — so you can see exactly which build you're on at a glance (handy when
  reporting an issue).
- **Simpler launchers.** One per channel, clearly named: `run_pulse.bat`
  (production), `run_pulse_beta.bat` (beta), `run_pulse_dev.bat` (dev). The dev
  launcher now always pulls the latest `dev`-branch commit instead of a stale
  tagged release. (The old `_web_`-prefixed names and the duplicate Pulse.WPF
  launchers are gone — WPF is deprecated.)
- **Pulse no longer leaves a desktop icon** — launch from the Start Menu
  instead (press **Win**, type "pulse", hit Enter). Cleaner footprint on the
  VPU. Existing installs auto-clean up the old desktop shortcut on next launch.
- **Removed the raw cameras.cfg table from Camera Connectivity.** Camera
  identity already shows on each port tile — the duplicate config dump just
  added clutter.
- **Clearer VPU orientation diagram + a port-layout toggle.** The "upright" and
  "on its side" pictures are now the same drawing (one is just rotated), so they
  can't disagree. New **Flip layout** button rotates the 4-port LED row between
  horizontal and vertical to match how the VPU is actually mounted.
- **Tighter Fault Isolator wording.** Phase steps, results, and conclusions are
  shorter and less repetitive — the same guidance, less to read on each screen.
- **Port Connectivity redesigned as port-led tiles.** Each tile leads with its
  protocol/port (e.g. `TCP/443`) and a Pass/Blocked status; services that share
  a port are combined into one tile (the HTTPS endpoints; Scorebot's port
  range), grouped into Required and Optional with a one-line summary at the top,
  replacing the old two-column TCP/UDP grid. Optional services (RTMP, Scorebot)
  are de-emphasized so a blocked optional port no longer looks like a failure.
- **Speed Test moved out of Advanced Diagnostics** to sit right under the
  internet adapter and domain checks — where you'd look for it first.
- **Internet Adapter details are grouped into labeled sections** (IP
  Configuration, Link, Connectivity, Time Sync) so the card reads top to bottom.
  Local Network Health regained its section icon, and the 4 / 10 / 20 / 50 ping
  presets now have a "Ping count" label.

### Fixed
- **"Install ScoreConnect III" no longer gets stuck at 5%.** The installer now
  opens in a visible window you complete on screen — approve the Windows
  administrator prompt, then follow the installer's prompts — and Pulse confirms
  ScoreConnect III is running once it finishes. If you decline the prompt or it
  stalls, Pulse now says so and offers **Retry** instead of spinning forever.
  (Also fixes the garbled text that used to appear in the progress message.)
- **Camera Connectivity no longer errors out when a port is down.** A page that
  showed only "Internal Server Error" now loads normally and tells you why the
  port is down (disabled / driver fault / no signal).
- **Cable unplug/replug now shows in ~2 seconds, not ~15.** Link status is read
  near-live instead of from a cached snapshot, so disconnecting or reconnecting
  a camera updates the port almost immediately.
- **The blue "connecting" state shows again on reconnect.** Plugging a cable
  back in now flashes the establishing-link cue before going green, instead of
  jumping straight from gray to linked.
- **Far fewer false network alarms.** Pulse no longer reports "no internet" on
  venues that simply block ping (it confirms reachability through real services
  instead); the DNS check now tests the VPU's actual configured resolver rather
  than a public one (8.8.8.8) that locked-down school networks block on purpose;
  harmless CDN address differences are no longer flagged; and the
  gateway-instability threshold was loosened so normal latency doesn't trip it.
- **Wi-Fi is only flagged when it's actually carrying the internet uplink** —
  idle or virtual wireless adapters no longer raise a warning, and the guidance
  now points to switching to Ethernet rather than disabling the adapter.
- **UDP port checks no longer show green on silently blocked ports.** The Zixi
  streaming ports (UDP 443 / 2088) previously passed whenever the firewall gave
  no answer at all — exactly what most school firewalls do when they block a
  port — so a venue could show all-green while streaming was actually blocked.
  Pulse now requires a real reply from Pixellot's echo server to pass (with
  retries so one lost packet doesn't cause a false alarm). If Pulse and another
  port tester now disagree, believe the one showing the failure.
- **The LogMeIn check now tests the real remote-access service.** It previously
  tested logmein.com, which now points at GoTo's marketing website — so it could
  pass while the actual LogMeIn gateways were blocked. It now tests
  secure.logmein.com, which lives on the same GoTo network the VPU's real
  LogMeIn sessions use.
- **Port Connectivity no longer cries "stream fails" when streaming actually
  works.** Pixellot can broadcast over any of three paths — UDP/2088 (primary),
  UDP/443 (backup), or the TCP/443 tunnel — so the stream only fails if all
  three are blocked. Pulse now treats one blocked streaming path with another
  still open as a yellow "no failover" warning, not a red failure, and only
  flags a true "stream cannot broadcast" critical when every path is down.
  (The UDP/443 row is also renamed from the misleading "Zixi QUIC" to "Zixi
  Backup.")
- **Network checks now read as one panel: ports on the left, domains on the
  right.** Port Connectivity and Domain Reachability share a single card.
  Each port tile leads with the port number and protocol (no hostnames — the
  domain detail all lives in the right-hand column), so the left is a clean
  "is this port open" view and the right is the full domain list.

## [0.2.1] - 2026-06-04

### Changed
- Removed the Repair Tools panel (DISM, System File Checker, and chkdsk) from
  the Disk & System Health page for this release. These run long or change
  boot state and shouldn't be triggered without guidance.

## [0.2.0] - 2026-06-02

### Added
- **Dashboard now flags missing main cameras.** If the VPU is configured for
  more cameras than are actually reporting on the camera NIC, you get a
  CRITICAL finding (none detected) or a WARNING (some missing, e.g.
  "1 of 2 main cameras detected"). Click it to jump straight to Camera
  Connectivity. Stays silent when expectations can't be read — never guesses.

### Changed
- **Launcher fails loud while we're in beta.** If something goes wrong on
  launch, the window stays open with the actual error/traceback instead of
  closing silently — and the browser still opens automatically once Pulse
  is ready.

### Fixed
- **Garbled box-line characters** in the launcher console output on VPUs
  whose console codepage isn't UTF-8. Output is now plain ASCII everywhere.

## [0.1.0] - 2026-05-29

### Added
- **Check for Update** in Settings — Pulse can now detect a newer build on its
  channel, install it, and restart on its own, with this changelog shown
  before you update. No more re-running the launcher by hand.
- **Full diagnostic report** now bundles the unit's complete state — every
  collector plus the detected cameras and Pulse's own findings — with a
  provenance header (which VPU, when, what build) for offline review.
- Launcher now **runs as Administrator** automatically so every diagnostic
  reads at full capability.

### Changed
- Findings are grouped by severity and each is tagged **CRITICAL** or
  **WARNING**; clicking one jumps to the relevant tab.
- The dashboard labels the gateway NIC as the **Motherboard Network Port**
  instead of an opaque "Ethernet 13".

### Fixed
- **OCR / scoreboard camera ports no longer raise a false low-speed warning** —
  they run at 100 Mbps by design; only the main 4K heads expect 1 Gbps.
- Sub-gigabit warnings now name the **physical port (Port 1–4)** and route to
  Camera Connectivity instead of Network.
- A disconnected port with stale ARP no longer reports a phantom camera/OCR.
