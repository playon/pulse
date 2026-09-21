"""Mock data for non-Windows demo mode."""

import base64
import random
import time
from datetime import datetime, timedelta


def _demo_frame(label, color):
    """A base64 SVG data URI standing in for a captured camera frame, so the
    Verify Video thumbnail UI can be exercised in demo mode (no ffmpeg)."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='480' height='270'>"
        f"<rect width='480' height='270' fill='{color}'/>"
        "<text x='240' y='150' font-family='sans-serif' font-size='20' "
        f"fill='#cbd5e1' text-anchor='middle'>{label}</text></svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _demo_black_frame(label):
    """A near-black frame with one bright spot (a stand-in scoreboard) — the
    OCR 'black picture' symptom, so the black-frame diagnosis renders in demo."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='480' height='270'>"
        "<rect width='480' height='270' fill='#050608'/>"
        "<rect x='360' y='24' width='84' height='38' rx='3' fill='#f4d35e'/>"
        "<text x='240' y='150' font-family='sans-serif' font-size='15' "
        f"fill='#3a3f47' text-anchor='middle'>{label}</text></svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

# ── Demo venue identity ──────────────────────────────────────
# Picked once at module load so all scripts return consistent data
# for a single Pulse session. Each session re-imports → fresh pick.
# The pool is small + curated so demos look like real Pixellot
# venues without ever showing actual customer data.
_DEMO_VENUES = [
    {"hostname": "PXLS2-31402", "vpuName": "PXLS2_31402 Westfield Academy (TX) - Gymnasium",     "venueId": "5fdb1c042e3a86412c7a04b8", "serial": "CZC8847PQR", "city": "Houston",      "state": "TX", "uplinkIp": "10.40.16.50", "gatewayIp": "10.40.16.1", "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-22158", "vpuName": "PXLS2_22158 Roosevelt High School (CA) - Main Court","venueId": "603a45f08c9e217d09b51230", "serial": "CZC7235HXM", "city": "Riverside",    "state": "CA", "uplinkIp": "10.22.8.50",  "gatewayIp": "10.22.8.1",  "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-19844", "vpuName": "PXLS2_19844 Lincoln Memorial (FL) - Sports Complex", "venueId": "5f0bdd24a91c834b287e0c91", "serial": "CZC9912NTL", "city": "Orlando",      "state": "FL", "uplinkIp": "10.18.4.50",  "gatewayIp": "10.18.4.1",  "swVersion": "5.13.4", "imageVersion": "26.02.003"},
    {"hostname": "PXLS2-27619", "vpuName": "PXLS2_27619 Northridge Prep (IL) - Fieldhouse",      "venueId": "6184e90f3d7c5e228f3ab472", "serial": "CZC8104WBQ", "city": "Chicago",      "state": "IL", "uplinkIp": "10.31.12.50", "gatewayIp": "10.31.12.1", "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-18203", "vpuName": "PXLS2_18203 Cedar Ridge (CO) - Performance Center",  "venueId": "60c2f1b8e84a5d3192058c6a", "serial": "CZC6502RJD", "city": "Denver",       "state": "CO", "uplinkIp": "10.55.20.50", "gatewayIp": "10.55.20.1", "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-34701", "vpuName": "PXLS2_34701 Pinecrest Academy (GA) - Stadium",       "venueId": "62a85b714c0f9d27ab1e6df3", "serial": "CZC9118MWE", "city": "Atlanta",      "state": "GA", "uplinkIp": "10.12.4.50",  "gatewayIp": "10.12.4.1",  "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-25618", "vpuName": "PXLS2_25618 Saguaro Heights (AZ) - West Court",      "venueId": "5e7c39d8d416a72594b30e85", "serial": "CZC7794KAV", "city": "Phoenix",      "state": "AZ", "uplinkIp": "10.66.8.50",  "gatewayIp": "10.66.8.1",  "swVersion": "5.13.4", "imageVersion": "26.02.003"},
    {"hostname": "PXLS2-29115", "vpuName": "PXLS2_29115 Harbor Bay HS (WA) - Aquatics Center",   "venueId": "6310aa56b9e1c4083f7d8290", "serial": "CZC8329LPB", "city": "Seattle",      "state": "WA", "uplinkIp": "10.77.16.50", "gatewayIp": "10.77.16.1", "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-21947", "vpuName": "PXLS2_21947 Magnolia Charter (LA) - Gymnasium",      "venueId": "612bf4c0a8351629d7f06ee4", "serial": "CZC6981XQH", "city": "Baton Rouge",  "state": "LA", "uplinkIp": "10.88.12.50", "gatewayIp": "10.88.12.1", "swVersion": "5.13.6", "imageVersion": "26.04.001"},
    {"hostname": "PXLS2-33028", "vpuName": "PXLS2_33028 Granite Peak (UT) - Field House",        "venueId": "5f8e6a3142b9d05c8773ec19", "serial": "CZC8866TRC", "city": "Salt Lake City", "state": "UT", "uplinkIp": "10.99.4.50",  "gatewayIp": "10.99.4.1",  "swVersion": "5.13.6", "imageVersion": "26.04.001"},
]
_VENUE = random.choice(_DEMO_VENUES)

# Uptime varies between 1-12 days for that "real VPU" feel — long enough
# to look stable, short enough not to trip the >30-day high-uptime finding.
_BOOT = time.time() - random.randint(1, 12) * 86400 - random.randint(0, 23) * 3600


def _uptime_secs():
    return int(time.time() - _BOOT)


