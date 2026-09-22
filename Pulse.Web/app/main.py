"""Pulse Web — FastAPI backend for VPU diagnostics."""

import os as _os
import sys as _sys

_app_dir = _os.path.dirname(_os.path.abspath(__file__))
if _app_dir not in _sys.path:
    _sys.path.insert(0, _app_dir)

# ── pythonw.exe console safety ───────────────────────────────
# The hidden launcher runs the server under pythonw.exe, which has NO
# console — so sys.stdout and sys.stderr are None. uvicorn's logging
# config attaches a StreamHandler to sys.stdout and raises on startup
# when it's None, so the server would import fine but never bind the
# port. Point both streams at the server log so the hidden server starts
# cleanly and uvicorn's own output is captured for the Server Log tab.
_SERVER_LOG_EARLY = _os.path.join(_os.path.dirname(_app_dir), "pulse-server.log")
try:
    open(_SERVER_LOG_EARLY, "w", encoding="utf-8").close()  # fresh log per launch
except Exception:
    pass
if _sys.stdout is None or _sys.stderr is None:
    try:
        _redir = open(_SERVER_LOG_EARLY, "a", buffering=1, encoding="utf-8", errors="replace")
        _sys.stdout = _redir
        _sys.stderr = _redir
    except Exception:
        pass

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from powershell import (
    run_ps, LOG_BUFFER, DEMO_MODE, _log as ps_log,
    get_running_tasks, cancel_task, cancel_all_tasks,
    clear_ps_cache,
)
import peer
import cloud_api

_web_root = _os.path.dirname(_app_dir)
SETTINGS_PATH = _os.path.join(_web_root, "pulse-settings.json")

# Persisted fault-isolator run history — survives reloads/restarts so a tech
# returning to a school can see prior tests (date, port, verdict, recommendation).
FAULT_HISTORY_PATH = _os.path.join(_web_root, "pulse-fault-history.json")
_FAULT_HISTORY_MAX = 50


def _load_fault_history() -> list:
    try:
        with open(FAULT_HISTORY_PATH, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_fault_history(runs: list) -> None:
    with open(FAULT_HISTORY_PATH, "w") as f:
        json.dump(runs[-_FAULT_HISTORY_MAX:], f, indent=2)


# Persisted ScoreConnect configuration history. ScoreConnect itself is
# stateless — a reconfigure (bot reassignment, vendor/sport change, reinstall)
# silently discards the previous setup. Pulse keeps an append-on-change log so
# a tech can see what this VPU was configured as before it changed.
# Snapshots are recorded passively off status collections Pulse already runs,
# and ONLY while ScoreConnect confirms scoreboard data is flowing ("Data is
# present…") — a probe of a down/idle/mid-reconfigure service records nothing.
SC_CONFIG_HISTORY_PATH = _os.path.join(_web_root, "pulse-scoreconnect-history.json")
_SC_CONFIG_HISTORY_MAX = 100

# Fields that define a distinct configuration. A change in ANY of these opens
# a new dated entry — bot reassignment included. version/firmware/scoreLinkPort
# are carried along but don't open entries: a software update isn't a
# scoreboard reconfiguration.
_SC_CONFIG_FP_FIELDS = ("vendor", "sport", "configName", "device",
                       "serialPort", "eventType", "botNumber", "scoreLinkModel")


def _load_sc_config_history() -> list:
    try:
        with open(SC_CONFIG_HISTORY_PATH, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_sc_config_history(entries: list) -> None:
    with open(SC_CONFIG_HISTORY_PATH, "w") as f:
        json.dump(entries[-_SC_CONFIG_HISTORY_MAX:], f, indent=2)


def _sc_config_snapshot(result):
    """Distill a Get-ScoreConnectStatus result into a config snapshot, or None
    when it shouldn't be recorded. Gate: SC III reachable AND reporting
    scoreboard data present — a configuration is only trusted as "the working
    setup" while data is confirmed flowing. (The zero-impact SC I/II probes
    have no data-present signal, so history records SC III only.)"""
    if not isinstance(result, dict) or not result.get("reachable"):
        return None
    if "data is present" not in str(result.get("dataStatus") or "").lower():
        return None
    cfg = result.get("configuration") or {}
    bot = result.get("botStatus") or {}
    snap = {
        "source": "ScoreConnect III",
        "version": result.get("version"),
        "vendor": cfg.get("vendor"),
        "sport": cfg.get("sport"),
        "configName": cfg.get("vendorConfigurationName"),
        "device": cfg.get("device"),
        "serialPort": cfg.get("serialPort"),
        "firmware": cfg.get("firmware"),
        "eventType": cfg.get("eventType"),
        "botNumber": bot.get("scoreConnectId"),
        "scoreLinkModel": result.get("scoreLinkModel") or None,
        "scoreLinkPort": result.get("scoreLinkPort") or None,
    }
    # Must identify a configuration — data flowing with every identifying
    # field empty (extended-config endpoint down) records nothing.
    if not any(snap[k] for k in ("vendor", "sport", "configName", "device",
                                 "serialPort", "botNumber")):
        return None
    return snap


def _record_sc_config_history(result) -> None:
    """Append-on-change: a new entry when the config fingerprint differs from
    the latest one; otherwise extend the latest entry's lastSeen, so each
    entry records the span it was the active configuration."""
    snap = _sc_config_snapshot(result)
    if snap is None:
        return
    from datetime import datetime as _dt
    now = _dt.now().isoformat(timespec="seconds")
    entries = _load_sc_config_history()

    def _fp(e):
        return tuple(str(e.get(k) or "") for k in _SC_CONFIG_FP_FIELDS)

    if entries and _fp(entries[-1]) == _fp(snap):
        latest = entries[-1]
        latest["lastSeen"] = now
        # Non-fingerprint fields track the most recent observation.
        for k in ("version", "firmware", "scoreLinkPort"):
            if snap.get(k):
                latest[k] = snap[k]
    else:
        snap["firstSeen"] = now
        snap["lastSeen"] = now
        entries.append(snap)
    _save_sc_config_history(entries)


async def _run_sc_status(sc_url: str, timeout: int = 15) -> dict:
    """Run the full ScoreConnect status collection and opportunistically
    record the configuration into the history log. Recording is best-effort —
    it must never break the status fetch itself."""
    result = await run_ps("Get-ScoreConnectStatus.ps1", {"BaseUrl": sc_url},
                          timeout=timeout)
    # Demo payloads randomise the bot number per call — logging them would
    # fabricate a config change on every fetch.
    if not DEMO_MODE:
        try:
            _record_sc_config_history(result)
        except Exception as e:
            _server_log.warning("ScoreConnect config history record failed: %s", e)
    return result

def _read_version() -> str:
    """Resolve the version string shown in the sidebar, splash and About tab.

    VERSION is the source of truth (per CLAUDE.md), and in the field it is
    always written by whichever launcher installed the box — run_pulse.bat and
    run_pulse_beta.bat write the release tag ("web-v1.0.2"), run_pulse_dev.bat
    writes "<branch>-<short-sha>" ("dev-73390dd"). All three then READ it back
    to decide whether an update is due, so it is load-bearing beyond display.
    web-build.yml also stamps it into the release zip.

    No shipped build carries a .git — verified on VPU2, which has no git binary
    installed at all — so the git branch below never runs in the field.

    git describe is only a fallback for a bare repo checkout with no VERSION.
    It describes HEAD, so it can't misreport what's actually running — the
    previous implementation asked for the newest `web-*` tag by creatordate
    repo-wide, which is unrelated to the checked-out commit and made a dev
    working tree announce itself as the latest production release.
    """
    try:
        with open(_os.path.join(_web_root, "VERSION")) as f:
            version = f.read().strip()
        if version:
            return version
    except OSError:
        pass
    import subprocess
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True,
            cwd=_os.path.dirname(_web_root), timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"

APP_VERSION = _read_version()
_static_dir = _os.path.join(_app_dir, "static")

SERVER_LOG_PATH = _os.path.join(_web_root, "pulse-server.log")

# ── Server log file ──────────────────────────────────────────
# Attach a file handler to the root logger so ANY library that logs
# (uvicorn, asyncio, fastapi, our app, third-party deps) flows into
# pulse-server.log. The Server Log tab in the UI tails this file.
#
# Append mode: the log was already truncated once at module top (see the
# pythonw console-safety block). Appending here avoids wiping uvicorn's
# startup lines and plays nicely with the stdout redirect above.
import logging as _logging
_server_log_handler = _logging.FileHandler(SERVER_LOG_PATH, mode="a", encoding="utf-8")
_server_log_handler.setLevel(_logging.INFO)
_server_log_handler.setFormatter(
    _logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                       datefmt="%Y-%m-%d %H:%M:%S")
)
_root_logger = _logging.getLogger()
_root_logger.setLevel(_logging.INFO)
_root_logger.addHandler(_server_log_handler)
_server_log = _logging.getLogger("pulse")
_server_log.info(f"pulse-server.log opened — Pulse Web bootstrap")

app = FastAPI(title="Pulse Web | VPU Diagnostics")
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

PIXELLOT_OUIS = ["00:0E:53", "00:30:53", "70:B3:D5", "00:D0:89"]

# ── US timezone allowlist ────────────────────────────────────
# VPUs must run in a US timezone for log timestamps / scheduling to line up
# with field operations. Anything off-continent (Jerusalem, UTC, Tokyo, etc.)
# breaks correlation with cloud-side event timing.
#
# Matches Windows TimeZoneInfo.StandardName values. Covers the 50 states +
# DC + Indiana/Arizona quirks. Excludes Mexico/Canada zones that share names
# with US zones, and explicitly excludes Atlantic Standard Time which is
# ambiguous (Puerto Rico is US, but Canada also uses it).
_US_TIMEZONE_IDS = {
    "Hawaiian Standard Time",          # HST (UTC-10)
    "Aleutian Standard Time",          # HAST/HADT (UTC-10/-9, Alaska Aleutians)
    "Alaskan Standard Time",           # AKST/AKDT (UTC-9/-8)
    "Pacific Standard Time",           # PST/PDT (UTC-8/-7)
    "US Mountain Standard Time",       # MST (UTC-7, Arizona — no DST)
    "Mountain Standard Time",          # MST/MDT (UTC-7/-6)
    "Central Standard Time",           # CST/CDT (UTC-6/-5)
    "US Eastern Standard Time",        # EST (UTC-5, Indiana East — no DST)
    "Eastern Standard Time",           # EST/EDT (UTC-5/-4)
}

# Fallback substrings for matching Caption strings when StandardName missing.
# Order matters — more specific first (so "Arizona" wins over "Mountain").
_US_CAPTION_HINTS = (
    "(US & Canada)",  # canonical Windows caption for the 4 main US zones
    "Hawaii",
    "Aleutian",
    "Alaska",
    "Arizona",
    "Indiana",
)


def _is_us_timezone(tz_id: str, tz_caption: str = "") -> bool:
    """True if the system is in a US timezone (50 states + DC).

    Prefers the stable StandardName (`tz_id`). Falls back to fuzzy substring
    matching on the user-visible caption for hosts that only supply that.
    Returns False for anything off-continent — Jerusalem, UTC, GMT, Mexico,
    Canada-only zones, etc.
    """
    if tz_id and tz_id in _US_TIMEZONE_IDS:
        return True
    if tz_caption:
        cap = tz_caption
        for hint in _US_CAPTION_HINTS:
            if hint in cap:
                return True
    return False


@app.on_event("startup")
async def _on_startup():
    """Log startup info to both the Script Log buffer (UI) and the
    Server Log file (pulse-server.log)."""
    msg_version = f"Pulse Web {APP_VERSION} starting"
    msg_python  = f"Python {_sys.version.split()[0]} | port {_os.environ.get('PORT', 8765)}"
    msg_mode    = f"Demo mode = {DEMO_MODE} | platform = {_sys.platform}"
    msg_paths   = f"Scripts dir = {_os.path.join(_app_dir, 'scripts')} | Settings = {SETTINGS_PATH}"
    for msg in (msg_version, msg_python, msg_mode, msg_paths):
        ps_log("server", 0, "ok", msg)
        _server_log.info(msg)

    # One-shot beta retirement (see _migrate_retired_beta). Runs before the
    # check-in so even this session's beacon reports the new channel. Cheap
    # file checks; inert everywhere but a managed beta install of a retired
    # release tag.
    _migrate_retired_beta()

    # Refresh the frozen Pulse.bat self-copy from this release's bundled
    # launcher (see _refresh_installed_launcher). Scheduled, not awaited: it
    # deliberately waits for the launcher that started us to exit first.
    try:
        asyncio.create_task(_refresh_installed_launcher(time.time()))
    except Exception:
        pass

    # Fire-and-forget run-tracking check-in (no-op until the check-in secret is
    # filled in, and never in demo/dev). Scheduled so it can't delay startup.
    try:
        asyncio.create_task(_send_checkin())
    except Exception:
        pass

    # Fire-and-forget removal of the retired Canopy Leaf agent (see
    # _remove_canopy_leaf). Scheduled so it can't delay startup; a cheap
    # folder pre-check makes it free on any already-clean unit.
    try:
        asyncio.create_task(_remove_canopy_leaf())
    except Exception:
        pass

    # Same treatment for Splashtop Streamer, deployed alongside Canopy (see
    # _remove_splashtop). Separate task because Leaf-clean units still carry
    # Splashtop.
    try:
        asyncio.create_task(_remove_splashtop())
    except Exception:
        pass

    # Close Pulse alongside the LogMeIn session that launched it (see
    # _lmi_session_watch). No-op in demo mode, off Windows, or when Pulse
    # wasn't opened from inside an LMI session.
    try:
        asyncio.create_task(_lmi_session_watch())
    except Exception:
        pass


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"scoreConnectUrl": "http://localhost:5000", "pollIntervalMs": 3000}


def save_settings(data: dict) -> None:
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── CGI probe for Dynacolor cameras (OCR + main heads) ──────────────
# Mirrors the WPF's OcrProbeService: HTTP GET to the camera's admin CGI
# returns the camera MAC, positively identifying it. OCR and main cameras
# share the same Dynacolor firmware and respond on the same endpoint.
#
# Results are cached by IP with a 30-second TTL so the 3-second live poll
# doesn't hammer the cameras. The probe runs via asyncio.to_thread to
# avoid blocking the event loop (no httpx dependency required).

import base64
import time
import urllib.request
import urllib.error
from typing import Optional

_CGI_PROBE_CACHE = {}  # ip -> {mac, ts, is_ocr}
# Short TTL so on-site troubleshooting (cable swaps, port moves) reflects
# quickly. The cache mainly protects cameras from being hammered by the
# 3-second live-refresh polling — 10s is enough for that without making
# the data feel stale.
_CGI_PROBE_TTL = 10  # seconds

# Per-NIC-port transition tracker (keyed by adapter MAC). Records the last
# observed link/camera state and when it was first seen, so we can:
#   1. show a "Connecting…" state while a freshly-changed port settles
#      (link up but camera not yet resolved), and
#   2. suppress transient degraded/error findings during that window —
#      a port mid-negotiation briefly reports 100 Mbps / errors before it
#      stabilizes, and alarming on that during a cable swap is noise.
_PORT_STATE_TRACKER = {}  # adapter_mac -> {"key", "since", "isUp", "upSince", ...}
_PORT_SETTLE_SECONDS = 8
# Startup grace for camera findings that depend on the ARP cache + CGI probe
# cache both being warm. Right after Pulse launches, the collection burst can
# starve both (neighbor entries aged out while the cameras sat quiet, probes
# timing out under the powershell fan-out), making a healthy rig look
# camera-less for exactly one collection — which fired a false CRITICAL
# "No main cameras detected" on VPU2 (2026-07-28). Within this window, a
# zero-camera reading that is contradicted by live link state is treated as
# not-yet-settled instead of alarmed on; the next collection decides.
_STARTUP_GRACE_SECONDS = 90
_PROCESS_START_MONO = time.monotonic()


def _in_startup_grace() -> bool:
    return (time.monotonic() - _PROCESS_START_MONO) < _STARTUP_GRACE_SECONDS
# How long a port shows the blue "connecting" cue after a down→up transition,
# even if its camera resolves instantly from cache. Without this, a quick
# cable reseat jumps straight gray→green and the tech never sees the
# establishing state. Kept short so it reads as a brief handshake, not a hang.
_PORT_CONNECTING_SECONDS = 6

# Frame-capture rate limit. Grabbing RTSP frames is a real pull on the
# cameras; a cooldown stops a tech from spamming the button.
# Init far in the past — monotonic() can start near 0, so 0.0 would falsely
# block the first capture for the cooldown window.
_LAST_FRAME_CAPTURE = -1e9      # time.monotonic() of the last actual capture
_FRAME_CAPTURE_COOLDOWN = 15    # seconds between captures


def _frame_cooldown_remaining(now: float) -> int:
    """Whole seconds left on the frame-capture cooldown (0 if ready)."""
    remaining = _FRAME_CAPTURE_COOLDOWN - (now - _LAST_FRAME_CAPTURE)
    return int(remaining) + 1 if remaining > 0 else 0

# Known default OCR IPs (from WPF's DefaultOcrIps + Pixellot convention)
_DEFAULT_OCR_IPS = {"169.254.16.52", "169.254.16.53", "169.254.16.60"}
# Known default main camera IPs
_DEFAULT_MAIN_IPS = {"169.254.16.50", "169.254.16.51"}

# Camera model → (role, expected link speed in Mbps)
# Used for positive hardware-based identification from CGI Brand.ProdNbr.
# Prefix-matched, so e.g. "T2SF-B_PX00" matches the "T2SF-B" key.
_CAMERA_MODELS = {
    "Z4SF-F": ("Main Camera", 1000),       # 4K main camera head
    "Z4SF-5": ("Main Camera", 1000),       # 4K main head variant (VPU2 bench unit reports this)
    "T2SF-B": ("Main Camera", 1000),       # 4K Bullet Outdoor main head
    "R2SD-G": ("OCR / Scoreboard", 100),
    "S5SD-G": ("OCR / Scoreboard", 100),
    "E8NC-G": ("OCR / Scoreboard", 1000),
}


def _lookup_camera_model(model_number: Optional[str]) -> tuple:
    """Return (role, expected_speed_mbps) for a known model, or (None, None)."""
    if not model_number:
        return None, None
    # Try exact match first, then prefix match (ProdNbr may have suffixes)
    if model_number in _CAMERA_MODELS:
        return _CAMERA_MODELS[model_number]
    for prefix, info in _CAMERA_MODELS.items():
        if model_number.startswith(prefix):
            return info
    return None, None


def _cgi_fetch_group(ip, group, headers, timeout=2.0):
    """Fetch a param.cgi group and return a flat dict of key=value pairs."""
    url = f"http://{ip}/cgi-bin/admin/param.cgi?action=list&group={group}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            result = {}
            for line in body.splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    if key.startswith("root."):
                        key = key[5:]
                    result[key] = val.strip()
            return result
    except Exception:
        return {}


def _cgi_probe_sync(ip: str, timeout: float = 2.0) -> Optional[dict]:
    """Probe a Dynacolor camera CGI endpoint for full diagnostic data.
    Pulls: MAC, brand/model, serial, firmware, network config, stream
    settings, and image sensor parameters. All queries except MAC are
    best-effort — missing data just means those fields are None.
    Runs in a thread — safe to call via asyncio.to_thread.

    Auth is the Pixellot/Dynacolor factory default (Admin / 1234). If a
    site has rotated camera credentials, probes will silently return None
    and identification falls back to ARP/cameras.cfg only.
    """
    # Demo mode can't reach the synthetic camera IPs over HTTP — serve the
    # canned probe so camerasDetected carries the full probe on a Mac.
    if DEMO_MODE:
        from demo_data import cgi_probe as _demo_cgi_probe
        return _demo_cgi_probe(ip)

    headers = {"Authorization": "Basic " + base64.b64encode(b"Admin:1234").decode()}

    # Request 1: MAC address (critical — determines if camera responds)
    mac_data = _cgi_fetch_group(ip, "Network.eth0.MACAddress", headers, timeout)
    mac = mac_data.get("Network.eth0.MACAddress")
    if not mac:
        return None

    # Request 2: Brand / model / product type
    brand = _cgi_fetch_group(ip, "Brand", headers, timeout)

    # Request 3: Firmware version + serial number
    props = _cgi_fetch_group(ip, "Properties", headers, timeout)

    # Request 4: Camera network config (IP, subnet, gateway, DHCP)
    net = _cgi_fetch_group(ip, "Network.eth0", headers, timeout)

    # Request 5: Stream encoding settings (S0 = primary H264, S1 = MJPEG)
    streams = _cgi_fetch_group(ip, "Image.I0.Appearance", headers, timeout)

    # Request 6: Image sensor / exposure settings
    sensor = _cgi_fetch_group(ip, "ImageSource.I0.Sensor", headers, timeout)

    # Request 7: Detected TV mode (ntsc_60 / pal_50). Drives frame-rate
    # expectations — a US venue camera reporting pal_50 is misconfigured.
    # (From Canopy getFirmwareAndTvMode.ps1 — same CGI endpoint as firmware.)
    video = _cgi_fetch_group(ip, "ImageSource.I0.Video.DetectedType", headers, timeout)

    def _v(d, k):
        """Get a value, return None if empty."""
        val = d.get(k, "")
        return val if val else None

    return {
        "mac": mac,
        # Device identity
        "brand": _v(brand, "Brand.Brand"),
        "model": _v(brand, "Brand.ProdFullName") or _v(brand, "Brand.ProdNbr"),
        "modelNumber": _v(brand, "Brand.ProdNbr"),
        "productType": _v(brand, "Brand.ProdType"),
        "serialNumber": _v(props, "Properties.System.SerialNumber"),
        "firmwareVersion": _v(props, "Properties.Firmware.Version"),
        "tvMode": _v(video, "ImageSource.I0.Video.DetectedType"),
        # Network
        "network": {
            "ip": _v(net, "Network.eth0.IPAddress"),
            "subnet": _v(net, "Network.eth0.SubnetMask"),
            "gateway": _v(net, "Network.eth0.DefaultRouter"),
            "dhcp": _v(net, "Network.eth0.DHCP.Enabled"),
        },
        # Stream 0 (primary — typically H264 for recording)
        "stream0": {
            "codec": _v(streams, "Image.I0.Appearance.Stream.S0.EncodeType"),
            "resolution": _v(streams, "Image.I0.Appearance.Stream.S0.Resolution"),
            "framerate": _v(streams, "Image.I0.Appearance.Stream.S0.Framerate"),
        },
        # Stream 1 (secondary — typically MJPEG for live preview)
        "stream1": {
            "enabled": _v(streams, "Image.I0.Appearance.Stream.S1.Enabled"),
            "codec": _v(streams, "Image.I0.Appearance.Stream.S1.EncodeType"),
            "resolution": _v(streams, "Image.I0.Appearance.Stream.S1.Resolution"),
            "framerate": _v(streams, "Image.I0.Appearance.Stream.S1.Framerate"),
        },
        # Image sensor tuning
        "sensor": {
            "exposure": _v(sensor, "ImageSource.I0.Sensor.Exposure"),
            "brightness": _v(sensor, "ImageSource.I0.Sensor.Brightness"),
            "contrast": _v(sensor, "ImageSource.I0.Sensor.Contrast"),
            "colorLevel": _v(sensor, "ImageSource.I0.Sensor.ColorLevel"),
            "maxShutterGain": _v(sensor, "ImageSource.I0.Sensor.Exposure.MaxShutterGain"),
            "minShutterSpeed": _v(sensor, "ImageSource.I0.Sensor.Exposure.MinShutterSpeed"),
        },
    }


async def _probe_camera_ip(ip, is_ocr_ip):
    """Probe a single camera IP, returning cached result if fresh."""
    now = time.monotonic()
    cached = _CGI_PROBE_CACHE.get(ip)
    if cached and (now - cached["ts"]) < _CGI_PROBE_TTL:
        return cached

    info = await asyncio.to_thread(_cgi_probe_sync, ip)
    if info and info.get("mac"):
        result = {
            **info,
            "mac": info["mac"].upper().replace("-", ":"),
            "ts": now,
            "is_ocr": is_ocr_ip,
            "ip": ip,
        }
        _CGI_PROBE_CACHE[ip] = result
        return result
    return None


def _collect_camera_ips(ports, ocr_ips):
    """Collect all IPs worth probing: defaults + any Pixellot ARP entries."""
    all_camera_ips = set(ocr_ips)
    all_camera_ips.update(_DEFAULT_OCR_IPS)
    all_camera_ips.update(_DEFAULT_MAIN_IPS)
    for port in ports:
        for arp in port.get("arpEntries", []):
            if _is_pixellot_mac(arp.get("mac", "")):
                ip = arp.get("ip", "").strip()
                if ip:
                    all_camera_ips.add(ip)
    return all_camera_ips


def _cached_probes_by_mac() -> dict:
    """Return the last-known probe result for every probed camera, keyed
    by MAC — regardless of age.

    A camera's CGI identity (model, serial, role) never changes, so we
    serve the last successful probe even if it's past the re-probe TTL.
    The TTL only governs WHEN we re-probe in the background, not whether
    we display what we already learned. This keeps the model badge and
    identity stable instead of flickering each time an entry ages out
    between background refreshes."""
    by_mac = {}
    for entry in list(_CGI_PROBE_CACHE.values()):
        if entry.get("mac"):
            by_mac[entry["mac"]] = entry
    return by_mac


async def _probe_all_cameras(ports, ocr_ips, block: bool = True):
    """Probe all camera IPs found in ARP entries across all ports.

    block=True  — wait for probes (used for dashboard/WS preload).
    block=False — return cached data immediately; start a fire-and-forget
                  background probe for any cold IPs. Used by /api/cameras
                  so the first paint isn't gated on slow CGI calls. The
                  next live-refresh tick picks up the new data.

    Returns a dict keyed by normalized MAC -> probe result.
    """
    all_camera_ips = _collect_camera_ips(ports, ocr_ips)

    if not block:
        now = time.monotonic()
        cold_ips = [
            ip for ip in all_camera_ips
            if (_CGI_PROBE_CACHE.get(ip) is None
                or (now - _CGI_PROBE_CACHE[ip]["ts"]) >= _CGI_PROBE_TTL)
        ]
        if cold_ips:
            async def _warm_cache():
                tasks = [
                    _probe_camera_ip(
                        ip, ip in ocr_ips or ip in _DEFAULT_OCR_IPS
                    )
                    for ip in cold_ips
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
            asyncio.create_task(_warm_cache())
        return _cached_probes_by_mac()

    tasks = []
    for ip in all_camera_ips:
        is_ocr = ip in ocr_ips or ip in _DEFAULT_OCR_IPS
        tasks.append(_probe_camera_ip(ip, is_ocr))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    by_mac = {}
    for r in results:
        if isinstance(r, dict) and r.get("mac"):
            by_mac[r["mac"]] = r
    return by_mac


def _is_pixellot_mac(mac: str) -> bool:
    if not mac:
        return False
    normalized = mac.upper().replace("-", ":").replace(".", ":")
    parts = normalized.split(":")
    if len(parts) >= 3:
        prefix = ":".join(parts[:3])
        return prefix in PIXELLOT_OUIS
    return False


PIXELLOT_MIN_RAM_GB = 32

# ── Approved NTP sources ─────────────────────────────────────
# Per Pixellot Troubleshooting Tips PDF #9: VPU clocks must sync from the
# US NTP pool. A school IT department occasionally points VPUs at an
# internal NTP server which drifts, breaking signed-URL streaming.
PIXELLOT_APPROVED_NTP_SOURCES = (
    "0.us.pool.ntp.org",
    "1.us.pool.ntp.org",
    "2.us.pool.ntp.org",
    "3.us.pool.ntp.org",
)


def _is_approved_ntp_source(source: Optional[str]) -> bool:
    """True if `source` matches one of the approved Pixellot NTP servers.

    Match is case-insensitive and tolerates trailing whitespace. We also
    accept any `*.us.pool.ntp.org` host since the four canonical names
    are aliases for the same NTP pool.
    """
    if not source:
        return False
    host = source.strip().lower()
    if host in PIXELLOT_APPROVED_NTP_SOURCES:
        return True
    return host.endswith(".us.pool.ntp.org")


# ── DNS resolution comparison (PDF #10) ──────────────────────
# system-resolver vs Google (8.8.8.8). We classify each domain so the UI can
# warn on real problems without crying wolf on benign CDN behavior.
import ipaddress as _ipaddress


def _is_private_or_bogon_ip(value) -> bool:
    """True if `value` is a non-public IPv4 (RFC1918, link-local, loopback,
    CGNAT, etc.). Used to tell a real DNS redirect — the local resolver hands
    back an *internal* IP — from benign CDN/GeoDNS load balancing, where both
    resolvers return different but equally-public IPs."""
    try:
        ip = _ipaddress.ip_address(str(value).strip())
    except (ValueError, AttributeError):
        return False
    return not ip.is_global


def _classify_dns_row(system: dict, google: dict) -> Optional[str]:
    """Classify one domain's system-vs-Google resolution.

    Returns:
      'system-blocked' — Google resolves, the configured resolver doesn't
                         (the venue DNS is filtering Pixellot infrastructure).
      'google-blocked' — the reverse (rare; usually a transient Google miss).
      'redirect'       — both resolve but the system resolver returns a
                         private/internal IP while Google returns a public one
                         (captive portal / SSL-inspection proxy / DNS rewrite).
      None             — healthy, including two *different public* IPs, which
                         is normal CDN/GeoDNS load balancing, not a problem.
    """
    sys_pass = (system or {}).get("status") == "pass"
    goog_pass = (google or {}).get("status") == "pass"
    if sys_pass and not goog_pass:
        return "google-blocked"
    if goog_pass and not sys_pass:
        return "system-blocked"
    if sys_pass and goog_pass:
        sys_ip = (system or {}).get("resolvedTo")
        goog_ip = (google or {}).get("resolvedTo")
        if (sys_ip and goog_ip and sys_ip != goog_ip
                and _is_private_or_bogon_ip(sys_ip)
                and not _is_private_or_bogon_ip(goog_ip)):
            return "redirect"
    return None


def _annotate_dns_resolution(dns_resolution):
    """Attach an authoritative `discrepancy` to each DNS row + recompute the
    aggregate counts. Classification lives here (tested) rather than in the
    PowerShell collector so the rule stays in one place and out of an
    untestable script."""
    if not dns_resolution or dns_resolution.get("error"):
        return dns_resolution
    results = dns_resolution.get("results") or []
    for row in results:
        row["discrepancy"] = _classify_dns_row(row.get("system"), row.get("google"))
    dns_resolution["systemBlockedCount"] = sum(
        1 for r in results if r.get("discrepancy") == "system-blocked")
    dns_resolution["redirectCount"] = sum(
        1 for r in results if r.get("discrepancy") == "redirect")
    return dns_resolution


def _internet_reachable(config, port_tests):
    """Authoritative 'does this VPU have internet', returned as
    (reachable: bool, tested_host: str | None).

    The raw probe in Get-NetworkConfig pings / TCP-connects to 8.8.8.8 etc.,
    but locked-down venue/school networks routinely block those public IPs
    entirely while Pixellot's own services stay reachable. A successful
    required TCP/443 service test is definitive proof of outbound HTTPS to a
    real endpoint — stronger evidence than any probe — so we treat that as
    'reachable' even when the probe failed."""
    internet = (config or {}).get("internet", {}) if isinstance(config, dict) else {}
    probe_host = internet.get("testedHost")
    if internet.get("reachable"):
        return True, probe_host
    results = port_tests.get("results") or [] if isinstance(port_tests, dict) else []
    for p in results:
        if (not p.get("optional")
                and str(p.get("port")) == "443"
                and (p.get("protocol") or "").upper() == "TCP"
                and (p.get("status") or "").lower() == "pass"):
            return True, "{}:443".format(p.get("host"))
    return False, probe_host


# ── Windows LTSC lifecycle map (PDF #4) ─────────────────────
# Pixellot VPUs ship on Win 10 IoT LTSC. Two builds in the field:
#   1809 (LTSC 2019) → build 17763 → all VPUs except Z2
#   21H2 (LTSC 2021) → build 19044 → Z2 VPUs
# Date format: ISO yyyy-mm-dd, used to compute days-until-EOS.
_LTSC_LIFECYCLE = {
    "17763": {
        "ltscRelease": "Windows 10 IoT Enterprise LTSC 2019 (1809)",
        "eosDate": "2029-01-09",  # IoT extended support / end-of-servicing
    },
    "19044": {
        "ltscRelease": "Windows 10 IoT Enterprise LTSC 2021 (21H2)",
        "eosDate": "2027-01-12",  # end-of-support per PDF #4
        "endOfServicingDate": "2032-01-13",  # IoT extended servicing
    },
}


def _os_lifecycle(build_number) -> Optional[dict]:
    """Return {ltscRelease, eosDate, daysToEos[, endOfServicingDate,
    daysToServicingEnd]} for a known Pixellot OS build, or None if build is
    unknown."""
    if not build_number:
        return None
    key = str(build_number).strip()
    info = _LTSC_LIFECYCLE.get(key)
    if not info:
        return None
    from datetime import date as _date

    def _days_until(iso):
        try:
            y, m, d = [int(x) for x in str(iso).split("-")]
            return (_date(y, m, d) - _date.today()).days
        except (ValueError, AttributeError):
            return None

    out = {
        **info,
        "daysToEos": _days_until(info.get("eosDate")),
    }
    if info.get("endOfServicingDate"):
        out["daysToServicingEnd"] = _days_until(info["endOfServicingDate"])
    return out


# ── Unsupported security software ────────────────────────────
# Per Pixellot Troubleshooting Tips PDF #11: any EDR / non-Defender
# antivirus blocks agent.exe and forces an RMA. Only Windows Defender is
# approved. Each entry is matched as a case-insensitive substring against
# the installed-software displayName.
# ── Pixellot version × hardware compatibility (field guidance) ──
# Per Logan T (2026-05-28):
#   Win 8 hosts                          → max 2.66.17
#   Maxwell GPU (5.x cap, GTX 9xx, M-)   → max 2.66.17 (these are all Win 8 hosts)
#   Win 10 + Pascal GPU (10xx, 6.x cap)  → max 5.2.x
#   Win 10 + Turing or newer (≥7.5 cap)  → any version
#   Volta GPU (7.0/7.2 — V100, Titan V)  → ANOMALY: never deployed; if detected,
#                                          flag as a hardware configuration error
#
# Pixellot version strings are dotted-numeric (e.g. "5.13.6"). Caps can
# be exact ("2.66.17") or wildcarded ("5.2.x") — the latter allows any
# patch under that major.minor.

# arch → max Pixellot version (None means unlimited, "__ANOMALY__" means
# not a known-deployed configuration)
_ARCH_VERSION_CAPS = {
    "Maxwell":    "2.66.17",
    "Pascal":     "5.2.x",
    "Volta":      "__ANOMALY__",
    "Turing":     None,
    "Ampere/Ada": None,
    "Hopper":     None,
    "Blackwell":  None,
    # Unknown/None handled separately
}


def _parse_version(v: str):
    """Return tuple of ints from a dotted version, ignoring suffixes.
    "5.13.6" → (5, 13, 6). "2.66.17" → (2, 66, 17). Empty/bad → ()."""
    if not v:
        return ()
    parts = []
    for piece in str(v).split("."):
        piece = piece.strip()
        # Strip non-numeric tail (e.g. "5.13.6-beta" → "5.13.6")
        num = ""
        for ch in piece:
            if ch.isdigit():
                num += ch
            else:
                break
        if num == "":
            break
        parts.append(int(num))
    return tuple(parts)


def _version_exceeds_cap(installed: str, cap: str) -> bool:
    """True if `installed` is strictly newer than `cap`.

    Cap formats:
      "2.66.17"   exact maximum (5.13.6 exceeds, 2.66.17 OK, 2.66.16 OK)
      "5.2.x"     wildcard patch — anything in 5.2.* allowed; 5.3.0+ exceeds
    """
    if not installed or not cap:
        return False
    iv = _parse_version(installed)
    if not iv:
        return False

    # Wildcard form: "5.2.x" → require major.minor match, patch unbounded
    if cap.lower().endswith(".x"):
        prefix = cap[:-2]  # "5.2"
        cv = _parse_version(prefix)
        if not cv:
            return False
        # Out of range if installed major > cap major, or same major + minor > cap minor
        if iv[0] != cv[0]:
            return iv[0] > cv[0]
        if len(iv) < 2 or len(cv) < 2:
            return False
        return iv[1] > cv[1]

    # Exact form: pad to same length and compare
    cv = _parse_version(cap)
    if not cv:
        return False
    max_len = max(len(iv), len(cv))
    iv_padded = iv + (0,) * (max_len - len(iv))
    cv_padded = cv + (0,) * (max_len - len(cv))
    return iv_padded > cv_padded


def _check_pixellot_compatibility(identity, gpu_info) -> dict:
    """Return a status dict describing Pixellot version compatibility
    with the detected Windows + GPU combination.

    Returns:
      {
        status: "ok" | "over" | "no-gpu" | "skip",
        installedVersion: str | None,
        maxVersion: str | None,          # None = unlimited
        capReason: str,                  # which rule applied
        architecture: str,
        windowsBuild: str | None,
      }
    """
    out = {
        "status": "skip",
        "installedVersion": None,
        "maxVersion": None,
        "capReason": "",
        "architecture": "Unknown",
        "windowsBuild": None,
    }
    if not identity or identity.get("error"):
        return out

    installed = (identity.get("pixellot") or {}).get("version")
    out["installedVersion"] = installed
    if not installed:
        out["status"] = "skip"
        out["capReason"] = "Pixellot version not detected. The VPU software may not be installed."
        return out

    os_caption = (identity.get("operatingSystem") or {}).get("caption") or ""
    os_build = (identity.get("operatingSystem") or {}).get("buildNumber") or ""
    out["windowsBuild"] = os_build

    # Win 8 / 8.1 binding constraint regardless of GPU
    is_win8 = "Windows 8" in os_caption
    if is_win8:
        out["maxVersion"] = "2.66.17"
        out["capReason"] = "Windows 8 hosts are capped at Pixellot 2.66.17"
        out["status"] = "over" if _version_exceeds_cap(installed, "2.66.17") else "ok"
        return out

    arch = (gpu_info or {}).get("primaryArchitecture") or "Unknown"
    out["architecture"] = arch

    if arch in ("None", None):
        out["status"] = "no-gpu"
        out["capReason"] = "No NVIDIA GPU detected. Pixellot needs NVIDIA hardware to encode."
        return out

    cap = _ARCH_VERSION_CAPS.get(arch)

    # Anomaly: architecture not deployed in the Pixellot field — flag as
    # a hardware configuration error so support can investigate.
    if cap == "__ANOMALY__":
        out["status"] = "anomaly"
        out["maxVersion"] = None
        out["capReason"] = (
            f"{arch} GPUs are not a deployed Pixellot configuration. "
            f"Check this host's hardware roster. Volta cards were never "
            f"shipped in production VPUs."
        )
        return out

    if cap is None:
        # Either an architecture that's unlimited (Turing+) or one we
        # don't have data for. For Unknown, default to compliant — we
        # don't want a false-positive critical finding on a strange host.
        out["maxVersion"] = None
        if arch in ("Turing", "Ampere/Ada", "Hopper", "Blackwell"):
            out["capReason"] = f"{arch} architecture, so there is no Pixellot version cap"
            out["status"] = "ok"
        else:
            out["capReason"] = f"Architecture '{arch}' has no cap data, so Pulse assumes it is compatible"
            out["status"] = "ok"
        return out

    out["maxVersion"] = cap
    out["capReason"] = f"{arch} GPU caps Pixellot at {cap}"
    out["status"] = "over" if _version_exceeds_cap(installed, cap) else "ok"
    return out


# ── Concerning software categories ───────────────────────────
# Each category lists case-insensitive substring patterns that match
# software displayName. The first matching category wins per row.
# The frontend uses the per-entry `concern` field to badge the
# Software Inventory table; _compute_findings emits dashboard findings
# from these as well.
_CONCERNING_SOFTWARE = {
    "security": {
        "severity": "critical",
        "label": "Unsupported security software",
        "shortLabel": "AV/EDR",
        "reason": (
            "Pixellot VPUs only support Windows Defender. Third-party AV/EDR "
            "products block agent.exe and force a hardware return (RMA)."
        ),
        "patterns": [
            "CrowdStrike", "SentinelOne", "Sophos", "Carbon Black", "Bitdefender",
            "McAfee", "Norton", "Symantec", "Trend Micro", "Kaspersky", "ESET",
            "Webroot", "Cylance", "Cortex XDR",
        ],
    },
    "crypto_miner": {
        "severity": "critical",
        "label": "Cryptocurrency miner",
        "shortLabel": "Miner",
        "reason": (
            "Mining software consumes GPU/CPU resources required for video "
            "encoding and is never legitimate on a VPU."
        ),
        # Be specific — "Claymore" alone risks false positives on common surnames,
        # but full strings like "Claymore's Miner" / NiceHash are unambiguous.
        "patterns": [
            "xmrig", "ethminer", "phoenixminer", "NiceHash", "MinerGate",
            "Claymore's Miner", "T-Rex Miner", "lolMiner", "Gminer", "TeamRedMiner",
        ],
    },
    "torrent": {
        "severity": "critical",
        "label": "Torrent client",
        "shortLabel": "Torrent",
        "reason": (
            "Torrent clients saturate upload bandwidth used for cloud streaming "
            "and are a common malware vector. Not appropriate on a VPU."
        ),
        "patterns": [
            "BitTorrent", "µTorrent", "uTorrent", "qBittorrent",
            "Transmission-Qt", "Deluge", "Vuze", "Tixati", "Frostwire",
        ],
    },
    "system_cleaner": {
        "severity": "critical",
        "label": "System cleaner / optimizer",
        "shortLabel": "Cleaner",
        "reason": (
            "Registry/system cleaners and driver-updater junkware are known to "
            "break Pixellot installs by deleting required files or registry keys. "
            "Uninstall and reimage if a cleaner was recently run."
        ),
        "patterns": [
            "CCleaner", "Advanced SystemCare", "IObit", "MyCleanPC", "PC Cleaner",
            "Glary Utilities", "Wise Care", "Auslogics BoostSpeed",
            "Driver Booster", "Driver Easy", "Driver Genius", "Driver Updater",
        ],
    },
    "alt_remote": {
        "severity": "warning",
        "label": "Non-standard remote-access tool",
        "shortLabel": "Alt Remote",
        "reason": (
            "LogMeIn is the approved Pixellot remote-access tool. Alternative "
            "products run their own background telemetry and may compete with "
            "LogMeIn for ports / system tray. Confirm with field operations "
            "before relying on these."
        ),
        # VNC variants (TightVNC, RealVNC) are often standard on VPUs — left out
        # to avoid false positives.
        "patterns": [
            "TeamViewer", "AnyDesk", "Splashtop", "GoToMyPC",
            "ConnectWise Control", "ScreenConnect", "Chrome Remote Desktop",
        ],
    },
    "game_platform": {
        "severity": "warning",
        "label": "Gaming platform",
        "shortLabel": "Games",
        "reason": (
            "Game launchers run background updates and game-streaming services "
            "that compete with Pixellot for CPU/GPU and upload bandwidth."
        ),
        "patterns": [
            "Steam", "Epic Games", "Battle.net", "Riot Client", "Riot Games",
            "GOG Galaxy", "Origin", "Ubisoft Connect", "EA app", "EA Desktop",
        ],
    },
    "consumer_sync": {
        "severity": "warning",
        "label": "Consumer cloud-sync client",
        "shortLabel": "Sync",
        "reason": (
            "Consumer-grade file sync can saturate upload bandwidth needed for "
            "video streams. Disable or pause sync during events."
        ),
        # Exclude OneDrive — common on Win 10 IoT and harder to remove cleanly.
        "patterns": ["Dropbox", "Google Drive", "iCloud", "Box Drive", "MEGAsync"],
    },
}


def _detect_concerning_software(installed_sw) -> dict:
    """Categorize installed software into concerning buckets.
    Returns {category_key: [{name, version, matched}, ...]}.
    Each software entry is matched against the first category whose
    patterns hit; subsequent categories are skipped for that entry."""
    out = {k: [] for k in _CONCERNING_SOFTWARE}
    if not installed_sw or installed_sw.get("error"):
        return out
    seen_names = set()  # dedupe — installers often appear under multiple keys
    for sw in installed_sw.get("software") or []:
        name = (sw.get("displayName") or "").strip()
        if not name:
            continue
        name_lc = name.lower()
        if name_lc in seen_names:
            continue
        for cat_key, cat in _CONCERNING_SOFTWARE.items():
            for pattern in cat["patterns"]:
                if pattern.lower() in name_lc:
                    seen_names.add(name_lc)
                    out[cat_key].append({
                        "name": name,
                        "version": (sw.get("displayVersion") or "").strip() or None,
                        "matched": pattern,
                    })
                    break
            if name_lc in seen_names:
                break
    return out


def _enrich_software_with_concerns(installed_sw):
    """Tag each software entry with a `concern` field if it matches a
    concerning-software pattern. Returns the same dict for chaining."""
    if not installed_sw or installed_sw.get("error"):
        return installed_sw
    for sw in installed_sw.get("software") or []:
        name_lc = (sw.get("displayName") or "").strip().lower()
        if not name_lc:
            continue
        for cat_key, cat in _CONCERNING_SOFTWARE.items():
            for pattern in cat["patterns"]:
                if pattern.lower() in name_lc:
                    sw["concern"] = {
                        "category": cat_key,
                        "severity": cat["severity"],
                        "label": cat["label"],
                        "shortLabel": cat["shortLabel"],
                        "reason": cat["reason"],
                        "matched": pattern,
                    }
                    break
            if "concern" in sw:
                break
    return installed_sw


# Backwards-compat shim — _compute_findings still uses this for the
# critical AV finding with its specific RMA copy.
def _detect_banned_security(installed_sw) -> list:
    return _detect_concerning_software(installed_sw).get("security", [])


def _total_ram_gb(hardware, performance) -> float:
    """Return total installed RAM in GB. Prefers DIMM sum (exact) over the
    OS-visible total (reduced by reserved memory). Returns 0 if neither
    source is usable."""
    if hardware and not hardware.get("error"):
        dimms = hardware.get("memory") or []
        total = sum((d.get("capacityGB") or 0) for d in dimms)
        if total > 0:
            return float(total)
    if performance and not performance.get("error"):
        mem = performance.get("memory") or {}
        # Real script emits totalMB; demo emits totalGB. Try both.
        total_mb = mem.get("totalMB")
        if total_mb:
            return round(total_mb / 1024, 2)
        total_gb = mem.get("totalGB")
        if total_gb:
            return float(total_gb)
    return 0.0


# Intel/Realtek parts used on the dedicated multi-port camera NIC card. Only a
# fallback hint when PCI bus info is missing — the authoritative signal is the
# PCI bus number (onboard motherboard LOM = bus 0; add-in camera card = bus > 0).
_CAMERA_NIC_CHIPSETS = ("i210", "i211", "i350", "82574l", "82576", "82580")


def _adapter_role(a: dict) -> str:
    """Classify a network adapter into its VPU role:
      wifi        — the wireless card (Native 802.11), for the Pixellot Connect app
      motherboard — the onboard Ethernet LOM (PCI bus 0), the intended internet uplink
      camera      — a port on the dedicated multi-port camera NIC (PCI bus > 0)
      wired-unknown / other — couldn't place it (no PCI info, or a virtual/WAN device)
    The motherboard port and the camera card often use the SAME Intel chipset, so
    we key on PCI bus location, not the chipset name."""
    media = (a.get("physicalMediaType") or "").strip().lower()
    desc = (a.get("interfaceDescription") or "").lower()
    if "802.11" in media or "wi-fi" in desc or "wireless" in desc or "wlan" in desc:
        return "wifi"
    is_wired = "802.3" in media
    bus = a.get("pciBus")
    if is_wired and bus is not None:
        return "motherboard" if int(bus) == 0 else "camera"
    if is_wired:
        return "wired-unknown"
    return "other"


def _classify_network_adapters(network_config):
    """Attach a `role` to every adapter in network_config (in place). Idempotent
    and cheap — safe to call from every consumer (findings, dashboard, network
    payload) so the role travels to both the backend findings and the frontend."""
    if not network_config or network_config.get("error"):
        return network_config
    for a in network_config.get("adapters") or []:
        a["role"] = _adapter_role(a)
    return network_config


def _misplaced_camera_uplinks(network_config):
    """Camera-NIC adapters carrying the internet uplink — the wiring fault
    where the venue cable is in a camera port. An adapter flags only when it
    is link-UP and carrying a real (non-APIPA) default gateway — a disconnected
    port can hold a stale gateway in the route table, so link state is the
    gate. Returns [(adapter, gateway), ...] (empty when wired correctly)."""
    if not network_config or network_config.get("error"):
        return []
    _classify_network_adapters(network_config)
    adapters = network_config.get("adapters") or []
    ip_by_idx = {}
    for ipc in network_config.get("ipConfigurations") or []:
        ip_by_idx[ipc.get("interfaceIndex")] = ipc

    def _real_gateway(a):
        ipc = ip_by_idx.get(a.get("interfaceIndex")) or {}
        raw = ipc.get("ipv4DefaultGateway")
        # PowerShell unwraps a single-element array to a scalar, so a one-gateway
        # adapter arrives as a bare string — normalize before iterating (else we'd
        # iterate the string's characters).
        gws = raw if isinstance(raw, list) else ([raw] if raw else [])
        for g in gws:
            if g and not str(g).startswith("169.254."):
                return g
        return None

    def _link_up(a):
        return str(a.get("status") or "").strip().lower() == "up"

    misplaced = []
    for a in adapters:
        if a.get("role") != "camera":
            continue
        gw = _real_gateway(a)
        if gw and _link_up(a):
            misplaced.append((a, gw))
    return misplaced


def _camera_nic_uplink_finding(network_config):
    """Dashboard finding for the misplaced-uplink wiring fault (see
    _misplaced_camera_uplinks). Returns a critical finding dict, or None."""
    misplaced = _misplaced_camera_uplinks(network_config)
    if not misplaced:
        return None
    adapters = network_config.get("adapters") or []

    # Motherboard port state, for the remediation message.
    def _mobo_state(a):
        admin = str(a.get("adminStatus") or "").strip().lower()
        status = str(a.get("status") or "").strip().lower()
        if admin == "down" or status == "disabled":
            return "disabled"
        if status in ("disconnected", "not present", "down"):
            return "unplugged"
        return "ok"

    mobo = [a for a in adapters if a.get("role") == "motherboard"]
    mobo_note = ""
    if mobo:
        st = _mobo_state(mobo[0])
        if st == "disabled":
            mobo_note = " The motherboard network port is disabled. Enable it in Windows."
        elif st == "unplugged":
            mobo_note = " The motherboard network port has no cable connected."
    else:
        mobo_note = " No motherboard network port was detected. It may be disabled."

    ports_txt = ", ".join(
        f"{a.get('name') or a.get('interfaceDescription') or '?'} (gateway {gw})"
        for a, gw in misplaced
    )
    return {
        "severity": "critical",
        "category": "Network",
        "title": "Internet is plugged into a camera port, not the motherboard network port",
        "recommendation": (
            f"The internet/venue connection is on a camera-NIC port ({ports_txt}), which can "
            f"disrupt camera discovery and streaming. On a Pixellot VPU it must connect to the "
            f"motherboard network port. The 4-port NIC is for cameras only.{mobo_note} Move the "
            f"cable there and confirm the port is enabled. Leave the Wi-Fi card enabled, because "
            f"the Pixellot Connect app needs it."
        ),
    }


def _wifi_disabled_finding(network_config):
    """The Wi-Fi card is how the Pixellot Connect app reaches the VPU. If it's
    administratively disabled, Connect can't find the unit. A *disabled* Wi-Fi
    NIC shows up with status 'Disabled' / adminStatus 'Down' (an absent card
    doesn't appear at all, so this won't false-fire on units without Wi-Fi).
    Wi-Fi Direct / hosted-network virtual adapters are skipped. Returns a
    warning finding, or None."""
    if not network_config or network_config.get("error"):
        return None
    _classify_network_adapters(network_config)
    disabled = []
    for a in network_config.get("adapters") or []:
        if a.get("role") != "wifi":
            continue
        desc = a.get("interfaceDescription") or ""
        if "Direct" in desc or "Virtual" in desc:
            continue  # Wi-Fi Direct / hosted-network plumbing, not the real card
        status = str(a.get("status") or "").strip().lower()
        admin = str(a.get("adminStatus") or "").strip().lower()
        if status == "disabled" or admin == "down":
            disabled.append(a)
    if not disabled:
        return None
    names = ", ".join(a.get("interfaceDescription") or a.get("name") or "Wi-Fi" for a in disabled)
    return {
        "severity": "warning",
        "category": "Network",
        "title": "Wi-Fi card is disabled, so the Pixellot Connect app can't reach this VPU",
        "recommendation": (
            f"The VPU's Wi-Fi adapter ({names}) is disabled. The Wi-Fi card is what the Pixellot "
            f"Connect app uses to talk to the VPU, so Connect won't find this unit until it's "
            f"turned back on. Enable it in Windows: Network Connections, right-click the Wi-Fi "
            f"adapter, Enable. The internet uplink should stay on the motherboard Ethernet port; "
            f"Wi-Fi is only for Connect."
        ),
    }


# TLS targets whose loss stops (or visibly degrades) a broadcast, as opposed
# to the support-plane hosts on the same probe list (secure.logmein.com,
# www.python.org). Only a hit in here gates readiness — a district blocking
# LogMeIn is a support headache, not a reason to tell a tech the game is at
# risk.

def _tls_exempt_list(rows):
    """The exact list to hand venue IT: a wildcard plus the bare domain for
    each affected site. Built from the failing rows so the example is never
    a domain that isn't actually broken on this network."""
    seen, out = set(), []
    for r in rows:
        base = ".".join((r.get("domain") or "").split(".")[-2:])
        if base and base not in seen:
            seen.add(base)
            out += [f"*.{base}", base]
    return ", ".join(out)

_BROADCAST_CRITICAL_TLS_DOMAINS = {
    "singular.live",
    "app.singular.live",
    "api.singular.live",
    "datastream.singular.live",
    "service.singular.live",
    "pixellot.tv",
    "software.pixellot.tv",
    "nfhsnetwork.com",
}


def _compute_findings(identity, performance, services, nics, hardware=None, installed_sw=None, network_config=None, install_state=None, port_tests=None, gpu_info=None, wifi=None, pixellot_config=None, expectations=None, disk_health=None, probe_results=None, tls_inspection=None, lmi_log=None) -> list:
    findings = []

    # None vs {} matters for probe_results: None means the caller never
    # probed (legacy ARP-only behavior applies); {} means probes ran and
    # every camera failed to answer — which right after launch is the
    # collection burst starving the probes, not an empty rig, and gates the
    # startup-grace suppressions below. Capture before any rebinding.
    probes_attempted = probe_results is not None

    # ── Wi-Fi uplink detection (Canopy adoption) ─────────────
    # Pixellot VPUs are wired-only by design. We only warn when Wi-Fi is the
    # VPU's actual internet uplink (a real Wi-Fi NIC holds the default route
    # and no wired adapter does). Windows always carries Wi-Fi Direct / hosted-
    # network virtual adapters that show "connected" — those are not the
    # uplink and must not trip this finding.
    if wifi and not wifi.get("error") and wifi.get("uplinkIsWifi"):
        uplink_wifi = [
            a for a in (wifi.get("adapters") or [])
            if a.get("isUp") and a.get("hasDefaultRoute") and not a.get("isVirtual")
        ]
        names = ", ".join(a.get("interfaceDescription") or a.get("name") or "?" for a in uplink_wifi)
        ssids = [a.get("ssid") for a in uplink_wifi if a.get("ssid")]
        ssid_str = f" (SSID: {', '.join(ssids)})" if ssids else ""
        findings.append(
            {
                "code": "wifi-uplink",
                "severity": "warning",
                "category": "Network",
                "title": "VPU is using Wi-Fi for its internet connection. Switch to wired Ethernet",
                "recommendation": (
                    f"The VPU's active internet path is over Wi-Fi: {names}{ssid_str}. "
                    f"The Wi-Fi card is meant for the Pixellot Connect app, not the internet "
                    f"uplink. Connect the motherboard Ethernet port to the venue network "
                    f"instead. Wi-Fi adds latency and packet loss that disrupt streaming."
                ),
            }
        )

    # ── Internet plugged into a camera port instead of the motherboard ───
    # The internet uplink must land on the motherboard network port; the
    # dedicated 4-port NIC is cameras-only. Detected via PCI bus role (add-in
    # card = bus > 0) + a live default gateway on that port.
    _cam_uplink = _camera_nic_uplink_finding(network_config)
    if _cam_uplink:
        findings.append(_cam_uplink)

    # ── Wi-Fi card disabled (Pixellot Connect can't reach the VPU) ───────
    _wifi_off = _wifi_disabled_finding(network_config)
    if _wifi_off:
        findings.append(_wifi_off)

    # ── NTP allowlist (PDF #9) ───────────────────────────────
    # School networks sometimes force VPUs onto an internal NTP server. If
    # that source drifts, signed-URL streaming breaks. The four canonical
    # `*.us.pool.ntp.org` hosts are the only Pixellot-approved sources.
    if network_config and not network_config.get("error"):
        ntp_src = (network_config.get("ntpSource") or "").strip()
        if ntp_src and not _is_approved_ntp_source(ntp_src):
            approved_list = ", ".join(PIXELLOT_APPROVED_NTP_SOURCES)
            findings.append(
                {
                    "code": "ntp-unapproved",
                    "severity": "warning",
                    "category": "Network",
                    "title": "VPU clock is syncing from the wrong time source",
                    "recommendation": (
                        f"Point the VPU's clock at an approved Pixellot time server. "
                        f"Current source: {ntp_src}. Approved: {approved_list}. To fix, run "
                        f"`w32tm /config /manualpeerlist:\"0.us.pool.ntp.org 1.us.pool.ntp.org "
                        f"2.us.pool.ntp.org 3.us.pool.ntp.org\" /syncfromflags:manual /update` and "
                        f"restart the Windows Time service."
                    ),
                }
            )

    # ── Concerning software (PDF #11 + general VPU hygiene) ──
    # Walks the installed-software list through the _CONCERNING_SOFTWARE
    # categories and emits one finding per category that matched anything.
    # AV/EDR stays critical with PDF #11 copy; miners/torrents/cleaners are
    # critical with their own reasons; alt-remote / games / cloud-sync are
    # warnings.
    concerns = _detect_concerning_software(installed_sw)
    if concerns.get("security"):
        names_str = ", ".join(
            f"{b['name']}" + (f" {b['version']}" if b.get('version') else "")
            for b in concerns["security"]
        )
        findings.append({
            "code": "sw-security",
            "severity": "critical",
            "category": "Hardware",
            "title": "Unsupported security software detected",
            "recommendation": (
                f"Uninstall {names_str} immediately. Pixellot VPUs only support "
                f"Windows Defender. Third-party antivirus and EDR software blocks "
                f"agent.exe and forces a hardware return (RMA)."
            ),
        })
    for cat_key in ("crypto_miner", "torrent", "system_cleaner"):
        hits = concerns.get(cat_key) or []
        if not hits:
            continue
        cat = _CONCERNING_SOFTWARE[cat_key]
        names_str = ", ".join(
            f"{h['name']}" + (f" {h['version']}" if h.get('version') else "")
            for h in hits
        )
        findings.append({
            "code": f"sw-{cat_key.replace('_', '-')}",
            "severity": "critical",
            "category": "Software",
            "title": f"{cat['label']} installed",
            "recommendation": f"Found: {names_str}. {cat['reason']} Uninstall this software.",
        })
    for cat_key in ("alt_remote", "game_platform", "consumer_sync"):
        hits = concerns.get(cat_key) or []
        if not hits:
            continue
        cat = _CONCERNING_SOFTWARE[cat_key]
        names_str = ", ".join(h["name"] for h in hits)
        findings.append({
            "code": f"sw-{cat_key.replace('_', '-')}",
            "severity": "warning",
            "category": "Software",
            "title": f"{cat['label']} installed",
            "recommendation": f"Found: {names_str}. {cat['reason']}",
        })

    # ── Installed RAM ────────────────────────────────────────
    # Pixellot VPUs ship with 32GB of RAM. Anything less suggests an
    # undersized host or a failed DIMM — encoder workloads will degrade.
    total_ram = _total_ram_gb(hardware, performance)
    if total_ram > 0 and total_ram < PIXELLOT_MIN_RAM_GB - 1:  # -1 GB tolerance for OS overhead when falling back to performance.memory
        findings.append(
            {
                "code": "ram-insufficient",
                "severity": "warning",
                "category": "Hardware",
                "title": "Not enough memory for a VPU",
                "recommendation": f"System has {total_ram:g} GB RAM; Pixellot VPUs require {PIXELLOT_MIN_RAM_GB} GB. Encoder workloads may stall or drop frames. Add memory or escalate for replacement.",
            }
        )

    if identity and not identity.get("error"):
        uptime_secs = identity.get("uptime", {}).get("totalSeconds", 0)
        if uptime_secs and uptime_secs > 30 * 86400:
            findings.append(
                {
                    "code": "uptime-high",
                    "severity": "warning",
                    "category": "System",
                    "title": "VPU hasn't been rebooted in a while",
                    "recommendation": f"Reboot the VPU. It's been running {uptime_secs // 86400} days, and a periodic reboot clears memory leaks and stuck processes.",
                }
            )

        # Timezone must be a US zone — cloud-side timestamps are recorded in
        # US local time, so a VPU set to Jerusalem (or any non-US zone) will
        # produce logs that don't line up with field events.
        tz_id = identity.get("timezoneId") or ""
        tz_caption = identity.get("timezone") or ""
        if (tz_id or tz_caption) and not _is_us_timezone(tz_id, tz_caption):
            shown = tz_caption or tz_id
            findings.append(
                {
                    "code": "tz-non-us",
                    "severity": "critical",
                    "category": "System",
                    "title": "VPU clock is set to a non-US time zone",
                    "recommendation": f"Set the VPU to a US time zone. Open Date & Time settings and choose Pacific, Mountain, Central, Eastern, Alaska, or Hawaii. Current zone: '{shown}'.",
                }
            )

        # ── OS lifecycle (PDF #4) ───────────────────────────────
        # Warn 12 months before the date security updates actually STOP,
        # critical at 3 months. For builds with IoT extended servicing
        # beyond the headline end-of-support date (LTSC 2021), that's
        # endOfServicingDate — the headline date passing is expected and
        # gets a reassuring info note, not an alarm. For LTSC 2019 the
        # eosDate IS the end of servicing. Skip silently if the build
        # isn't in our LTSC map (covers non-VPU dev boxes).
        build = identity.get("operatingSystem", {}).get("buildNumber")
        lifecycle = _os_lifecycle(build)
        if lifecycle and lifecycle.get("daysToEos") is not None:
            days = lifecycle["daysToEos"]
            release = lifecycle["ltscRelease"]
            eos = lifecycle["eosDate"]
            servicing_date = lifecycle.get("endOfServicingDate")
            days_servicing = lifecycle.get("daysToServicingEnd")
            if servicing_date and days_servicing is not None:
                eol_date, eol_days = servicing_date, days_servicing
            else:
                eol_date, eol_days = eos, days
            if eol_days < 0:
                findings.append({
                    "code": "os-eos-reached",
                    "severity": "critical",
                    "category": "System",
                    "title": "Windows version is past its support date",
                    "recommendation": f"{release} reached its end of servicing on {eol_date} ({abs(eol_days)} days ago). This host no longer receives security updates and should be re-imaged to a supported Windows version.",
                })
            elif eol_days < 90:
                findings.append({
                    "code": "os-eos-imminent",
                    "severity": "critical",
                    "category": "System",
                    "title": "Windows version loses support soon",
                    "recommendation": f"{release} end of servicing is {eol_date}, {eol_days} days away. Plan re-imaging to a supported Windows version before that date.",
                })
            elif eol_days < 365:
                months = eol_days // 30
                findings.append({
                    "code": "os-eos-approaching",
                    "severity": "warning",
                    "category": "System",
                    "title": "Windows support ends within a year",
                    "recommendation": f"{release} end of servicing is {eol_date} (~{months} months away). Begin planning a re-image to a supported Windows version.",
                })
            elif servicing_date and days < 365:
                # Headline (mainstream) end-of-support is near or passed, but
                # IoT extended servicing has years left — reassure, don't alarm.
                if eol_days >= 730:
                    left = f"about {eol_days // 365} more years"
                else:
                    left = f"about {eol_days // 30} more months"
                findings.append({
                    "code": "os-mainstream-eos",
                    "severity": "info",
                    "category": "System",
                    "title": ("Windows mainstream support ends within a year, but this VPU stays covered"
                              if days >= 0 else
                              "Windows mainstream support has ended, but this VPU is still covered"),
                    "recommendation": (
                        f"{release} mainstream support {'ends' if days >= 0 else 'ended'} on {eos}. "
                        f"That is expected and fine. VPUs run the IoT Enterprise release of Windows, "
                        f"which keeps getting security updates until {eol_date} (end of servicing), "
                        f"so there is {left} of coverage. No action is needed on this unit."
                    ),
                })

        # ── Pixellot version × hardware compatibility ───────────
        # Logan T 2026-05-28: Win 8 caps at 2.66.17, Win 10 + Pascal at
        # 5.2.x, Win 10 + Turing+ unlimited. Critical if installed > cap.
        compat = _check_pixellot_compatibility(identity, gpu_info)
        if compat["status"] == "over":
            arch_str = compat["architecture"] if compat["architecture"] != "Unknown" else "this hardware"
            findings.append({
                "code": "pixellot-over-cap",
                "severity": "critical",
                "category": "Pixellot",
                "title": "Pixellot version is too new for this VPU's hardware",
                "recommendation": (
                    f"Installed Pixellot {compat['installedVersion']} is newer than the maximum "
                    f"supported version for {arch_str} ({compat['maxVersion']}). "
                    f"{compat['capReason']}. Downgrade Pixellot to {compat['maxVersion']} or earlier "
                    f"on this VPU. Newer builds will not run correctly on this GPU/OS combination."
                ),
            })
        elif compat["status"] == "no-gpu":
            findings.append({
                "code": "gpu-none",
                "severity": "critical",
                "category": "Hardware",
                "title": "No NVIDIA GPU detected",
                "recommendation": (
                    "Pixellot requires an NVIDIA GPU for video encoding. No NVIDIA graphics card "
                    "was detected on this VPU. If a card is physically installed, check that its "
                    "driver is installed and the card is seated; otherwise this VPU cannot run "
                    "the encoder."
                ),
            })
        elif compat["status"] == "anomaly":
            # Volta hardware shouldn't exist in the Pixellot field — escalate.
            findings.append({
                "code": "gpu-anomaly",
                "severity": "critical",
                "category": "Hardware",
                "title": "Unrecognized graphics hardware",
                "recommendation": (
                    f"{compat['architecture']} GPU detected, which is not a known Pixellot "
                    f"deployment configuration. Escalate to support, because this host may be "
                    f"mis-imaged or the hardware roster may need review. "
                    f"Installed Pixellot: {compat['installedVersion']}."
                ),
            })

    # ── Dedicated GPU presence (Canopy / Leaf / checkDedicatedGpu.ps1) ──
    # A Pixellot VPU must have a dedicated NVIDIA or AMD card. Intel iGPU
    # alone is wrong-hardware. Skipped if the compat check above already
    # raised a "no-gpu" critical (would be duplicate noise).
    if hardware and not hardware.get("error"):
        compat_no_gpu = any(f["title"] == "No NVIDIA GPU detected" for f in findings)
        if not compat_no_gpu:
            gpus = hardware.get("gpus") or []
            dedicated = [g for g in gpus if g.get("isDedicated")]
            if gpus and not dedicated:
                # Got at least one GPU but none are NVIDIA/AMD — most likely
                # an Intel-iGPU-only host, which is wrong hardware.
                vendors = sorted({(g.get("vendor") or "Unknown") for g in gpus})
                vendor_str = ", ".join(vendors)
                findings.append({
                    "code": "gpu-igpu-only",
                    "severity": "warning",
                    "category": "Hardware",
                    "title": "No dedicated graphics card, so this is the wrong hardware for a VPU",
                    "recommendation": (
                        f"Only built-in graphics found ({vendor_str}). "
                        f"Pixellot VPUs require a dedicated NVIDIA or AMD card for video "
                        f"encoding, so this host is the wrong hardware platform for a VPU. "
                        f"Check that the graphics card is seated, powered, and has a current driver."
                    ),
                })

    if performance and not performance.get("error"):
        # Use `is not None` instead of truthy checks so a legitimate 0 value
        # doesn't get short-circuited (would mask metric-collection bugs).
        cpu = performance.get("cpu", {}).get("usagePercent")
        if cpu is not None and cpu > 90:
            findings.append(
                {
                    "code": "cpu-critical",
                    "severity": "critical",
                    "category": "Performance",
                    "title": "CPU usage critically high",
                    "recommendation": f"Check for runaway processes. CPU is at {cpu}%.",
                }
            )
        elif cpu is not None and cpu > 75:
            findings.append(
                {
                    "code": "cpu-elevated",
                    "severity": "warning",
                    "category": "Performance",
                    "title": "CPU usage elevated",
                    "recommendation": f"Watch for sustained high usage. CPU is at {cpu}%.",
                }
            )

        mem = performance.get("memory", {}).get("usedPercent")
        if mem is not None and mem > 90:
            findings.append(
                {
                    "code": "mem-critical",
                    "severity": "critical",
                    "category": "Performance",
                    "title": "Memory usage critically high",
                    "recommendation": f"Close apps or add memory. Memory is at {mem}%.",
                }
            )
        elif mem is not None and mem > 80:
            findings.append(
                {
                    "code": "mem-elevated",
                    "severity": "warning",
                    "category": "Performance",
                    "title": "Memory usage elevated",
                    "recommendation": f"Watch for memory pressure. Memory is at {mem}%.",
                }
            )

        temp = performance.get("temperature", {}).get("celsius")
        if temp is not None and temp > 85:
            findings.append(
                {
                    "code": "temp-critical",
                    "severity": "critical",
                    "category": "Hardware",
                    "title": "VPU running hot",
                    "recommendation": f"Check cooling. Temperature is at {temp}°C.",
                }
            )

    # Disk space — one finding per offending VOLUME, from disk-health's
    # logicalDisks. `performance.disk.usedPercent` sums ALL fixed drives, so on
    # the typical fleet box (small C: for OS + stream processing, large D: for
    # VOD storage) a critically full C: averages out against a near-empty D:
    # and the alert never fired (PULSEDEV-49). The aggregate remains only as a
    # fallback for when disk-health didn't run.
    volumes = []
    if disk_health and not disk_health.get("error"):
        for d in (disk_health.get("logicalDisks") or []):
            letter = str(d.get("deviceID") or "").rstrip(":").upper()
            pct = d.get("usedPercent")
            if letter and isinstance(pct, (int, float)):
                volumes.append((letter, pct))
    if not volumes and performance and not performance.get("error"):
        agg = (performance.get("disk") or {}).get("usedPercent")
        if isinstance(agg, (int, float)):
            volumes = [("all drives combined", agg)]
    drive_roles = {
        "C": ("system drive", "The live stream is processed on C:, so a full "
                              "system drive can stop capture."),
        "D": ("recordings drive", "New event recordings (VODs) can't be stored "
                                  "once it fills. Clear old VODs."),
    }
    for letter, pct in volumes:
        role, consequence = drive_roles.get(letter, (None, None))
        label = f"{letter}: ({role})" if role else (
            letter if len(letter) > 1 else f"{letter}:")
        name = f"Drive {letter}:" if len(letter) == 1 else "Disk"
        # D: is classed info (see F15b), so its title has to carry the
        # consequence — "Worth knowing" next to a bare "Drive D: almost full"
        # reads as ignorable, and losing the school's recording is not. This
        # is a suffix on the finished title, not on `name`: `name` is
        # interpolated as f"{name} almost full" below.
        title_tail = " — recordings may not save" if letter == "D" else ""
        if pct > 90:
            # At >90% on D: the Disks page shows the Storage Cleanup card —
            # point the tech straight at it instead of a vague "clear VODs".
            cleanup_hint = (
                "The Disks page can clear space for you: open Disks and use "
                "Storage Cleanup." if letter == "D" else None)
            # Readiness gates C: and D: through its own per-drive checks
            # (F15a/F15b below), because a blocker on C: and a risk on D: is
            # not the same call. That left one full drive described by two
            # records: this finding, and readiness' own entry. The policy
            # table classed this one `info` to stop it double-counting in the
            # rollup, and the dashboard then rendered a full recording drive
            # as "Worth knowing" while the same card counted it as a risk one
            # line above.
            #
            # Say which record wins, in the data, instead of leaving each
            # layer to infer it: readiness drops the superseded copy from its
            # audit record, and the UI takes the tone of the entry named here.
            superseded_by = {"C": "disk-c-critical", "D": "disk-d-critical"}.get(letter)
            findings.append(
                {
                    "code": "disk-critical",
                    "severity": "critical",
                    "category": "Storage",
                    "title": f"{name} almost full{title_tail}",
                    "recommendation": " ".join(filter(None, [
                        f"Free up space now. {label} is {pct:g}% full.",
                        consequence,
                        cleanup_hint,
                    ])),
                    **({"supersededBy": superseded_by} if superseded_by else {}),
                }
            )
        # No warning tier below 90% — disk fill alerts are critical-only.
        # The old `disk-low` finding at 80–90% ("plan a cleanup soon") was
        # noise a tech could do nothing about; Storage Cleanup only offers
        # itself at 90%, so the alert and the remedy now arrive together.

    # Drive SMART / reliability — the coarse Healthy/Unhealthy rollup plus the
    # SSD-fleet early-warning signals (wear %, uncorrectable errors, OS pre-fail
    # flag) from Get-DiskHealth. Pre-fail takes precedence over high wear, and we
    # emit at most one of each so a multi-disk box doesn't spam the findings list.
    if disk_health and not disk_health.get("error"):
        prefail_drive = "A drive" if disk_health.get("predictFailure") else None
        wear_drive = None  # (name, wearPercent)
        for d in (disk_health.get("physicalDisks") or []):
            name = d.get("friendlyName") or "A drive"
            smart = d.get("smart") or {}
            uncorrected = (smart.get("readErrorsUncorrected") or 0) + (smart.get("writeErrorsUncorrected") or 0)
            health = (d.get("healthStatus") or "").strip().lower()
            wear = smart.get("wearPercent")
            if prefail_drive is None and (uncorrected > 0 or (health and health != "healthy")):
                prefail_drive = name
            if wear is not None and wear >= 80 and (wear_drive is None or wear > wear_drive[1]):
                wear_drive = (name, wear)
        if prefail_drive:
            findings.append(
                {
                    "code": "disk-smart-prefail",
                    "severity": "critical",
                    "category": "Storage",
                    "title": f"{prefail_drive} is predicting failure (SMART)",
                    "recommendation": (
                        "Back up recordings and plan to replace this drive. Its built-in "
                        "self-check (SMART) is reporting uncorrectable errors or a pre-failure status."
                    ),
                }
            )
        elif wear_drive:
            findings.append(
                {
                    "code": "disk-smart-wear",
                    "severity": "warning",
                    "category": "Storage",
                    "title": f"{wear_drive[0]} nearing end of rated life",
                    "recommendation": (
                        f"This SSD has used {wear_drive[1]}% of its rated write life. Plan a "
                        "replacement before it drops to read-only."
                    ),
                }
            )

    if services and not services.get("error"):
        # agent + coordinator are core capture processes (in C:\Pixellot\Bin,
        # detected by process not service). vpu-not-running is normal (idle).
        critical_svcs = {"agent", "coordinator"}
        for svc in services.get("services", []):
            name_lower = svc["name"].lower()
            display = svc.get("displayName") or svc["name"]
            status = svc.get("status")

            # KeepAgentUp is the watchdog that relaunches agent/coordinator if
            # they die. If it's down the VPU loses self-healing — warn even
            # when the core procs are currently up.
            if name_lower == "keepagentup":
                if status != "Running":
                    findings.append(
                        {
                            "code": "watchdog-down",
                            "severity": "warning",
                            "category": "Services",
                            "title": "Pixellot watchdog (KeepAgentUp) not running",
                            "recommendation": (
                                "KeepAgentUp relaunches Agent and Coordinator if they crash. "
                                "While it's down the VPU can't self-heal a process failure. "
                                "Use 'Restart Agent + Coordinator' on the Services page "
                                "(runs keepagentup.exe), or reboot the VPU."
                            ),
                        }
                    )
                continue

            # Core processes report Running/Stopped (never NotFound now — they
            # aren't services). NotFound remains possible for the real services.
            if status in ("Stopped", "NotFound") and name_lower in critical_svcs:
                findings.append(
                    {
                        "code": f"{name_lower}-down",  # agent-down / coordinator-down
                        "severity": "critical",
                        "category": "Services",
                        "title": f"{display} not running",
                        "recommendation": (
                            f"{display} is not running, so the VPU cannot capture or stream. "
                            f"Use 'Restart Agent + Coordinator' on the Services page "
                            f"(runs keepagentup.exe) to relaunch it."
                        ),
                    }
                )

    if nics and not nics.get("error"):
        # Sort into stable physical order and label "Port N" — matching the
        # Camera Connectivity tab and the dashboard NIC table. The raw Windows
        # adapter name ("Ethernet 30") is meaningless to a field tech; the
        # physical port number is what they need to check.
        ordered_ports = _order_ports_physically(nics.get("ports", []))
        # A CGI probe confirms the OCR/scoreboard camera regardless of the live
        # ARP cache — the probe always tries the default OCR IPs (.52/.53/.60)
        # whether or not a neighbor entry exists. We use this below so the OCR's
        # transient ARP entry can't flip the slow-port finding on and off
        # between dashboard polls. None/empty (callers that don't probe) →
        # falls back to the ARP-only behavior.
        probe_results = probe_results or {}
        ocr_confirmed = any(r.get("is_ocr") for r in probe_results.values())
        for idx, port in enumerate(ordered_ports):
            label = f"Port {idx + 1}"
            is_up = port.get("status") == "Up"
            speed = port.get("linkSpeedMbps")

            # NOTE: We deliberately do NOT emit a "port down" finding here.
            # A down port's ARP is stale (a live camera keeps its link up),
            # so flagging down ports on ARP alone produces false positives on
            # unused NIC ports. Genuine missing-camera detection belongs on
            # the Camera Connectivity tab via expected-vs-detected count,
            # which has the Pixellot config context to do it correctly.

            # Cameras only count on an UP link (stale-ARP guard, as above).
            pixellot_arps = []
            if is_up:
                pixellot_arps = [
                    a for a in (port.get("arpEntries") or [])
                    if _is_pixellot_mac(a.get("mac", ""))
                ]

            # Flag a camera port running below gigabit. The only legitimate
            # sub-gigabit case is an OCR / scoreboard camera (R2SD-G, S5SD-G),
            # which is natively 100 Mbps. Identify it the same way enrichment
            # does — by its link-local IP (the .52/.53/.60 default-OCR-IP
            # convention) — NOT by OUI: on many units the main heads share the
            # OCR's Dynacolor OUI (00:D0:89), so the OUI can't tell them apart
            # (and the raw ARP MAC is dash-formatted, so the old colon-prefix
            # check never matched anyway).
            if is_up and speed and speed < 1000:
                port_is_ocr = any(
                    (a.get("ip") or "").strip() in _DEFAULT_OCR_IPS
                    for a in pixellot_arps
                )
                # ARP-independent OCR guard. The OCR is natively 100 Mbps, and
                # its neighbor entry ages out when the camera is quiet — so a
                # cold poll can show its port at 100 Mbps with an EMPTY ARP
                # list, and the check above (which needs a default-OCR-IP ARP
                # entry) would then wrongly flag it as "running slow". The
                # finding then vanishes on the next poll once a camera probe
                # re-warms ARP — the flicker field techs reported. When a CGI
                # probe confirms an OCR is present and this 100 Mbps port
                # carries no identified MAIN camera, treat the link as the
                # expected OCR, matching the Camera Connectivity tab (which
                # uses the same probe and never flags it).
                if speed == 100 and ocr_confirmed and not port_is_ocr:
                    port_has_main = False
                    for a in pixellot_arps:
                        if (a.get("ip") or "").strip() in _DEFAULT_MAIN_IPS:
                            port_has_main = True
                            break
                        pr = probe_results.get(
                            (a.get("mac") or "").strip().upper().replace("-", ":")
                        )
                        if pr:
                            role, _ = _lookup_camera_model(pr.get("modelNumber"))
                            if role and "OCR" not in role:
                                port_has_main = True
                                break
                    if not port_has_main:
                        port_is_ocr = True
                only_ocr_at_100 = speed == 100 and port_is_ocr
                # Cold-start ambiguity: a 100 Mbps port with an empty ARP
                # list, where probes RAN but none answered (both caches
                # cold, right after launch), is indistinguishable from the
                # expected OCR — the ocr_confirmed guard above needs at
                # least one probe to have landed. Don't alarm on it during
                # the startup grace; the next collection has warm probes
                # and decides for real. Callers that never probe
                # (probe_results=None) keep the ARP-only behavior.
                cold_start_ambiguous = (
                    speed == 100
                    and not pixellot_arps
                    and probes_attempted
                    and not probe_results
                    and _in_startup_grace()
                )
                if not only_ocr_at_100 and not cold_start_ambiguous:
                    has_cameras = bool(pixellot_arps)
                    # A degraded link on a camera port is a Camera problem
                    # (frames drop); a bare NIC at low speed is Network.
                    category = "Camera" if has_cameras else "Network"
                    findings.append(
                        {
                            "code": "nic-slow",
                            "severity": "warning",
                            "category": category,
                            "title": f"{'Camera' if has_cameras else 'Network'} port {idx + 1} is running slow at {speed} Mbps (should be 1 Gbps)",
                            "recommendation": (
                                f"{label} ({port.get('name', 'unknown')}) negotiated to "
                                f"{speed} Mbps instead of 1 Gbps. Camera streams on this port "
                                f"will drop frames at reduced bandwidth. Check cable quality "
                                f"(Cat5e+ required), reseat the connector, and confirm the "
                                f"switch port is set to auto-negotiate."
                            ),
                        }
                    )

    # ── Half-finished install (PDF #3) ───────────────────────
    # If part_1/2/3 files exist in c:\pixellot\downloadedversion and the
    # most-recent installer log doesn't end with "Rebooting...", the last
    # install run was interrupted and needs to be resumed.
    if install_state and not install_state.get("error") and install_state.get("incomplete"):
        part_count = install_state.get("partCount", 0)
        log = install_state.get("log") or {}
        last_line = (log.get("lastLine") or "").strip()
        log_name = log.get("name") or "(no log)"
        last_excerpt = last_line[:160] + ("…" if len(last_line) > 160 else "")
        findings.append(
            {
                "code": "install-incomplete",
                "severity": "warning",
                "category": "Pixellot",
                "title": "Pixellot update didn't finish",
                "recommendation": (
                    f"A previous update stopped partway through. Re-run the installer in "
                    f"C:\\pixellot\\downloadedversion to complete it. ({part_count} part "
                    f"file(s) present; {log_name} didn't reach 'Rebooting...'. Last log "
                    f'line: "{last_excerpt}".)'
                ),
            }
        )

    # ── Required port blocked ────────────────────────────────
    # Test-NetworkPorts hits the cloud endpoints Pixellot needs to stream.
    # A "required" (non-optional) port that fails is almost always a venue
    # firewall blocking it — surfaces on the Dashboard so the tech sees it
    # without drilling into the Network tab. Optional ports (RTMP, etc.)
    # are intentionally skipped — they vary by venue configuration.
    if port_tests and not port_tests.get("error"):
        results = port_tests.get("results", [])
        # Streaming model (verified from VPU logs + packet capture, Olympic WA
        # 2026-08-18): the feeder walks a fixed failover chain — Zixi UDP/2088
        # (Zixi Streaming) → Zixi UDP/443 (Zixi Backup, same protocol on a
        # disguise port) → RTMP TCP/1935 (RTMP Fallback) → nothing. Either UDP
        # rung alone is a fully healthy stream. RTMP is a degraded last resort:
        # each dead rung burns ~60s of retries (~4 min of dead air when all
        # four Zixi attempts fail) and RTMP carries no FEC/ARQ. TCP/443
        # (Pixellot Echo) is the CONTROL PLANE — cloud API, remote support,
        # VOD upload — and carries no live video; it is handled by the generic
        # required-port loop below, not here. Keep purposes in sync with
        # ZIXI_PURPOSES / RTMP_FALLBACK_PURPOSE in app.js and
        # Test-NetworkPorts.ps1.
        zixi_purposes = {"Zixi Streaming", "Zixi Backup"}
        rtmp_fallback_purpose = "RTMP Fallback"
        stream_rung_purposes = zixi_purposes | {rtmp_fallback_purpose}

        def _lbl(rows):
            return ", ".join(
                f"{(r.get('protocol') or '').upper()}/{r.get('port')}" for r in rows
            )

        rungs = [
            r for r in results
            if r.get("purpose") in stream_rung_purposes and not r.get("optional")
        ]
        rungs_blocked = [r for r in rungs if r.get("status") == "fail"]
        zixi_open = any(
            r.get("purpose") in zixi_purposes and r.get("status") == "pass"
            for r in rungs
        )
        rtmp_rows = [r for r in rungs if r.get("purpose") == rtmp_fallback_purpose]
        rtmp_open = any(r.get("status") == "pass" for r in rtmp_rows)

        if rungs and not zixi_open and not rtmp_open:
            # Every rung of the failover chain is dead — the broadcast cannot
            # go on air. The only tier that earns "can't broadcast".
            findings.append({
                "code": "stream-blocked",
                "severity": "critical",
                "category": "Network",
                "title": "Streaming is blocked, so the VPU can't broadcast",
                "recommendation": (
                    "The venue's network is blocking every path the VPU can use to "
                    "send live video: the primary and backup streaming connections "
                    "and the last-resort fallback. The game can't broadcast until at "
                    f"least one is unblocked. Ask the venue's IT team to open "
                    f"{_lbl(rungs_blocked)} (UDP to prod-echo.pixellot.tv; the live "
                    "stream itself goes to *.pixellot.stream, so domain-based rules "
                    "are needed on filters that classify by destination)."
                ),
            })
        elif rungs and not zixi_open:
            # Both Zixi/UDP rungs dead, RTMP reachable: games WILL air, but on
            # the unprotected last resort — ~4 min of dead air at the start
            # while the feeder walks the dead rungs, then RTMP with no loss
            # protection. Urgent, but not "can't broadcast".
            findings.append({
                "code": "stream-degraded-rtmp",
                "severity": "critical",
                "category": "Network",
                "title": "Streaming is degraded and running on the emergency fallback",
                "recommendation": (
                    "The venue's network blocks both Zixi streaming connections "
                    f"({_lbl([r for r in rungs_blocked if r.get('purpose') in zixi_purposes])}), "
                    "so broadcasts fall back to RTMP over TCP/1935. Games start "
                    "roughly 4 minutes late and stream with no packet-loss "
                    "protection. Ask the venue's IT team to open UDP 2088 and "
                    "UDP 443 outbound. On filters that classify by destination they "
                    "need to allow the domain *.pixellot.stream, because broadcast "
                    "servers rotate per event."
                ),
            })
        elif rungs_blocked:
            # Stream is healthy on Zixi, but one or more rungs of the chain are
            # blocked — reduced resiliency, not an outage.
            on_backup = not any(
                r.get("purpose") == "Zixi Streaming" and r.get("status") == "pass"
                for r in rungs
            )
            findings.append({
                "code": "stream-resiliency-reduced",
                "severity": "warning",
                "category": "Network",
                "title": (
                    "Streaming is riding its backup connection"
                    if on_backup else "Streaming resiliency is reduced"
                ),
                "recommendation": (
                    ("The primary streaming connection (UDP/2088) is blocked, so the "
                     "stream rides the UDP/443 backup. Quality is unaffected, but it "
                     "is one step from the degraded RTMP fallback. "
                     if on_backup else
                     "The stream is healthy, but part of its failover chain is "
                     "blocked, so there is less to fall back on if the main "
                     "connection has trouble during a game. ")
                    + f"Ask the venue's IT team to unblock {_lbl(rungs_blocked)}."
                ),
            })

        # Name resolution demonstrably working? Any required hostname-based port
        # that passed proves it (you can't reach pixellot.tv:443 without resolving
        # pixellot.tv) — so a failed UDP/53 probe must NOT be reported as DNS down
        # (it can target a stale resolver off another adapter, or go unanswered).
        name_resolution_ok = any(
            r.get("status") != "fail" and not r.get("optional")
            and (r.get("purpose") or "").upper() != "DNS"
            and any(c.isalpha() for c in str(r.get("host") or ""))
            for r in results
        )

        # Non-streaming required ports — each blocked one is its own warning.
        # The streaming failover rungs are handled above, so skip those. Note
        # TCP/443 (Pixellot Echo) lands here on purpose: it's the control
        # plane (cloud API, remote support, VOD upload), not a streaming rung.
        for r in results:
            if r.get("status") != "fail" or r.get("optional"):
                continue
            if r.get("purpose") in stream_rung_purposes:
                continue
            host = r.get("host", "?")
            port = r.get("port", "?")
            proto = (r.get("protocol") or "").upper()
            purpose = r.get("purpose") or "service"
            err = r.get("errorMessage") or "No response"
            # DNS (port 53) blocked breaks name resolution for everything → a
            # readiness blocker; every other required port is a readiness risk.
            is_dns = purpose.upper() == "DNS" or str(port) == "53"
            # …but don't cry "DNS blocked" when names are clearly resolving — the
            # UDP/53 probe is unreliable and can hit the wrong resolver.
            if is_dns and name_resolution_ok:
                continue
            findings.append(
                {
                    "code": "port-dns-blocked" if is_dns else "port-required-blocked",
                    "severity": "warning",
                    "category": "Network",
                    "title": f"{purpose} is blocked ({proto}/{port})",
                    "recommendation": (
                        f"{proto} port {port} to {host} is unreachable ({err}). "
                        f"This is a required Pixellot endpoint. Ask the venue's "
                        f"IT team to open it in the firewall."
                    ),
                }
            )

    # ── SSL inspection (certificate substitution) ──────────────
    # Test-TlsInspection completes a real handshake to each Pixellot-critical
    # HTTPS service and validates the certificate actually presented. An
    # "intercepted" row means a middlebox (school firewall doing SSL
    # deep-packet inspection) substituted its own cert — the field signature
    # is video streaming fine while Singular graphics never load, because the
    # graphics client rightly rejects the firewall's cert. Port tests can't
    # see this (TCP/443 connects fine), so this is its own finding. Only the
    # confirmed substitution goes to the dashboard; softer TLS signals
    # (handshake failures, clock-related cert errors) stay on the Network tab.
    if tls_inspection and not tls_inspection.get("error"):
        tls_rows = tls_inspection.get("results") or []
        intercepted = [r for r in tls_rows if r.get("status") == "intercepted"]
        if intercepted:
            interceptors = ", ".join(tls_inspection.get("interceptorIssuers") or [])
            hosts = ", ".join(r.get("domain", "?") for r in intercepted)
            exempt = _tls_exempt_list(intercepted)
            findings.append(
                {
                    "code": "ssl-inspection",
                    "severity": "critical",
                    "category": "Network",
                    "title": "The venue firewall is intercepting secure connections (SSL inspection)",
                    "recommendation": (
                        f"The firewall{f' ({interceptors})' if interceptors else ''} is replacing "
                        f"the VPU's certificates for {hosts}, so the VPU refuses those connections. "
                        f"Ask venue IT to exempt these from SSL decryption (an allowlist entry "
                        f"alone won't do it): {exempt}"
                    ),
                }
            )

        # ── Category / SNI filtering (no certificate substitution) ──
        # The other half of the DPI story, and the half Pulse used to mumble
        # about. A content filter reads the hostname from the unencrypted SNI
        # field of the ClientHello and, if the domain sits in a blocked
        # category, resets the connection outright. Nothing is decrypted, no
        # cert is substituted, so `intercepted` never fires — the collector
        # marks these rows `filtered`. Field: Linewize at an Ohio venue
        # 2026-08-19 — eight Pixellot-critical hosts reset while readiness
        # still read PASS, because the only signal was a soft "possible SSL
        # inspection" note on the Network tab.
        #
        # The distinction matters operationally: an SSL-decryption bypass
        # does NOT fix a category block, and vice versa. Say which one it is.
        filtered = [r for r in tls_rows if r.get("status") == "filtered"]
        if filtered:
            vendors = [v for v in (tls_inspection.get("filterVendors") or []) if v]
            vendor_txt = " / ".join(vendors)
            block_urls = [r.get("blockPageUrl") for r in filtered if r.get("blockPageUrl")]
            broadcast_hit = [
                r for r in filtered
                if (r.get("domain") or "") in _BROADCAST_CRITICAL_TLS_DOMAINS
            ]
            hosts = ", ".join(r.get("domain", "?") for r in filtered)
            # Dashboard findings render as a title only, so the title has to
            # be the whole statement: what is blocking, and how much.
            who = (
                f"Venue web filter ({vendor_txt})" if vendor_txt
                else "A web filter on the venue network"
            )
            who_lower = (
                f"The venue's {vendor_txt} web filter" if vendor_txt
                else "A web filter on the venue network"
            )
            evidence = (
                f" The filter's block page names the rule it applied: {block_urls[0]}"
                if block_urls else ""
            )
            fix = (
                f"Ask venue IT for a category exception (not just a URL entry) and an "
                f"SSL-decryption exemption: {_tls_exempt_list(filtered)}"
            )
            if broadcast_hit:
                findings.append(
                    {
                        "code": "tls-filtered",
                        "severity": "critical",
                        "category": "Network",
                        "title": (
                            f"{who} is blocking {len(filtered)} Pixellot service"
                            f"{'s' if len(filtered) != 1 else ''}"
                        ),
                        "recommendation": (
                            f"{who_lower} drops connections to {hosts} by category. Certificates "
                            f"aren't touched, so an SSL-decryption bypass alone won't fix it. "
                            f"{fix}{evidence}"
                        ),
                    }
                )
            else:
                findings.append(
                    {
                        "code": "tls-filtered-support",
                        "severity": "warning",
                        "category": "Network",
                        "title": (
                            f"{who} is blocking {len(filtered)} support service"
                            f"{'s' if len(filtered) != 1 else ''} ({hosts})"
                        ),
                        "recommendation": (
                            f"Tonight's broadcast is unaffected, but remote support and installer "
                            f"downloads will fail on this network. {fix}{evidence}"
                        ),
                    }
                )

    # ── LogMeIn's own log confirms the block (historical evidence) ──
    # Get-LmiGatewayLog reads LogMeIn's service log for the middlebox
    # signature: "SSL error: SSLv3/TLS write client hello" on every gateway
    # connect — the handshake killed the instant it starts, the same mechanism
    # as the 'filtered' rows above. The live TLS probe only sees the network
    # as it is right now; the log carries the timeline (when the block
    # started, and — after IT disables inspection — the exact minute the unit
    # came back). Field origin: a VPU dark in LMI for 16 hours, 2026-08-28.
    # Only a CURRENT block reaches the dashboard; a recovered one is history
    # and stays on the Network tab.
    if lmi_log and not lmi_log.get("error") and lmi_log.get("blockedNow"):
        n = lmi_log.get("sslFailures") or 0
        since = (lmi_log.get("firstSslFailure") or "")[:10]
        last_ok = lmi_log.get("lastLogin")
        findings.append(
            {
                "code": "lmi-ssl-blocked",
                "severity": "warning",
                "category": "Network",
                "title": (
                    "The venue network is killing LogMeIn's secure connection "
                    "— remote support can't reach this VPU"
                ),
                "recommendation": (
                    f"LogMeIn's own service log shows {n} failed secure handshakes"
                    + (f" since {since}" if since else "")
                    + (f", and no successful gateway login since {last_ok}"
                       if last_ok else ", and no successful gateway login in the log")
                    + ". Each attempt dies the instant LogMeIn starts its TLS "
                    "handshake — the signature of a firewall inspecting or "
                    "category-blocking the connection. Note LogMeIn connects to "
                    "control.lmi-app*.logmein.com gateways and speaks TLS on port "
                    "80 as well as 443, so ask the venue's IT team to exempt "
                    "*.logmein.com AND logmein.com from both SSL inspection and "
                    "the web filter's category policy — an allowlist entry for "
                    "secure.logmein.com alone will not cover the gateways. "
                    "The timeline in C:\\ProgramData\\LogMeIn is evidence you "
                    "can hand them."
                ),
            }
        )

    # ── Missing / under-count main cameras ─────────────────────
    # Compare what the Coordinator says the VPU is configured for
    # (`expectedMainCameras`, from Get-CameraExpectations) against what's
    # actually present on the camera NIC. Only fires when we have an
    # authoritative expected count — never guesses. OCR ports don't count
    # toward the main total (the OCR camera is its own role).
    if expectations and not expectations.get("error") and nics and not nics.get("error"):
        expected_main = expectations.get("expectedMainCameras")
        if isinstance(expected_main, int) and expected_main > 0:
            # Enrich ports for accurate Main vs OCR classification (by ARP +
            # default-OCR-IP convention; no CGI probe results required).
            enriched_ports = _enrich_ports(nics, pixellot_config, None)
            detected_main = 0
            for p in enriched_ports:
                if not p.get("isUp") or p.get("isOcr"):
                    continue
                for c in (p.get("camerasDetected") or []):
                    if "OCR" not in (c.get("role") or ""):
                        detected_main += 1

            # ── ARP-independent count from CGI probes ──
            # The ARP snapshot alone can read zero on a cold start: cameras
            # that sat quiet age out of the Windows neighbor cache, so the
            # count above sees nothing even though both mains are alive.
            # The CGI probe always tries the default camera IPs regardless
            # of ARP (same philosophy as the ARP-independent OCR guard on
            # the slow-port finding), so a probe answer is positive proof a
            # camera is present. probe_results is keyed by MAC — each
            # camera counts once. Take the better of the two counts.
            probe_main = 0
            for r in (probe_results or {}).values():
                role, _speed = _lookup_camera_model(r.get("modelNumber"))
                if role is not None:
                    probe_is_ocr = "OCR" in role
                else:
                    probe_is_ocr = (
                        bool(r.get("is_ocr"))
                        or (r.get("ip") or "").strip() in _DEFAULT_OCR_IPS
                    )
                if not probe_is_ocr:
                    probe_main += 1
            detected_main = max(detected_main, probe_main)

            # Cold-start guard for the zero-count CRITICAL. If probes ran
            # but nothing was seen by ARP *or* probe while a non-OCR port
            # has live link, the link layer contradicts "no cameras" — a
            # link doesn't come up without a powered device on the other
            # end. During the startup grace that reading means the
            # collection burst starved both caches, not that the rig is
            # dark; skip once and let the next collection (warm caches)
            # decide. Ports genuinely down still alarm immediately, even
            # at startup.
            suppress_cold_zero = (
                detected_main == 0
                and probes_attempted
                and not (probe_results or {})
                and _in_startup_grace()
                and any(
                    p.get("isUp") and not p.get("isOcr")
                    for p in enriched_ports
                )
            )
            if detected_main < expected_main and not suppress_cold_zero:
                missing = expected_main - detected_main
                if detected_main == 0:
                    sev = "critical"
                    title = f"No main cameras detected (expected {expected_main})"
                    rec = (
                        f"The VPU is configured for {expected_main} main camera"
                        f"{'s' if expected_main != 1 else ''} but none are reporting "
                        f"on the camera NIC. Check that the camera cables are seated, "
                        f"the cameras have power, and the correct ports are in use. "
                        f"See the Camera Connectivity tab for per-port detail."
                    )
                else:
                    sev = "warning"
                    title = (
                        f"{detected_main} of {expected_main} main cameras detected "
                        f"({missing} missing)"
                    )
                    rec = (
                        f"{missing} main camera{'s are' if missing != 1 else ' is'} "
                        f"expected but not detected. Inspect the missing port(s) on "
                        f"the Camera Connectivity tab. It is usually a cable, a switch "
                        f"port, or camera power."
                    )
                findings.append({
                    "code": "cam-none" if detected_main == 0 else "cam-partial",
                    "severity": sev,
                    "category": "Camera",
                    "title": title,
                    "recommendation": rec,
                })

    # Deduplicate by (category, title) — separate checks shouldn't produce
    # the same finding twice on the dashboard.
    seen = set()
    deduped = []
    for f in findings:
        key = (f.get("category", ""), f.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    return deduped


# ── Stream Readiness Engine (policy v1) ──────────────────────────────────
# Rolls the per-run findings above into one PASS / WARN / FAIL verdict per
# VPU. Spec: ~/Code/Resources/stream-readiness-policy-v1.md (decided 2026-06-16).
#
# The policy is DATA, not code: each finding `code` maps to a readiness class
# (blocker / risk / info). A season of calibration is table edits, not redeploys.
#
# Readiness class is a deliberate OVERRIDE of the diagnostic severity — they
# diverge on purpose. OS-end-of-support is `critical` on the dashboard but
# readiness `info` (it never stops tonight's game); iGPU-only is `warning` but
# readiness `blocker` (wrong hardware, can't encode). Don't reuse `severity`.
READINESS_POLICY_VERSION = "v1"

_READINESS_POLICY = {
    # ── BLOCKERS → FAIL (don't expect a clean broadcast tonight) ──
    "stream-blocked":        "blocker",  # F1  every streaming rung dead (UDP/2088,
                                         #     UDP/443, TCP/1935) — broadcast cannot
                                         #     go on air. Replaced stream-2088-blocked
                                         #     when the failover chain was verified
                                         #     (Olympic WA, 2026-08-18).
    "agent-down":            "blocker",  # F2  core capture process down
    "coordinator-down":      "blocker",  # F3  core capture process down
    "cam-none":              "blocker",  # F4  0 of N main cameras present
    "gpu-none":              "blocker",  # F5  no NVIDIA GPU — encoder can't run
    "gpu-igpu-only":         "blocker",  # F11 Intel iGPU only — wrong hardware
    "port-dns-blocked":      "blocker",  # F23a DNS down → name resolution fails
    "ssl-inspection":        "blocker",  # F37 venue DPI substituting certs on
                                         #     Pixellot-critical HTTPS. Every port
                                         #     test stays green, so nothing else
                                         #     gates on it — but the affected
                                         #     services are cut off outright and
                                         #     only the venue's firewall can fix
                                         #     it. Field: East Henderson (NC),
                                         #     2026-08-10 (Zscaler).
    "tls-filtered":          "blocker",  # F38 venue content filter resetting the
                                         #     TLS handshake to Pixellot-critical
                                         #     hosts (blocked category / SNI block).
                                         #     Same practical outcome as F37 -
                                         #     graphics, scheduling and updates
                                         #     severed, fixable only on the venue
                                         #     network - but a different fix, so it
                                         #     is its own code. Field: Linewize,
                                         #     Ohio venue 2026-08-19, where this
                                         #     scored PASS.
    # F15a C: disk >90% is computed below from disk-health (not the
    # `disk-critical` finding — see _compute_readiness).

    # ── RISKS → WARN (will likely stream, but a human should eyeball) ──
    "cam-partial":           "risk",     # F6  k of N present (k>0)
    "nic-slow":              "risk",     # F7  camera NIC below gigabit
    "stream-degraded-rtmp":  "risk",     # F1b both UDP rungs dead, RTMP open — games
                                         #     air ~4 min late, no loss protection.
                                         #     Diagnostic severity is critical; games
                                         #     still air, so readiness is WARN not FAIL.
    "stream-resiliency-reduced": "risk", # F8  stream healthy on Zixi but part of the
                                         #     failover chain blocked (was stream-443-blocked)
    "watchdog-down":         "risk",     # F9  KeepAgentUp down — no self-heal
    "pixellot-over-cap":     "risk",     # F10 build newer than GPU/OS supports
    "gpu-anomaly":           "risk",     # F12 Volta / roster anomaly
    "install-incomplete":    "risk",     # F13 interrupted installer, agent up
    # F16 (`disk-low`, a volume at 80–90%) removed — disk fill is critical-only now.
    "disk-smart-prefail":    "risk",     # F16b drive SMART pre-fail / uncorrectable errors
    "ram-insufficient":      "risk",     # F21 <32 GB host
    "ntp-unapproved":        "risk",     # F22 drift can break signed-URL stream
    "port-required-blocked": "risk",     # F23b NTP / Pixellot cloud / etc.
    "wifi-uplink":           "risk",     # F24 Wi-Fi uplink — latency/loss
    # F14 temp≥90, F15b D:>90, F17 CPU sustained, F19 mem sustained are computed
    # below (readiness-specific thresholds the dashboard findings don't surface).

    # ── INFO → context only (never gates the verdict) ──
    "cpu-elevated":          "info",     # F18 75–90% snapshot
    "mem-elevated":          "info",     # F20 80–90% snapshot
    "cpu-critical":          "info",     # snapshot >90% — readiness uses the average (F17)
    "mem-critical":          "info",     # snapshot >90% — readiness uses the average (F19)
    # Kept classified so test_every_critical_finding_code_is_classified holds,
    # but for C:/D: the finding carries supersededBy and never reaches here --
    # F15a/F15b report those drives at their own class. This entry is the
    # fallback for any OTHER volume >90%.
    "disk-critical":         "info",
    "disk-smart-wear":       "info",     # SSD ≥80% rated life — heads-up, won't stop tonight's game
    "temp-critical":         "info",     # 85°C snapshot — readiness gate is 90°C (F14)
    "tz-non-us":             "info",     # F25
    "os-eos-reached":        "info",     # F26
    "os-eos-imminent":       "info",     # F27
    "os-eos-approaching":    "info",     # F28
    "os-mainstream-eos":     "info",     # headline EOS passed, IoT servicing continues
    "sw-security":           "info",     # F29 (if it's blocking agent.exe, that surfaces as F2)
    "sw-crypto-miner":       "info",     # F30
    "sw-torrent":            "info",     # F31
    "sw-system-cleaner":     "info",     # F32
    "sw-alt-remote":         "info",     # F33
    "sw-game-platform":      "info",     # F34
    "sw-consumer-sync":      "info",     # F35
    "uptime-high":           "info",     # F36
    "tls-filtered-support":  "info",     # F38b only support-plane hosts filtered
                                         #      (LogMeIn / python.org) - remote
                                         #      support and installer downloads
                                         #      suffer, tonight's game does not.
    "lmi-ssl-blocked":       "info",     # F39 LogMeIn's own service log shows the
                                         #     venue killing its TLS handshakes
                                         #     (SSL error on client hello) with no
                                         #     login since. Support plane like
                                         #     F38b - remote support is cut off,
                                         #     tonight's game is not. Field:
                                         #     2026-08-28, VPU dark in LMI ~16h
                                         #     until packet inspection was
                                         #     disabled.
}


def _readiness_class(code: str) -> str:
    """Map a finding code to its readiness class. Unmapped / unknown codes →
    `info` (Ian's call: note an unverifiable or new check, never gate on it)."""
    return _READINESS_POLICY.get(code or "", "info")


def _disk_used_by_letter(disk_health, performance):
    """Return (cPct, dPct) used-percent for C:/D: from the disk-health
    collection — the same per-volume source the System Disk gauge uses
    (`_systemDiskPct` in app.js). `performance.disk.usedPercent` is an
    ALL-VOLUMES AGGREGATE, not C:, so it's only a last-resort fallback for C:
    when disk-health didn't run."""
    c_pct = d_pct = None
    if disk_health and not disk_health.get("error"):
        for d in (disk_health.get("logicalDisks") or []):
            letter = (d.get("deviceID") or "").rstrip(":").upper()
            if letter == "C":
                c_pct = d.get("usedPercent")
            elif letter == "D":
                d_pct = d.get("usedPercent")
    if c_pct is None and performance and not performance.get("error"):
        c_pct = (performance.get("disk") or {}).get("usedPercent")
    return c_pct, d_pct


def _compute_readiness(findings, performance=None, disk_health=None,
                       perf_sample=None, now=None) -> dict:
    """Roll the findings into one PASS / WARN / FAIL verdict per VPU.

    Rollup: any blocker → FAIL · any risk → WARN · else PASS. The return value
    is an auditable record — `{timestamp, policyVersion, status, blockers,
    risks, info}` — so every FAIL says exactly which findings drove it and old
    verdicts can be re-scored when the policy table changes.

    Most classes come straight from the policy table keyed on each finding's
    `code`. Four checks are computed here instead, because readiness uses a
    different metric or threshold than the dashboard finding does:
      • F17/F19 — CPU/mem averaged over a short sample (not a one-instant snapshot)
      • F14     — temperature ≥90°C (the dashboard finding keeps its 85°C tier)
      • F15a/b  — C:/D: by drive letter from disk-health (not the aggregate)
    """
    blockers, risks, info = [], [], []

    def add(cls, code, title, recommendation, category=""):
        entry = {
            "code": code,
            "title": title,
            "recommendation": recommendation,
            "category": category,
        }
        {"blocker": blockers, "risk": risks}.get(cls, info).append(entry)

    # (1) Finding-derived classes, straight from the policy table.
    for f in (findings or []):
        code = f.get("code") or ""
        # A finding that names its successor is the same condition a
        # readiness-specific check below reports at the right class. Adding it
        # too would put one full drive in the record twice, once as `info`.
        if f.get("supersededBy"):
            continue
        add(_readiness_class(code), code, f.get("title", ""),
            f.get("recommendation", ""), f.get("category", ""))

    # (2) Readiness-specific computed checks (different metric/threshold than
    #     the dashboard finding — see docstring).
    # F17 — CPU sustained >90%, from the averaged sample (snapshot fallback).
    cpu_avg = (perf_sample or {}).get("cpuAvgPercent")
    if cpu_avg is None and performance and not performance.get("error"):
        cpu_avg = (performance.get("cpu") or {}).get("usagePercent")
    if isinstance(cpu_avg, (int, float)) and cpu_avg > 90:
        add("risk", "cpu-sustained", "CPU sustained above 90%",
            f"CPU averaged {cpu_avg:g}% over the sample window. Sustained load "
            f"this high risks dropped frames mid-broadcast. Check for a runaway "
            f"process before game time.", "Performance")

    # F19 — Memory sustained >90%, averaged (snapshot fallback).
    mem_avg = (perf_sample or {}).get("memAvgPercent")
    if mem_avg is None and performance and not performance.get("error"):
        mem_avg = (performance.get("memory") or {}).get("usedPercent")
    if isinstance(mem_avg, (int, float)) and mem_avg > 90:
        add("risk", "mem-sustained", "Memory sustained above 90%",
            f"Memory averaged {mem_avg:g}% over the sample window. The encoder "
            f"can stall under sustained pressure. Close apps or add RAM.",
            "Performance")

    # F14 — Temperature ≥90°C (dashboard finding still fires its own at 85°C).
    if performance and not performance.get("error"):
        temp = (performance.get("temperature") or {}).get("celsius")
        if isinstance(temp, (int, float)) and temp >= 90:
            add("risk", "temp-90", "Temperature high (≥90°C)",
                f"Temperature at {temp:g}°C. Sustained heat throttles the encoder "
                f"and risks frame drops. Check airflow and fans.", "Hardware")

    # F15a/b — C:/D: by drive letter. Critical-only: the old 80–90%
    # `disk-c-low` risk band was removed along with the disk-low finding.
    #
    # C: is a blocker and D: is INFO, and the asymmetry is the whole point.
    # Readiness answers one question — can this VPU stream tonight's game —
    # and the live stream is processed on C: (see drive_roles above), so a
    # full C: can stop capture. Nothing in the broadcast path touches D:; it
    # holds the post-event VOD. A 91%-full D: cannot stop or degrade a
    # broadcast, so calling it a risk overstated it, and calling it a blocker
    # (which the display briefly did) was simply wrong.
    #
    # It is not nothing, though: a full D: means the school loses its
    # recording. That consequence rides in the title rather than in the
    # severity, so "Worth knowing" cannot be read as "ignore this", and the
    # Disks tab still renders any volume over 90% as Critical on its own
    # (app.js ~6115) — so a tech working storage sees the urgency there,
    # where the fix is.
    c_pct, d_pct = _disk_used_by_letter(disk_health, performance)
    if isinstance(c_pct, (int, float)) and c_pct > 90:
        add("blocker", "disk-c-critical", "System drive (C:) almost full",
            f"C: is {c_pct:g}% full. The live stream is processed on C:. If it "
            f"fills, the VPU can't process the broadcast. Free space on C: now.",
            "Storage")
    if isinstance(d_pct, (int, float)) and d_pct > 90:
        add("info", "disk-d-critical",
            "Recording drive (D:) almost full — recordings may not save",
            f"D: is {d_pct:g}% full. The post-event recording (VOD) is written to "
            f"D:. If it fills during the game the recording may not save. Free "
            f"space on D:.", "Storage")

    status = "FAIL" if blockers else "WARN" if risks else "PASS"
    from datetime import datetime, timezone
    return {
        "timestamp": (now or datetime.now(timezone.utc)).isoformat(),
        "policyVersion": READINESS_POLICY_VERSION,
        "status": status,
        "blockers": blockers,
        "risks": risks,
        "info": info,
    }


def _build_camera_sets(pixellot_config=None):
    """Return cameras.cfg-derived sets for OCR and Main camera identification.

    Returns dict with keys:
      ocr_ips, ocr_macs  — OCR cameras (role contains "OCR")
      main_ips, main_macs — Main/Panoramic/Tactical cameras (other roles)
    Always includes the hardcoded default OCR IPs.
    """
    ocr_ips = set(_DEFAULT_OCR_IPS)
    ocr_macs = set()
    main_ips = set()
    main_macs = set()
    cfg_cameras = []
    if pixellot_config and not pixellot_config.get("error"):
        cfg_cameras = pixellot_config.get("cameras", [])
    for cam in cfg_cameras:
        role = (cam.get("role") or cam.get("section") or "").strip()
        ip = cam.get("ip", "").strip()
        mac = cam.get("mac", "").strip().upper().replace("-", ":")
        if role.upper() == "OCR":
            if ip:
                ocr_ips.add(ip)
            if mac:
                ocr_macs.add(mac)
        elif role:
            # Main, Panoramic, Tactical, etc — non-OCR Pixellot camera roles.
            if ip:
                main_ips.add(ip)
            if mac:
                main_macs.add(mac)
    return {
        "ocr_ips": ocr_ips,
        "ocr_macs": ocr_macs,
        "main_ips": main_ips,
        "main_macs": main_macs,
    }


def _build_ocr_sets(pixellot_config=None):
    """Backwards-compatible wrapper — returns (ocr_ips, ocr_macs)."""
    s = _build_camera_sets(pixellot_config)
    return s["ocr_ips"], s["ocr_macs"]


def _mac_to_int(mac) -> int:
    """Normalize a MAC string to an int for sorting. Unknown → very large
    so MAC-less adapters sort last in ascending order."""
    try:
        return int(str(mac).upper().replace("-", "").replace(":", ""), 16)
    except (ValueError, AttributeError, TypeError):
        return 1 << 64


def _order_ports_physically(raw_ports):
    """Return NIC ports in stable physical order (Port 1 = lowest MAC).

    Windows `Get-NetAdapter` enumerates adapters in discovery order, which
    is effectively arbitrary and NOT stable between reads — that's why the
    Port N labels would shuffle when re-checked on-site. On Intel multiport
    camera NICs the per-port MACs are burned in sequentially in physical
    port order, so sorting by MAC restores a deterministic, physically
    meaningful order.

    Convention: lowest MAC = Port 1 (matches the demo data layout and the
    standard Intel base-MAC-on-port-1 assignment). If a chassis is found
    to label ports in the opposite direction, flip `reverse=` here.
    """
    return sorted(list(raw_ports or []), key=lambda p: _mac_to_int(p.get("mac")))


def _derive_down_reason(port: dict) -> str:
    """Classify *why* a down port is down, so the UI can guide the tech
    instead of just saying 'Down':
      disabled — adapter turned off in Windows (fixable: enable it)
      driver   — NIC driver reports a fault (escalate / reinstall driver)
      no-link  — link is enabled & driver OK, but nothing is on the wire
                 (cable unplugged/broken, or camera unpowered/dead)
    """
    # Coerce every field to a string before inspecting it. Windows reports
    # these as enums, and PowerShell's ConvertTo-Json serializes enums as
    # bare integers on a real VPU (demo data happens to use strings), so a
    # raw .lower() on an int crashes the whole /api/cameras endpoint.
    admin = str(port.get("adminStatus") or "").strip().lower()
    media = str(port.get("mediaConnectionState") or "").strip().lower()
    driver = str(port.get("driverStatus") or "").strip().lower()
    status = str(port.get("status") or "").strip().lower()
    if admin == "down" or status == "disabled":
        return "disabled"
    # driverStatus is a PnP health word ("OK"/"Error"/"Degraded"/...). If it
    # arrived as a bare numeric enum we can't interpret it, so ignore digits
    # rather than mis-flag a healthy driver as faulted.
    if driver and not driver.isdigit() and driver not in ("ok", "unknown"):
        return "driver"
    if media == "disconnected" or status in (
        "disconnected", "down", "not present", "lower layer down"
    ):
        return "no-link"
    return "down"


def _enrich_ports(
    nics: dict,
    pixellot_config: dict = None,
    probe_results=None,
    expected_main_cameras=None,
) -> list:
    """Enrich raw NIC port data with status flags and camera detection.

    Identity resolution, highest authority first (CGI is the source of
    truth; cameras.cfg is unreliable per field guidance):
      1. CGI model number → role + expected link speed (actual hardware)
      2. Pixellot default-IP convention (.50/.51 main, .52/.53/.60 OCR)
      3. CGI-confirmed Pixellot camera with unknown model → generic label
      4. cameras.cfg role mapping (last resort — may be inaccurate)
      5. Pixellot OUI only → vendor known, role unknown
    Degraded = actual speed < expected speed for the camera model. When
    model is unknown, any sub-1 Gbps non-OCR port is treated as degraded.

    probe_results: dict keyed by normalized MAC -> {mac, ip, is_ocr, ...}
    from _probe_all_cameras(). Optional — when absent, falls back to
    default-IP / cfg identification.
    """
    cam_sets = _build_camera_sets(pixellot_config)
    # cameras.cfg-derived sets ONLY (defaults handled separately below).
    # Per field guidance the cameras.cfg role data is not always accurate,
    # so it is used only as a last-resort identity hint — after CGI probe
    # and the Pixellot default-IP convention.
    cfg_ocr_ips = cam_sets["ocr_ips"] - _DEFAULT_OCR_IPS
    cfg_ocr_macs = cam_sets["ocr_macs"]
    cfg_main_ips = cam_sets["main_ips"]
    cfg_main_macs = cam_sets["main_macs"]
    probe_results = probe_results or {}

    ports = []
    if nics and not nics.get("error"):
        # Sort into stable physical order before assigning Port N labels —
        # raw Windows enumeration order is arbitrary and unstable.
        ordered = _order_ports_physically(nics.get("ports", []))
        for port_idx, port in enumerate(ordered):
            speed = port.get("linkSpeedMbps")
            is_up = port.get("status") == "Up"

            # Build enriched camera list from ARP entries.
            # A camera only communicates over an UP link. ARP entries linger
            # in the OS cache after a camera is unplugged or a link drops, so
            # a DOWN port's ARP is stale and must NOT be treated as a live
            # camera — otherwise an empty, never-used port shows a phantom
            # "OCR" badge and triggers a false "camera down" finding.
            cameras = []
            is_ocr = False
            expected_speed = None  # from camera model lookup
            arp_entries = port.get("arpEntries", []) if is_up else []
            for arp in arp_entries:
                arp_mac_raw = arp.get("mac", "")
                if not _is_pixellot_mac(arp_mac_raw):
                    continue
                arp_ip = (arp.get("ip") or "").strip()
                arp_mac = arp_mac_raw.strip().upper().replace("-", ":")

                # Determine camera identity — layered approach
                probe = probe_results.get(arp_mac)
                cam_entry = {**arp}

                # Copy all CGI probe fields (model, serial, streams, etc.)
                if probe:
                    cam_entry["cgiConfirmed"] = True
                    cam_entry["cgiMac"] = probe["mac"]
                    for pkey in ("model", "modelNumber", "brand",
                                 "productType", "serialNumber",
                                 "firmwareVersion", "tvMode", "network",
                                 "stream0", "stream1", "sensor"):
                        if probe.get(pkey) is not None:
                            cam_entry[pkey] = probe[pkey]

                # ── Identity resolution, highest authority first ──
                # CGI probe is the source of truth; cameras.cfg is a
                # last-resort hint because its role data is unreliable.
                model_role, model_speed = _lookup_camera_model(
                    cam_entry.get("modelNumber")
                )
                if model_role:
                    # 1. CGI model number — actual hardware identity.
                    cam_entry["role"] = model_role
                    cam_entry["identitySource"] = "Camera model"
                    cam_entry["expectedSpeedMbps"] = model_speed
                    expected_speed = model_speed
                    if "OCR" in model_role:
                        is_ocr = True
                elif arp_ip in _DEFAULT_OCR_IPS:
                    # 2. Pixellot default-IP convention (OCR: .52/.53/.60).
                    cam_entry["role"] = "OCR / Scoreboard"
                    cam_entry["identitySource"] = "Default OCR IP"
                    is_ocr = True
                elif arp_ip in _DEFAULT_MAIN_IPS:
                    # 2. Pixellot default-IP convention (main: .50/.51).
                    cam_entry["role"] = "Main Camera"
                    cam_entry["identitySource"] = "Default IP"
                elif probe:
                    # 3. CGI-confirmed Pixellot camera, model not in our
                    #    table — generic label beats a possibly-wrong
                    #    cameras.cfg role.
                    cam_entry["role"] = "Pixellot Camera"
                    cam_entry["identitySource"] = "CGI probe"
                elif arp_ip in cfg_ocr_ips or arp_mac in cfg_ocr_macs:
                    # 4. cameras.cfg — last resort.
                    cam_entry["role"] = "OCR / Scoreboard"
                    cam_entry["identitySource"] = "cameras.cfg"
                    is_ocr = True
                elif arp_ip in cfg_main_ips or arp_mac in cfg_main_macs:
                    cam_entry["role"] = "Main Camera"
                    cam_entry["identitySource"] = "cameras.cfg"
                else:
                    # 5. Pixellot OUI only — vendor known, role unknown.
                    cam_entry["role"] = None
                    cam_entry["identitySource"] = "OUI vendor match"

                cameras.append(cam_entry)

            # Degraded: compare actual speed against expected speed from
            # camera model. If model is unknown, fall back to < 1 Gbps
            # for non-OCR ports.
            if expected_speed is not None:
                is_degraded = (
                    is_up and speed is not None and speed < expected_speed
                )
            else:
                is_degraded = (
                    is_up
                    and speed is not None
                    and speed < 1000
                    and not is_ocr
                )

            # Populate expectedSpeedMbps so downstream consumers (findings,
            # fault isolator) have a consistent value. When model lookup
            # didn't fire, default to 100 for OCR (most common) or 1000
            # for everything else. This is a safe heuristic — the 1 Gbps
            # OCR variant (E8NC-G) only gets correctly classified when
            # CGI probe succeeds and the model match runs.
            if expected_speed is None and cameras:
                expected_speed = 100 if is_ocr else 1000

            ports.append(
                {
                    **port,
                    "portIndex": port_idx,
                    "portLabel": f"Port {port_idx + 1}",
                    "isUp": is_up,
                    "isOcr": is_ocr,
                    "isDegraded": is_degraded,
                    "expectedSpeedMbps": expected_speed,
                    "camerasDetected": cameras,
                    # Why is a down port down? (disabled / driver / no-link)
                    "downReason": None if is_up else _derive_down_reason(port),
                }
            )

    def _mac_key(c):
        return str(c.get("cgiMac") or c.get("mac") or "").upper().replace("-", ":")

    # ── A Down port has no live camera ──
    # No link means nothing is physically connected right now; any camera
    # in a down port's ARP table is a stale entry left over from before the
    # cable was unplugged/moved. During on-site troubleshooting techs plug
    # and unplug constantly, so trusting stale ARP on a dead port produced
    # phantom cameras and false "camera last detected" alarms. Clear them.
    for p in ports:
        if not p.get("isUp"):
            p["camerasDetected"] = []

    # ── Dedupe duplicate camera MACs across UP ports ──
    # Briefly, ARP lag can show the same camera MAC on two live ports right
    # after a move. A camera lives on exactly one port, so attribute it to
    # the port carrying the most RX traffic (the active stream) and strip
    # the stale copy from the other.
    mac_owners = {}  # mac → [port, ...]
    for p in ports:
        for c in p.get("camerasDetected") or []:
            m = _mac_key(c)
            if m:
                mac_owners.setdefault(m, []).append(p)

    for m, owners in mac_owners.items():
        if len(owners) <= 1:
            continue
        owners.sort(key=lambda p: -(p.get("rxBytes") or 0))
        for losing_port in owners[1:]:
            losing_port["camerasDetected"] = [
                c for c in losing_port.get("camerasDetected") or []
                if _mac_key(c) != m
            ]

    # ── Transition tracking: "connecting" state + finding settle window ──
    # Compare each port's current link/camera state to what we last saw.
    # When it changes, reset the settle timer. A freshly-changed port that
    # is up but hasn't resolved a camera yet is "connecting"; transient
    # findings are suppressed until it settles (see _compute_camera_findings).
    now_mono = time.monotonic()
    for p in ports:
        cams = p.get("camerasDetected") or []
        is_up = p.get("isUp")
        speed = p.get("linkSpeedMbps") or 0
        has_cam = bool(cams)
        cam_macs = ",".join(sorted(_mac_key(c) for c in cams))
        state_key = f"{is_up}|{speed}|{cam_macs}"
        adapter_id = p.get("mac") or p.get("name") or p.get("portLabel")

        prev = _PORT_STATE_TRACKER.get(adapter_id)
        prev_up = bool(prev.get("isUp")) if prev else None  # None = never seen

        # up_since: when this port most recently went down→up. Tracks the LINK
        # transition specifically (not speed/camera changes) so the blue
        # "connecting" cue fires on every reconnect, even when the camera
        # resolves instantly from cache. On first sight (prev is None) treat an
        # already-up port as long-established — never flash "connecting" just
        # because the page loaded.
        if prev is None:
            up_since = (now_mono - _PORT_CONNECTING_SECONDS) if is_up else None
        elif is_up and not prev_up:
            up_since = now_mono                       # observed a real down→up
        elif is_up:
            up_since = prev.get("upSince") or now_mono
        else:
            up_since = None                           # down

        if not prev or prev["key"] != state_key:
            # State changed — reset the settle timer but carry forward the
            # "this port has hosted a camera" memory used for drop detection.
            entry = {
                "key": state_key,
                "since": now_mono,
                "everHadCamera": (prev or {}).get("everHadCamera", False),
                "lastCam": (prev or {}).get("lastCam"),
            }
            _PORT_STATE_TRACKER[adapter_id] = entry
        else:
            entry = prev
        entry["isUp"] = bool(is_up)
        entry["upSince"] = up_since
        # When a Pixellot camera is actively present, remember it so that if
        # it later disappears we can tell what dropped (and from where).
        if is_up and has_cam:
            entry["everHadCamera"] = True
            entry["lastCam"] = {
                "ip": cams[0].get("ip"),
                "mac": (cams[0].get("cgiMac") or cams[0].get("mac")),
            }

        since = entry["since"]
        fresh = (now_mono - since) < _PORT_SETTLE_SECONDS
        p["_fresh"] = fresh
        p["_settled"] = not fresh
        p["_everHadCamera"] = entry["everHadCamera"]
        p["_lastCam"] = entry["lastCam"]
        # Connecting (blue): the port just came up and is still establishing.
        # Primary driver is the down→up transition window, so a reconnect is
        # always visible even if the camera resolves instantly. Plus the
        # original cases: link still negotiating (speed 0), or up-but-no-camera
        # during the settle window.
        came_up_recently = (
            is_up and up_since is not None
            and (now_mono - up_since) < _PORT_CONNECTING_SECONDS
        )
        p["connecting"] = bool(
            is_up and (came_up_recently or speed == 0 or (not cams and fresh))
        )

    # Second pass: number main cameras and OCR cameras by camera IP so
    # numbering is stable (Main Camera 1 = .50, Main Camera 2 = .51, etc).
    # Only UP ports are numbered — stale ARP on a down port shouldn't
    # produce a spurious "Main Camera 3" label.
    main_ports = []
    ocr_ports = []
    for p in ports:
        cams = p.get("camerasDetected") or []
        if not cams or not p.get("isUp"):
            p["cameraLabel"] = None
            continue
        role = cams[0].get("role") or ""
        if "OCR" in role:
            ocr_ports.append(p)
        elif role == "Main Camera":
            main_ports.append(p)
        elif role == "Pixellot Camera":
            p["cameraLabel"] = "Pixellot Camera"
        else:
            p["cameraLabel"] = "Camera"

    def _ip_sort_key(p):
        # Numeric per-octet sort so .50 < .100 (string sort would invert)
        ip = p["camerasDetected"][0].get("ip", "")
        try:
            return tuple(int(o) for o in ip.split("."))
        except (ValueError, AttributeError):
            return (999, 999, 999, 999)

    # Cap the number of "Main Camera N" labels so stale ARP can't invent a
    # phantom "Main Camera 3". The authoritative limit is the system's
    # configured main-camera count from the Coordinator log (S1=4, S2=2,
    # S2S=1). When that's unknown, fall back to 2 on Windows — the common
    # Dynacolor 2-cam (S2) head — and leave Linux uncapped.
    import platform as _platform
    if expected_main_cameras and expected_main_cameras > 0:
        main_cap = expected_main_cameras
    elif _platform.system().lower() == "windows":
        main_cap = 2
    else:
        main_cap = None

    main_ports.sort(key=_ip_sort_key)
    for i, p in enumerate(main_ports, 1):
        if main_cap is not None and i > main_cap:
            p["cameraLabel"] = "Camera"
        else:
            p["cameraLabel"] = f"Main Camera {i}"

    # OCR labels. The 1 Gbps OCR variant (E8NC-G) is tagged "OCR-1G" so a
    # tech seeing it linked at 100 Mbps understands the 1 Gbps expectation
    # is real (and the degraded flag is correct), not a Pulse data error.
    # The 1G variant is only known when CGI confirmed the model — otherwise
    # we conservatively show plain "OCR".
    def _ocr_base(p):
        return "OCR-1G" if (p.get("expectedSpeedMbps") or 0) >= 1000 else "OCR"

    ocr_ports.sort(key=_ip_sort_key)
    if len(ocr_ports) == 1:
        ocr_ports[0]["cameraLabel"] = _ocr_base(ocr_ports[0])
    else:
        for i, p in enumerate(ocr_ports, 1):
            p["cameraLabel"] = f"{_ocr_base(p)} {i}"

    return ports


def _flag_uplink_ports(ports: list, network_config) -> None:
    """Mark camera-tab ports that carry the venue/internet uplink (the cable
    that belongs in the motherboard network port). Matches the misplaced
    camera-NIC adapters from network config to the NIC-collector ports by MAC
    (formats differ: 'AA-BB' vs 'aa:bb'), falling back to adapter name.
    Re-gated on the port's live link state so the callout clears within a
    poll or two of the cable being moved, even while the (25s-cached)
    network-config copy still shows the old gateway. Mutates in place."""
    misplaced = _misplaced_camera_uplinks(network_config)
    if not misplaced:
        return

    def _norm_mac(m):
        return str(m or "").upper().replace("-", "").replace(":", "")

    by_mac = {}
    by_name = {}
    for a, gw in misplaced:
        mac = _norm_mac(a.get("macAddress") or a.get("mac"))
        if mac:
            by_mac[mac] = gw
        for n in (a.get("name"), a.get("interfaceAlias")):
            if n:
                by_name[str(n).strip().lower()] = gw

    for p in ports:
        if not p.get("isUp"):
            continue
        gw = by_mac.get(_norm_mac(p.get("mac")))
        if gw is None:
            gw = by_name.get(str(p.get("name") or "").strip().lower())
        if gw is not None:
            p["hasInternetUplink"] = True
            p["uplinkGateway"] = gw


def _compute_camera_findings(ports: list, poe=None) -> list:
    findings = []

    # PoE card running on slot power alone — the supplementary Molex lead is
    # unplugged, so it cannot power a full camera set. Warning, not critical:
    # a 1-2 camera venue can look entirely healthy on slot power, and a critical
    # here would contradict the passing per-port checks beside it. The card
    # still needs fixing before another camera is added or one browns out.
    if isinstance(poe, dict) and (poe.get("budget") or {}).get("underPowered"):
        b = poe["budget"]
        findings.append({
            "severity": "warning",
            "title": "PoE card power budget too low, Molex lead likely unplugged",
            "body": f"The camera card reports a total PoE budget of {b.get('totalW')} W, "
                    f"below the {b.get('healthyFloorW')} W a healthy card provides. Its "
                    "supplementary Molex power lead is most likely disconnected, leaving it on "
                    "slot power only. Power the VPU down and reseat the Molex lead on the camera "
                    "card. VPU Manager reports this same fault as a failed POE Power Test.",
        })

    # The venue/internet cable in a camera port disrupts camera discovery and
    # streaming — name the exact port so the tech knows which cable to move.
    for port in ports:
        if port.get("hasInternetUplink"):
            label = port.get("portLabel", port.get("name", "Port"))
            gw = port.get("uplinkGateway")
            findings.append({
                "severity": "critical",
                "title": f"{label}: internet cable plugged into a camera port",
                "body": f"This port is carrying the venue's internet connection"
                        + (f" (gateway {gw})" if gw else "") +
                        ". Move that cable to the motherboard network port. The "
                        "4-port camera card is for cameras only.",
            })

    # Every camera MAC currently present on any port — used to tell a true
    # drop from a move (a camera that reappears elsewhere didn't drop).
    present_macs = set()
    for port in ports:
        for c in port.get("camerasDetected") or []:
            m = str(c.get("cgiMac") or c.get("mac") or "").upper().replace("-", ":")
            if m:
                present_macs.add(m)

    for port in ports:
        label = port.get("portLabel", port.get("name", "Port"))
        is_up = port.get("isUp")
        cams = port.get("camerasDetected") or []

        # Session-relative camera drop. A port that hosted a streaming
        # Pixellot camera earlier this session, now has none, and has
        # settled is a real "camera went away" — UNLESS that camera's MAC
        # reappeared on another port (it moved, not dropped). This replaces
        # the old stale-ARP "camera last detected" alarm, which fired on
        # ports that never had a confirmed camera. Needs no cameras.cfg.
        if (port.get("_everHadCamera") and not cams and port.get("_settled")):
            last = port.get("_lastCam") or {}
            last_mac = str(last.get("mac") or "").upper().replace("-", ":")
            moved = bool(last_mac and last_mac in present_macs)
            if not moved:
                ipinfo = f" ({last.get('ip')})" if last.get("ip") else ""
                findings.append({
                    "severity": "critical",
                    "title": f"{label}: camera dropped",
                    "body": f"A camera{ipinfo} was streaming on this port "
                            "earlier this session and is no longer detected. Check the "
                            "cable and camera power, or use Camera Connection Troubleshooting.",
                })

        # Skip transient findings for a freshly-changed port. A port that
        # just had a cable plugged/moved briefly reports 100 Mbps / errors
        # while it negotiates; we wait for it to settle before alarming.
        if port.get("_fresh"):
            continue

        if is_up and port.get("isDegraded"):
            speed = port.get("linkSpeedMbps")
            exp = port.get("expectedSpeedMbps") or 1000
            exp_label = f"{exp} Mbps" if exp < 1000 else f"{exp // 1000} Gbps"
            findings.append(
                {
                    "severity": "warning",
                    "title": f"{label} running at {speed} Mbps, expected {exp_label}",
                    "body": f"Degraded link speed usually means a bad cable, faulty connector, or wrong duplex negotiation.",
                }
            )

        if is_up and port.get("fullDuplex") is False:
            findings.append(
                {
                    "severity": "warning",
                    "title": f"{label} in half-duplex mode",
                    "body": f"Half-duplex causes collisions and packet loss at camera scale. Check cable quality.",
                }
            )

        rx_errs = (port.get("rxPacketErrors") or 0) + (port.get("rxDiscards") or 0)
        tx_errs = (port.get("txPacketErrors") or 0) + (port.get("txDiscards") or 0)
        total_errs = rx_errs + tx_errs
        if is_up and total_errs > 0:
            findings.append(
                {
                    "severity": "warning",
                    "title": f"{label}: {total_errs} packet error(s)",
                    "body": f"RX {rx_errs}, TX {tx_errs}. May indicate a bad cable or NIC driver issue.",
                }
            )

    return findings


# ─── Data-building helpers (shared by per-page and preload) ──


def _build_dashboard(identity, performance, services, nics, network_config=None, hardware=None, installed_sw=None, install_state=None, port_tests=None, gpu_info=None, wifi=None, pixellot_config=None, expectations=None, disk_health=None, perf_sample=None, probe_results=None, tls_inspection=None, lmi_log=None):
    # Tag adapter roles (motherboard / camera / wifi) so both the findings and
    # the embedded "Network config" the dashboard ships carry them.
    _classify_network_adapters(network_config)
    flat_identity = {}
    if identity and not identity.get("error"):
        flat_identity = {
            "hostname": identity.get("computerSystem", {}).get("name"),
            "manufacturer": identity.get("computerSystem", {}).get("manufacturer"),
            "model": identity.get("computerSystem", {}).get("model"),
            "serialNumber": identity.get("bios", {}).get("serialNumber"),
            "uptime": identity.get("uptime", {}).get("formatted"),
            "uptimeSeconds": identity.get("uptime", {}).get("totalSeconds"),
            "os": identity.get("operatingSystem", {}).get("caption"),
            "osVersion": identity.get("operatingSystem", {}).get("version"),
            "pixellotVersion": identity.get("pixellot", {}).get("version"),
            "imageVersion": identity.get("pixellot", {}).get("imageVersion"),
            "vpuName": identity.get("pixellot", {}).get("vpuName"),
            "venueId": identity.get("pixellot", {}).get("venueId"),
            "isNonVpuHost": identity.get("isNonVpuHost", False),
        }

    # Basic network config for the dashboard network card
    net_cfg = {}
    if network_config and not network_config.get("error"):
        dash_reachable, dash_tested = _internet_reachable(network_config, port_tests)
        # Role of the adapter currently carrying the uplink, so the dashboard
        # can avoid mislabeling a camera-NIC port as "Motherboard Network Port".
        _uplink_alias = (network_config.get("uplinkAdapter") or {}).get("interfaceAlias")
        _uplink_role = None
        for a in network_config.get("adapters") or []:
            if a.get("name") == _uplink_alias or a.get("interfaceAlias") == _uplink_alias:
                _uplink_role = a.get("role")
                break
        net_cfg = {
            "ipConfig": network_config.get("ipConfigurations", []),
            "uplinkAdapter": network_config.get("uplinkAdapter"),
            "uplinkRole": _uplink_role,
            "internetReachable": dash_reachable,
            "testedHost": dash_tested,
            "ntpSource": network_config.get("ntpSource"),
        }

    # Report which underlying scripts failed so the dashboard can show a
    # clear "some checks couldn't complete" notice instead of silently
    # blanking the affected cards. (A real VPU will occasionally have a
    # script time out — network/port probes especially.)
    _sources = {
        "System identity": identity,
        "Performance": performance,
        "Services": services,
        "Network adapters": nics,
        "Network config": network_config,
        "Hardware": hardware,
        "Installed software": installed_sw,
        "Port connectivity": port_tests,
    }
    source_errors = [
        name for name, data in _sources.items()
        if isinstance(data, dict) and data.get("error")
    ]

    findings = _compute_findings(identity, performance, services, nics, hardware, installed_sw, network_config, install_state, port_tests, gpu_info, wifi, pixellot_config=pixellot_config, expectations=expectations, disk_health=disk_health, probe_results=probe_results, tls_inspection=tls_inspection, lmi_log=lmi_log)

    return {
        "identity": flat_identity,
        "performance": performance if not performance.get("error", False) else {},
        "services": services if not services.get("error", False) else {"services": []},
        "findings": findings,
        "readiness": _compute_readiness(findings, performance=performance, disk_health=disk_health, perf_sample=perf_sample),
        "networkConfig": net_cfg,
        "sourceErrors": source_errors,
    }


def _build_network(config, domains, ports, ntp, local=None, ntp_peers=None, dns_resolution=None, wifi=None, tls=None, lmi_log=None):
    net = {}
    _classify_network_adapters(config)
    if config and not config.get("error"):
        ntp_src = config.get("ntpSource")
        reachable, tested_host = _internet_reachable(config, ports)
        net = {
            "adapters": config.get("adapters", []),
            "ipConfig": config.get("ipConfigurations", []),
            "uplinkAdapter": config.get("uplinkAdapter"),
            "uplinkStats": config.get("uplinkStats"),
            "internetReachable": reachable,
            "testedHost": tested_host,
            "ntpSource": ntp_src,
            "ntpSourceApproved": _is_approved_ntp_source(ntp_src),
            "ntpSourceApprovedList": list(PIXELLOT_APPROVED_NTP_SOURCES),
        }

    # Classify DNS rows here (single, tested source of truth) before handing
    # the data to the frontend.
    dns_resolution = _annotate_dns_resolution(dns_resolution)

    # Pass local, ntpPeers, dnsResolution, wifi through even on error — let
    # the frontend surface whichever subsection failed.
    return {"config": net, "domains": domains, "ports": ports, "ntp": ntp,
            "local": local, "ntpPeers": ntp_peers,
            "dnsResolution": dns_resolution, "wifi": wifi, "tls": tls,
            "lmiLog": lmi_log}


# ─── Routes ───────────────────────────────────────────────────


_BOOT_TS = str(int(__import__("time").time()))  # changes every server restart


@app.get("/")
async def serve_index():
    with open(_os.path.join(_static_dir, "index.html")) as f:
        html = f.read()
    # Cache-bust with version + boot timestamp so Chrome always gets fresh
    # assets. Regex-based replacement is robust to attribute reordering or
    # additional tag attributes — string replace would silently break.
    import re
    bust = f"{APP_VERSION}.{_BOOT_TS}"
    html = re.sub(
        r'(/static/[a-z0-9_\-]+\.(?:css|js))(\?[^"\']*)?',
        lambda m: f"{m.group(1)}?v={bust}",
        html,
    )
    # Inject demo-mode flag synchronously so the splash screen can decide
    # whether to slow the per-section progress bar BEFORE the first fetch
    # resolves. /api/version exposes the same field for runtime consumers.
    demo_js = f"<script>window.__PULSE_DEMO_MODE={'true' if DEMO_MODE else 'false'};</script>"
    html = html.replace("</head>", f"  {demo_js}\n  </head>", 1)
    # Render the version into the splash so it shows under the logo while the
    # diagnostics load — server-side fill means no fetch flash. Blank if unknown.
    html = html.replace("{{PULSE_VERSION}}", "" if APP_VERSION in (None, "", "unknown") else APP_VERSION)
    return HTMLResponse(html)


@app.get("/api/version")
async def api_version():
    # demoMode is exposed here (and not only on /api/logs) so the splash
    # screen can decide synchronously whether to slow the per-section
    # progress bar — the loading visual is the user's first impression
    # and instant-fast in demo mode flashes past in milliseconds.
    # channelMoved is non-null only in the session that just migrated this
    # install off the retired beta channel (see _migrate_retired_beta) — the
    # UI shows its one-time "moved to production" notice from it.
    return {"version": APP_VERSION, "demoMode": DEMO_MODE, "channelMoved": _channel_migration}


@app.get("/api/logs")
async def api_logs(since: int = Query(default=0)):
    """Return recent script execution logs. `since` is an index offset."""
    logs = list(LOG_BUFFER)
    return {"demoMode": DEMO_MODE, "logs": logs[since:], "total": len(logs)}


@app.get("/api/server-log")
async def api_server_log(tail: int = Query(default=200)):
    """Return the last N lines of the server bootstrap/startup log file."""
    try:
        with open(SERVER_LOG_PATH, "r", errors="replace") as f:
            lines = f.readlines()
        return {"lines": [l.rstrip() for l in lines[-tail:]], "total": len(lines)}
    except FileNotFoundError:
        return {"lines": [], "total": 0}


@app.get("/api/scripts/running")
async def api_scripts_running():
    return {"tasks": get_running_tasks()}


@app.post("/api/scripts/cancel")
async def api_scripts_cancel(request: Request):
    body = await request.json()
    task_id = body.get("taskId", "")
    return {"ok": cancel_task(task_id)}


@app.post("/api/scripts/clear-cache")
async def api_scripts_clear_cache():
    """Clear the server-side PS result cache. Called by the client's
    Run-All Diagnostics path so a forced refresh actually re-runs
    every script instead of returning cached results."""
    count = clear_ps_cache()
    return {"ok": True, "cleared": count}


@app.post("/api/scripts/cancel-all")
async def api_scripts_cancel_all():
    count = cancel_all_tasks()
    return {"ok": True, "cancelled": count}


async def _collect_dashboard() -> dict:
    """Run the dashboard's data-collection scripts and build the payload
    (findings + Stream Readiness verdict). Shared by `/api/dashboard` and the
    launch check-in beacon so both score readiness with identical inputs."""
    (identity, performance, services, nics, net_config, hardware, installed_sw,
     install_state, port_tests, gpu_info, wifi, pixellot_config, expectations,
     disk_health, perf_sample, tls_inspection, lmi_log) = await asyncio.gather(
        run_ps("Get-SystemIdentity.ps1"),
        run_ps("Get-Performance.ps1"),
        run_ps("Get-Services.ps1"),
        run_ps("Get-NicAdapters.ps1"),
        run_ps("Get-NetworkConfig.ps1", timeout=15),
        run_ps("Get-Hardware.ps1"),
        run_ps("Get-InstalledSoftware.ps1"),
        run_ps("Test-PixellotInstallState.ps1", timeout=15),
        # 30s for dashboard use — UDP rows now require an echoed reply and
        # retry once (a blocked-UDP venue costs ~14s in port checks alone),
        # so 20s would expire on exactly the venues the test exists to catch.
        # Healthy connections still finish in well under 15s.
        run_ps("Test-NetworkPorts.ps1", timeout=30),
        run_ps("Get-GpuInfo.ps1", timeout=15),
        run_ps("Get-WifiAdapters.ps1", timeout=10),
        # Pixellot config + expected camera count feed the dashboard's new
        # "missing main cameras" finding (compared against what's detected on
        # the camera NIC). Same scripts the Camera Connectivity tab uses.
        run_ps("Get-PixellotConfig.ps1", timeout=15),
        run_ps("Get-CameraExpectations.ps1", timeout=10),
        # Readiness inputs: D: volume (post-event VOD) for the C:/D: split, and
        # a short CPU/mem sample so a one-instant spike can't move the verdict.
        run_ps("Get-DiskHealth.ps1", timeout=15),
        run_ps("Get-PerfSample.ps1", timeout=15),
        # SSL-inspection check — feeds the "firewall is intercepting secure
        # connections" critical. Port tests alone can't see this failure mode
        # (TCP/443 connects fine while the substituted cert kills graphics).
        run_ps("Test-TlsInspection.ps1", timeout=60),
        # LogMeIn's own service log — the historical half of the middlebox
        # story (feeds the "venue is killing LogMeIn's connection" warning).
        run_ps("Get-LmiGatewayLog.ps1", timeout=20),
    )
    # CGI probe (cached 30s; usually already warm from preload) so the
    # slow-port finding identifies the OCR by its actual camera model, not a
    # transient ARP entry — keeping the dashboard consistent with the Camera
    # Connectivity tab and free of the OCR "running slow" flicker.
    ocr_ips, _ = _build_ocr_sets(pixellot_config)
    raw_ports = nics.get("ports", []) if nics and not nics.get("error") else []
    probe_results = await _probe_all_cameras(raw_ports, ocr_ips)

    # CPU observer-effect guard. The snapshot and the 3s sample above both run
    # INSIDE the collector fan-out — several concurrent powershell.exe startups
    # push an otherwise-idle VPU to 85-93% (measured on VPU2, 2026-07-23), so a
    # healthy box shows a phantom "CPU elevated" warning on every dashboard
    # load. If either reading is in finding territory, take a fresh sustained
    # sample now that the burst is over and let it replace both inputs: the
    # findings/display CPU (performance.cpu.usagePercent) and the readiness
    # sample. A genuinely hot box (e.g. vpu.exe encoding a live event) confirms
    # high and still alerts; the only cost is ~4s extra when the first reading
    # looked elevated.
    cpu_snapshot = ((performance or {}).get("cpu") or {}).get("usagePercent")
    cpu_sampled = (perf_sample or {}).get("cpuAvgPercent")
    readings = [c for c in (cpu_snapshot, cpu_sampled) if isinstance(c, (int, float))]
    if readings and max(readings) > 75:
        confirm = await run_ps("Get-PerfSample.ps1", timeout=15, use_cache=False)
        confirmed_cpu = (confirm or {}).get("cpuAvgPercent")
        if isinstance(confirmed_cpu, (int, float)):
            perf_sample = confirm
            if performance and not performance.get("error"):
                cpu_block = performance.get("cpu") or {}
                cpu_block["usagePercent"] = confirmed_cpu
                performance["cpu"] = cpu_block

    return _build_dashboard(
        identity, performance, services, nics, net_config, hardware,
        installed_sw, install_state, port_tests, gpu_info, wifi,
        pixellot_config=pixellot_config, expectations=expectations,
        disk_health=disk_health, perf_sample=perf_sample,
        probe_results=probe_results, tls_inspection=tls_inspection,
        lmi_log=lmi_log,
    )


@app.get("/api/dashboard")
async def api_dashboard():
    """Top-level Dashboard payload: the aggregated system snapshot plus the
    Stream Readiness verdict. Delegates to _collect_dashboard, which fans out to
    the per-area collectors and rolls their results into findings."""
    return await _collect_dashboard()


def _enrich_identity_lifecycle(identity):
    """Attach OS lifecycle info (PDF #4) to identity.operatingSystem so the
    System Overview can display it next to the OS version. No-op if the
    build number isn't in our LTSC map."""
    if not identity or identity.get("error"):
        return identity
    os_block = identity.get("operatingSystem") or {}
    lifecycle = _os_lifecycle(os_block.get("buildNumber"))
    if lifecycle:
        os_block["lifecycle"] = lifecycle
        identity["operatingSystem"] = os_block
    return identity


def _enrich_identity_pixellot_compat(identity, gpu_info):
    """Attach pixellotCompat = {status, installedVersion, maxVersion, ...}
    to identity so System Overview can render the GPU/OS-vs-Pixellot banner."""
    if not identity or identity.get("error"):
        return identity
    compat = _check_pixellot_compatibility(identity, gpu_info)
    pix_block = identity.get("pixellot") or {}
    pix_block["compat"] = compat
    identity["pixellot"] = pix_block
    return identity


@app.get("/api/system")
async def api_system():
    """System tab data: identity, hardware, installed software, and GPU info
    collected in parallel, then enriched with Windows lifecycle (LTSC
    end-of-support) and Pixellot hardware-compatibility info before returning."""
    identity, hardware, software, gpu_info = await asyncio.gather(
        run_ps("Get-SystemIdentity.ps1"),
        run_ps("Get-Hardware.ps1"),
        run_ps("Get-InstalledSoftware.ps1"),
        run_ps("Get-GpuInfo.ps1", timeout=15),
    )
    identity = _enrich_identity_lifecycle(identity)
    identity = _enrich_identity_pixellot_compat(identity, gpu_info)
    return {
        "identity": identity,
        "hardware": hardware,
        "software": _enrich_software_with_concerns(software),
    }


@app.get("/api/users-domains")
async def api_users_domains():
    """Domain/workgroup membership + local user accounts for the System
    Overview 'Users & Domains' panel. Lazy-fetched on tab visit."""
    return await run_ps("Get-UsersAndDomains.ps1", timeout=20)


@app.get("/api/peripherals")
async def api_peripherals():
    """Mouse / keyboard / monitor presence for the System Overview
    'Peripherals' panel. Lazy-fetched on tab visit."""
    return await run_ps("Get-Peripherals.ps1", timeout=15)


@app.get("/api/pixellot-config")
async def api_pixellot_config():
    r"""Local, on-host Pixellot configuration (NOT the Pixellot Cloud lane):
    install/agent version + GPU-vs-version compatibility, cameras.cfg
    (IP/MAC/role) enriched with live per-camera firmware/tvMode/serial via the
    shared CGI probe, and calibration status (main multisport + OCR) read from
    C:\Pixellot\Data\Configuration.
    """
    cfg, identity, gpu_info = await asyncio.gather(
        run_ps("Get-PixellotConfig.ps1", timeout=20),
        run_ps("Get-SystemIdentity.ps1"),
        run_ps("Get-GpuInfo.ps1", timeout=15),
    )
    if not isinstance(cfg, dict) or cfg.get("error"):
        return cfg

    # Reuse the System Overview version-compatibility banner data.
    cfg["compat"] = _check_pixellot_compatibility(identity, gpu_info)

    # Enrich each camera with live firmware / tvMode / serial / model via the
    # same cached CGI probe the Camera Connectivity lane uses (Admin:1234
    # param.cgi). Skipped in demo mode — demo data already carries these.
    cams = cfg.get("cameras") or []
    if not DEMO_MODE and cams:
        ocr_ips, _ = _build_ocr_sets(cfg)
        targets = [c for c in cams if c.get("ip")]
        probes = await asyncio.gather(
            *[_probe_camera_ip(c["ip"], c["ip"] in ocr_ips) for c in targets]
        )
        for cam, probe in zip(targets, probes):
            cam["reachable"] = bool(probe)
            if not probe:
                continue
            for key in ("firmwareVersion", "tvMode", "serialNumber", "model"):
                if probe.get(key):
                    cam[key] = probe[key]
    return cfg


@app.get("/api/network")
async def api_network():
    """Network tab data: gathers adapter config, domain reachability, port
    checks, NTP drift + peers, the local-network probe, DNS resolution, and
    Wi-Fi adapters in parallel, then assembles them into the network panel."""
    config, domains, ports, ntp, local, ntp_peers, dns_resolution, wifi, tls, lmi_log = await asyncio.gather(
        run_ps("Get-NetworkConfig.ps1", timeout=15),
        run_ps("Test-NetworkDomains.ps1", timeout=20),
        run_ps("Test-NetworkPorts.ps1", timeout=45),
        run_ps("Test-NtpDrift.ps1", timeout=15),
        run_ps("Test-LocalNetwork.ps1", timeout=20),
        run_ps("Get-NtpPeers.ps1", timeout=15),
        run_ps("Test-DnsResolution.ps1", timeout=30),
        run_ps("Get-WifiAdapters.ps1", timeout=10),
        # 60s: eleven sequential handshakes; a fully-blackholed network costs
        # ~4s per host in TCP timeouts alone. Healthy venues finish in ~5s.
        run_ps("Test-TlsInspection.ps1", timeout=60),
        # LogMeIn's service log — historical middlebox evidence (a healthy
        # week of dailies parses in well under a second).
        run_ps("Get-LmiGatewayLog.ps1", timeout=20),
    )
    return _build_network(config, domains, ports, ntp, local, ntp_peers, dns_resolution, wifi, tls, lmi_log)


@app.get("/api/network/local-ping")
async def api_local_ping(count: int = 4):
    count = max(1, min(count, 100))  # clamp 1-100
    timeout = max(20, count * 3)  # ~3s per ping round
    result = await run_ps("Test-LocalNetwork.ps1", timeout=timeout,
                          args={"Count": count})
    return result


@app.get("/api/network/health")
async def api_network_health():
    return await run_ps("Get-NetworkHealth.ps1", timeout=10)


@app.get("/api/network/capture")
async def api_network_capture(duration: int = 30):
    duration = max(10, min(duration, 60))
    timeout = duration + 30  # extra headroom for pktmon stop + analysis
    result = await run_ps("Start-NetworkCapture.ps1", timeout=timeout,
                          args={"DurationSec": duration})
    return result


@app.get("/api/network/traceroute")
async def api_traceroute(target: str = "pixellot.tv", max_hops: int = 20):
    max_hops = max(5, min(max_hops, 30))
    timeout = max(30, max_hops * 3)  # generous — most finish well under this
    result = await run_ps("Test-Traceroute.ps1", timeout=timeout,
                          args={"Target": target, "MaxHops": max_hops})
    return result


@app.get("/api/network/speedtest")
async def api_speedtest(result_id: str = ""):
    """Fetch a Speedtest.net result by ID or URL and parse the speeds."""
    import re
    import urllib.request
    import urllib.error

    # Extract numeric ID from URL or bare ID
    result_id = result_id.strip()
    m = re.search(r"(\d{9,14})", result_id)
    if not m:
        return {"error": True, "message": "Invalid result ID. Paste the Speedtest result URL or numeric ID."}
    rid = m.group(1)
    url = f"https://www.speedtest.net/result/{rid}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
            "Accept": "text/html",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return {"error": True, "message": f"Speedtest returned HTTP {e.code}. Check the result ID."}
    except Exception as e:
        return {"error": True, "message": f"Failed to fetch result: {e}"}

    # Strategy 1: Parse OG description — "Download: XX.XX Mbps Upload: XX.XX Mbps Ping: XX ms"
    download = upload = ping = jitter = isp = server = None

    og_desc = re.search(r'<meta\s+[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)', html, re.I)
    if og_desc:
        desc = og_desc.group(1)
        dl_m = re.search(r"Download[:\s]+(\d+(?:\.\d+)?)\s*(Mbps|Kbps|Gbps)", desc, re.I)
        ul_m = re.search(r"Upload[:\s]+(\d+(?:\.\d+)?)\s*(Mbps|Kbps|Gbps)", desc, re.I)
        pg_m = re.search(r"Ping[:\s]+(\d+(?:\.\d+)?)\s*ms", desc, re.I)
        if dl_m:
            download = float(dl_m.group(1))
            if dl_m.group(2).lower() == "kbps": download /= 1000
            elif dl_m.group(2).lower() == "gbps": download *= 1000
        if ul_m:
            upload = float(ul_m.group(1))
            if ul_m.group(2).lower() == "kbps": upload /= 1000
            elif ul_m.group(2).lower() == "gbps": upload *= 1000
        if pg_m:
            ping = float(pg_m.group(1))

    # Strategy 2: Look for JSON data in script tags
    if download is None:
        json_m = re.search(r'"download"[:\s]+(\d+(?:\.\d+)?)', html)
        if json_m:
            val = float(json_m.group(1))
            download = val / 1000 if val > 10000 else val  # might be kbps
    if upload is None:
        json_m = re.search(r'"upload"[:\s]+(\d+(?:\.\d+)?)', html)
        if json_m:
            val = float(json_m.group(1))
            upload = val / 1000 if val > 10000 else val
    if ping is None:
        json_m = re.search(r'"ping"[:\s]+(\d+(?:\.\d+)?)', html)
        if json_m:
            ping = float(json_m.group(1))

    # ISP and server
    isp_m = re.search(r'"isp_name"[:\s]*"([^"]+)"', html) or re.search(r'"isp"[:\s]*"([^"]+)"', html)
    if isp_m: isp = isp_m.group(1)
    srv_m = re.search(r'"server_name"[:\s]*"([^"]+)"', html) or re.search(r'"name"[:\s]*"([^"]+)"', html)
    if srv_m: server = srv_m.group(1)
    jitter_m = re.search(r'"jitter"[:\s]+(\d+(?:\.\d+)?)', html)
    if jitter_m: jitter = float(jitter_m.group(1))

    if download is None and upload is None:
        return {"error": True, "message": "Could not parse speeds from the result page. The result may be private or the page format changed."}

    return {
        "resultId": rid,
        "url": url,
        "download": round(download, 2) if download else None,
        "upload": round(upload, 2) if upload else None,
        "ping": round(ping, 1) if ping else None,
        "jitter": round(jitter, 1) if jitter else None,
        "isp": isp,
        "server": server,
    }


@app.get("/api/cameras")
async def api_cameras(refresh: bool = False):
    # Manual Refresh button clears the CGI probe cache + forces a blocking
    # re-probe so on-site troubleshooting sees fresh data immediately
    # instead of waiting up to TTL for the cache to expire.
    if refresh:
        _CGI_PROBE_CACHE.clear()
    # NIC link state must be near-real-time: a cable unplug/replug should show
    # within a poll or two, not whenever the default 25s cache happens to
    # expire. cache_ttl=1.5 forces a fresh adapter read on each ~2s live poll
    # (the in-flight dedup still prevents overlapping runs if one is slow).
    # PixellotConfig / Expectations change rarely, so they keep the long cache.
    # networkConfig rides along (long default cache — it's the same result the
    # dashboard uses) so the port tiles can flag the venue/internet cable when
    # it's plugged into a camera port. The per-port flag below re-gates on the
    # port's live link state, so a fixed cable clears within a poll or two even
    # while this cached copy is stale.
    # PoE power rides this payload rather than getting its own endpoint: the
    # card belongs next to the port tiles, and gathering it here keeps watts and
    # link state from the same instant instead of two independently-cached
    # snapshots.
    #
    # cache_ttl=6 deliberately refreshes PoE SLOWER than the 2s page poll and
    # slower than the NIC read's 1.5s. Measured on a production GIE74P
    # (2026-08-12): the SmartPoE getters cost ~90ms each, so one read pass is
    # ~1.0s, and with powershell.exe startup a full collector run is ~1.8s.
    # Refreshing that every 2s would mean near-continuous PowerShell on a box
    # whose actual job is encoding video, for a signal that barely moves —
    # a camera's draw is not a fast-changing value the way link state is.
    # In-flight dedup means the intervening page polls just reuse the cached
    # payload.
    nics, pix_config, expectations, net_config, poe = await asyncio.gather(
        run_ps("Get-NicAdapters.ps1", cache_ttl=1.5),
        run_ps("Get-PixellotConfig.ps1"),
        run_ps("Get-CameraExpectations.ps1", timeout=10),
        run_ps("Get-NetworkConfig.ps1", timeout=15),
        run_ps("Get-PoePower.ps1", timeout=20, cache_ttl=6),
    )
    ocr_ips, _ = _build_ocr_sets(pix_config)
    # Expected main-camera count from the Coordinator log (S1=4/S2=2/S2S=1).
    # Authoritative — drives the main-camera cap and the system-type label.
    expected_main = None
    system_type = None
    vpu_running = False
    if expectations and not expectations.get("error"):
        expected_main = expectations.get("expectedMainCameras")
        system_type = expectations.get("systemType")
        vpu_running = bool(expectations.get("vpuRunning"))
    # First paint: use cached probes only; warm the cache in the background
    # so the next live-refresh tick picks up fresh camera identification.
    # Manual refresh blocks until probes complete so the user sees the
    # update immediately.
    raw_ports = nics.get("ports", []) if nics and not nics.get("error") else []
    probe_results = await _probe_all_cameras(raw_ports, ocr_ips, block=refresh)
    ports = _enrich_ports(nics, pix_config, probe_results, expected_main_cameras=expected_main)
    _flag_uplink_ports(ports, net_config)
    return {
        "ports": ports,
        "pixellotConfig": pix_config,
        "findings": _compute_camera_findings(ports, poe),
        "systemType": system_type,
        "expectedMainCameras": expected_main,
        # Whole collector payload, not just the readings — the frontend needs
        # supported/available/reason to tell "this NIC family can't measure
        # power" apart from "the driver isn't installed" apart from "measured,
        # and here it is".
        "poe": poe if isinstance(poe, dict) else None,
        # vpuRunning gates the "Get Camera Frames" button — frame capture is
        # disabled while the capture engine owns the RTSP streams.
        "vpuRunning": vpu_running,
        # Frontend uses this to skip swap-verification in the fault isolator,
        # since static demo data can't simulate the ARP change after a swap.
        "demoMode": DEMO_MODE,
    }


@app.get("/api/cameras/s1")
async def api_cameras_s1():
    """Discover JAI S1 cameras (4-cam systems Pulse's CGI probe can't see).
    Returns { available, count, cameras: [...] }; available=false on
    non-S1 VPUs where the JAI SDK isn't installed."""
    return await run_ps("Get-S1Cameras.ps1", timeout=15)


# ── Black-frame diagnosis ────────────────────────────────────────────
# A camera can grab a frame fine (ok=true, "Active") yet send a black picture —
# the exact symptom techs hit on OCR/scoreboard cameras whose picture settings
# need adjusting. ffmpeg's signalstats (Test-CameraVideo.ps1) gives us the
# frame's average luminance, so we can call this out instead of letting a black
# thumbnail pass as healthy. Luma is 0-255; chroma centres on 128.
_DARK_FRAME_YAVG = 16     # at/below this average brightness the frame reads black
_LIT_FRAME_YAVG = 50      # at/above this a frame is clearly showing the room
_BRIGHT_PIXEL_YMAX = 230  # a near-white pixel present → a bright light in view


def _to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _frame_yavg(r):
    """Average luminance of a captured frame, or None if unmeasured."""
    luma = r.get("luma") if isinstance(r, dict) else None
    return _to_float(luma.get("yavg")) if isinstance(luma, dict) else None


def _frame_settings_hint(target, results):
    """Plain-English note on how a black camera's picture settings differ from
    the cameras that returned a normal picture in the same room (the 'B' half:
    same-room settings comparison). Reads the CGI sensor block already merged
    onto each result. Returns None when nothing notable stands out."""
    tsen = target.get("sensor") or {}
    peers = [r.get("sensor") or {} for r in results
             if r is not target and r.get("ok")
             and (_frame_yavg(r) or 0) >= _LIT_FRAME_YAVG]
    if not peers:
        return None
    notes = []
    # Exposure left on Manual in a venue whose lighting changes is a classic
    # black-picture cause.
    texp = str(tsen.get("exposure") or "").strip().lower()
    peer_auto = any(str(s.get("exposure") or "").strip().lower() == "auto" for s in peers)
    if texp and texp != "auto" and peer_auto:
        notes.append(f"Its exposure is {tsen.get('exposure')}, but the cameras "
                     "that look fine are on Auto.")
    # Brightness dialled well below the working cameras.
    tb = _to_float(tsen.get("brightness"))
    pbs = [v for v in (_to_float(s.get("brightness")) for s in peers) if v is not None]
    if tb is not None and pbs:
        pavg = sum(pbs) / len(pbs)
        if tb <= pavg - 15:
            notes.append(f"Its brightness ({tsen.get('brightness')}) is lower than "
                         f"the cameras that look fine (~{round(pavg)}).")
    return " ".join(notes) or None


def _diagnose_camera_frames(results):
    """Flag cameras that captured a frame but the picture came back black, in
    words a field tech can act on. Mutates each affected result in place, adding
    diagnosis = { severity, summary, detail? }. No-op when nothing looks black."""
    if not isinstance(results, list):
        return
    # Any camera clearly showing a lit room is proof the lights are on and the
    # venue is fine — so a black camera is a camera problem, not the room.
    lit = None
    for r in results:
        if r.get("ok") and (_frame_yavg(r) or 0) >= _LIT_FRAME_YAVG:
            lit = r.get("label") or "another camera"
            break
    for r in results:
        if not r.get("ok"):
            continue
        y = _frame_yavg(r)
        if y is None or y > _DARK_FRAME_YAVG:
            continue  # bright enough to read — nothing to flag
        label = r.get("label") or "This camera"
        ymax = _to_float((r.get("luma") or {}).get("ymax"))
        if ymax is not None and ymax >= _BRIGHT_PIXEL_YMAX:
            summary = (f"{label} is sending an almost black picture. Adjust its "
                       "exposure/brightness so the rest of the scene shows.")
        else:
            summary = (f"{label} is sending an almost black picture. It is set too dark for "
                       "this room. Turn up its brightness/exposure.")
        if lit:
            summary += (f" {lit} looks normal in the same room, so it's a camera "
                        "setting, not the venue.")
        diag = {"severity": "warn", "summary": summary}
        hint = _frame_settings_hint(r, results)
        if hint:
            diag["detail"] = hint
        r["diagnosis"] = diag


@app.post("/api/cameras/video-test")
async def api_cameras_video_test(request: Request):
    """Grab a single frame from each detected camera to confirm it's
    streaming decodable video (and return it as a thumbnail). Re-derives
    the camera IPs server-side (authoritative, not client-supplied).
    Wired to an explicit 'Get Camera Frames' button — never polled.

    An optional JSON body {"ips": ["<ip>", ...]} restricts the capture to
    those cameras — this backs the per-camera 'Refresh' button. With no
    body (or an empty one) every detected camera is captured, as before.

    Each result also carries the camera's model + firmware (from the CGI
    probe) and the VPU's systemType (S1/S2/S2S) so the UI can label the
    snapshot fully.

    Two guards: refuse while vpu.exe is capturing (don't compete for the
    cameras' RTSP sessions during a live event), and a cooldown to stop
    the button being spammed."""
    global _LAST_FRAME_CAPTURE

    # Parse the body up front. {"ips": [...]} restricts the capture (per-camera
    # Refresh). There is no override: a {"force": true} flag used to relax both
    # guards below for the Inspection Report's fleet audit, and it went out with
    # that tab — nothing may compete with vpu.exe for the cameras' RTSP sessions
    # during a live event, whatever the caller claims to be doing.
    try:
        body = await request.json()
    except Exception:
        body = None

    # Rate limit first — cheap, no PowerShell needed.
    remaining = _frame_cooldown_remaining(time.monotonic())
    if remaining > 0:
        return {"available": True, "results": [], "blocked": "cooldown",
                "cooldown": remaining,
                "reason": f"Wait {remaining}s before capturing frames again."}

    # Don't capture while the Pixellot capture engine owns the streams.
    expectations = await run_ps("Get-CameraExpectations.ps1", timeout=10, use_cache=False)
    if expectations and not expectations.get("error") and expectations.get("vpuRunning"):
        return {"available": False, "results": [], "blocked": "vpu",
                "reason": "The Pixellot capture engine (vpu.exe) is running, so "
                          "frame capture is disabled to avoid interfering with the "
                          "live stream. Stop the VPU process to capture frames."}

    # Optional: restrict the capture to specific camera IPs (the per-camera
    # 'Refresh' button posts {"ips": [...]}). No body → capture everything.
    target_ips = None
    if isinstance(body, dict):
        raw = body.get("ips") or ([body["ip"]] if body.get("ip") else None)
        if raw:
            # Validate each client value as a real IP address at the boundary.
            # These IPs only *filter* the server-derived camera list — the
            # values handed to the capture command come from camerasDetected,
            # never from the request — but rejecting anything that isn't a
            # well-formed address keeps untrusted strings out of the selection
            # path entirely. Malformed entries are dropped silently.
            target_ips = set()
            for x in raw:
                ip = str(x).strip()
                try:
                    _ipaddress.ip_address(ip)
                except ValueError:
                    continue
                target_ips.add(ip)

    sys_type = expectations.get("systemType") if isinstance(expectations, dict) else None

    nics, pix_config = await asyncio.gather(
        run_ps("Get-NicAdapters.ps1"),
        run_ps("Get-PixellotConfig.ps1"),
    )
    ocr_ips, _ = _build_ocr_sets(pix_config)
    raw_ports = nics.get("ports", []) if nics and not nics.get("error") else []
    probe_results = await _probe_all_cameras(raw_ports, ocr_ips, block=False)
    ports = _enrich_ports(nics, pix_config, probe_results)

    # Collect (ip, label) for every detected camera on an up port, plus a
    # per-IP link-health map so we can flag degraded streams on the frames:
    # a single frame may grab fine, but a degraded link won't sustain video.
    cams = []
    cam_meta = {}
    for p in ports:
        for c in p.get("camerasDetected") or []:
            ip = (c.get("ip") or "").strip()
            if ip:
                cams.append((ip, p.get("cameraLabel") or p.get("portLabel") or ip))
                cam_meta[ip] = {
                    "degraded": bool(p.get("isDegraded")),
                    "linkSpeedMbps": p.get("linkSpeedMbps"),
                    "expectedSpeedMbps": p.get("expectedSpeedMbps"),
                    "model": c.get("model"),
                    "firmwareVersion": c.get("firmwareVersion"),
                    "sensor": c.get("sensor"),
                }

    # Single-camera refresh: keep only the requested IP(s).
    if target_ips is not None:
        cams = [c for c in cams if c[0] in target_ips]

    if not cams:
        reason = ("Requested camera not detected." if target_ips
                  else "No cameras detected to test.")
        return {"available": True, "results": [], "reason": reason,
                "systemType": sys_type}

    # Order: Main cameras first (by number), then OCRs, then anything else.
    def _cam_order(c):
        label = c[1] or ""
        grp = 0 if label.startswith("Main") else 1 if "OCR" in label else 2
        # Trailing number (regex-free — re isn't imported at this scope).
        digits = ""
        for ch in reversed(label.strip()):
            if ch.isdigit():
                digits = ch + digits
            elif digits:
                break
        return (grp, int(digits) if digits else 0, label)
    cams.sort(key=_cam_order)

    ips = ",".join(c[0] for c in cams)
    labels = ",".join(c[1] for c in cams)
    # Single-frame grab is fast: a probe + frame capture is bounded by the
    # script's own -stimeout (~6-8s) per camera. Budget ~20s/camera + margin.
    budget = 20 * len(cams) + 20
    # Stamp the cooldown now — a capture is about to run; this prevents a
    # second request landing while this one is still in flight.
    _LAST_FRAME_CAPTURE = time.monotonic()
    # use_cache=False: each click captures fresh frames — never replay a
    # cached snapshot from a previous request.
    result = await run_ps(
        "Test-CameraVideo.ps1",
        {"CameraIps": ips, "Labels": labels},
        timeout=budget,
        use_cache=False,
    )
    # Merge link health + camera identity onto each frame: link health lets
    # the UI warn that a degraded camera, while it grabbed a frame, won't
    # stream reliably; model/firmware label the snapshot. systemType (the
    # VPU's camera generation — S1/S2/S2S) is the same for every camera, so
    # it rides on the envelope, not each result.
    if isinstance(result, dict):
        for r in result.get("results") or []:
            meta = cam_meta.get((r.get("ip") or "").strip())
            if meta:
                r["degraded"] = meta["degraded"]
                r["linkSpeedMbps"] = meta["linkSpeedMbps"]
                r["expectedSpeedMbps"] = meta["expectedSpeedMbps"]
                r["model"] = meta.get("model")
                r["firmwareVersion"] = meta.get("firmwareVersion")
                r["sensor"] = meta.get("sensor")
        result["systemType"] = sys_type
        # Look inside the captured frames: flag any camera that grabbed a frame
        # but the picture came back black (the OCR/scoreboard symptom).
        _diagnose_camera_frames(result.get("results"))
    return result


# A couple of example past runs so the history panel demonstrates the
# "tech returns to the school" workflow in demo mode.
_DEMO_FAULT_HISTORY = [
    {"ts": "2026-05-26T15:12:00", "conclusion": "Cable",
     "title": "CONCLUSION: FAULTY CABLE", "suspectPort": "Port 1", "testPort": "Port 4",
     "camera": {"label": "Main Camera 1", "ip": "169.254.16.50", "mac": "00-0E-53-AA-01-01"},
     "recommendation": "Replacing the cable restored the link. Re-terminate both ends or replace the cable end-to-end; inspect the run for damage.",
     "history": [
         {"ts": "3:11:58 PM", "phase": "Phase 1 - Baseline", "speed": "100 Mbps", "verdict": "Link degraded at 100 Mbps. Beginning isolation.", "severity": "Fail"},
         {"ts": "3:12:34 PM", "phase": "Phase 2 - NIC Port Test", "speed": "100 Mbps", "verdict": "Fault followed the cable/camera, not the NIC port.", "severity": "Info"},
         {"ts": "3:12:58 PM", "phase": "Phase 3 - Cable Test", "speed": "1 Gbps", "verdict": "Link restored with a known-good cable. The original cable is the fault.", "severity": "Pass"},
     ]},
]


@app.get("/api/fault-isolator/history")
async def api_fault_history():
    """Prior fault-isolator runs on this VPU (newest first), for a returning
    tech to see what was found and recommended before."""
    runs = sorted(_load_fault_history(), key=lambda r: r.get("ts", ""), reverse=True)
    if DEMO_MODE:
        runs = runs + _DEMO_FAULT_HISTORY  # seed examples beneath any real runs
    return {"runs": runs}


@app.post("/api/fault-isolator/history")
async def api_fault_history_save(run: dict):
    """Append a completed fault-isolation run to the persisted history."""
    if not isinstance(run, dict) or not run.get("conclusion"):
        return {"ok": False, "error": "invalid run record"}
    if not run.get("ts"):
        from datetime import datetime as _dt
        run["ts"] = _dt.now().isoformat()
    runs = _load_fault_history()
    runs.append(run)
    _save_fault_history(runs)
    return {"ok": True, "count": len(runs)}


@app.get("/api/services")
async def api_services():
    return await run_ps("Get-Services.ps1")


@app.post("/api/services/restart")
async def api_restart_service(request: Request):
    body = await request.json()
    name = body.get("serviceName", "")
    return await run_ps("Restart-Service.ps1", {"ServiceName": name}, timeout=60)


@app.post("/api/services/restart-agent")
async def api_restart_agent():
    """Runs c:\\pixellot\\bin\\keepagentup.exe per PDF #13 — the documented
    fast remedy for hung agent/coordinator before escalating to RMA."""
    return await run_ps("Restart-PixellotAgent.ps1", timeout=120)


@app.get("/api/services/install-state")
async def api_install_state():
    """PDF #3: detect a half-finished install in c:\\pixellot\\downloadedversion.
    Returns the part files present and the last line of the most-recent
    installer log."""
    return await run_ps("Test-PixellotInstallState.ps1", timeout=15)


@app.get("/api/services/dependencies")
async def api_dependencies():
    """Reads HKLM:\\SOFTWARE\\Pixellot\\dependencies to surface the installed
    deps version as a read-only status line on the Service Status tab.
    Adapted from Canopy/Leaf/getVpuDepsFromRegistry.ps1."""
    return await run_ps("Get-PixellotDependencies.ps1", timeout=10)


@app.get("/api/disk-health")
async def api_disk_health():
    return await run_ps("Get-DiskHealth.ps1")


# PDF #1: Image / file repair commands. RestoreHealth and sfc /scannow
# can run 10–30 minutes, so each action gets its own generous timeout.
_REPAIR_TIMEOUTS = {
    "CheckHealth":    240,    # ~30s typical, give it 4 min
    "RestoreHealth":  1900,   # up to 30 min + buffer
    "SfcScan":        1900,
    "ChkdskSchedule": 60,     # just queues, returns fast
}


@app.post("/api/disk-health/repair")
async def api_disk_repair(request: Request):
    body = await request.json()
    action = body.get("action", "")
    if action not in _REPAIR_TIMEOUTS:
        return {"error": True, "message": f"Unknown action: {action!r}. Expected one of {list(_REPAIR_TIMEOUTS)}"}
    return await run_ps(
        "Invoke-RepairTool.ps1",
        {"Action": action},
        timeout=_REPAIR_TIMEOUTS[action],
    )


@app.get("/api/disk-health/cleanup-preview")
async def api_disk_cleanup_preview():
    """Read-only enumeration of what the D: storage cleanup would delete:
    daily test clips older than 90 days and game recordings older than a
    year, under D:\\recordedevents only. Sizing a few hundred candidate
    folders means walking their file trees, hence the generous timeout.
    Never cached — the preview is the tech's evidence for a destructive
    confirmation, so it must reflect the disk right now."""
    return await run_ps(
        "Get-RecordingsCleanupPreview.ps1", timeout=300, use_cache=False,
    )


@app.post("/api/disk-health/cleanup")
async def api_disk_cleanup(request: Request):
    """Pulse's first destructive action: permanently delete old event
    folders from D:\\recordedevents. The script re-enumerates candidates
    with the same rules as the preview — the client never sends a folder
    list, only its confirmation."""
    body = await request.json()
    if body.get("confirm") is not True:
        return {"error": True,
                "message": "Cleanup requires explicit confirmation."}
    return await run_ps(
        "Invoke-RecordingsCleanup.ps1", {"Acknowledge": "DELETE"},
        timeout=900, use_cache=False,
    )


@app.get("/api/events")
async def api_events(
    hours: int = Query(default=48), level: str = Query(default="all")
):
    """Windows Event Log query — recent System/Application events within the
    given lookback window (hours), optionally filtered by level
    (error / warning / all)."""
    return await run_ps("Get-EventLogs.ps1", {"HoursBack": hours, "Level": level})


@app.get("/api/reboots")
async def api_reboots(hours: int = Query(default=168)):
    """Reboot/shutdown history with cause + a pending-reboot indicator.
    Answers "why did this VPU restart, and is one pending?" — and positively
    distinguishes a Pulse-initiated reboot (Reboot-Vpu.ps1 stamps the event
    Comment) from an external one (scheduled task, Windows Update, crash)."""
    return await run_ps("Get-RebootHistory.ps1", {"HoursBack": hours}, timeout=30)


@app.get("/api/pixellot-logs")
async def api_pixellot_logs(hours: int = Query(default=24)):
    """Scan C:\\Pixellot\\Data\\Log for errors, fatals, and process
    restarts in the last `hours` (PDF #5). Returns up to 500 matches with
    a `depsErrorDetected` flag that the UI surfaces as a prompt to escalate
    to Pixellot support."""
    return await run_ps("Search-PixellotLogs.ps1", {"HoursBack": hours}, timeout=30)


@app.get("/api/cloud-events")
async def api_cloud_events():
    """Event Streaming lane: chain the box's own identifiers (venueId +
    recorded pixellot event ids) through the public NFHS cloud APIs to show
    recent events, a streamed/failed verdict per event, and cloud-side
    evidence for failure causes. All cloud calls are server-side, timeout
    bounded, and fail-soft — an unreachable cloud is reported as such, never
    as a device finding."""
    identity, local, signals = await asyncio.gather(
        run_ps("Get-SystemIdentity.ps1"),
        run_ps("Get-PixellotEvents.ps1"),
        run_ps("Get-EventWindowSignals.ps1", timeout=45),
    )
    identity = identity if isinstance(identity, dict) else {}
    local = local if isinstance(local, dict) else {}
    venue_id = (identity.get("pixellot") or {}).get("venueId")
    local_events = local.get("events") or []
    loop = asyncio.get_event_loop()
    cloud = await loop.run_in_executor(
        None, cloud_api.fetch_cloud, venue_id, local_events, signals
    )
    return {
        "identity": {
            "venueId": venue_id,
            "vpuName": (identity.get("pixellot") or {}).get("vpuName"),
            "hostname": (identity.get("computerSystem") or {}).get("name"),
            "isNonVpuHost": identity.get("isNonVpuHost"),
        },
        "localEvents": local,
        "cloud": cloud,
    }


@app.get("/api/audio")
async def api_audio():
    # The Audio tab polls every 2s to animate live signal meters; the default
    # 25s result cache would freeze them between refreshes. Demand near-fresh
    # data (in-flight dedup still coalesces overlapping polls) — the collector
    # is cheap now that the interop compiles once to a cached DLL.
    return await run_ps("Get-AudioDevices.ps1", cache_ttl=1.5)


@app.post("/api/audio/volume")
async def api_audio_volume(request: Request):
    body = await request.json()
    device_id = body.get("deviceId", "")
    volume = body.get("volume")

    # Validate — reject bad input before it reaches PowerShell.
    if not isinstance(device_id, str) or not device_id.strip():
        return {"error": True, "message": "deviceId must be a non-empty string"}
    try:
        volume = int(volume)
    except (TypeError, ValueError):
        return {"error": True, "message": "volume must be an integer"}
    if volume < 0 or volume > 100:
        return {"error": True, "message": "volume must be 0-100"}

    # use_cache=False: an action, not a read — replaying a cached "success"
    # for a repeated (device, volume) pair would silently skip the actual set
    # (e.g. 78 -> 50 -> back to 78 within the 25s window).
    return await run_ps("Set-AudioVolume.ps1", {"DeviceId": device_id, "Volume": volume}, use_cache=False)


@app.get("/api/scoreconnect")
async def api_scoreconnect():
    settings = load_settings()
    url = settings.get("scoreConnectUrl", "http://localhost:5000")
    # 15s timeout — SC III REST probes ~2-4s, SC II file-based probe < 2s.
    return await _run_sc_status(url, timeout=15)


@app.get("/api/scoreconnect/history")
async def api_scoreconnect_history():
    """Previous scoreboard configurations recorded on this VPU, newest first.
    Read-only reference history — see _record_sc_config_history for how and
    when entries are captured."""
    entries = list(reversed(_load_sc_config_history()))
    if DEMO_MODE:
        from demo_data import _demo_scoreconnect_history
        entries = entries + _demo_scoreconnect_history()
    return {"entries": entries}


def _fetch_sc3_status(url: str) -> dict:
    """Blocking GET of SC III get-status via stdlib urllib (no PowerShell
    spawn, no extra deps). Runs in a thread so the event loop stays free."""
    import urllib.request
    req = urllib.request.Request(
        f"{url}/api/configuration/get-status",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


@app.get("/api/scoreconnect/live")
async def api_scoreconnect_live():
    """High-frequency live poll of SC III scoreboard data only. Uses a direct
    stdlib HTTP GET to localhost:5000 (NOT a PowerShell spawn) so it's cheap
    enough to poll multiple times per second — the clock ticks every second,
    so sub-second sampling avoids skipped seconds.

    Single stateless GET. Does NOT touch SC II or enumerate WMI. SC III is a
    REST service built for concurrent clients, so this does not interfere with
    the data stream Pixellot's agent relies on."""
    if DEMO_MODE:
        from demo_data import _demo_scoreconnect_live
        return _demo_scoreconnect_live()

    settings = load_settings()
    url = settings.get("scoreConnectUrl", "http://localhost:5000").rstrip("/")
    try:
        data = await asyncio.to_thread(_fetch_sc3_status, url)
        raw = str(data.get("data", "") or "").strip() or None
        sb = data.get("scoreBoardData") or {}
        return {
            "reachable": True,
            "rawData": raw,
            "dataStatus": sb.get("description") if isinstance(sb, dict) else None,
        }
    except Exception as e:
        return {"reachable": False, "rawData": None, "dataStatus": None, "error": str(e)}


@app.get("/api/scoreconnect/scorelink")
async def api_scoreconnect_scorelink():
    """Live check of the ScoreLink USB device (a light WMI query). Polled by
    the Score Connect page every few seconds to flag a USB disconnect — which
    drops scoreboard data the same way the controller powering off does."""
    return await run_ps("Get-ScoreLinkStatus.ps1", timeout=8)


@app.post("/api/scoreconnect/install-sc3")
async def api_install_sc3():
    """Kicks off a ScoreConnect III install that runs hidden in the background.
    Returns immediately — an elevated child (UAC prompt still shows) downloads
    the Canopy script, strips its console-only pause/cls lines, runs it hidden
    with output captured, then verifies SC III on :5000. Falls back to the old
    visible window only if the script grows a prompt the sanitizer can't strip.
    Frontend polls /api/scoreconnect/install-sc3/status for progress.
    """
    return await run_ps("Install-ScoreConnectIII.ps1", timeout=30)


@app.get("/api/scoreconnect/service-recovery")
async def api_sc3_service_recovery():
    """Whether ScoreConnect III is set to restart itself after a crash, plus
    recent crash / auto-recovery counts from the System log.

    SC III crashes on an unhandled WebSocket exception in every version shipped,
    and Sportzcast's installer configures no recovery, so an unprotected unit
    just goes dark. Pulse-driven installs apply the SCM restart actions; this
    endpoint is how a tech confirms a given VPU actually has them.
    """
    return await run_ps("Get-Sc3ServiceRecovery.ps1", timeout=25, cache_ttl=15.0)


@app.get("/api/scoreconnect/install-sc3/status")
async def api_install_sc3_status():
    """Polls the SC III install status file written by the elevated install
    process. Returns stage, percent, message, error. cache_ttl=1.0 so each
    poll reflects the latest stage instead of replaying the 25s-cached result
    (which would make a healthy, progressing install look frozen).
    Frontend should poll this every 1.5–2s while an install is in progress."""
    return await run_ps("Get-Sc3InstallStatus.ps1", timeout=5, cache_ttl=1.0)


@app.get("/api/settings")
async def api_get_settings():
    return load_settings()


@app.post("/api/settings")
async def api_save_settings(request: Request):
    body = await request.json()
    save_settings(body)
    return {"ok": True}


# ── Self-update ──────────────────────────────────────────────
# Pulse installs to C:\Pulse via a channel launcher (Pulse.bat) that already
# knows how to resolve -> download -> install -> restart a release. These
# endpoints let the running app check GitHub for a newer build on its channel
# and trigger that same launcher from inside the UI, so field techs don't have
# to re-run a .bat by hand.
_UPDATE_PUBLIC_REPO = "playon/pulse"
_UPDATE_SOURCE_REPO = "playon/pulse"
# channel -> (release-tag prefix, accept pre-releases)
_UPDATE_CHANNELS = {
    "production": ("web-v", False),
    "beta": ("web-beta-v", True),
    "dev": ("web-dev-v", True),
    "branch": ("web-dev-v", True),
}


def _pulse_bat_path():
    return _os.path.join(_web_root, "Pulse.bat")


def _installed_tag():
    """The release tag the launcher recorded at install (e.g. web-beta-v0.2.0)."""
    try:
        with open(_os.path.join(_web_root, "VERSION")) as f:
            return f.read().strip()
    except Exception:
        return None


def _is_managed_install():
    """True only for a launcher-managed C:\\Pulse install we can update in place
    (the launcher self-copies to Pulse.bat and writes VERSION). A from-source
    git checkout returns False, so we never try to self-update a dev tree."""
    return _os.path.exists(_pulse_bat_path()) and _installed_tag() is not None


def _update_channel():
    try:
        with open(_os.path.join(_web_root, "CHANNEL")) as f:
            ch = f.read().strip().lower()
            if ch in _UPDATE_CHANNELS:
                return ch
    except Exception:
        pass
    tag = (_installed_tag() or "").lower()
    if tag.startswith("web-beta-v"):
        return "beta"
    if tag.startswith("web-dev-v"):
        return "dev"
    if tag.startswith("web-v"):
        return "production"
    return "dev"


# ── One-shot beta-channel retirement ─────────────────────────────────────────
# The beta program is closed (2026-08). This build ships as the FINAL beta
# release: any install still on the beta channel is moved to production at
# startup — Pulse.bat (the frozen self-copy of the beta launcher that the
# Start Menu shortcut targets) is replaced with the bundled production
# launcher and CHANNEL is set to production, so the next launch installs the
# latest web-v* release. Gated on the EXACT installed release tag: a future
# beta cycle ships under a tag that isn't in this set, so it can never
# self-retire by accident. Closing that future cycle = add its final tag
# here and tag one last beta release (see docs/BETA_CHANNEL_PLAYBOOK.md).
_RETIRED_BETA_TAGS = {"web-beta-v1.0.6"}
_BUNDLED_PROD_LAUNCHER = _os.path.join(_web_root, "launcher", "run_pulse.bat")
# Set when THIS session performed the move — /api/version surfaces it so the
# UI can show the "you've been moved to production" notice exactly once.
_channel_migration = None


def _migrate_retired_beta():
    """Move a retired-beta install to the production channel. Fail-open in
    every branch: a failed migration logs and simply retries next launch
    (e.g. UAC was declined and C:\\Pulse wasn't writable this run)."""
    global _channel_migration
    try:
        if not _is_managed_install() or _update_channel() != "beta":
            return
        if (_installed_tag() or "") not in _RETIRED_BETA_TAGS:
            return
        if not _os.path.exists(_BUNDLED_PROD_LAUNCHER):
            _server_log.warning(
                "Beta retirement: bundled production launcher missing (%s)",
                _BUNDLED_PROD_LAUNCHER,
            )
            return
        with open(_BUNDLED_PROD_LAUNCHER, "rb") as src:
            launcher = src.read()
        with open(_pulse_bat_path(), "wb") as dst:
            dst.write(launcher)
        with open(_os.path.join(_web_root, "CHANNEL"), "w") as f:
            f.write("production\n")
        _channel_migration = {"from": "beta", "to": "production"}
        msg = ("Beta program closed. This install now tracks the production "
               "channel. The next launch installs the latest production release.")
        ps_log("server", 0, "ok", msg)
        _server_log.info(msg)
    except Exception as e:
        try:
            _server_log.warning("Beta retirement failed (will retry next launch): %s", e)
        except Exception:
            pass


# ── Keep the installed launcher current ──────────────────────────────────
# C:\Pulse\Pulse.bat is a FROZEN self-copy. The launcher only copies itself in
# when it runs from somewhere else (%~f0 != the install path), and the Start
# Menu shortcut runs the install copy — so a box that already has Pulse keeps
# whatever launcher it was first set up with, forever. It picks up every new
# run.bat from the release zip, but never a fix to the OUTER launcher: Chrome
# install, release lookup, download, extract, copy into C:\Pulse. Caught on the
# vpu-home bench at 1.2.3, which ran the new run.bat under a 1.2.2 Pulse.bat.
#
# Every release zip carries that release's production launcher at
# launcher\run_pulse.bat, so refresh Pulse.bat from it whenever the two differ.
#
# Three constraints shape this:
#   - Production channel only. The bundled copy IS the production launcher;
#     writing it over a dev or beta install's Pulse.bat would silently move
#     that box to a different channel.
#   - Never mid-launch. Pulse.bat is still executing while this server starts,
#     and cmd reads a .bat incrementally BY BYTE OFFSET: replace it underneath
#     a running cmd and execution resumes at that offset in the new file, on
#     whatever line fragment happens to live there. This is not theoretical.
#     A first cut of this used a fixed 30s delay and trusted os.replace() to
#     refuse while cmd held the file; on the bench it did neither. Windows let
#     the replace through (cmd opens the .bat with FILE_SHARE_DELETE), cmd
#     resumed mid-line with "'t' is not recognized as an internal or external
#     command", and then re-ran the whole launcher body from that offset.
#     30s was also simply too short: Wait-AndLaunch can hold run.bat for ~36s
#     after the port opens, waiting out three 12s attempts at a Chrome window.
#     So the trigger is a signal, not a guess — run.bat writes
#     pulse-launch-done as its last act, and we wait for THIS session's marker
#     plus a settle margin before touching anything.
#   - Never leave a half-written Pulse.bat. A truncated launcher orphans the
#     Start Menu shortcut, which is the failure the launcher goes out of its
#     way to avoid. Write a sibling temp file and rename it into place.
#
# Fail-open in every branch: a skipped refresh just retries on the next launch.
_LAUNCH_DONE_MARKER = _os.path.join(_web_root, "pulse-launch-done")
_LAUNCHER_REFRESH_POLL_SECS = 5
_LAUNCHER_REFRESH_MAX_WAIT_SECS = 300
# Between run.bat writing the marker and the launcher that called it closing,
# there is only that caller's own exit. Ten seconds is an eternity for it.
_LAUNCHER_REFRESH_SETTLE_SECS = 10


async def _wait_for_launch_complete(started_at: float) -> bool:
    """True once run.bat has recorded that THIS session's launch finished.

    A marker older than this server's start belongs to a previous launch and
    proves nothing about the cmd running right now, so it is ignored. Returns
    False if no fresh marker shows up — the caller then leaves the launcher
    alone and tries again next launch, which is the safe direction to fail:
    a stale launcher works, a half-rewritten one does not.
    """
    # Deadline off the monotonic clock rather than a count of sleeps: the
    # loop must terminate on elapsed time whatever the poll interval is.
    deadline = time.monotonic() + _LAUNCHER_REFRESH_MAX_WAIT_SECS
    while True:
        try:
            # -2s of slack for clock/filesystem-timestamp granularity; a real
            # previous-launch marker is minutes or days old, not seconds.
            if _os.path.getmtime(_LAUNCH_DONE_MARKER) >= started_at - 2:
                await asyncio.sleep(_LAUNCHER_REFRESH_SETTLE_SECS)
                return True
        except OSError:
            pass  # no marker yet (or ever, on a launch that didn't use run.bat)
        if time.monotonic() >= deadline:
            return False
        await asyncio.sleep(_LAUNCHER_REFRESH_POLL_SECS)


async def _refresh_installed_launcher(started_at: float = None) -> None:
    if DEMO_MODE:
        return
    if started_at is None:
        started_at = time.time()
    try:
        if not _is_managed_install() or _update_channel() != "production":
            return
        if not _os.path.exists(_BUNDLED_PROD_LAUNCHER):
            return
        with open(_BUNDLED_PROD_LAUNCHER, "rb") as src:
            bundled = src.read()
        # A truncated or empty bundled copy is never worth installing.
        if len(bundled) < 1000:
            _server_log.warning(
                "Launcher refresh skipped: bundled launcher is only %d bytes",
                len(bundled),
            )
            return
        target = _pulse_bat_path()
        try:
            with open(target, "rb") as dst:
                current = dst.read()
        except Exception:
            current = None
        if current == bundled:
            return  # already current — the steady state after the first refresh

        if not await _wait_for_launch_complete(started_at):
            _server_log.info(
                "Launcher refresh deferred: this launch never recorded "
                "pulse-launch-done, so the launcher may still be running"
            )
            return

        tmp = target + ".new"
        try:
            with open(tmp, "wb") as f:
                f.write(bundled)
            _os.replace(tmp, target)
        except Exception:
            try:
                _os.remove(tmp)
            except Exception:
                pass
            raise
        msg = ("Installed launcher refreshed from this release's bundled copy "
               f"({len(current or b'')} -> {len(bundled)} bytes). The Start Menu "
               "shortcut now runs the current launcher.")
        ps_log("server", 0, "ok", msg)
        _server_log.info(msg)
    except Exception as e:
        # Fail-open: a stale launcher still works, and we retry next launch.
        try:
            _server_log.info("Launcher refresh skipped (retries next launch): %s", e)
        except Exception:
            pass


# ── Run-tracking check-in ───────────────────────────────────────────────────
# ── One-shot Canopy Leaf removal ────────────────────────────────────────────
# PlayOn retired the Banyan Hills Canopy platform (fully shut down mid-2026),
# but fleet VPUs still carry the orphaned Leaf agent: four auto-start services,
# watchdog scheduled tasks, and ~250MB under C:\Banyan. On launch Pulse runs
# Remove-CanopyLeaf.ps1 in the background: silent NSIS uninstalls, task/service
# cleanup, then deletes C:\Banyan. The folder's absence is the "already done"
# marker, and the pre-check below skips even spawning PowerShell on a clean
# unit, so the fleet steady-state cost is zero. Fail-open in every branch —
# cleanup must never slow or break Pulse itself.

async def _remove_canopy_leaf() -> None:
    if DEMO_MODE:
        return
    try:
        if not _os.path.exists("C:\\Banyan"):
            return  # already clean — the overwhelming steady-state
        # Let the dashboard preload burst claim the PowerShell slots first;
        # the cleanup is a background chore with no user waiting on it.
        await asyncio.sleep(15)
        result = await run_ps("Remove-CanopyLeaf.ps1", timeout=600, use_cache=False)
        status = (result or {}).get("status") or "unknown"
        if status in ("removed", "not-present"):
            _server_log.info("Canopy Leaf removal: %s", status)
        else:
            _server_log.warning("Canopy Leaf removal incomplete: %s", json.dumps(result))
    except Exception as e:
        # Fail-open: the cleanup must never affect Pulse.
        try:
            _server_log.info("Canopy Leaf removal skipped (%s)", e)
        except Exception:
            pass


# ── One-shot Splashtop Streamer removal ─────────────────────────────────────
# Splashtop Streamer shipped to the fleet as part of the same Banyan Hills
# Canopy deployment the Leaf remover retires, but it is a separate MSI with
# its own footprint, so it gets its own sweep: a unit already clean of
# C:\Banyan can still be running Splashtop. Remove-Splashtop.ps1 does the MSI
# uninstall (/qn /norestart) plus a service/process/folder leftover sweep;
# validated end-to-end on VPU2 under PS 5.1 (2026-08-07). Same contract as
# the Leaf remover: dir pre-check keeps the fleet steady-state cost at zero,
# and every branch fails open.

_SPLASHTOP_DIRS = (
    "C:\\Program Files (x86)\\Splashtop",
    "C:\\Program Files\\Splashtop",
    "C:\\ProgramData\\Splashtop",
)


async def _remove_splashtop() -> None:
    if DEMO_MODE:
        return
    try:
        if not any(_os.path.exists(d) for d in _SPLASHTOP_DIRS):
            return  # already clean — the overwhelming steady-state
        # Stagger behind the dashboard preload burst (and the Leaf sweep's
        # own slot) — background chore, nobody is waiting on it.
        await asyncio.sleep(25)
        result = await run_ps("Remove-Splashtop.ps1", timeout=600, use_cache=False)
        status = (result or {}).get("status") or "unknown"
        if status in ("removed", "not-present"):
            _server_log.info("Splashtop removal: %s", status)
        else:
            _server_log.warning("Splashtop removal incomplete: %s", json.dumps(result))
    except Exception as e:
        # Fail-open: the cleanup must never affect Pulse.
        try:
            _server_log.info("Splashtop removal skipped (%s)", e)
        except Exception:
            pass


# Fire-and-forget "Pulse ran on this VPU" beacon for fleet tracking. The sink is
# a Google Apps Script web app that upserts one row per unit (first/last seen,
# run count). The URL + secret are embedded below by deliberate choice: this is
# a low-value, rotatable, write-only spreadsheet key, and baking it into main.py
# means every release checks in with zero per-VPU setup. Env vars
# PULSE_CHECKIN_URL / PULSE_CHECKIN_SECRET override the embedded defaults.
#
# Never runs in demo/dev (DEMO_MODE) so a developer's machine can't pollute the
# list. Identity-only payload; one-way (we POST, we don't act on any response).
# Fail-open in every branch: a blocked network or unreachable sink must never
# slow or break launch. Stdlib urllib on purpose (no httpx) — the beacon has to
# work on any installed build, even one missing an optional pip dependency.
#
# ============================================================================
#  >>> PASTE YOUR APPS SCRIPT SECRET HERE <<<
#  Replace PASTE_CHECKIN_SECRET_HERE below with the secret from your Apps Script
#  deployment. The URL is already set. Until then, check-in stays inert (it
#  won't send with the placeholder).
# ============================================================================
_CHECKIN_URL    = "https://script.google.com/macros/s/AKfycbworYEcINtNfd1R6sTvHFDFqOHzYVA1XxHZRStB54T2GcTgQ8JvE0lxnboJ9q_jEFS4/exec"
_CHECKIN_SECRET = "7a161bad7765fc5078b8375007999160c5687bf5da52ae1ca717ebbad628e648"


def _post_checkin_sync(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    # Apps Script 302-redirects the POST to a result URL; urllib follows it as a
    # GET and reads the JSON ack. We don't need the body — just don't error.
    with urllib.request.urlopen(req, timeout=4) as resp:
        resp.read(256)


async def _send_checkin() -> None:
    url = (_os.environ.get("PULSE_CHECKIN_URL") or _CHECKIN_URL).strip()
    secret = (_os.environ.get("PULSE_CHECKIN_SECRET") or _CHECKIN_SECRET).strip()
    if not url or not secret or secret == "PASTE_CHECKIN_SECRET_HERE" or DEMO_MODE:
        return  # not configured (placeholder secret), or a dev/demo machine — never report
    try:
        ident = await run_ps("Get-SystemIdentity.ps1")
        if not isinstance(ident, dict) or ident.get("error"):
            return  # couldn't read identity — skip silently
        cs   = ident.get("computerSystem") or {}
        bios = ident.get("bios") or {}
        px   = ident.get("pixellot") or {}
        payload = {
            "secret":       secret,
            "hostname":     cs.get("name"),
            "serialNumber": bios.get("serialNumber"),
            "venueId":      px.get("venueId"),
            "vpuName":      px.get("vpuName"),
            "model":        cs.get("model"),
            "pulseVersion": APP_VERSION,
            "channel":      _update_channel(),
        }
        # Stream Readiness verdict on the beacon → a pre-game-readiness time
        # series at ~zero marginal cost (the beacon already fires on launch).
        # Fail-open like everything else here: a readiness error never blocks
        # the check-in — we just send the identity fields without the verdict.
        try:
            dash = await _collect_dashboard()
            verdict = (dash or {}).get("readiness") or {}
            if verdict:
                payload["readiness"] = {
                    "status":        verdict.get("status"),
                    "policyVersion": verdict.get("policyVersion"),
                    "blockers":      [b.get("code") for b in verdict.get("blockers", [])],
                    "risks":         [r.get("code") for r in verdict.get("risks", [])],
                }
        except Exception as e:
            _server_log.info("Check-in readiness skipped (%s)", e)
        await asyncio.to_thread(_post_checkin_sync, url, payload)
        _server_log.info("Check-in sent for %s", payload.get("hostname") or "unknown VPU")
    except Exception as e:
        # Fail-open: the beacon must never affect Pulse.
        try:
            _server_log.info("Check-in skipped (%s)", e)
        except Exception:
            pass


async def _resolve_latest_release(channel):
    # Stdlib urllib on purpose — NOT httpx. A self-updater has to work on any
    # already-installed build, including one where an extra pip dependency
    # never got installed; depending on httpx here is exactly what breaks the
    # feature it's meant to provide. Runs in a thread so the blocking call
    # doesn't stall the event loop.
    prefix, accept_pre = _UPDATE_CHANNELS.get(channel, ("web-dev-v", True))

    def _fetch():
        import urllib.request
        import json as _json
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Pulse-Updater"}
        # Track reachability separately from match: "the feed answered but has
        # no release for this channel" is a publishing problem, not a network
        # problem, and the UI must not tell a tech to go check the internet.
        reachable = False
        for repo in (_UPDATE_PUBLIC_REPO, _UPDATE_SOURCE_REPO):
            try:
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/releases", headers=headers
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    releases = _json.loads(resp.read().decode("utf-8"))
            except Exception:
                continue
            reachable = True
            for rel in releases:
                if rel.get("draft"):
                    continue
                tag = rel.get("tag_name", "")
                if not tag.startswith(prefix):
                    continue
                if rel.get("prerelease") and not accept_pre:
                    continue
                return {"tag": tag, "url": rel.get("html_url"), "notes": rel.get("body") or ""}, True
        return None, reachable

    return await asyncio.to_thread(_fetch)


@app.get("/api/update/check")
async def api_update_check():
    # Never let this 500 — a crash here just renders as a useless error in the
    # UI. Always return a JSON envelope with a human-readable string in `error`.
    try:
        channel = _update_channel()
        current = _installed_tag() or APP_VERSION
        if not _is_managed_install():
            return {
                "managed": False, "channel": channel, "current": current,
                "updateAvailable": False,
                "note": "Pulse is running from source here, so updates come from git, not this button.",
            }
        latest, reachable = await _resolve_latest_release(channel)
        if not latest:
            if reachable:
                error = (f"The update server is reachable, but no {channel} release has "
                         "been published yet, so there is nothing to compare against. "
                         "That is a publishing issue on our side, not a problem with "
                         "this VPU or its network.")
            else:
                error = ("Couldn't reach the update server. Check the VPU's internet "
                         "connection and try again.")
            return {
                "managed": True, "channel": channel, "current": current,
                "updateAvailable": False,
                "error": error,
            }
        return {
            "managed": True, "channel": channel, "current": current,
            "latest": latest["tag"], "latestUrl": latest["url"], "notes": latest["notes"],
            "updateAvailable": latest["tag"] != current,
        }
    except Exception as e:
        return {
            "managed": True, "updateAvailable": False,
            "error": f"Update check failed: {type(e).__name__}: {e}",
        }


@app.post("/api/update/apply")
async def api_update_apply():
    if _sys.platform != "win32":
        return {"ok": False, "error": "Self-update only runs on Windows VPUs."}
    if not _is_managed_install():
        return {"ok": False, "error": "Pulse isn't a launcher-managed install here; update with git instead."}
    import subprocess
    pulse_bat = _pulse_bat_path()
    port = int(_os.environ.get("PORT", 8765))
    updater_path = _os.path.join(_web_root, "pulse-update.bat")
    lines = [
        "@echo off",
        "rem Pulse self-update helper - spawned detached by the running server.",
        "rem 1) let the HTTP reply flush  2) stop the server so its files unlock",
        "rem 3) hand off to the channel launcher (resolve/download/install/restart).",
        "rem PULSE_NO_BROWSER stops a second browser tab; the open page reloads itself.",
        "ping -n 2 127.0.0.1 >nul",
        f"""for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":{port} " ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1""",
        "ping -n 3 127.0.0.1 >nul",
        'set "PULSE_NO_BROWSER=1"',
        f'call "{pulse_bat}"',
        "",
    ]
    try:
        with open(updater_path, "w", newline="") as f:
            f.write("\r\n".join(lines))
    except Exception as e:
        return {"ok": False, "error": f"Couldn't write the updater script: {e}"}
    _CREATE_NEW_CONSOLE = 0x00000010
    _CREATE_NEW_PROCESS_GROUP = 0x00000200
    try:
        subprocess.Popen(
            ["cmd", "/c", updater_path],
            cwd=_web_root,
            creationflags=_CREATE_NEW_CONSOLE | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"Couldn't start the updater: {e}"}
    return {"ok": True, "message": "Pulse is updating and will restart shortly."}


# ── Maintenance: restart Pulse / reboot the VPU ──────────────────────────────
@app.post("/api/maintenance/restart-app")
async def api_restart_app():
    """Relaunch the CURRENT Pulse build (no download). Mirrors the update
    handoff — spawn a detached helper that lets the HTTP reply flush, taskkills
    the server so its port frees, then re-runs the hidden launcher
    (pulse-launch.vbs) to start the same build again. Recovers a wedged app
    without touching the OS or any recording. The open page reloads itself once
    the server is back (see _pollForRestart)."""
    if _sys.platform != "win32":
        return {"ok": False, "error": "Restarting Pulse only works on Windows VPUs."}
    import subprocess
    vbs = _os.path.join(_web_root, "pulse-launch.vbs")
    if not _os.path.exists(vbs):
        return {"ok": False, "error": "pulse-launch.vbs not found, so the server can't be relaunched."}
    port = int(_os.environ.get("PORT", 8765))
    helper = _os.path.join(_web_root, "pulse-restart.bat")
    lines = [
        "@echo off",
        "rem Pulse restart helper - spawned detached by the running server.",
        "rem 1) let the HTTP reply flush  2) stop the server so its port frees",
        "rem 3) relaunch the SAME build via the hidden launcher (no download).",
        "ping -n 2 127.0.0.1 >nul",
        f"""for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":{port} " ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1""",
        "ping -n 3 127.0.0.1 >nul",
        f'wscript "{vbs}"',
        "",
    ]
    try:
        with open(helper, "w", newline="") as f:
            f.write("\r\n".join(lines))
    except Exception as e:
        return {"ok": False, "error": f"Couldn't write the restart script: {e}"}
    _CREATE_NEW_CONSOLE = 0x00000010
    _CREATE_NEW_PROCESS_GROUP = 0x00000200
    try:
        subprocess.Popen(
            ["cmd", "/c", helper],
            cwd=_web_root,
            creationflags=_CREATE_NEW_CONSOLE | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except Exception as e:
        return {"ok": False, "error": f"Couldn't start the restart helper: {e}"}
    return {"ok": True, "message": "Pulse is restarting and will reload shortly."}


@app.post("/api/maintenance/reboot-vpu")
async def api_reboot_vpu():
    """Schedule a full VPU reboot. Uses shutdown.exe /r /t <delay> (via
    Reboot-Vpu.ps1) so the OS reboots after a short delay and the HTTP reply
    flushes first — Restart-Computer would kill the server before the reply
    lands. Confirmation-gated in the UI; interrupts any active recording."""
    if _sys.platform != "win32":
        return {"success": False, "message": "Rebooting the VPU only works on Windows."}
    return await run_ps("Reboot-Vpu.ps1", timeout=30)


async def build_report() -> dict:
    """Full diagnostic bundle for offline review. Runs every (non-interactive)
    data-collection script, adds the enriched camera view and Pulse's own
    computed findings, and wraps it all in a provenance envelope so a reviewer
    knows where/when it came from and which collectors (if any) failed.

    Shared by the Reports download (/api/reports/export) and the LAN peer push
    (/api/peer/send) so both ship the identical snapshot."""
    sc_url = load_settings().get("scoreConnectUrl", "http://localhost:5000")

    # (section key, coroutine). Interactive/slow-by-design probes (traceroute,
    # local ping, packet capture, RTSP video test) and action scripts are
    # intentionally excluded — this is a state snapshot, not a live workbench.
    collectors = [
        ("identity",             run_ps("Get-SystemIdentity.ps1")),
        ("hardware",             run_ps("Get-Hardware.ps1")),
        ("performance",          run_ps("Get-Performance.ps1")),
        ("networkConfig",        run_ps("Get-NetworkConfig.ps1", timeout=15)),
        ("nicAdapters",          run_ps("Get-NicAdapters.ps1")),
        ("services",             run_ps("Get-Services.ps1")),
        ("diskHealth",           run_ps("Get-DiskHealth.ps1")),
        ("eventLogs",            run_ps("Get-EventLogs.ps1")),
        ("scoreConnect",         _run_sc_status(sc_url, timeout=20)),
        ("scoreLink",            run_ps("Get-ScoreLinkStatus.ps1", timeout=15)),
        ("pixellotConfig",       run_ps("Get-PixellotConfig.ps1", timeout=15)),
        ("pixellotInstallState", run_ps("Test-PixellotInstallState.ps1", timeout=15)),
        ("pixellotDependencies", run_ps("Get-PixellotDependencies.ps1", timeout=15)),
        ("installedSoftware",    run_ps("Get-InstalledSoftware.ps1")),
        ("gpuInfo",              run_ps("Get-GpuInfo.ps1", timeout=15)),
        ("wifi",                 run_ps("Get-WifiAdapters.ps1", timeout=10)),
        ("audio",                run_ps("Get-AudioDevices.ps1", timeout=15)),
        ("s1Cameras",            run_ps("Get-S1Cameras.ps1", timeout=20)),
        ("cameraExpectations",   run_ps("Get-CameraExpectations.ps1", timeout=10)),
        ("networkHealth",        run_ps("Get-NetworkHealth.ps1", timeout=10)),
        ("networkDomains",       run_ps("Test-NetworkDomains.ps1", timeout=30)),
        # 40s: UDP rows retry once and require an echoed reply, so a
        # blocked-UDP venue adds ~14s — this is the report path, completeness
        # beats a few extra seconds here.
        ("networkPorts",         run_ps("Test-NetworkPorts.ps1", timeout=40)),
        ("ntpDrift",             run_ps("Test-NtpDrift.ps1", timeout=20)),
        ("ntpPeers",             run_ps("Get-NtpPeers.ps1", timeout=15)),
        ("dnsResolution",        run_ps("Test-DnsResolution.ps1", timeout=30)),
        # SSL-inspection evidence (per-domain certificate issuers) — the report
        # is what gets sent to a district's IT team, so the raw cert detail
        # matters here even more than in the UI.
        ("tlsInspection",        run_ps("Test-TlsInspection.ps1", timeout=60)),
    ]

    def _norm(r):
        if isinstance(r, Exception):
            return {"error": f"{type(r).__name__}: {r}"}
        return r

    keys = [k for k, _ in collectors]
    raw = await asyncio.gather(*[c for _, c in collectors], return_exceptions=True)
    sections = {k: _norm(r) for k, r in zip(keys, raw)}

    nics = sections.get("nicAdapters")
    pix_cfg = sections.get("pixellotConfig")

    # Enriched camera connectivity: physical ports + detected cameras/OCR +
    # live CGI probe (firmware, model) — the Camera Connectivity lane's output,
    # which the raw nicAdapters dump alone doesn't capture.
    cam_probes = None  # None = probes never ran (findings keep ARP-only behavior)
    try:
        ocr_ips, _ = _build_ocr_sets(pix_cfg)
        raw_ports = nics.get("ports", []) if isinstance(nics, dict) and not nics.get("error") else []
        cam_probes = await _probe_all_cameras(raw_ports, ocr_ips)
        sections["cameras"] = _enrich_ports(nics, pix_cfg, cam_probes)
    except Exception as e:
        sections["cameras"] = {"error": f"camera enrichment failed: {type(e).__name__}: {e}"}

    # Pulse's own analysis, so a reviewer sees the tool's conclusions next to
    # the raw data it drew them from.
    try:
        sections["findings"] = _compute_findings(
            sections.get("identity"), sections.get("performance"), sections.get("services"),
            nics, sections.get("hardware"), sections.get("installedSoftware"),
            sections.get("networkConfig"), sections.get("pixellotInstallState"),
            sections.get("networkPorts"), sections.get("gpuInfo"), sections.get("wifi"),
            pixellot_config=pix_cfg, expectations=sections.get("cameraExpectations"),
            disk_health=sections.get("diskHealth"),
            probe_results=cam_probes,
            tls_inspection=sections.get("tlsInspection"),
        )
    except Exception as e:
        sections["findings"] = {"error": f"findings computation failed: {type(e).__name__}: {e}"}

    source_errors = {
        k: v["error"] for k, v in sections.items()
        if isinstance(v, dict) and v.get("error")
    }
    ident = sections.get("identity")
    hostname = ((ident.get("computerSystem") or {}).get("name")
                if isinstance(ident, dict) else None)

    import datetime
    return {
        **sections,
        "_meta": {
            "schema": "pulse-report/2",
            "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "pulseVersion": APP_VERSION,
            "channel": _update_channel(),
            "managed": _is_managed_install(),
            "hostname": hostname,
            "sourceErrors": source_errors,
        },
    }


@app.get("/api/reports/export")
async def api_export():
    return await build_report()


# ─── LAN peer sharing — send a snapshot to another Pulse ─────
# The receiving side opts in (peer.start_listener), which is the only path
# that binds to the LAN; the sending side just makes an outbound POST. See
# peer.py for the loopback-preserving rationale and the pairing-code scheme.

def _lan_port() -> int:
    """Port the receive listener binds on the LAN. Default = UI port + 1 so a
    single host can run two instances for testing without colliding."""
    try:
        return int(_os.environ.get("PULSE_LAN_PORT", int(_os.environ.get("PORT", 8765)) + 1))
    except ValueError:
        return 8766


@app.get("/api/peer/receive-mode")
async def api_peer_receive_mode():
    return peer.listener_status()


@app.post("/api/peer/receive-mode")
async def api_peer_set_receive_mode(request: Request):
    body = await request.json()
    if body.get("on"):
        try:
            status = await peer.start_listener(_lan_port(), APP_VERSION, body.get("ip"))
        except Exception as e:
            return {"on": False, "error": f"{type(e).__name__}: {e}"}
        # Open the Windows firewall for the LAN port so peers can actually reach
        # us — otherwise Defender silently drops inbound. Best-effort, elevated;
        # the listener still runs if it fails (the tech can allow it manually).
        status["firewall"] = await _open_share_firewall(status.get("lanPort") or _lan_port())
        return status
    return await peer.stop_listener()


async def _open_share_firewall(port: int) -> dict:
    """Add a one-time inbound allow-rule for the LAN share port (Windows only).
    Idempotent: if the rule already exists no prompt appears; otherwise it adds
    the rule elevated (single UAC prompt), mirroring the SC3 installer."""
    if _os.name != "nt":
        return {"applied": False, "reason": "not Windows: open the port manually if it is firewalled"}
    try:
        return await run_ps("Set-PulseShareFirewall.ps1", {"Port": str(port)}, timeout=20)
    except Exception as e:
        return {"applied": False, "error": f"{type(e).__name__}: {e}"}


@app.get("/api/peer/inbox")
async def api_peer_inbox():
    return {"reports": peer.list_received()}


@app.get("/api/peer/inbox/{rec_id}")
async def api_peer_inbox_get(rec_id: str):
    report = peer.get_received(rec_id)
    if report is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return report


@app.delete("/api/peer/inbox/{rec_id}")
async def api_peer_inbox_delete(rec_id: str):
    return {"ok": peer.delete_received(rec_id)}


def _resolve_peer_target(code: str, address: str):
    """Turn a pairing code (and optional address override) into (ip, port,
    nonce). The code carries ip/port/nonce; an address overrides ip:port for a
    multi-NIC host. Raises ValueError with a tech-readable message."""
    code = (code or "").strip()
    address = (address or "").strip()
    ip = port = nonce = None
    if code:
        try:
            ip, port, nonce = peer.decode_pair(code)
        except Exception:
            raise ValueError("that pairing code doesn't look right")
    if address:
        target = peer.parse_address(address, port or _lan_port())
        if not target:
            raise ValueError("address should look like 192.168.1.42:8766")
        ip, port = target
    if not ip or not port:
        raise ValueError("enter a pairing code (or an address) for the receiving Pulse")
    return ip, port, nonce


@app.get("/api/peer/send/ping")
async def api_peer_send_ping(code: str = Query(""), address: str = Query("")):
    try:
        ip, port, _ = _resolve_peer_target(code, address)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    try:
        info = await asyncio.to_thread(peer.ping_peer_sync, ip, port)
        if not (isinstance(info, dict) and info.get("pulse")):
            return {"ok": False, "error": "reachable, but that isn't a Pulse receiver"}
        return {"ok": True, "address": f"{ip}:{port}", "hostname": info.get("hostname")}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"can't reach {ip}:{port}: {getattr(e, 'reason', e)}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@app.post("/api/peer/send")
async def api_peer_send(request: Request):
    """Build the current snapshot and push it to a peer. Requires a pairing
    code (it carries the nonce the receiver checks); an optional address
    overrides the IP:port encoded in the code, e.g. for a multi-NIC host."""
    body = await request.json()
    try:
        ip, port, nonce = _resolve_peer_target(body.get("code"), body.get("address"))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not nonce:
        return {"ok": False, "error": "paste the pairing code shown on the receiving Pulse"}

    report = await build_report()
    payload = json.dumps(report).encode("utf-8")
    try:
        res = await asyncio.to_thread(peer.push_report_sync, payload, ip, port, nonce)
        return {"ok": bool(res.get("ok", True)), "peer": res.get("hostname"),
                "address": f"{ip}:{port}", "bytes": len(payload)}
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {"ok": False, "error": "the receiver rejected the pairing code, so re-copy it"}
        return {"ok": False, "error": f"receiver returned HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"can't reach {ip}:{port}: {getattr(e, 'reason', e)}"}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ─── WebSocket — live metrics + auto-shutdown ────────────────

_ws_clients: set = set()
_shutdown_task = None  # Optional[asyncio.Task]
_ever_had_client: bool = False
IDLE_SHUTDOWN_SECS = 60  # shut down 60s after last client disconnects


def _self_sigint():
    """Send SIGINT to ourselves so uvicorn's lifespan handlers run cleanly.
    _os._exit would bypass cleanup and abruptly tear down the process."""
    import signal
    try:
        _os.kill(_os.getpid(), signal.SIGINT)
    except Exception:
        _os._exit(0)  # fall back to hard exit if signal raise fails


async def _idle_shutdown():
    """Shut down the server after all WebSocket clients disconnect."""
    await asyncio.sleep(IDLE_SHUTDOWN_SECS)
    # Stay alive while a LAN receive listener is enabled — a peer may push a
    # report even with no browser tab open. Receiver turns it off to release us.
    if not _ws_clients and _ever_had_client and not peer.is_receiving():
        ps_log("auto-shutdown", 0, "ok", f"no clients for {IDLE_SHUTDOWN_SECS}s")
        _self_sigint()


def _on_ws_connect(ws: WebSocket):
    global _shutdown_task, _ever_had_client
    _ws_clients.add(id(ws))
    _ever_had_client = True
    if _shutdown_task and not _shutdown_task.done():
        _shutdown_task.cancel()
        _shutdown_task = None


def _on_ws_disconnect(ws: WebSocket):
    global _shutdown_task
    _ws_clients.discard(id(ws))
    if not _ws_clients and _ever_had_client:
        _shutdown_task = asyncio.create_task(_idle_shutdown())


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    """Live-metrics WebSocket. After accept, streams periodic snapshots (CPU /
    memory / temperature), tails new log-buffer lines, and refreshes Pixellot
    config on the poll interval from settings (pollIntervalMs, floored at 1s)
    until the client disconnects."""
    await ws.accept()
    _on_ws_connect(ws)
    try:
        settings = load_settings()
        interval = max(settings.get("pollIntervalMs", 3000), 1000) / 1000
        last_log_idx = len(LOG_BUFFER)
        # Cache pixellot config but refresh periodically so config changes
        # made during a long session pick up without forcing a reconnect.
        pix_cfg = await run_ps("Get-PixellotConfig.ps1", timeout=10)
        ws_ocr_ips, _ = _build_ocr_sets(pix_cfg)
        pix_cfg_ttl_secs = 120  # refresh every ~2 minutes
        last_pix_refresh = time.time()

        while True:
            # Periodically refresh pixellot config (cheap — runs in parallel below).
            if time.time() - last_pix_refresh > pix_cfg_ttl_secs:
                try:
                    pix_cfg = await run_ps("Get-PixellotConfig.ps1", timeout=10)
                    ws_ocr_ips, _ = _build_ocr_sets(pix_cfg)
                    last_pix_refresh = time.time()
                except Exception as e:
                    ps_log("ws-refresh", 0, "warn", f"pix_cfg refresh failed: {e}")
                    _server_log.warning(f"pix_cfg refresh failed: {e}")

            perf, nics, net_health = await asyncio.gather(
                run_ps("Get-Performance.ps1", timeout=10),
                run_ps("Get-NicAdapters.ps1", timeout=10),
                run_ps("Get-NetworkHealth.ps1", timeout=10),
            )
            # CGI probes use 30s cache — no extra network cost on each tick
            ws_raw = nics.get("ports", []) if nics and not nics.get("error") else []
            ws_probes = await _probe_all_cameras(ws_raw, ws_ocr_ips)
            all_logs = list(LOG_BUFFER)
            new_logs = all_logs[last_log_idx:]
            last_log_idx = len(all_logs)

            await ws.send_json(
                {
                    "type": "metrics",
                    "performance": perf,
                    "ports": _enrich_ports(nics, pix_cfg, ws_probes),
                    "networkHealth": net_health,
                    "logs": new_logs,
                    # Seconds until the LMI auto-close fires, or None when no
                    # countdown is running (see _lmi_session_watch below).
                    "lmiShutdownSecs": (
                        max(0, int(_lmi_shutdown_deadline - time.time()))
                        if _lmi_shutdown_deadline else None
                    ),
                }
            )
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Log unexpected errors so they're surfaced in BOTH the Script Log
        # buffer (for live WS clients) and the Server Log file (for
        # post-hoc inspection) instead of silently killing live metric updates.
        msg = f"WebSocket loop crashed: {type(e).__name__}: {e}"
        ps_log("ws-loop", 0, "error", msg)
        _server_log.exception(msg)
    finally:
        _on_ws_disconnect(ws)


# ─── LogMeIn session watcher — close Pulse with the LMI session ───
#
# Support techs reach Pulse through a LogMeIn Remote Control session. When
# the tech closes LMI, the Chrome window stays open on the VPU console, its
# WebSocket stays connected, and the idle auto-shutdown above never fires —
# Pulse runs until the next reboot. LogMeIn spawns LogMeInRC.exe for the
# lifetime of a Remote Control session (verified on VPU2 2026-08-07: the
# process appears at Application-event 202 "session started" and exits
# within a second of 205 "session ended"), so its absence means nobody is
# remoting in via LMI.
#
# Armed only when Pulse starts DURING an LMI session. A console, Splashtop,
# or RDP user never had LogMeInRC.exe running at launch, so for them the
# watcher stands down and Pulse is never touched.

LMI_POLL_SECS = 5
LMI_GRACE_SECS = 300  # survive a network blip + LMI reconnect

# Epoch of the pending auto-close while the grace countdown runs, else None.
# The WebSocket metrics frame derives lmiShutdownSecs from this so the UI
# can show a live countdown banner (and clear it when a reconnect cancels).
_lmi_shutdown_deadline = None  # Optional[float]


def _lmi_rc_present() -> bool:
    """True while LogMeInRC.exe (LMI's per-session Remote Control process)
    is running. Fails safe: a probe error reports the session as present so
    a broken tasklist can never shut Pulse down."""
    import subprocess
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq LogMeInRC.exe", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return "logmeinrc.exe" in (out.stdout or "").lower()
    except Exception:
        return True


def _close_pulse_browser():
    """Best-effort graceful Chrome close (no /F — WM_CLOSE, not a kill).
    Without this, the dead Pulse tab greets the next tech with a Chrome
    error page. Only ever called after LMI_GRACE_SECS with no remote
    session, so nobody is looking at that console."""
    import subprocess
    try:
        subprocess.run(
            ["taskkill", "/IM", "chrome.exe"],
            capture_output=True, timeout=10,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception:
        pass


async def _lmi_session_watch():
    """Close Pulse LMI_GRACE_SECS after the LogMeIn session that launched
    it ends (see section comment above)."""
    global _lmi_shutdown_deadline
    if DEMO_MODE or _sys.platform != "win32":
        return
    if not await asyncio.to_thread(_lmi_rc_present):
        msg = "no LogMeIn session at launch - LMI auto-close not armed"
        ps_log("lmi-watch", 0, "ok", msg)
        _server_log.info(msg)
        return
    msg = (f"LogMeIn session detected - Pulse will close "
           f"{LMI_GRACE_SECS // 60} min after it ends")
    ps_log("lmi-watch", 0, "ok", msg)
    _server_log.info(msg)
    while True:
        await asyncio.sleep(LMI_POLL_SECS)
        if await asyncio.to_thread(_lmi_rc_present):
            continue
        msg = (f"LogMeIn session ended - closing Pulse in "
               f"{LMI_GRACE_SECS // 60} min unless it reconnects")
        ps_log("lmi-watch", 0, "warn", msg)
        _server_log.warning(msg)
        deadline = time.time() + LMI_GRACE_SECS
        _lmi_shutdown_deadline = deadline
        reconnected = False
        while time.time() < deadline:
            await asyncio.sleep(LMI_POLL_SECS)
            if await asyncio.to_thread(_lmi_rc_present):
                reconnected = True
                break
        if reconnected:
            _lmi_shutdown_deadline = None
            msg = "LogMeIn session reconnected - auto-close cancelled"
            ps_log("lmi-watch", 0, "ok", msg)
            _server_log.info(msg)
            continue
        if peer.is_receiving():
            _lmi_shutdown_deadline = None
            # A LAN receive listener may be waiting on a peer's report push —
            # stay up. The outer loop re-enters the grace cycle, so Pulse
            # still closes once the listener is released.
            msg = "grace expired but LAN receive listener is on - staying up"
            ps_log("lmi-watch", 0, "warn", msg)
            _server_log.warning(msg)
            continue
        msg = f"no LogMeIn session for {LMI_GRACE_SECS // 60} min - closing Pulse"
        ps_log("lmi-watch", 0, "ok", msg)
        _server_log.info(msg)
        _close_pulse_browser()
        _self_sigint()
        return


# ─── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(_os.environ.get("PORT", 8765))
    # Bind to loopback only. Pulse is always accessed from the VPU's own
    # browser (directly or over LogMeIn/RDP), never from another machine,
    # so 127.0.0.1 is correct AND avoids the Windows Defender Firewall
    # prompt that 0.0.0.0 (all interfaces) triggers on first launch.
    #
    # Pass the app object, NOT the "main:app" import string. The import-
    # string form makes uvicorn re-import this module as "main", re-running
    # all top-level code (re-truncating the log, double-attaching handlers).
    # Passing the object runs it once. reload is already off, so we lose
    # nothing.
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)