def _fmt_uptime(s):
    d, r = divmod(s, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    return f"{d}d {h}h {m}m"


# Demo "game" state — chosen once per session so the full fetch and the
# live polls agree on scores. The clock is derived from wall-clock time so
# it ticks down realistically across live polls.
_DEMO_GAME = {
    "guest": random.randint(0, 35),
    "home": random.randint(0, 35),
    "quarter": random.randint(1, 4),
    "down": random.randint(1, 4),
    "to_go": random.randint(1, 15),
    "ball_on": random.randint(10, 50),
    "period_secs": 12 * 60,  # 12:00 quarters
    "anchor": time.time(),
}


def _demo_live_clock():
    """Count down from the period length based on wall-clock elapsed time,
    wrapping at 0 so the demo clock ticks forever."""
    elapsed = int(time.time() - _DEMO_GAME["anchor"])
    remaining = _DEMO_GAME["period_secs"] - (elapsed % _DEMO_GAME["period_secs"])
    return remaining // 60, remaining % 60


def _demo_raw_data():
    """Build a ScoreConnect CG raw string from the demo game state with a
    live (wall-clock-derived) game clock. Reproduces the real SC III
    FIXED-WIDTH byte layout exactly (verified against live VPU captures):

        "025728  25 38 42  33     3Home    Visitor R:S <chk>"
         pos 0-1  header "02"
         pos 2-5  clock (right-justified: "5728" or " 944" under 10:00)
         pos 8-9  field A (constant in tests)
         pos 11-12 HOME score
         pos 14-15 VISITOR score
         pos 18-19 field B (constant in tests)
         pos 25   quarter
         then Home/Visitor labels + clock-run flag + checksum
    """
    g = _DEMO_GAME
    minutes, seconds = _demo_live_clock()
    clock = f"{minutes}{seconds:02d}".rjust(4)   # "1225" or " 944"
    chk = f"00D3098DEBCE{random.randint(0, 0xFFFFFF):06X}"
    # Packed down/to-go/ball-on at pos 20-24: down(1) togo(2) ballon(2).
    dtb = f"{g['down']}{g['to_go']:02d}{g['ball_on']:02d}"
    # Field widths chosen so HOME lands at 11-12, VISITOR at 14-15,
    # timeouts at 18-19, down/dist at 20-24, quarter at 25.
    return (
        f"02{clock}  25 {g['home']:>2} {g['guest']:>2}  33{dtb}{g['quarter']}"
        f"Home    Visitor R:S {chk}"
    )


def _demo_scoreconnect_live():
    """Lightweight live-poll demo data — mirrors Get-ScoreConnectLive.ps1."""
    return {
        "reachable": True,
        "rawData": _demo_raw_data(),
        "dataStatus": "Data is present and in the correct format",
        "ts": datetime.now().isoformat(),
        "error": None,
    }


def _demo_scoreconnect_history():
    """Seeded 'previous configurations' entries (newest first) so the history
    panel demonstrates the change timeline in demo mode. Mirrors the entry
    shape _record_sc_config_history writes: a bot reassignment on the same
    scoreboard, then an older different-sport setup from last season."""
    return [
        {"source": "ScoreConnect III", "version": "1.4.0.10",
         "vendor": "Daktronics", "sport": "Daktronics Football",
         "configName": "Wireless", "device": None, "serialPort": None,
         "firmware": None, "eventType": None, "botNumber": "54025",
         "scoreLinkModel": "ScoreLink", "scoreLinkPort": "COM7",
         "firstSeen": "2026-05-26T15:36:00", "lastSeen": "2026-06-12T19:02:00"},
        {"source": "ScoreConnect III", "version": "1.4.0.10",
         "vendor": "Daktronics", "sport": "Daktronics Football",
         "configName": "Wireless", "device": None, "serialPort": None,
         "firmware": None, "eventType": None, "botNumber": "31882",
         "scoreLinkModel": "ScoreLink", "scoreLinkPort": "COM7",
         "firstSeen": "2026-04-02T10:14:00", "lastSeen": "2026-05-26T15:31:00"},
        {"source": "ScoreConnect III", "version": "1.3.2.4",
         "vendor": "All Sport 5000", "sport": "Basketball",
         "configName": "Serial", "device": None, "serialPort": "COM3",
         "firmware": None, "eventType": None, "botNumber": "31882",
         "scoreLinkModel": "ScoreLink", "scoreLinkPort": "COM3",
         "firstSeen": "2026-01-09T18:40:00", "lastSeen": "2026-03-14T21:22:00"},
    ]


# Simulated SC III install timeline. Mirrors the real status file stages
# (Install-ScoreConnectIII.ps1 → Get-Sc3InstallStatus.ps1) so the install
# modal can be demoed end-to-end: each entry is (ends-at-seconds, stage,
# percent, message, log-line-added-at-this-point).
_SC3_INSTALL_TIMELINE = [
    (3, "starting", 5, "Approve the Windows administrator prompt to begin installing ScoreConnect III.", None),
    (8, "downloading", 20, "Downloading the ScoreConnect III installer from Canopy.",
     "Downloading from https://canopy-public-packages.nfhsnetwork.com/SC3/Current/installScript3_current.ps1"),
    (13, "installing", 55, "Installer: Downloading installer version 1.4.1.1 to temporary directory... this might take a minute.",
     "Sanitized installer script; headless=True"),
    (18, "installing", 62, "Installer: Attempting to uninstall SC1... this might take a minute.",
     "installer: Download complete."),
    (22, "installing", 68, "Installer: Checking if SC2 needs uninstalled...",
     "installer: Uninstall of SC1 attempt complete."),
    (28, "installing", 78, "Installer: Attempting ScoreConnectIII 1.4.1.1 install now. This will take 60 seconds.",
     "installer: Uninstall stage complete."),
    (33, "verifying", 85, "Verifying ScoreConnect III is running.",
     "installer: Install complete and shortcut created."),
]
_sc3_demo_install = {"started": None}


def _demo_sc3_install_start():
    _sc3_demo_install["started"] = time.time()
    return {
        "ok": True,
        "message": "Install started. Poll /api/scoreconnect/install-sc3/status for progress.",
        "statusUrl": "/api/scoreconnect/install-sc3/status",
    }


def _demo_sc3_install_status():
    started = _sc3_demo_install["started"]
    if started is None:
        # Mirrors the script's 'idle' branch (no status file present).
        return {"stage": "idle", "percent": 0, "message": "No install in progress"}

    elapsed = time.time() - started
    log = []
    current = None
    for ends_at, stage, percent, message, log_line in _SC3_INSTALL_TIMELINE:
        if log_line and elapsed >= ends_at - 1:
            log.append(log_line)
        if current is None and elapsed < ends_at:
            current = (stage, percent, message)
    if current is None:
        current = ("complete", 100, "ScoreConnect III is installed and running.")
        log.append("Service recovery configured: auto-restart on crash (5s/5s/30s, counter resets daily)")
        log.append("SC III reachable on :5000 - install complete")

    stage, percent, message = current
    return {
        "stage": stage,
        "percent": percent,
        "message": message,
        "error": None,
        "updatedAt": datetime.now().isoformat(),
        "stale": False,
        "logTail": "\n".join(log) or None,
    }


def _demo_scoreconnect():
    """Generate consistent ScoreConnect demo data.

    Simulates ScoreConnect III (web-based, raw RTD data only — no parsed
    scores).  SC II (web-based, has parsed data) and SC I (.exe, has parsed
    data) are different products with different API surfaces.

    Bot number is intentionally included but is notoriously stale on real
    hardware — SC III often reports a previous unit's number until reset.
    """
    has_data = True
    data_status = "Data is present and in the correct format"
    raw_data = _demo_raw_data() if has_data else None

    bot_id = str(random.randint(10000, 99999))
    bot_connected = random.choice([True, False])

    return {
        "reachable": True,
        "baseUrl": "http://localhost:5000",
        "version": "1.4.0.10",
        "dataStatus": data_status,
        "rawData": raw_data,
        "networkStatus": "Internet is detected",
        "hasLocalStream": has_data,  # local stream tracks data presence
        "configuration": {
            "vendor": "Daktronics",
            "sport": "Daktronics Football",
            "vendorConfigurationName": "Wireless",
        },
        "botStatus": {
            "isConnected": bot_connected,
            "scoreConnectId": bot_id,
            "botServerAddress": None,
            "lastErrorMessage": None,
        },
        "scoreLinkConnected": True,
        "scoreLinkPort": "COM7",
        "scoreLinkModel": "ScoreLink",
        "scoreLinkStatusLabel": "ScoreLink device connected (COM7)",
        "error": None,
        "sc2": {
            "reachable": True,
            "baseUrl": "http://localhost:1400",
            "version": "2.0.3.11",
            "hardware": "ScoreConnectII",
            "uid": "6C02E069700E",
            "scores": None,
            "teamNames": {
                "visitor": random.choice(["Eagles", "Warriors", "Knights", "Bulldogs"]),
                "home": random.choice(["Tigers", "Panthers", "Hawks", "Bears"]),
            },
            "vendor": "Daktronics Football",
            "sport": 2,
            "botNumber": 54025,
            "license": "07/01/2029",
            "scoreLink": {
                "description": "ScoreLinkII USB",
                "type": "ScoreLinkII",
                "address": "USB",
                "serial": "0000005B13C2",
            },
            "networkIfaces": [
                {"name": "Ethernet 44", "address": "192.168.111.184", "type": "Ethernet"},
                {"name": "Ethernet 55", "address": "169.254.79.80", "type": "Ethernet"},
            ],
            "statusLeds": None,
            "error": None,
        },
    }


# ── Synthetic camera CGI probe (demo mode) ───────────────────
# On non-Windows demo, _cgi_probe_sync() can't reach the synthetic camera
# IPs over HTTP, so it short-circuits to cgi_probe() below. This mirrors the
# real probe's return shape (see _cgi_probe_sync in main.py): MAC + device
# identity + network + stream + sensor groups. Keyed by the ARP IP each
# camera answers on, so _enrich_ports() matches it to the detected camera and
# the Camera Hardware tab renders a full probe in demo. The modelNumbers map
# through _CAMERA_MODELS, so role / expected-speed resolution — and the
# Port 2 "degraded" finding (gigabit main camera negotiated to 100 Mbps) —
# stay intact.
def _demo_cam(ip, mac, serial, *, ocr=False, gateway=None):
    if ocr:
        return {
            "mac": mac,
            "brand": "Dynacolor",
            "model": "Dynacolor MPC-IPC",
            "modelNumber": "R2SD-G",  # OCR / Scoreboard, 100 Mbps native
            "productType": "Box Scoreboard Camera",
            "serialNumber": serial,
            "firmwareVersion": "DC-2.4.1",
            "tvMode": "ntsc_60",
            "network": {"ip": ip, "subnet": "255.255.0.0", "gateway": gateway, "dhcp": "no"},
            "stream0": {"codec": "H264", "resolution": "1920x1080", "framerate": "30"},
            "stream1": {"enabled": "yes", "codec": "MJPEG", "resolution": "640x480", "framerate": "10"},
            # Brightness dialled well below the main cameras — drives the
            # same-room settings comparison in the black-frame diagnosis.
            "sensor": {"exposure": "auto", "brightness": "20", "contrast": "52",
                       "colorLevel": "50", "maxShutterGain": "30", "minShutterSpeed": "1/60"},
        }
    return {
        "mac": mac,
        "brand": "Pixellot",
        "model": "Pixellot SuperBowl",
        "modelNumber": "Z4SF-F",  # Main Camera, gigabit
        "productType": "4K Panoramic Camera",
        "serialNumber": serial,
        "firmwareVersion": "1.9.13",
        "tvMode": "ntsc_60",
        "network": {"ip": ip, "subnet": "255.255.255.0", "gateway": gateway, "dhcp": "no"},
        "stream0": {"codec": "H264", "resolution": "3840x2160", "framerate": "30"},
        "stream1": {"enabled": "yes", "codec": "MJPEG", "resolution": "1920x1080", "framerate": "15"},
        "sensor": {"exposure": "auto", "brightness": "50", "contrast": "50",
                   "colorLevel": "55", "maxShutterGain": "36", "minShutterSpeed": "1/30"},
    }


_DEMO_CGI_PROBES = {
    "192.168.10.100": _demo_cam("192.168.10.100", "00:0E:53:AA:01:01", "MC1-7741A", gateway="192.168.10.1"),
    "192.168.10.101": _demo_cam("192.168.10.101", "00:0E:53:AA:01:02", "PC2-7741B", gateway="192.168.10.1"),
    "192.168.10.102": _demo_cam("192.168.10.102", "00:0E:53:AA:01:03", "TC3-7741C", gateway="192.168.10.1"),
    "192.168.11.100": _demo_cam("192.168.11.100", "00:0E:53:BB:02:01", "MC4-9920A", gateway="192.168.11.1"),
    "192.168.11.101": _demo_cam("192.168.11.101", "00:0E:53:BB:02:02", "PC5-9920B", gateway="192.168.11.1"),
    "169.254.16.52":  _demo_cam("169.254.16.52",  "00:D0:89:1B:03:01", "DYN-OCR-3318", ocr=True),
}


def cgi_probe(ip):
    """Synthetic CGI probe for a known demo camera IP (else None).
    Called by _cgi_probe_sync() when DEMO_MODE is on so camerasDetected
    carries the full probe on a Mac, same as a real VPU."""
    probe = _DEMO_CGI_PROBES.get(ip)
    return dict(probe) if probe else None


# ── Storage cleanup demo (D: recordings) ─────────────────────
# Candidate list is computed once at module load so the preview and the
# post-delete receipt tell one consistent story within a session. Numbers
# mirror the real bench VPU: hundreds of ~10 MB daily test clips (small)
# and dozens of multi-GB game recordings (where the space actually is).
def _demo_cleanup_candidates():
    cands = []
    for i in range(208):
        d = datetime.now() - timedelta(days=91 + i * 2)
        cands.append({
            "name": f"{d:%Y-%m-%d}_p_DAILYTEST{d:%Y%m%d}",
            "category": "dailytest",
            "date": f"{d:%Y-%m-%d}",
            "sizeMB": round(random.uniform(7.5, 13.5), 1),
        })
    for i in range(47):
        d = datetime.now() - timedelta(days=366 + i * 4)
        hexid = "".join(random.choice("0123456789abcdef") for _ in range(24))
        cands.append({
            "name": f"{d:%Y-%m-%d}_p_{hexid}",
            "category": "recording",
            "date": f"{d:%Y-%m-%d}",
            "sizeMB": round(random.uniform(2400.0, 4300.0), 1),
        })
    cands.sort(key=lambda c: c["date"])
    return cands


_DEMO_CLEANUP_CANDIDATES = _demo_cleanup_candidates()
# Matches the Get-DiskHealth demo payload: D: is 953 GB with 86 GB free (91%).
_DEMO_D_SIZE_GB, _DEMO_D_FREE_GB = 953, 86


def _demo_cleanup_bucket(category):
    items = [c for c in _DEMO_CLEANUP_CANDIDATES if c["category"] == category]
    return {
        "count": len(items),
        "sizeGB": round(sum(c["sizeMB"] for c in items) / 1024, 1),
        "oldest": items[0]["date"] if items else None,
        "newest": items[-1]["date"] if items else None,
    }


def _demo_cleanup_preview(**kw):
    daily = _demo_cleanup_bucket("dailytest")
    recs = _demo_cleanup_bucket("recording")
    total_gb = round(daily["sizeGB"] + recs["sizeGB"], 1)
    projected_free = round(_DEMO_D_FREE_GB + total_gb, 1)
    return {
        "rootExists": True,
        "root": "D:\\recordedevents",
        "params": {"recentGuardDays": 90, "recordingMaxAgeDays": 365},
        "drive": {"letter": "D", "sizeGB": _DEMO_D_SIZE_GB, "freeGB": _DEMO_D_FREE_GB, "usedPercent": 91},
        "dailyTest": daily,
        "recordings": recs,
        "totalSizeGB": total_gb,
        "totalFolders": len(_DEMO_CLEANUP_CANDIDATES) + 132,
        "skippedRecent": 131,
        "skippedUnrecognized": ["0001-01-01_p_"],
        "projectedFreeGB": projected_free,
        "projectedUsedPercent": round((_DEMO_D_SIZE_GB - projected_free) / _DEMO_D_SIZE_GB * 100, 1),
        "candidates": _DEMO_CLEANUP_CANDIDATES,
    }


def _demo_cleanup_result(**kw):
    p = _demo_cleanup_preview()
    freed = p["totalSizeGB"]
    return {
        "success": True,
        "deletedCount": len(_DEMO_CLEANUP_CANDIDATES),
        "deletedDailyTest": p["dailyTest"]["count"],
        "deletedRecordings": p["recordings"]["count"],
        "failedCount": 0,
        "freedGB": freed,
        "before": {"letter": "D", "sizeGB": _DEMO_D_SIZE_GB, "freeGB": _DEMO_D_FREE_GB, "usedPercent": 91},
        "after": {"letter": "D", "sizeGB": _DEMO_D_SIZE_GB, "freeGB": p["projectedFreeGB"],
                  "usedPercent": p["projectedUsedPercent"]},
        "durationMs": 84250,
        "deleted": _DEMO_CLEANUP_CANDIDATES,
        "failed": [],
    }


def _demo_poe_power():
    """ADLINK SmartPoE card telemetry, matching Get-PoePower.ps1's shape.

    Keyed to the Get-NicAdapters.ps1 demo above so the two agree: that payload
    reports I210/I211 ports (so PoE telemetry is supported), with Ethernet 4
    unplugged -- so port 4 reads unpowered here and poeOnCount lands at 3.

    Watts jitter per call so the meters aren't frozen in demo.

    All figures below are calibrated to a real production GIE74P read on
    2026-08-12 rather than guessed:
      - Per-port draw 4-7 W, NOT the ~10 W first assumed. Pixellot CHUs sit far
        under the 25.5 W PoE+ ceiling, which is why demo bars look ~20% full.
      - Port voltage is a stable per-port constant (that card read 54.709 and
        54.149 V unchanged across samples); only current moves.
      - An empty port floats slightly rather than reading exactly 0 V -- the
        real card showed 0.187 V on its unpopulated port. Port 4 reproduces
        that so the >1.0 V powered-test stays exercised in demo.
      - Total is ~60 W and NOT fixed: on real hardware consumed and remaining
        both drifted down together, so total is a noisy derived figure. Both
        jitter independently here to keep that honest.

    Total stays above the 55 W healthy floor so demo never fires the Molex
    warning. Drop `remaining` to ~8 W (total ~25 W) to exercise it -- that
    reproduces the 20 W VPU Manager reports on a Molex-disconnected card.
    """
    port_specs = [
        (1, 54.709, (0.084, 0.127)),  # Main camera 1 - real measured range
        (2, 54.149, (0.078, 0.102)),  # Main camera 2
        (3, 54.402, (0.088, 0.104)),  # OCR / scoreboard camera
        (4, 0.187,  (0.0, 0.0)),      # Unplugged, matches Ethernet 4 above
    ]
    ports = []
    consumed = 0.0
    poe_on = 0
    for num, voltage, (lo, hi) in port_specs:
        current = round(random.uniform(lo, hi), 3) if hi > 0 else 0.0
        watts = round(voltage * current, 1)
        on = voltage > 1.0
        if on:
            poe_on += 1
            consumed += watts
        ports.append({
            "port": num,
            "voltage": round(voltage, 2),
            "current": current,
            "watts": watts,
            "poeOn": on,
            "state": "Powered" if on else "Off",
            "readOk": True,
        })

    consumed = round(consumed, 1)
    # Jittered independently of consumed, because on real hardware the two are
    # not complementary — both drifted downward together across samples, so
    # total is a noisy derived number rather than the card's rating.
    remaining = round(random.uniform(46.0, 52.0), 1)
    total = round(consumed + remaining, 1)
    return {
        "supported": True,
        "available": True,
        "nicModel": "I210",
        "cardLabel": "ADLINK GIE74P (Intel I210 x4)",
        "reason": "",
        "dllPath": r"C:\Program Files\ADLINK\GIE Series\Library\Dll\x64\SmartPoE.dll",
        "budget": {
            "totalW": total,
            "consumedW": consumed,
            "remainingW": remaining,
            "tempC": round(random.uniform(45.0, 47.0), 1),
            "poeOnCount": poe_on,
            "healthyFloorW": 55.0,
            "underPowered": total > 0 and total < 55.0,
            "portMaxW": 25.5,
            # Per-port readings must account for what the card says it draws.
            # Demo is self-consistent by construction, so this always passes;
            # it exists so the integrity-footnote path has a field to read.
            "portSumW": consumed,
            "portSumOk": True,
        },
        "ports": ports,
    }


def _demo_network_capture(**kw):
    """Demo payload for the Advanced Diagnostics packet-capture card.

    Kept faithful to what the real collector can actually report on the fleet
    image, because the previous version of this payload is why a completely
    broken card looked healthy for so long: it invented a full set of stats and
    top talkers, so demo mode showed a working capture while every real VPU
    returned a pktmon parameter error. Two invariants from the live script are
    preserved here.

    Packet totals come from the NIC counters while the decoded count comes from
    the capture file, so inspected is always a subset of the total -- never a
    separate roll of the dice that can exceed it. And tcpSyns stays 0 because
    pktmon on Windows 1809 never logs an outbound SYN; a demo showing 94 of
    them would re-hide exactly the kind of defect this payload once masked.
    """
    total = random.randint(1800, 4200)
    inspected = int(total * random.uniform(0.85, 1.0))
    retransmits = random.randint(0, 6)
    if retransmits > 0:
        findings = [{
            "severity": "info",
            "title": f"{retransmits} TCP retransmission(s) detected",
            "body": "Minor retransmissions. These only matter if they are sustained.",
        }]
    else:
        findings = [{
            "severity": "pass",
            "title": "No issues detected",
            "body": f"Inspected {inspected} packets over 30s with no retransmissions, resets, or drops.",
        }]
    return {
        "durationSec": int((kw or {}).get("DurationSec", 30)),
        # Demo stands in for a patched VPU, which is the only kind that can
        # capture packets. Unpatched units return captureMode "counters" with
        # nulls for everything the October 2018 packet monitor cannot measure.
        "captureMode": "capture",
        "osBuild": "17763.8880",
        "totalPackets": total,
        "inspectedPackets": inspected,
        "droppedPackets": 0,
        "tcpRetransmits": retransmits,
        "tcpResets": 0,
        "tcpSyns": 0,
        "tcpSynAcks": random.randint(40, 120),
        "tcpFins": random.randint(20, 60),
        "topTalkers": [
            {"remoteAddr": "52.20.181.46", "remotePort": 1935, "remoteHost": "live.pixellot.tv", "packets": random.randint(600, 1500)},
            {"remoteAddr": "52.217.44.54", "remotePort": 443, "remoteHost": "software.pixellot.tv", "packets": random.randint(300, 800)},
            {"remoteAddr": "52.20.181.44", "remotePort": 443, "remoteHost": "api.pixellot.tv", "packets": random.randint(100, 400)},
            {"remoteAddr": "52.20.181.45", "remotePort": 443, "remoteHost": "cloud.pixellot.tv", "packets": random.randint(80, 300)},
            {"remoteAddr": "76.76.21.21", "remotePort": 443, "remoteHost": "service.singular.live", "packets": random.randint(20, 80)},
        ],
        "findings": findings,
    }


DEMO = {
    "Get-SystemIdentity.ps1": lambda **kw: {
        "computerSystem": {"name": _VENUE["hostname"], "manufacturer": "HP", "model": "HP Z2 Tower G9 Workstation Desktop PC"},
        "bios": {"serialNumber": _VENUE["serial"]},
        "uptime": {"formatted": _fmt_uptime(_uptime_secs()), "totalSeconds": _uptime_secs()},
        # LTSC 2019 (1809, build 17763) — EOS Jan 2029, well clear of the EOL
        # warning window so the demo dashboard stays clean. (Older LTSC build
        # 19044 here used to trigger the "OS EOL approaching" finding.)
        "operatingSystem": {"caption": "Microsoft Windows 10 IoT Enterprise LTSC 2019", "version": "10.0.17763", "buildNumber": "17763", "osArchitecture": "64-bit", "installDate": "2024-01-15T08:00:00.0000000-05:00"},
        "pixellot": {
            "version": _VENUE["swVersion"],
            "imageVersion": _VENUE["imageVersion"],
            "vpuName": _VENUE["vpuName"],
            "venueId": _VENUE["venueId"],
        },
        "isNonVpuHost": False,
        "timezone": "(UTC-05:00) Eastern Time (US & Canada)",
        "timezoneId": "Eastern Standard Time",
        "locale": "en-US",
    },
    "Get-Performance.ps1": lambda **kw: {
        "cpu": {"usagePercent": round(28 + random.uniform(-8, 15), 1)},
        "memory": {"usedPercent": round(58 + random.uniform(-5, 10), 1), "totalGB": 16, "usedGB": round(9.3 + random.uniform(-0.5, 1.0), 1)},
        # All-fixed-volumes aggregate (C: ~62% of 465 GB + D: ~25% of 953 GB
        # ≈ 37%). Deliberately differs from C:'s own 62% so the demo reproduces
        # the real-VPU bug: the dashboard gauge must show C: (62%), not this
        # aggregate. See _systemDiskPct() in app.js.
        "disk": {"usedPercent": round(37 + random.uniform(-1, 2), 1)},
        "temperature": {"celsius": round(47 + random.uniform(-3, 8), 0)},
    },
    # Averaged CPU/mem for the Stream Readiness engine (F17/F19). Tighter
    # spread than the snapshot above — it's a multi-second average, so it sits
    # comfortably under the 90% sustained-WARN bar.
    "Get-PerfSample.ps1": lambda **kw: {
        "cpuAvgPercent": round(30 + random.uniform(-5, 6), 1),
        "memAvgPercent": round(59 + random.uniform(-4, 5), 1),
        "sampleCount": 3,
        "windowSeconds": 3,
    },
    "Get-Services.ps1": lambda **kw: {
        # Core Pixellot components are PROCESSES in C:\Pixellot\Bin (kind=process),
        # not Windows services — detected by process, no SCM start type.
        # ScoreConnect + LogMeIn are real Windows services (kind=service).
        "services": [
            # ── Demo: Agent deliberately STOPPED to drive a single, narrative-
            # clean CRITICAL finding ("Pixellot Agent process not running").
            # This is the demo's "click finding → jump to tab → one-click
            # restart" moment. Flip back to "Running" if you want a fully-
            # green dashboard.
            {"name": "agent", "displayName": "Pixellot Agent", "status": "Running", "startType": None,
             "kind": "process", "pid": 11324, "path": "C:\\Pixellot\\Bin\\Agent.exe", "memoryMB": 184, "watchdog": False},
            {"name": "coordinator", "displayName": "Pixellot Coordinator", "status": "Running", "startType": None,
             "kind": "process", "pid": 10596, "path": "C:\\Pixellot\\Bin\\Coordinator.exe", "memoryMB": 15, "watchdog": False},
            {"name": "vpu", "displayName": "Pixellot VPU", "status": "Running", "startType": None,
             "kind": "process", "pid": 12044, "path": "C:\\Pixellot\\Bin\\vpu.exe", "memoryMB": 240, "watchdog": False},
            {"name": "keepagentup", "displayName": "Pixellot Watchdog (KeepAgentUp)", "status": "Running", "startType": None,
             "kind": "process", "pid": 9940, "path": "C:\\Pixellot\\Bin\\KeepAgentUp.exe", "memoryMB": 9, "watchdog": True},
            # Real SCM identity of an SC III box: service name "ScoreConnectIII",
            # display "Sportzcast ScoreConnect III". The collector probes the
            # versioned names (SC I/II/III) and reports whichever is installed.
            {"name": "ScoreConnectIII", "displayName": "Sportzcast ScoreConnect III", "status": "Running", "startType": "Automatic",
             "kind": "service", "pid": None, "path": None, "memoryMB": None, "watchdog": False},
            {"name": "LogMeIn", "displayName": "LogMeIn Remote Access", "status": "Running", "startType": "Automatic",
             "kind": "service", "pid": None, "path": None, "memoryMB": None, "watchdog": False},
        ]
    },
    "Get-NicAdapters.ps1": lambda **kw: {
        "ports": [
            {"name": "Ethernet 1", "interfaceDescription": "Intel(R) I210 Gigabit Network Connection", "status": "Up", "linkSpeedMbps": 1000, "fullDuplex": True, "mac": "A4:4C:C8:12:34:01",
             "rxBytes": 82749103726, "txBytes": 5283910234, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0,
             "arpEntries": [{"ip": "192.168.10.100", "mac": "00:0E:53:AA:01:01"}, {"ip": "192.168.10.101", "mac": "00:0E:53:AA:01:02"}, {"ip": "192.168.10.102", "mac": "00:0E:53:AA:01:03"}]},
            # Ethernet 2 deliberately negotiated to 100 Mbps with main-camera
            # MACs (00:0E:53 OUI). The new finding logic flags this as
            # degraded — the OCR-OUI heuristic only spares ports where every
            # Pixellot MAC is Dynacolor (00:D0:89).
            {"name": "Ethernet 2", "interfaceDescription": "Intel(R) I210 Gigabit Network Connection #2", "status": "Up", "linkSpeedMbps": 100, "fullDuplex": True, "mac": "A4:4C:C8:12:34:02",
             "rxBytes": 18238473625, "txBytes": 1283746281, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0,
             "arpEntries": [{"ip": "192.168.11.100", "mac": "00:0E:53:BB:02:01"}, {"ip": "192.168.11.101", "mac": "00:0E:53:BB:02:02"}]},
            # Ethernet 3 is the OCR / scoreboard camera. OCR cameras are
             # natively 100 Mbps, so this is HEALTHY (not degraded). Uses the
             # default-OCR link-local IP convention (169.254.16.52/53/60) so
             # the dashboard correctly identifies it as OCR and skips the
             # "below gigabit" warning for this port.
            {"name": "Ethernet 3", "interfaceDescription": "Intel(R) I210 Gigabit Network Connection #3", "status": "Up", "linkSpeedMbps": 100, "fullDuplex": True, "mac": "A4:4C:C8:12:34:03",
             "rxBytes": 1028374, "txBytes": 293847, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0,
             "arpEntries": [{"ip": "169.254.16.52", "mac": "00:D0:89:1B:03:01"}]},
            # Port 4 demoed as a dead link (cable unplugged) so the no-link
            # down-port tile + Fault Isolator no-link path are exercisable in
            # demo. status=Disconnected + adminStatus=Up + driver OK →
            # _derive_down_reason() == "no-link".
            {"name": "Ethernet 4 (Uplink)", "interfaceDescription": "Intel(R) I211 Gigabit Network Connection", "status": "Disconnected", "adminStatus": "Up", "mediaConnectionState": "Disconnected", "driverStatus": "OK", "linkSpeedMbps": 0, "fullDuplex": False, "mac": "A4:4C:C8:12:34:04",
             "rxBytes": 129384756012, "txBytes": 98273640182, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0,
             "arpEntries": []},
        ]
    },
    "Get-PoePower.ps1": lambda **kw: _demo_poe_power(),
    "Get-Hardware.ps1": lambda **kw: {
        "processors": [{"name": "Intel(R) Core(TM) i5-10500 CPU @ 3.10GHz", "numberOfCores": 6, "numberOfLogicalProcessors": 12, "maxClockSpeedMHz": 3100}],
        "memory": [
            {"capacityGB": 16, "speedMHz": 3200, "memoryType": "DDR4", "deviceLocator": "DIMM_A1"},
            {"capacityGB": 16, "speedMHz": 3200, "memoryType": "DDR4", "deviceLocator": "DIMM_B1"},
        ],
        "gpus": [
            {"name": "Intel(R) UHD Graphics 630", "adapterRAMMB": 1024, "driverVersion": "27.20.100.8935",
             "adapterCompatibility": "Intel Corporation", "vendor": "Intel", "isDedicated": False},
            # Ampere-arch GPU (RTX 3060) so the Pixellot version × hardware
            # compat check passes — Ampere has no version cap. (Was GTX 1070
            # = Pascal, capped at 5.2.x, which conflicted with the 5.13.x
            # swVersion the demo venues use and produced a CRITICAL finding.)
            {"name": "NVIDIA GeForce RTX 3060", "adapterRAMMB": 12288, "driverVersion": "31.0.15.5212",
             "adapterCompatibility": "NVIDIA", "vendor": "NVIDIA", "isDedicated": True},
        ],
        "diskDrives": [
            {"model": "Samsung SSD 870 EVO 500GB", "sizeGB": 500, "interfaceType": "SATA", "serialNumber": "S3Z8NB0K901234A"}
        ],
    },
    "Get-UsersAndDomains.ps1": lambda **kw: {
        "domain": {
            "computerName": _VENUE["hostname"],
            "partOfDomain": False,
            "domain": None,
            "workgroup": "WORKGROUP",
            "role": "Standalone Workstation",
            "currentUser": f"{_VENUE['hostname']}\\pixellot",
        },
        "users": [
            {"name": "pixellot", "fullName": "Pixellot Service", "enabled": True, "isAdmin": True, "lockedOut": False, "rid": 1001},
            {"name": "Administrator", "fullName": None, "enabled": False, "isAdmin": True, "lockedOut": False, "rid": 500},
            {"name": "support", "fullName": "PlayOn Field Support", "enabled": True, "isAdmin": False, "lockedOut": False, "rid": 1002},
            {"name": "Guest", "fullName": None, "enabled": False, "isAdmin": False, "lockedOut": False, "rid": 501},
        ],
        "userCount": 4,
        "adminCount": 2,
        "diagnostics": {"usersError": None, "domainError": None},
    },
    "Get-Peripherals.ps1": lambda **kw: {
        "mouse":    {"connected": True,  "count": 1, "devices": ["HID-compliant mouse"], "error": None},
        "keyboard": {"connected": True,  "count": 1, "devices": ["HID Keyboard Device"], "error": None},
        # Headless is common for VPUs — demo shows no monitor so the
        # not-connected state is visible.
        "monitor":  {"connected": False, "count": 0, "displays": [], "source": "pnp", "error": None},
    },
    "Get-InstalledSoftware.ps1": lambda **kw: {
        "count": 10,
        "software": [
            {"displayName": "Pixellot VPU Agent", "displayVersion": _VENUE["swVersion"], "publisher": "Pixellot Ltd."},
            {"displayName": "Pixellot VPU Engine", "displayVersion": _VENUE["swVersion"], "publisher": "Pixellot Ltd."},
            {"displayName": "Pixellot Encoder", "displayVersion": "3.8.0", "publisher": "Pixellot Ltd."},
            {"displayName": "Google Chrome", "displayVersion": "120.0.6099.130", "publisher": "Google LLC"},
            {"displayName": "LogMeIn", "displayVersion": "4.1.0.14083", "publisher": "LogMeIn, Inc."},
            {"displayName": "Microsoft Visual C++ 2019 Redistributable (x64)", "displayVersion": "14.29.30139", "publisher": "Microsoft"},
            {"displayName": "Microsoft .NET Runtime - 6.0.25", "displayVersion": "6.0.25", "publisher": "Microsoft"},
            {"displayName": "Intel(R) Network Connections", "displayVersion": "27.2", "publisher": "Intel"},
            {"displayName": "7-Zip 23.01 (x64)", "displayVersion": "23.01", "publisher": "Igor Pavlov"},
            {"displayName": "TightVNC", "displayVersion": "2.8.81", "publisher": "GlavSoft LLC."},
            # ── To exercise the "unsupported security software" or
            # "non-standard remote-access tool" findings, add (e.g.)
            # CrowdStrike Falcon Sensor or TeamViewer here. Kept OUT of the
            # default demo so the dashboard stays narrative-clean.
        ],
    },
    "Get-NetworkConfig.ps1": lambda **kw: {
        # Healthy wiring: internet on the motherboard port (onboard I219-LM on
        # PCI bus 0), cameras on the dedicated 4-port NIC card (I210 on PCI buses
        # 1-3), Wi-Fi card enabled (for the Pixellot Connect app). pciBus is what
        # separates the motherboard uplink from a camera port, and physicalMediaType
        # picks out Wi-Fi — see _adapter_role in main.py.
        #   • To DEMO the "internet on a camera port" critical: flip Ethernet 1's
        #     status to "Up", give its ipConfig a gateway (e.g. _VENUE["gatewayIp"]),
        #     and set Ethernet 4 status to "Disconnected".
        #   • To DEMO the "Wi-Fi card disabled" warning: set the Wi-Fi adapter's
        #     status to "Disabled" and adminStatus to "Down".
        "adapters": [
            {"name": "Ethernet 4 (Uplink)", "interfaceDescription": "Intel(R) Ethernet Connection (7) I219-LM", "status": "Up", "adminStatus": "Up", "mediaConnectionState": "Connected", "physicalMediaType": "802.3", "macAddress": "A0-36-9F-11-22-33", "linkSpeed": "1 Gbps", "interfaceIndex": 4, "pnpDeviceId": "PCI\\VEN_8086&DEV_15BB&SUBSYS_83E0103C&REV_10\\3&11583659&3&FE", "pciBus": 0, "pciDevice": 31, "pciFunction": 6, "fullDuplex": True, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0},
            {"name": "Ethernet 1", "interfaceDescription": "Intel(R) I210 Gigabit Network Connection", "status": "Up", "adminStatus": "Up", "mediaConnectionState": "Connected", "physicalMediaType": "802.3", "macAddress": "A0-36-9F-AA-BB-CC", "linkSpeed": "100 Mbps", "interfaceIndex": 1, "pnpDeviceId": "PCI\\VEN_8086&DEV_1533&SUBSYS_00000000&REV_03\\003064FFFF30C7E600", "pciBus": 1, "pciDevice": 0, "pciFunction": 0, "fullDuplex": True, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0},
            {"name": "Ethernet 2", "interfaceDescription": "Intel(R) I210 Gigabit Network Connection #2", "status": "Up", "adminStatus": "Up", "mediaConnectionState": "Connected", "physicalMediaType": "802.3", "macAddress": "A0-36-9F-DD-EE-FF", "linkSpeed": "100 Mbps", "interfaceIndex": 2, "pnpDeviceId": "PCI\\VEN_8086&DEV_1533&SUBSYS_00000000&REV_03\\003064FFFF30C7E700", "pciBus": 2, "pciDevice": 0, "pciFunction": 0, "fullDuplex": True, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0},
            {"name": "Ethernet 3", "interfaceDescription": "Intel(R) I350 Gigabit Network Connection", "status": "Down", "adminStatus": "Up", "mediaConnectionState": "Disconnected", "physicalMediaType": "802.3", "macAddress": "A0-36-9F-00-11-22", "linkSpeed": "", "interfaceIndex": 3, "pnpDeviceId": "PCI\\VEN_8086&DEV_1521&SUBSYS_00000000&REV_01\\003064FFFF30C7E800", "pciBus": 3, "pciDevice": 0, "pciFunction": 0, "fullDuplex": None, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0},
            {"name": "Wi-Fi", "interfaceDescription": "Intel(R) Wireless-AC 9560 160MHz", "status": "Up", "adminStatus": "Up", "mediaConnectionState": "Connected", "physicalMediaType": "Native 802.11", "macAddress": "C8-58-C0-39-4D-D8", "linkSpeed": "866.7 Mbps", "interfaceIndex": 33, "pnpDeviceId": "PCI\\VEN_8086&DEV_A370&SUBSYS_00348086&REV_10\\3&11583659&3&A3", "pciBus": 0, "pciDevice": 20, "pciFunction": 3},
        ],
        "ipConfigurations": [
            {"interfaceAlias": "Ethernet 4 (Uplink)", "interfaceIndex": 4, "ipv4Address": [_VENUE["uplinkIp"]], "ipv4DefaultGateway": [_VENUE["gatewayIp"]], "dnsServers": ["8.8.8.8", "8.8.4.4"], "dhcpEnabled": True, "prefixLength": 24},
            {"interfaceAlias": "Ethernet 1", "interfaceIndex": 1, "ipv4Address": ["192.168.10.1"], "ipv4DefaultGateway": [], "dnsServers": [], "dhcpEnabled": False, "prefixLength": 24},
            {"interfaceAlias": "Ethernet 2", "interfaceIndex": 2, "ipv4Address": ["192.168.11.1"], "ipv4DefaultGateway": [], "dnsServers": [], "dhcpEnabled": False, "prefixLength": 24},
            {"interfaceAlias": "Ethernet 3", "interfaceIndex": 3, "ipv4Address": ["192.168.12.1"], "ipv4DefaultGateway": [], "dnsServers": [], "dhcpEnabled": False, "prefixLength": 24},
        ],
        "uplinkAdapter": {"interfaceAlias": "Ethernet 4 (Uplink)", "gateway": _VENUE["gatewayIp"], "interfaceIndex": 4},
        "uplinkStats": {"fullDuplex": True, "rxBytes": 129384756012, "txBytes": 98273640182, "rxErrors": 0, "txErrors": 0, "rxPacketErrors": 0, "rxDiscards": 0, "txPacketErrors": 0, "txDiscards": 0},
        "internet": {"reachable": True, "testedHost": "8.8.8.8"},
        "ntpSource": "0.us.pool.ntp.org",
    },
    "Test-NetworkDomains.ps1": lambda **kw: {
        "results": [
            {"domain": "nfhsnetwork.com", "resolvedTo": "52.20.181.43", "status": "pass", "resolutionMs": round(random.uniform(8, 25), 1)},
            {"domain": "pixellot.tv", "resolvedTo": "52.20.181.44", "status": "pass", "resolutionMs": round(random.uniform(5, 18), 1)},
            {"domain": "software.pixellot.tv", "resolvedTo": "52.20.181.45", "status": "pass", "resolutionMs": round(random.uniform(6, 20), 1)},
            {"domain": "sportzcast.net", "resolvedTo": "104.26.11.87", "status": "pass", "resolutionMs": round(random.uniform(10, 35), 1)},
            {"domain": "service.singular.live", "resolvedTo": "76.76.21.21", "status": "pass", "resolutionMs": round(random.uniform(12, 40), 1)},
            {"domain": "logmein.com", "resolvedTo": "216.52.233.2", "status": "pass", "resolutionMs": round(random.uniform(5, 15), 1)},
        ]
    },
    "Test-NetworkPorts.ps1": lambda **kw: {
        "results": [
            # Required — core Pixellot streaming + cloud services
            {"purpose": "DNS", "host": "8.8.8.8", "port": 53, "protocol": "UDP", "status": "pass", "optional": False},
            {"purpose": "Pixellot", "host": "pixellot.tv", "port": 443, "protocol": "TCP", "status": "pass", "optional": False},
            {"purpose": "Pixellot Echo", "host": "prod-echo.pixellot.tv", "port": 443, "protocol": "TCP", "status": "pass", "optional": False},
            {"purpose": "NFHS Network", "host": "nfhsnetwork.com", "port": 443, "protocol": "TCP", "status": "pass", "optional": False},
            {"purpose": "Singular Overlay", "host": "service.singular.live", "port": 443, "protocol": "TCP", "status": "pass", "optional": False},
            {"purpose": "LogMeIn", "host": "secure.logmein.com", "port": 443, "protocol": "TCP", "status": "pass", "optional": False},
            {"purpose": "NTP", "host": "prod-echo.pixellot.tv", "port": 123, "protocol": "UDP", "status": "pass", "optional": False},
            # Demo: both Zixi/UDP streaming rungs are blocked but the RTMP
            # fallback (TCP/1935) is open — the DEGRADED tier: games air ~4 min
            # late on unprotected RTMP. Exercises the critical "Streaming is
            # degraded — running on the emergency fallback" (the Olympic WA
            # 2026-08-18 scenario). Other tiers to demo: set one Zixi row to
            # "pass" for the healthy-with-reduced-resiliency warning; set RTMP
            # Fallback to "fail" too for the true "can't broadcast" critical.
            {"purpose": "Zixi Backup", "host": "prod-echo.pixellot.tv", "port": 443, "protocol": "UDP", "status": "fail", "optional": False},
            {"purpose": "Zixi Streaming", "host": "prod-echo.pixellot.tv", "port": 2088, "protocol": "UDP", "status": "fail", "optional": False},
            # Required — RTMP fallback egress (last streaming rung; probed
            # against a stable public RTMP host, see Test-NetworkPorts.ps1)
            {"purpose": "RTMP Fallback", "host": "a.rtmp.youtube.com", "port": 1935, "protocol": "TCP", "status": "pass", "optional": False},
            # Optional — Sportzcast Scorebot range (ScoreConnect deployments only)
            {"purpose": "Scorebot", "host": "scorebot.sportzcast.net", "port": 1400, "protocol": "TCP", "status": "pass", "optional": True},
            {"purpose": "Scorebot", "host": "scorebot.sportzcast.net", "port": 1401, "protocol": "TCP", "status": "pass", "optional": True},
            {"purpose": "Scorebot", "host": "scorebot.sportzcast.net", "port": 1402, "protocol": "TCP", "status": "pass", "optional": True},
            {"purpose": "Scorebot", "host": "scorebot.sportzcast.net", "port": 1403, "protocol": "TCP", "status": "pass", "optional": True},
            {"purpose": "Scorebot", "host": "scorebot.sportzcast.net", "port": 1404, "protocol": "TCP", "status": "pass", "optional": True},
            {"purpose": "Scorebot", "host": "scorebot.sportzcast.net", "port": 1405, "protocol": "TCP", "status": "pass", "optional": True},
        ]
    },
    # SSL-inspection detector — every service presents a public-CA cert that
    # chains to a trusted root. To DEMO the "firewall is intercepting secure
    # connections" critical (the Kent School District signature: video up,
    # graphics down), flip the singular.live rows: set status "intercepted",
    # trusted False, chainErrors "UntrustedRoot", and issuer/issuerCn/issuerOrg
    # to the DPI box (e.g. issuerCn "KSD-FW1-DPI", issuerOrg "Kent School
    # District"); optionally set one row to "handshake-fail" (schannel refusing
    # the interception) and add the device to interceptorIssuers, e.g.
    # ["KSD-FW1-DPI (Kent School District)"]. To DEMO the wrong-clock warning,
    # set a row's status to "cert-time" with chainErrors "NotTimeValid".
    #
    # To DEMO the OTHER middlebox failure - a content filter blocking the
    # domain by category (Linewize, Ohio venue 2026-08-19: no cert is
    # substituted, the handshake is just reset) - set the affected rows to
    # status "filtered", failureKind "reset", trusted None, detail "An
    # existing connection was forcibly closed by the remote host", and on the
    # first few rows filterVendor "Linewize / Family Zone" + blockPageHost
    # "blocked.syd-1.linewize.net" + a blockPageUrl; then set the top-level
    # "filterVendors" to ["Linewize / Family Zone"]. That is the case that
    # scored a green PASS before the tls-filtered finding existed.
    "Test-TlsInspection.ps1": lambda **kw: {
        "results": [
            {"domain": "singular.live", "purpose": "Singular graphics (apex)", "status": "pass", "trusted": True, "issuer": "CN=WE1, O=Google Trust Services, C=US", "issuerCn": "WE1", "issuerOrg": "Google Trust Services", "subjectCn": "singular.live", "chainErrors": "", "notAfter": "2026-09-28", "latencyMs": round(random.uniform(80, 220), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "app.singular.live", "purpose": "Singular graphics app", "status": "pass", "trusted": True, "issuer": "CN=WE1, O=Google Trust Services, C=US", "issuerCn": "WE1", "issuerOrg": "Google Trust Services", "subjectCn": "app.singular.live", "chainErrors": "", "notAfter": "2026-09-28", "latencyMs": round(random.uniform(80, 220), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "api.singular.live", "purpose": "Singular graphics API", "status": "pass", "trusted": True, "issuer": "CN=WE1, O=Google Trust Services, C=US", "issuerCn": "WE1", "issuerOrg": "Google Trust Services", "subjectCn": "api.singular.live", "chainErrors": "", "notAfter": "2026-09-28", "latencyMs": round(random.uniform(80, 220), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "datastream.singular.live", "purpose": "Singular graphics data feed", "status": "pass", "trusted": True, "issuer": "CN=WE1, O=Google Trust Services, C=US", "issuerCn": "WE1", "issuerOrg": "Google Trust Services", "subjectCn": "datastream.singular.live", "chainErrors": "", "notAfter": "2026-09-28", "latencyMs": round(random.uniform(80, 220), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "service.singular.live", "purpose": "Singular overlay service", "status": "pass", "trusted": True, "issuer": "CN=R11, O=Let's Encrypt, C=US", "issuerCn": "R11", "issuerOrg": "Let's Encrypt", "subjectCn": "service.singular.live", "chainErrors": "", "notAfter": "2026-08-30", "latencyMs": round(random.uniform(80, 220), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "pixellot.tv", "purpose": "Pixellot cloud", "status": "pass", "trusted": True, "issuer": "CN=Amazon RSA 2048 M02, O=Amazon, C=US", "issuerCn": "Amazon RSA 2048 M02", "issuerOrg": "Amazon", "subjectCn": "pixellot.tv", "chainErrors": "", "notAfter": "2027-01-12", "latencyMs": round(random.uniform(60, 180), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "software.pixellot.tv", "purpose": "Pixellot software updates", "status": "pass", "trusted": True, "issuer": "CN=Amazon RSA 2048 M02, O=Amazon, C=US", "issuerCn": "Amazon RSA 2048 M02", "issuerOrg": "Amazon", "subjectCn": "software.pixellot.tv", "chainErrors": "", "notAfter": "2027-01-12", "latencyMs": round(random.uniform(60, 180), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "nfhsnetwork.com", "purpose": "NFHS Network", "status": "pass", "trusted": True, "issuer": "CN=Amazon RSA 2048 M03, O=Amazon, C=US", "issuerCn": "Amazon RSA 2048 M03", "issuerOrg": "Amazon", "subjectCn": "nfhsnetwork.com", "chainErrors": "", "notAfter": "2026-11-02", "latencyMs": round(random.uniform(60, 180), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "secure.logmein.com", "purpose": "Remote support (LogMeIn)", "status": "pass", "trusted": True, "issuer": "CN=DigiCert TLS RSA SHA256 2020 CA1, O=DigiCert Inc, C=US", "issuerCn": "DigiCert TLS RSA SHA256 2020 CA1", "issuerOrg": "DigiCert Inc", "subjectCn": "*.logmein.com", "chainErrors": "", "notAfter": "2026-10-15", "latencyMs": round(random.uniform(60, 180), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
            {"domain": "www.python.org", "purpose": "Pulse installer download", "status": "pass", "trusted": True, "issuer": "CN=GlobalSign Atlas R3 DV TLS CA 2025 Q2, O=GlobalSign nv-sa, C=BE", "issuerCn": "GlobalSign Atlas R3 DV TLS CA 2025 Q2", "issuerOrg": "GlobalSign nv-sa", "subjectCn": "www.python.org", "chainErrors": "", "notAfter": "2026-09-07", "latencyMs": round(random.uniform(60, 180), 1), "detail": None, "failureKind": None, "blockPageHost": None, "blockPageUrl": None, "filterVendor": None},
        ],
        "interceptorIssuers": [],
        "filterVendors": [],
    },
    # LogMeIn service-log scan — the healthy shape: a couple of routine
    # gateway reconnects over the week, zero killed handshakes (a
    # long-connected unit logs no gateway lines at all for days; that is
    # normal, not a failure). To DEMO the "venue is killing LogMeIn's
    # connection" warning (field log 2026-08-28: a VPU dark in LMI ~16 hours),
    # set sslFailures ~201, handshakeFailures ~60, gatewayFailures ~141,
    # attempts ~142, logins 0, firstSslFailure/lastSslFailure spanning the
    # day, lastLogin None, blockedNow True, recoveredAt None. To DEMO the
    # recovered/info variant (packet inspection disabled while you watch),
    # keep the failures but set logins 1, lastLogin/recoveredAt a few minutes
    # after lastSslFailure, and blockedNow False.
    "Get-LmiGatewayLog.ps1": lambda **kw: {
        "installed": True,
        "logsFound": True,
        "logDir": "C:\\ProgramData\\LogMeIn",
        "windowDays": 7,
        "filesScanned": 8,
        "attempts": 3,
        "sslFailures": 0,
        "handshakeFailures": 0,
        "gatewayFailures": 0,
        "logins": 3,
        "firstSslFailure": None,
        "lastSslFailure": None,
        "lastLogin": (datetime.now() - timedelta(days=2, hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
        "blockedNow": False,
        "recoveredAt": None,
        "gatewayHosts": ["control.lmi-app25-04.logmein.com", "control.lmi-app25-10.logmein.com"],
    },
    "Test-NtpDrift.ps1": lambda **kw: {"offsetSeconds": round(random.uniform(-0.3, 0.5), 3), "status": "ok", "source": "0.us.pool.ntp.org", "configuredSource": "0.us.pool.ntp.org", "networkSynced": True},
    "Get-NtpPeers.ps1": lambda **kw: {
        "status": {
            "source": "0.us.pool.ntp.org",
            "sourceIp": "23.186.168.130",
            "stratum": 2,
            "stratumText": "2 (secondary reference - syncd by (S)NTP)",
            "lastSync": (datetime.now() - timedelta(minutes=12)).strftime("%-m/%-d/%Y %-I:%M:%S %p"),
            "leapIndicator": "0(no warning)",
            "rootDelay": "0.0445007s",
            "rootDispersion": "7.7799853s",
            "pollInterval": "10 (1024s)",
        },
        "peers": [
            {
                "name": "0.us.pool.ntp.org",
                "state": "Active",
                "timeRemaining": "534.1234567s",
                "mode": "3 (Client)",
                "stratum": 2,
                "stratumText": "2 (secondary reference - syncd by (S)NTP)",
                "peerPollInterval": "10 (1024s)",
                "hostPollInterval": "10 (1024s)",
                "lastSyncTimestamp": (datetime.now() - timedelta(minutes=12)).strftime("%-m/%-d/%Y %-I:%M:%S %p"),
            },
        ],
    },
    "Get-WifiAdapters.ps1": lambda **kw: {
        # Realistic wired VPU: a Wi-Fi Direct *virtual* adapter is present and
        # shows "connected" (Windows always carries one), but Ethernet holds
        # the default route. uplinkIsWifi=False, so NO warning fires — this is
        # the false-positive case the finding must not trip on.
        "anyActive": False,
        "activeCount": 0,
        "ethernetHasDefaultRoute": True,
        "uplinkIsWifi": False,
        "adapters": [
            {
                "name": "Local Area Connection* 2",
                "interfaceAlias": "Local Area Connection* 2",
                "interfaceDescription": "Microsoft Wi-Fi Direct Virtual Adapter #2",
                "macAddress": "B8-9A-2A-4C-7D-13",
                "linkSpeed": "0 bps",
                "status": "Up",
                "isUp": True,
                "isVirtual": True,
                "hasDefaultRoute": False,
                "connected": True,
                "ssid": "DIRECT-3a-DESKTOP",
                "networkCategory": "Public",
                "ipv4Connectivity": "NoTraffic",
                "ipv6Connectivity": "NoTraffic",
            },
        ],
    },
    # Raw resolution rows only — the backend (_classify_dns_row) decides what
    # counts as a discrepancy. The pixellot/CDN rows return *different public*
    # IPs (the real screenshot values) which is benign CDN/GeoDNS balancing
    # and must NOT warn; www.pixellot.tv is system-blocked (a real finding).
    "Test-DnsResolution.ps1": lambda **kw: {
        "googleServer": "8.8.8.8",
        "results": [
            {"host": "www.pixellot.tv",
             "system": {"resolvedTo": "52.1.53.61",     "status": "pass", "resolutionMs": round(random.uniform(6, 14), 1),  "error": None},
             "google": {"resolvedTo": "52.1.53.61",     "status": "pass", "resolutionMs": round(random.uniform(8, 20), 1),       "error": None}},
            {"host": "pixellot.tv",
             "system": {"resolvedTo": "52.44.182.199",  "status": "pass", "resolutionMs": round(random.uniform(6, 14), 1),  "error": None},
             "google": {"resolvedTo": "52.1.53.61",     "status": "pass", "resolutionMs": round(random.uniform(8, 16), 1),  "error": None}},
            {"host": "software.pixellot.tv",
             "system": {"resolvedTo": "143.204.160.127", "status": "pass", "resolutionMs": round(random.uniform(6, 14), 1),  "error": None},
             "google": {"resolvedTo": "143.204.160.99",  "status": "pass", "resolutionMs": round(random.uniform(8, 16), 1),  "error": None}},
            {"host": "nfhsnetwork.com",
             "system": {"resolvedTo": "143.204.160.62",  "status": "pass", "resolutionMs": round(random.uniform(6, 14), 1),  "error": None},
             "google": {"resolvedTo": "143.204.160.113", "status": "pass", "resolutionMs": round(random.uniform(8, 16), 1),  "error": None}},
        ],
    },
    "Test-LocalNetwork.ps1": lambda **kw: {
        "gateway": {"target": _VENUE["gatewayIp"], "label": "Gateway", "reachable": True, "sent": 4, "received": 4, "lossPercent": 0, "minMs": 1, "avgMs": 2, "maxMs": 4, "status": "pass"},
        "dns": {"target": "8.8.8.8", "label": "DNS Server", "reachable": True, "sent": 4, "received": 4, "lossPercent": 0, "minMs": 8, "avgMs": 12, "maxMs": 18, "status": "pass"},
    },
    "Get-DiskHealth.ps1": lambda **kw: {
        "logicalDisks": [
            {"deviceID": "C:", "freeSpaceGB": 176, "sizeGB": 465, "usedPercent": 62, "fileSystem": "NTFS"},
            # D: over the 90% gate so demo mode exercises the Storage Cleanup card.
            {"deviceID": "D:", "freeSpaceGB": 86, "sizeGB": 953, "usedPercent": 91, "fileSystem": "NTFS"},
        ],
        "physicalDisks": [
            {"friendlyName": "Samsung SSD 870 EVO 500GB", "sizeGB": 465, "mediaType": "SSD", "busType": "SATA", "serialNumber": "S3Z8NB0K901234A", "healthStatus": "Healthy", "operationalStatus": "OK",
             "smart": {"wearPercent": 11, "powerOnHours": 8423, "temperatureC": 41, "readErrorsUncorrected": 0, "writeErrorsUncorrected": 0}},
            {"friendlyName": "Samsung SSD 870 QVO 1TB", "sizeGB": 931, "mediaType": "SSD", "busType": "SATA", "serialNumber": "S5RANG0N712345B", "healthStatus": "Healthy", "operationalStatus": "OK",
             "smart": {"wearPercent": 23, "powerOnHours": 8101, "temperatureC": 44, "readErrorsUncorrected": 0, "writeErrorsUncorrected": 0}},
        ],
        "predictFailure": False,
        "pixellotPaths": [
            {"path": "C:\\Pixellot", "sizeGB": 12.4, "fileCount": 847},
            {"path": "D:\\Recordings", "sizeGB": 198.7, "fileCount": 3241},
            {"path": "D:\\Uploads", "sizeGB": 22.1, "fileCount": 156},
        ],
        "diskEvents": [{"timeCreated": (datetime.now() - timedelta(hours=6)).isoformat(), "level": "Warning", "source": "Ntfs", "eventId": 55, "message": "The file system structure on the disk is corrupt. Run chkdsk on volume D:"}],
    },
    "Get-RecordingsCleanupPreview.ps1": lambda **kw: _demo_cleanup_preview(**kw),
    "Invoke-RecordingsCleanup.ps1": lambda **kw: _demo_cleanup_result(**kw),
    "Get-EventLogs.ps1": lambda **kw: {
        "entries": [
            {"timeCreated": (datetime.now() - timedelta(hours=2)).isoformat(), "level": "Error", "source": "PixellotAgent", "eventId": 1001, "message": "Connection timeout to cloud service api.pixellot.tv - retrying in 30s"},
            {"timeCreated": (datetime.now() - timedelta(hours=1)).isoformat(), "level": "Critical", "source": "Kernel-Power", "eventId": 41, "message": "The system has rebooted without cleanly shutting down first."},
            {"timeCreated": (datetime.now() - timedelta(hours=3)).isoformat(), "level": "Warning", "source": "PixellotEncoder", "eventId": 2010, "message": "Encoder buffer underrun on Camera1 stream - 2 frames dropped"},
            {"timeCreated": (datetime.now() - timedelta(hours=5)).isoformat(), "level": "Error", "source": "Service Control Manager", "eventId": 7034, "message": "The PixellotWatchdog service terminated unexpectedly."},
            {"timeCreated": (datetime.now() - timedelta(hours=8)).isoformat(), "level": "Info", "source": "PixellotAgent", "eventId": 1000, "message": "Agent connected to cloud service successfully"},
            {"timeCreated": (datetime.now() - timedelta(hours=12)).isoformat(), "level": "Warning", "source": "PixellotVPU", "eventId": 3005, "message": "Camera2 stream quality degraded, switching to fallback bitrate"},
            {"timeCreated": (datetime.now() - timedelta(hours=24)).isoformat(), "level": "Error", "source": "PixellotEncoder", "eventId": 2001, "message": "Hardware encoder init failed, falling back to software encoding"},
        ]
    },
    "Get-RebootHistory.ps1": lambda **kw: {
        "pending": {
            "isPending": True,
            "reasons": ["Windows Update is waiting to finish"],
        },
        "lastBoot": (datetime.now() - timedelta(minutes=25)).isoformat(),
        "uptime": "0d 0h 25m",
        # The PnP task that reboots after a driver install flags reboot-required
        # — fired ~28 min ago, the "unprovoked restart shortly after logon".
        "deviceInstallRebootTaskLastRun": (datetime.now() - timedelta(minutes=28)).isoformat(),
        "count": 4,
        "history": [
            # External planned restart — empty comment proves it was NOT Pulse.
            {"time": (datetime.now() - timedelta(minutes=28)).isoformat(), "eventId": 1074,
             "kind": "restart", "category": "planned",
             "process": "C:\\Windows\\system32\\shutdown.exe (VPU)", "user": "VPU\\Pixellot",
             "reasonCode": "0x800000ff", "reasonText": "Reason not recorded by Windows",
             "comment": "", "byPulse": False, "source": "Planned - external",
             "message": "The process C:\\Windows\\system32\\shutdown.exe (VPU) has initiated the restart of computer VPU on behalf of user VPU\\Pixellot ... Reason Code: 0x800000ff  Shutdown Type: restart  Comment:"},
            # Pulse-initiated reboot — stamped comment, positively attributed.
            {"time": (datetime.now() - timedelta(days=2)).isoformat(), "eventId": 1074,
             "kind": "restart", "category": "planned",
             "process": "C:\\Windows\\system32\\shutdown.exe (VPU)", "user": "VPU\\Pixellot",
             "reasonCode": "0x80040002", "reasonText": "Other (Planned)",
             "comment": "Reboot requested from Pulse diagnostics", "byPulse": True,
             "source": "Pulse (Reboot VPU)",
             "message": "The process C:\\Windows\\system32\\shutdown.exe (VPU) has initiated the restart ... Comment: Reboot requested from Pulse diagnostics"},
            # Windows Update restart.
            {"time": (datetime.now() - timedelta(days=4)).isoformat(), "eventId": 1074,
             "kind": "restart", "category": "planned",
             "process": "C:\\Windows\\system32\\MusNotification.exe", "user": "NT AUTHORITY\\SYSTEM",
             "reasonCode": "0x80020002", "reasonText": "Operating System: Recovery (Planned)",
             "comment": "", "byPulse": False, "source": "Windows Update",
             "message": "The process MusNotification.exe has initiated the restart ... Operating System: Recovery (Planned)"},
            # Unexpected loss (power blip / hard crash).
            {"time": (datetime.now() - timedelta(days=6)).isoformat(), "eventId": 41,
             "kind": "unexpected", "category": "unexpected",
             "process": "", "user": "", "reasonCode": "", "reasonText": "",
             "comment": "", "byPulse": False,
             "source": "Unexpected (kernel-power: no clean shutdown)",
             "message": "The system has rebooted without cleanly shutting down first."},
        ],
    },
    "Get-ScoreConnectStatus.ps1": lambda **kw: _demo_scoreconnect(),
    "Get-ScoreConnectLive.ps1": lambda **kw: _demo_scoreconnect_live(),
    # Kicking off an install starts a simulated timeline (below) so the
    # install modal can be exercised end-to-end in demo mode.
    "Install-ScoreConnectIII.ps1": lambda **kw: _demo_sc3_install_start(),
    "Get-Sc3InstallStatus.ps1": lambda **kw: _demo_sc3_install_status(),
    # Protected unit: the SCM restart actions a Pulse-driven install applies.
    # Carries a real crash that SCM recovered, so the "it already saved you
    # once" evidence line renders in demo mode too.
    "Get-Sc3ServiceRecovery.ps1": lambda **kw: {
        "serviceName": "ScoreConnectIII",
        "installed": True,
        "status": "Running",
        "startType": "Auto",
        "recoveryConfigured": True,
        "resetPeriodSec": 86400,
        "actions": [
            {"type": "Restart", "delayMs": 5000},
            {"type": "Restart", "delayMs": 5000},
            {"type": "Restart", "delayMs": 30000},
        ],
        "actionSummary": "Restart after 5s, 5s, 30s",
        "crashCount": 2,
        "autoRecoveredCount": 2,
        "lastCrash": (datetime.now() - timedelta(hours=3)).isoformat(),
        "lastAutoRestart": (datetime.now() - timedelta(hours=3)).isoformat(),
        "daysBack": 7,
        "error": None,
    },
    "Get-ScoreLinkStatus.ps1": lambda **kw: {
        "connected": True, "port": "COM7", "model": "ScoreLink",
        "statusLabel": "ScoreLink device connected (COM7)",
    },
    "Get-PixellotConfig.ps1": lambda **kw: {
        # Camera firmware / tvMode / serial mirror the live CGI probe
        # (_probe_camera_ip in main.py) — Admin:1234 param.cgi, same data the
        # Canopy getFirmwareAndTvMode.ps1 pulled. ntsc_60 = US venue.
        "cameras": [
            {"section": "Camera1", "ip": "192.168.10.100", "mac": "00:0E:53:AA:01:01", "role": "Main",
             "firmwareVersion": "1.9.13", "tvMode": "ntsc_60", "serialNumber": "MC1-7741A", "model": "Pixellot SuperBowl"},
            {"section": "Camera2", "ip": "192.168.10.101", "mac": "00:0E:53:AA:01:02", "role": "Panoramic",
             "firmwareVersion": "1.9.13", "tvMode": "ntsc_60", "serialNumber": "PC2-7741B", "model": "Pixellot SuperBowl"},
            {"section": "Camera3", "ip": "192.168.10.102", "mac": "00:0E:53:AA:01:03", "role": "Tactical",
             "firmwareVersion": "1.9.13", "tvMode": "ntsc_60", "serialNumber": "TC3-7741C", "model": "Pixellot SuperBowl"},
            {"section": "Camera4", "ip": "192.168.11.100", "mac": "00:0E:53:BB:02:01", "role": "Main",
             "firmwareVersion": "1.9.13", "tvMode": "ntsc_60", "serialNumber": "MC4-9920A", "model": "Pixellot SuperBowl"},
            {"section": "Camera5", "ip": "192.168.11.101", "mac": "00:0E:53:BB:02:02", "role": "Panoramic",
             "firmwareVersion": "1.9.13", "tvMode": "ntsc_60", "serialNumber": "PC5-9920B", "model": "Pixellot SuperBowl"},
            {"section": "OCR", "ip": "192.168.12.50", "mac": "00:D0:89:1B:03:01", "role": "OCR",
             "firmwareVersion": "DC-2.4.1", "tvMode": "ntsc_60", "serialNumber": "DYN-OCR-3318", "model": "Dynacolor MPC-IPC"},
        ],
        "cameraCfgExists": True,
        # Selected HKLM:\SOFTWARE\Pixellot values (the live script dumps ALL).
        "registryConfig": {
            "version": _VENUE["swVersion"],
            "InstallPath": "C:\\Pixellot",
            "DataPath": "C:\\Pixellot\\Data",
            "imageVersion": _VENUE["imageVersion"],
            "dependencies": "5.0.0",
            "vpuName": _VENUE["vpuName"],
            "venueId": _VENUE["venueId"],
        },
        # Calibration is filesystem-presence-based (see Get-PixellotConfig.ps1).
        "calibration": {
            "multisport": {
                "calibrated": True,
                "primary": "basketball",
                "sports": [
                    {"name": "basketball", "lastCalibrated": (datetime.now() - timedelta(days=18)).isoformat()},
                    {"name": "volleyball", "lastCalibrated": (datetime.now() - timedelta(days=63)).isoformat()},
                ],
            },
            "ocr": {
                "calibrated": True,
                "lastCalibrated": (datetime.now() - timedelta(days=18)).isoformat(),
                "hasEnhancedPip": True,
                "hasInnerObjects": True,
            },
        },
    },
    # Expected main-camera count from the Coordinator log. Demo box is an
    # S2 (2 main cameras + 1 OCR), matching the Get-PixellotConfig demo.
    # vpuRunning False → idle box, so frame capture is allowed in demo.
    "Get-CameraExpectations.ps1": lambda **kw: {
        "expectedMainCameras": 2,
        "systemType": "S2",
        "vpuRunning": False,
    },
    # JAI S1 camera discovery. The demo box is a standard Dynacolor system,
    # so no S1 cameras — mirror what a non-S1 VPU returns (SDK absent).
    "Get-S1Cameras.ps1": lambda **kw: {
        "available": False,
        "reason": "JAI SDK not found (Jai_FactoryDotNet.dll absent). This VPU is not an S1 system.",
        "count": 0,
        "cameras": [],
    },
    # Single-frame capture. Demo returns plausible per-camera results with
    # placeholder thumbnail frames (one camera intentionally not streaming)
    # so the snapshot UI can be exercised without real ffmpeg.
    "Test-CameraVideo.ps1": lambda **kw: {
        "available": True,
        "results": [
            {"ip": "192.168.10.100", "label": "Main Camera 1", "ok": True,
             "codec": "h264", "frameRate": 30.0, "resolution": "3840x2160",
             "image": _demo_frame("Main Camera 1", "#1f3a5f"), "error": None,
             "luma": {"yavg": 112, "ymin": 6, "ymax": 240, "uavg": 124, "vavg": 132}},
            {"ip": "192.168.11.100", "label": "Main Camera 2", "ok": True,
             "codec": "h264", "frameRate": 30.0, "resolution": "3840x2160",
             "image": _demo_frame("Main Camera 2", "#244a36"), "error": None,
             "luma": {"yavg": 96, "ymin": 4, "ymax": 232, "uavg": 120, "vavg": 136}},
            # The OCR grabs a frame (reads "Active") but the picture is black —
            # the reported symptom. Low yavg + a near-white spot (the scoreboard)
            # drives the black-frame diagnosis.
            {"ip": "169.254.16.52", "label": "OCR", "ok": True,
             "codec": "h264", "frameRate": 10.0, "resolution": "1920x1080",
             "image": _demo_black_frame("OCR"), "error": None,
             "luma": {"yavg": 5, "ymin": 0, "ymax": 238, "uavg": 127, "vavg": 129}},
        ],
    },
    "Get-NetworkHealth.ps1": lambda **kw: {
        "tcp": {
            "retransmitsSec": round(random.uniform(0, 3.5), 2),
            "connFailures": random.randint(0, 4),
            "connResets": random.randint(0, 2),
            "established": random.randint(12, 22),
            "segsOutSec": random.randint(800, 3000),
            "segsInSec": random.randint(2000, 8000),
        },
        # Match the real script: no remoteHost (reverse DNS removed for poll-loop speed).
        "connections": [
            {"localPort": 49201, "remoteAddr": "52.20.181.44", "remotePort": 443, "state": "Established", "pid": 4120},
            {"localPort": 49205, "remoteAddr": "52.20.181.45", "remotePort": 443, "state": "Established", "pid": 4120},
            {"localPort": 49210, "remoteAddr": "52.20.181.46", "remotePort": 1935, "state": "Established", "pid": 5230},
            {"localPort": 49215, "remoteAddr": "52.217.44.54", "remotePort": 443, "state": "Established", "pid": 4120},
            {"localPort": 49220, "remoteAddr": "76.76.21.21", "remotePort": 443, "state": "Established", "pid": 6010},
            {"localPort": 49225, "remoteAddr": "216.52.233.2", "remotePort": 443, "state": "TimeWait", "pid": 0},
        ],
        "nics": [
            {"name": "intel[r] i210 gigabit network connection", "queueLen": 0, "rxErrors": 0, "txErrors": 0, "rxPktSec": random.randint(1500, 4000), "txPktSec": random.randint(200, 800)},
            {"name": "intel[r] i210 gigabit network connection _2", "queueLen": 0, "rxErrors": 0, "txErrors": 0, "rxPktSec": random.randint(800, 2000), "txPktSec": random.randint(100, 400)},
            {"name": "intel[r] i211 gigabit network connection", "queueLen": 0, "rxErrors": 0, "txErrors": 0, "rxPktSec": random.randint(400, 1200), "txPktSec": random.randint(1000, 4000)},
        ],
    },
    "Start-NetworkCapture.ps1": lambda **kw: _demo_network_capture(**kw),
    "Test-Traceroute.ps1": lambda **kw: {
        "target": (kw or {}).get("Target", "pixellot.tv"),
        "targetIp": "52.20.181.44",
        "reached": True,
        "hops": [
            {"hop": 1, "ip": _VENUE["gatewayIp"], "hostname": "gateway.local", "rttMs": 1, "status": "transit"},
            {"hop": 2, "ip": "172.16.0.1", "hostname": None, "rttMs": 3, "status": "transit"},
            {"hop": 3, "ip": "10.200.0.1", "hostname": "core-rtr-1.isp.net", "rttMs": 8, "status": "transit"},
            {"hop": 4, "ip": None, "hostname": None, "rttMs": None, "status": "timeout"},
            {"hop": 5, "ip": "72.14.215.85", "hostname": "edge-1.isp.net", "rttMs": 12, "status": "transit"},
            {"hop": 6, "ip": "108.170.248.33", "hostname": None, "rttMs": 15, "status": "transit"},
            {"hop": 7, "ip": "142.251.78.29", "hostname": None, "rttMs": 18, "status": "transit"},
            {"hop": 8, "ip": "52.20.181.44", "hostname": "ec2-52-20-181-44.compute-1.amazonaws.com", "rttMs": 22, "status": "reached"},
        ],
        "hopCount": 8,
    },
    "Restart-Service.ps1": lambda **kw: {"success": True, "message": "Service restarted successfully (demo)"},
    "Search-PixellotLogs.ps1": lambda **kw: {
        "entries": [
            {"file": "vpu_2026-05-27.log", "lineNumber": 1452,
             "level": "restart", "timestamp": "2026-05-27 14:22:11",
             "content": "[2026-05-27 14:22:11] start new log - process restart detected",
             "fileMTime": (datetime.now() - timedelta(hours=6)).isoformat(),
             "depsError": False},
            {"file": "vpu_2026-05-27.log", "lineNumber": 1453,
             "level": "fatal", "timestamp": "2026-05-27 14:22:11",
             "content": "[2026-05-27 14:22:11] FATAL: CUDNN_STATUS_EXECUTION_FAILED at inference step",
             "fileMTime": (datetime.now() - timedelta(hours=6)).isoformat(),
             "depsError": True},
            {"file": "vpu_2026-05-27.log", "lineNumber": 1454,
             "level": "error", "timestamp": "2026-05-27 14:22:12",
             "content": "[2026-05-27 14:22:12] ERROR: TensorFlow runtime initialization failed - falling back",
             "fileMTime": (datetime.now() - timedelta(hours=6)).isoformat(),
             "depsError": True},
            {"file": "agent_vpu2_2026-05-27.log", "lineNumber": 87,
             "level": "error", "timestamp": "2026-05-27 12:08:43",
             "content": "[2026-05-27 12:08:43] ERROR: failed to upload chunk 481 to leaf-uploads.s3.amazonaws.com (HTTP 503)",
             "fileMTime": (datetime.now() - timedelta(hours=8)).isoformat(),
             "depsError": False},
            {"file": "agent_vpu2_2026-05-27.log", "lineNumber": 42,
             "level": "restart", "timestamp": "2026-05-27 09:14:02",
             "content": "[2026-05-27 09:14:02] start new log - agent service initialized",
             "fileMTime": (datetime.now() - timedelta(hours=11)).isoformat(),
             "depsError": False},
        ],
        "stats": {"error": 2, "fatal": 1, "restart": 2, "total": 5},
        "depsErrorDetected": True,
        "scannedFiles": 2,
        "hoursBack": int((kw or {}).get("HoursBack", 24)),
        "truncated": False,
    },
    "Invoke-RepairTool.ps1": lambda **kw: (lambda action: {
        "action": action,
        "success": True,
        "exitCode": 0,
        "timedOut": False,
        "durationMs": {"CheckHealth": 32000, "RestoreHealth": 480000, "SfcScan": 540000, "ChkdskSchedule": 1200}.get(action, 5000),
        "command": {
            "CheckHealth": "dism.exe /Online /Cleanup-Image /CheckHealth",
            "RestoreHealth": "dism.exe /Online /Cleanup-Image /RestoreHealth",
            "SfcScan": "sfc.exe /scannow",
            "ChkdskSchedule": "cmd.exe /c echo Y | chkdsk C: /f /r",
        }.get(action, "?"),
        "stdout": {
            "CheckHealth": "Deployment Image Servicing and Management tool\nVersion: 10.0.19041.844\n\nImage Version: 10.0.19044.4046\n\n[==========================100.0%==========================]\nNo component store corruption detected.\nThe operation completed successfully.",
            "RestoreHealth": "Deployment Image Servicing and Management tool\nVersion: 10.0.19041.844\n\nImage Version: 10.0.19044.4046\n\n[==========================100.0%==========================]\nThe restore operation completed successfully.",
            "SfcScan": "Beginning system scan. This process will take some time.\n\nBeginning verification phase of system scan.\nVerification 100% complete.\n\nWindows Resource Protection did not find any integrity violations.",
            "ChkdskSchedule": "The type of the file system is NTFS.\nCannot lock current drive.\n\nChkdsk cannot run because the volume is in use by another process.\nWould you like to schedule this volume to be checked the next time the system restarts? (Y/N) y\n\nThis volume will be checked the next time the system restarts.",
        }.get(action, ""),
        "stderr": "",
        "cbsTail": [
            "2026-05-27 14:22:01, Info                  CSI    00000001 IAdvancedInstallerAwareStore_ResolvePendingTransactions called (call 1, sequence 3)",
            "2026-05-27 14:22:02, Info                  CSI    00000002@2026/5/27:18:22:02.123 CSI Transaction @0x... initialized for deployment engine with flags 00000001",
            "2026-05-27 14:22:03, Info                  CSI    00000003 Components: Reading installer dependencies (deployment engine 7.4.13)",
            "2026-05-27 14:25:48, Info                  CSI    000000a4 No corrupt component-store payload detected. Image scan completed.",
            "2026-05-27 14:25:48, Info                  CSI    000000a5 Repair operation completed. Result: 0x0",
        ],
        "cbsLogPath": "C:\\Windows\\Logs\\CBS\\CBS.log",
    })((kw or {}).get("Action", "CheckHealth")),
    "Get-GpuInfo.ps1": lambda **kw: {
        # Ampere-arch GPU (RTX 3060) — no Pixellot version cap, so the
        # compat check passes cleanly for the demo. Was a Pascal GTX 1070
        # which conflicted with the demo venues' 5.13.x Pixellot version
        # and produced a noisy CRITICAL finding for the presentation.
        # (Flip to Pascal/GTX 1070 + computeCap 6.1 to exercise the cap.)
        "gpus": [
            {"name": "Intel(R) UHD Graphics 630", "computeCap": None, "architecture": "NotNvidia", "source": "wmi"},
            {"name": "NVIDIA GeForce RTX 3060", "computeCap": "8.6", "architecture": "Ampere/Ada", "source": "nvidia-smi"},
        ],
        "primaryArchitecture": "Ampere/Ada",
        "primaryComputeCap": "8.6",
        "nvidiaSmiAvailable": True,
        "nvidiaSmiError": None,
    },
    "Get-PixellotDependencies.ps1": lambda **kw: {
        # Demo shows an outdated 4.8.0 install so the "outdated" badge state
        # is visible in demo mode. A VPU on the latest deps would report
        # 5.0.0 → "current".
        "installedVersion": "4.8.0",
        "latestKnownVersion": "5.0.0",
        "status": "outdated",
        "registryKey": "HKLM:\\SOFTWARE\\Pixellot",
        "registryValueName": "dependencies",
        "registryKeyPresent": True,
    },
    "Test-PixellotInstallState.ps1": lambda **kw: {
        "dirExists": True,
        "dir": "C:\\pixellot\\downloadedversion",
        "incomplete": False,
        "rebooting": True,
        "partFiles": [],
        "partCount": 0,
        "log": {
            "path": "C:\\pixellot\\downloadedversion\\install_log_2026-05-26.log",
            "name": "install_log_2026-05-26.log",
            "sizeKB": 42.1,
            "lastWrite": (datetime.now() - timedelta(days=2, hours=3)).isoformat(),
            "lastLine": "Install completed successfully. Rebooting...",
        },
        "message": "Last install completed cleanly. No part files remain.",
    },
    # Realistic outcome on a healthy VPU: the resident keepagentup watchdog is
    # already running, so a manual run exits 0 without restarting anything.
    # ("KeekAgentUp" is Pixellot's typo, verbatim from the real exe.)
    "Restart-PixellotAgent.ps1": lambda **kw: {
        "success": False,
        "watchdogResident": True,
        "exitCode": 0,
        "path": "C:\\pixellot\\bin\\keepagentup.exe",
        "stdout": 'KeekAgentUp Exit as another "KeekAgentUp" process is running',
        "stderr": "",
        "agentStatus": "Running (process, PID 7772)",
        "coordinatorStatus": "Running (process, PID 6140)",
        "agentPidBefore": 7772,
        "agentPidAfter": 7772,
        "message": "The keepagentup watchdog is already resident on this VPU, so this run exited without restarting anything. The agent was NOT restarted.",
    },
    "Get-AudioDevices.ps1": lambda **kw: {
        "devices": [
            {
                "id": "{0.0.1.00000000}.{a1b2c3d4-1111-2222-3333-444455556666}",
                "name": "Line In (Realtek High Definition Audio)",
                "dataFlow": "Input",
                "state": "Active",
                "formFactor": "LineLevel",
                "volume": 78,
                "muted": False,
                # Stays clearly above signal threshold (1%) so the "Signal
                # Detected" indicator doesn't flicker between frames.
                "peak": round(random.uniform(12, 32), 1),
                "isDefaultCapture": True,
                "isDefaultCaptureComms": True,
                "isDefaultRender": False,
            },
            {
                "id": "{0.0.1.00000000}.{a1b2c3d4-1111-2222-3333-444455557777}",
                "name": "Microphone (Realtek High Definition Audio)",
                "dataFlow": "Input",
                "state": "Active",
                "formFactor": "Microphone",
                "volume": 62,
                "muted": True,  # Demonstrates the muted-slider state
                "peak": round(random.uniform(0, 0.8), 1),  # always below threshold
            },
            {
                "id": "{0.0.1.00000000}.{a1b2c3d4-1111-2222-3333-444455558888}",
                "name": "Stereo Mix (Realtek High Definition Audio)",
                "dataFlow": "Input",
                "state": "Disabled",
                "formFactor": "Unknown",
                "volume": None,
                "muted": None,
                "peak": None,
            },
            {
                "id": "{0.0.0.00000000}.{b2c3d4e5-2222-3333-4444-555566667777}",
                "name": "Speakers (Realtek High Definition Audio)",
                "dataFlow": "Output",
                "state": "Active",
                "formFactor": "Speakers",
                "volume": 45,
                "muted": False,
                "peak": round(random.uniform(2, 8), 1),  # clearly above threshold
                "isDefaultCapture": False,
                "isDefaultCaptureComms": False,
                "isDefaultRender": True,
            },
            {
                "id": "{0.0.0.00000000}.{b2c3d4e5-2222-3333-4444-555566668888}",
                "name": "HDMI Audio (Intel Display Audio)",
                "dataFlow": "Output",
                "state": "Unplugged",
                "formFactor": "DigitalDisplay",
                "volume": None,
                "muted": None,
                "peak": None,
            },
            # NotPresent ghosts — Windows remembers every endpoint it has ever
            # seen; real VPUs carry dozens of these. The UI hides them, so
            # these exercise that they never render anywhere.
            {
                "id": "{0.0.1.00000000}.{c3d4e5f6-3333-4444-5555-666677778888}",
                "name": "Microphone (USB Audio CODEC)",
                "dataFlow": "Input",
                "state": "NotPresent",
                "formFactor": "Microphone",
                "volume": None,
                "muted": None,
                "peak": None,
            },
            {
                "id": "{0.0.0.00000000}.{d4e5f6a7-4444-5555-6666-777788889999}",
                "name": "",
                "dataFlow": "Output",
                "state": "NotPresent",
                "formFactor": "Unknown",
                "volume": None,
                "muted": None,
                "peak": None,
            },
        ],
        "inputCount": 2,
        "outputCount": 1,
    },
    "Set-AudioVolume.ps1": lambda **kw: {"success": True, "deviceId": (kw or {}).get("DeviceId", ""), "volume": int((kw or {}).get("Volume", 50))},
    "Get-PixellotEvents.ps1": lambda **kw: _demo_pixellot_events(),
    "Get-EventWindowSignals.ps1": lambda **kw: {
        "available": True,
        "daysBack": 21,
        "collectedAt": datetime.now().isoformat(),
        # Off-period spanning the demo "offline" event (3 days ago, 7 PM):
        # box shut down 18:40, back 22:35.
        "boots": [(_cloud_day(3) + timedelta(hours=3, minutes=35)).isoformat()],
        "shutdowns": [{
            "time": (_cloud_day(3) - timedelta(minutes=20)).isoformat(),
            "unexpected": True,
        }],
        "gpuErrors": [],
        "serviceEvents": [],
        "appCrashes": [],
        # One mid-event Agent death (KeepAgentUp recovery restart), timed
        # inside the demo "partial" event's window.
        "processRestarts": [{
            "time": (_cloud_day(9) + timedelta(minutes=55)).isoformat(),
            "process": "Agent",
        }],
    },
}


# ── Event Streaming lane (cloud-events) demo fabric ─────────────
# One coherent scenario shared by the local collector payload and the cloud
# payload (demo_cloud_events) so the merge in cloud_api produces a realistic
# timeline: three normal events, one quality blip, one partial, one failed
# test stream (never recorded locally, broadcast stuck in `scheduled`).

def _cloud_ev_id(n):
    return f"6a70c0ffeedeadbeef{n:06d}"


def _cloud_day(days_ago, hour=19):
    dt = datetime.now() - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0)


# (idx, days_ago, sport/headline, verdict-scenario)
# One event per failure class: camera/capture (failed_test), unit offline
# (offline — no recording folder is ever created), network block (netblock —
# recorded fine, nothing uploaded), plus healthy/quality/partial rows.
_CLOUD_SCENARIO = [
    {"n": 1, "days": 1, "headline": "Test Stream", "sport": None,
     "kind": "failed_test", "videoBytes": 0, "uploads": 0},
    {"n": 2, "days": 2, "headline": "Varsity Boys Basketball", "sport": "Basketball",
     "kind": "streamed", "videoBytes": 8_412_990_211, "uploads": 3},
    {"n": 5, "days": 3, "headline": "Varsity Girls Flag Football", "sport": "Flag Football",
     "kind": "offline", "videoBytes": 0, "uploads": 0},
    {"n": 3, "days": 5, "headline": "JV Girls Volleyball", "sport": "Volleyball",
     "kind": "quality", "videoBytes": 6_204_112_484, "uploads": 3},
    {"n": 6, "days": 6, "headline": "Varsity Boys Water Polo", "sport": "Water Polo",
     "kind": "netblock", "videoBytes": 5_733_881_204, "uploads": 0},
    {"n": 4, "days": 9, "headline": "Varsity Boys Soccer", "sport": "Soccer",
     "kind": "partial", "videoBytes": 2_101_733_902, "uploads": 2},
]


def _demo_pixellot_events():
    events = [
        {
            "eventId": _cloud_ev_id(s["n"]),
            "date": _cloud_day(s["days"]).strftime("%Y-%m-%d"),
            "name": s["headline"],
            "videoBytes": s["videoBytes"],
            "uploadedCount": s["uploads"],
            "folder": f"{_cloud_day(s['days']).strftime('%Y-%m-%d')}_p_{_cloud_ev_id(s['n'])}",
            "lastWriteTime": _cloud_day(s["days"]).isoformat(),
        }
        for s in _CLOUD_SCENARIO
        # the failed test never recorded, but its folder still exists (0
        # bytes); an offline box never creates a folder at all
        if s["kind"] != "offline"
    ]
    daily = [
        {
            "date": (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d"),
            "folder": (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
            + "_p_DAILYTEST"
            + (datetime.now() - timedelta(days=d)).strftime("%Y%m%d"),
        }
        for d in range(1, 8)
    ]
    return {
        "available": True,
        "recordedEventsPath": "D:\\recordedEvents",
        "daysBack": 21,
        "events": events,
        "dailyTests": daily,
    }


def demo_cloud_events(venue_id, local_events):
    """Demo counterpart of cloud_api.fetch_cloud — same payload shape."""
    now = datetime.now()

    def iso(dt):
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    eqs_by_kind = {
        "streamed": {"onAir": True, "eventDuration": True, "exposure": True,
                     "calibration": True, "focus": True, "calibrationZoomSet": True,
                     "audio": 1, "scoreboard": True, "wasManuallyEnded": False,
                     "eventScore": 1},
        "quality": {"onAir": True, "eventDuration": True, "exposure": True,
                    "calibration": True, "focus": True, "calibrationZoomSet": True,
                    "audio": 0, "scoreboard": True, "wasManuallyEnded": False,
                    "eventScore": 0.775},
        "partial": {"onAir": True, "eventDuration": False, "exposure": False,
                    "calibration": True, "focus": True, "calibrationZoomSet": True,
                    "audio": 1, "scoreboard": True, "wasManuallyEnded": False,
                    "eventScore": 0.475},
    }
    verdict_map = {
        "streamed": ("streamed", []),
        "quality": ("quality", ["Failed: audio"]),
        "partial": ("partial", [
            "Ended early",
            "Failed: exposure",
            "Agent restarted mid-event",
            "Box recorded video, so the problem is in the streaming path",
        ]),
        "failed_test": ("failed", [
            "Never went on air",
            "Box never recorded, so the problem is on the camera/capture side",
        ]),
        "offline": ("failed", [
            "Never went on air",
            "Unit was off during the event",
        ]),
        "netblock": ("failed", [
            "Never went on air",
            "Box recorded but uploaded nothing, which points to a network block",
        ]),
    }

    events = []
    failed_kinds = ("failed_test", "offline", "netblock")
    for s in _CLOUD_SCENARIO:
        start = _cloud_day(s["days"])
        verdict, reasons = verdict_map[s["kind"]]
        events.append({
            "gameKey": f"gamdemo{s['n']:07d}",
            "headline": s["headline"] if s["kind"] != "failed_test"
            else "Test Stream (unlisted)",
            "sport": s["sport"],
            "startTime": iso(start),
            "localStartTime": start.isoformat(),
            "status": "scheduled" if s["kind"] in failed_kinds else "complete",
            "hasVod": s["kind"] not in failed_kinds,
            # offline: box never even created a folder -> listed-only, no
            # local evidence. failed_test: unlisted, box-only.
            "source": "box" if s["kind"] == "failed_test"
            else "listed" if s["kind"] == "offline" else "listed+box",
            "unlisted": s["kind"] == "failed_test",
            "pixellotEventId": None if s["kind"] == "offline" else _cloud_ev_id(s["n"]),
            "broadcastKey": f"bdcdemo{s['n']:06d}",
            "local": None if s["kind"] == "offline" else {
                "recorded": s["videoBytes"] > 0,
                "videoBytes": s["videoBytes"],
                "uploadedCount": s["uploads"],
                "name": s["headline"],
            },
            "eqs": eqs_by_kind.get(s["kind"]),
            "verdict": verdict,
            "verdictReasons": reasons,
        })
    upcoming = _cloud_day(-3, hour=18)
    events.insert(0, {
        "gameKey": "gamdemo9999999",
        "headline": "Varsity Football",
        "sport": "Football",
        "startTime": iso(upcoming),
        "localStartTime": upcoming.isoformat(),
        "status": "scheduled",
        "hasVod": False,
        "source": "listed",
        "unlisted": False,
        "pixellotEventId": None,
        "local": None,
        "eqs": None,
        "verdict": "upcoming",
        "verdictReasons": [],
    })
    # A go-live in trouble right now: started 15 minutes ago, event window
    # still active, broadcast still 'scheduled' — exercises the "Unable to
    # stream" verdict a tech would see standing at the box during a failed
    # start.
    late_start = now - timedelta(minutes=15)
    events.insert(1, {
        "gameKey": "gamdemo8888888",
        "headline": "JV Boys Basketball",
        "sport": "Basketball",
        "startTime": iso(late_start),
        "localStartTime": late_start.isoformat(),
        "status": "scheduled",
        "hasVod": False,
        "source": "listed",
        "unlisted": False,
        "durationHours": 2.0,
        "pixellotEventId": None,
        "local": None,
        "eqs": None,
        "verdict": "unable",
        "verdictReasons": [
            "Event started 15 min ago, not on air yet.",
        ],
    })

    return {
        "available": True,
        "error": None,
        "errors": None,
        "producer": {
            # mirrors search-api's producer formatted_name shape:
            # "AIA: Mesquite High School, Gilbert, AZ - Field"
            "name": f"GHSA: {_VENUE['vpuName'].split(' ', 1)[1].rsplit(' (', 1)[0]}, "
                    f"{_VENUE['city']}, {_VENUE['state']} - "
                    f"{_VENUE['vpuName'].rsplit(' - ', 1)[-1]}",
            "producerKey": "pdcdemo1234567",
            "pixellotKey": "pxldemo9876543",
            "pixellotName": _VENUE["vpuName"].rsplit(" - ", 1)[-1],
            "internalStatus": "broadcasting",
            "lastStatus": "Sleep",
            "statusChangedAt": iso(now - timedelta(days=40)),
            "broadcastStatusReason": None,
            "currentSwVersion": _VENUE["swVersion"],
            "targetSwVersion": "5.14.2",
            "targetSwVersionSetDate": iso(now - timedelta(days=12)),
            "state": _VENUE["state"],
            "activationDate": "2023-08-14T16:20:00.000Z",
            "publishers": [{
                "key": "0demo77ccba",
                "name": _VENUE["vpuName"].split(" ", 1)[1].rsplit(" (", 1)[0]
                if "(" in _VENUE["vpuName"] else _VENUE["city"],
                "type": "school",
                "city": _VENUE["city"],
                "state": _VENUE["state"],
            }],
        },
        "metrics": {
            "connection": "Ok", "status": "Ok", "status_severity": "Ok",
            "darkCourt": "Error", "hdBandwidth": "Ok", "panoBandwidth": "Ok",
        },
        "eqsAvgScore": 0.8125,
        "events": events,
        "causeHints": [
            {"severity": "warning",
             "text": "Cloud reports the camera picture is dark. The camera "
                     "may be obstructed or powered off, or the room is dark",
             "page": "cameras"},
            {"severity": "info",
             "text": f"Pixellot software is behind its target "
                     f"({_VENUE['swVersion']} installed, 5.14.2 assigned)",
             "page": None},
        ],
        "generatedAt": now.isoformat(),
    }


def get_demo(script_name, args=None):
    fn = DEMO.get(script_name)
    if fn is None:
        return None
    return fn(**(args or {}))
