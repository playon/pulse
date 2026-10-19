"""The fleet agent's report, pulse.telemetry/v1. Moved out of main.py (PV-49)
so it versions with the agent (pulse_agent/VERSION). The fields are the check-in
contract Pulse Vitals reads: docs/contract.md in playon/pulse-vitals.

The collectors and verdicts it reads still live in main.py: see engine.py.
"""

import asyncio
import json
import re
from typing import Optional

from pulse_agent.engine import engine


# ── Fleet-monitor telemetry (pulse.telemetry/v1) ─────────────────────────────
# What the scheduled monitor reports: the utilitarian fields Ian chose for NFHS
# Console on 2026-10-13 (verdict, blockers, streaming path, failed ports, the
# internet adapter's IPv4 setup and MAC, cameras with per-port detail,
# services down, scoreboard source, boots and power loss, versions). Oracle
# already shows Pixellot's own live metrics (CPU, bandwidth, dark court), so
# this carries what Pixellot can't see from outside the box. The hardware
# inventory came with PV-64; the camera card and PoE, restart history, disk
# space and health, components, applications, programs and the Windows/clock
# environment with PV-65 to PV-76, for Vitals' unit tabs. The full findings
# copy and recordings are still left out. Kept small on purpose: Unity writes
# must be, and the check-in Worker drops a document over 16 KB
# (_fit_telemetry). Leaves out hostname, BIOS serial, disk serials and camera
# serials.
_TELEMETRY_SCHEMA = "pulse.telemetry/v1"
def _port_names() -> dict:
    # Built per call: the RTMP purpose is the engine's, and main.py binds the
    # engine after this module is imported.
    return {
        "Zixi Streaming": "Streaming (Zixi primary)",
        "Zixi Backup":    "Streaming (Zixi backup)",
        engine._RTMP_FALLBACK_PURPOSE: "Streaming (RTMP last resort)",
    }


def _telemetry_ports(port_tests) -> Optional[list]:
    if not isinstance(port_tests, dict) or port_tests.get("error"):
        return None
    out = []
    for r in port_tests.get("results") or []:
        purpose = r.get("purpose") or ""
        out.append({
            "name":     _port_names().get(purpose, purpose),
            "rule":     f"{(r.get('protocol') or '').upper()} {r.get('port')}".strip(),
            "host":     r.get("host"),
            "ok":       r.get("status") == "pass",
            "optional": bool(r.get("optional")),
        })
    return out


def _telemetry_streaming_path(port_tests) -> Optional[str]:
    """Which rung of the Zixi UDP 2088 -> UDP 443 -> RTMP TCP 1935 chain a
    stream would use now, or None if the port probe didn't run."""
    if not isinstance(port_tests, dict) or port_tests.get("error"):
        return None
    ok = {r.get("purpose") for r in port_tests.get("results") or [] if r.get("status") == "pass"}
    for purpose, name in (("Zixi Streaming", "zixi-2088"), ("Zixi Backup", "zixi-443"),
                          (engine._RTMP_FALLBACK_PURPOSE, "rtmp-1935")):
        if purpose in ok:
            return name
    return "blocked"


def _telemetry_cameras(raw: dict) -> dict:
    nics = raw.get("nics")
    expectations = raw.get("expectations") or {}
    expected = expectations.get("expectedMainCameras") if not expectations.get("error") else None
    out = {"expected": expected if isinstance(expected, int) else None,
           "detected": None, "systemType": expectations.get("systemType"), "ports": []}
    if not isinstance(nics, dict) or nics.get("error"):
        return out
    probes = raw.get("probe_results") or {}
    ports = engine._enrich_ports(nics, raw.get("pixellot_config"), probes)
    engine._flag_uplink_ports(ports, raw.get("network_config"))
    out["detected"] = engine._count_main_cameras(ports, probes)
    for p in ports:
        if p.get("hasInternetUplink"):
            role = "internet cable"
        elif not p.get("isUp"):
            role = "no link"
        elif p.get("isOcr"):
            role = "scoreboard camera"
        elif p.get("camerasDetected"):
            role = "camera"
        else:
            role = "linked, no camera answering"
        cams = p.get("camerasDetected") or []
        out["ports"].append({
            "port":          p.get("portLabel") or p.get("name"),
            "portMac":       _norm_mac(p.get("mac")),
            "state":         role,
            "linkMbps":      p.get("linkSpeedMbps") if p.get("isUp") else None,
            "expectedMbps":  p.get("expectedSpeedMbps"),
            "slow":          bool(p.get("isDegraded")),
            "cameraModel":   cams[0].get("model") if cams else None,
            "cameraMac":     _norm_mac(cams[0].get("cgiMac") or cams[0].get("mac")) if cams else None,
            "cameraFirmware": cams[0].get("firmwareVersion") if cams else None,
        })
    return out


async def _collect_telemetry_extras(raw: dict, skip_intrusive: bool = False) -> None:
    """Collectors the telemetry needs beyond the dashboard pass: boots and
    power loss, the scoreboard source, calibration, the Windows patch level,
    clock drift and the camera card's PoE. Fills `raw`; each part fails soft.
    `skip_intrusive` is accepted for symmetry. None of them probes the venue
    network the way Test-NetworkPorts does: Test-NtpDrift sends one NTP sample
    to the unit's own time source, which Windows does on its own anyway."""
    del skip_intrusive
    card = _camera_card(raw.get("network_config"))

    async def _poe():
        # Only a card whose chip reports PoE ever loads SmartPoE.dll: on the
        # GIE64 and GIE74P-AN, Register_Card fails or hangs (PV-66). The
        # collector keeps its own crash sentinel, in SYSTEM's TEMP here.
        if not card or not card.get("poeSupported"):
            return None
        return await engine.run_ps("Get-PoePower.ps1", timeout=20)

    reboots, sc, calib, ubr, ntp, poe = await asyncio.gather(
        engine.run_ps("Get-RebootHistory.ps1", timeout=30),
        # Straight to the collector, not _run_sc_status: that also appends to
        # the ScoreConnect config history, which is the interactive tab's job.
        engine.run_ps("Get-ScoreConnectStatus.ps1", {"BaseUrl": engine.sc3_base_url()}, timeout=15),
        # Two folders and a few file times. Not Get-PixellotConfig: that also
        # probes every camera over CGI. The monitor serves it from its 6 h disk
        # cache (monitor_once.SLOW_COLLECTOR_TTLS), so most passes start no
        # PowerShell for it; no args, or the cache would not apply.
        engine.run_ps("Get-CalibrationStatus.ps1", timeout=15),
        # PV-75. One registry read (6 h cache) and one NTP sample (1 h cache).
        engine.run_ps("Get-WindowsUbr.ps1", timeout=10),
        engine.run_ps("Test-NtpDrift.ps1", timeout=20),
        _poe(),
        return_exceptions=True,
    )

    def ok(v):
        return v if isinstance(v, dict) and not v.get("error") else None
    raw.update(reboots=ok(reboots),
               scoreconnect=sc if isinstance(sc, dict) else None,
               calibration=ok(calib), ubr=ok(ubr), ntp=ok(ntp),
               poe=poe if isinstance(poe, dict) else None)


def _prefix_to_mask(prefix) -> Optional[str]:
    try:
        n = int(prefix)
    except (TypeError, ValueError):
        return None
    if not 0 <= n <= 32:
        return None
    bits = (0xFFFFFFFF << (32 - n)) & 0xFFFFFFFF if n else 0
    return ".".join(str((bits >> sh) & 0xFF) for sh in (24, 16, 8, 0))


def _norm_mac(v) -> Optional[str]:
    """AA:BB:CC:DD:EE:FF, whatever separator the collector used."""
    hexes = re.sub(r"[^0-9A-Fa-f]", "", str(v or ""))
    if len(hexes) != 12:
        return None
    return ":".join(hexes[i:i + 2] for i in range(0, 12, 2)).upper()


def _telemetry_adapters(network_config, uplink_alias) -> Optional[list]:
    """Every adapter's IPv4 setup. The internet adapter is flagged; camera
    ports usually sit on 169.254 link-local, flagged so a grid can hide them."""
    if not isinstance(network_config, dict) or network_config.get("error"):
        return None
    macs = {a.get("interfaceIndex"): _norm_mac(a.get("macAddress"))
            for a in network_config.get("adapters") or [] if a.get("interfaceIndex") is not None}
    out = []
    # The collector names it ipConfigurations; the dashboard payload, ipConfig.
    for a in network_config.get("ipConfigurations") or network_config.get("ipConfig") or []:
        ips = a.get("ipv4Address") or []
        gws = a.get("ipv4DefaultGateway") or []
        dns = [d for d in (a.get("dnsServers") or []) if ":" not in str(d)]  # IPv4 only
        ip = ips[0] if ips else None
        out.append({
            "adapter":    a.get("interfaceAlias"),
            "mac":        macs.get(a.get("interfaceIndex")),
            "internet":   a.get("interfaceAlias") == uplink_alias,
            "ip":         ip,
            "subnetMask": _prefix_to_mask(a.get("prefixLength")),
            "gateway":    gws[0] if gws else None,
            "dns1":       dns[0] if len(dns) > 0 else None,
            "dns2":       dns[1] if len(dns) > 1 else None,
            "dhcp":       a.get("dhcpEnabled"),
            "linkLocal":  bool(ip and str(ip).startswith("169.254.")),
        })
    return out


def _telemetry_scoreboard(raw: dict) -> Optional[dict]:
    sc = raw.get("scoreconnect")
    nics = raw.get("nics")
    ocr = "unknown"
    if isinstance(nics, dict) and not nics.get("error"):
        ports = engine._enrich_ports(nics, raw.get("pixellot_config"), raw.get("probe_results") or {})
        engine._flag_uplink_ports(ports, raw.get("network_config"))
        ocr = engine._scoreboard_camera_state(ports, raw.get("pixellot_config"))
    if sc is None and ocr == "unknown":
        return None
    src = engine._scoreboard_source(sc, ocr)
    out = {"source": src.get("source"), "ok": src.get("ok")}
    # What `ok` doesn't say (it means "ScoreConnect is running" when there's
    # no OCR camera): is the ScoreLink plugged in, is score data arriving, and
    # which sport ScoreConnect decodes. 6493 read ok for a whole event with
    # its ScoreLink missing (2026-10-14). Additive fields; `ok` keeps its v1
    # meaning.
    if isinstance(sc, dict) and not sc.get("error"):
        if isinstance(sc.get("scoreLinkConnected"), bool):
            out["scoreLinkConnected"] = sc["scoreLinkConnected"]
        ds = sc.get("dataStatus")
        if isinstance(ds, str) and ds:
            out["dataFlowing"] = ds.lower().startswith("data is present")
            out["dataStatus"] = ds[:120]
        sport = (sc.get("configuration") or {}).get("sport") if isinstance(sc.get("configuration"), dict) else None
        if sport:
            out["sport"] = str(sport)[:80]
    out["ocr"] = _telemetry_scoreboard_ocr(ocr, src, raw.get("pixellot_config"))
    out["scoreConnect"] = _telemetry_scoreconnect(sc)
    return out


def _telemetry_scoreboard_ocr(ocr, src: dict, pixellot_config) -> Optional[dict]:
    """PV-59: the OCR camera half of the source. None when the camera state
    couldn't be read: the NICs failed, or Get-PixellotConfig did, which would
    otherwise read as "no OCR entry in cameras.cfg" (never `configured: false`
    by default). A read that found no OCR camera is a real answer.
    `configured` is cameras.cfg's OCR role; an OCR camera seen live without
    one makes `source` "ocr" with `configured` false. `issue` is the OCR
    problem only, so it stays null when ScoreConnect is the source."""
    if ocr == "unknown" or not isinstance(pixellot_config, dict) or pixellot_config.get("error"):
        return None
    return {"configured": bool(isinstance(ocr, dict) and ocr.get("configured")),
            "issue": src.get("issue") if src.get("source") == "ocr" else None}


def _tel_str(v) -> Optional[str]:
    """A trimmed string capped at 80 chars, or None. Booleans and containers
    are not values (str(True) would read as a setting)."""
    if v is None or isinstance(v, (bool, dict, list, tuple)):
        return None
    s = str(v).strip()
    return s[:80] if s else None


def _telemetry_scoreconnect(sc) -> Optional[dict]:
    """PV-59: what ScoreConnect is set up as, from the Get-ScoreConnectStatus
    result the pass already has (the same fields the config history keeps, but
    not gated on data flowing: a unit with no score data is exactly when this
    matters). None only when the collector itself failed or didn't run (an
    `error`, or no result). Otherwise the block is sent and each unknown value
    is None. When SC III isn't answering (`reachable` false), its configuration
    and bot status are null, so `firmware`, `serialPort`, `eventType` and
    `botNumber` are None; `version` (the exe on disk) and the ScoreLink model
    and port (the USB scan) can still be set.
    `version` is the ScoreConnect III exe, so a legacy SC I/II unit reads null
    (its detail is in the `sc2` slot, not reported). Unverified: `firmware`,
    `serialPort` and `eventType` have not yet been seen populated on a unit with
    live score data; the collector guesses SC III's key names (Pick-First over
    get-current-configuration-extended), so they are null when SC III doesn't
    report them under those names. The bot number is best-effort: SC III can
    report a previous unit's number until its service restarts. No serials or
    hostnames: the bot number is ScoreConnect's cloud id, not a device serial,
    and botServerAddress and `device` are left out."""
    if not isinstance(sc, dict) or sc.get("error"):
        return None
    cfg = sc.get("configuration") if isinstance(sc.get("configuration"), dict) else {}
    bot = sc.get("botStatus") if isinstance(sc.get("botStatus"), dict) else {}
    return {
        "version":        _tel_str(sc.get("version")),
        "firmware":       _tel_str(cfg.get("firmware")),
        "scoreLinkModel": _tel_str(sc.get("scoreLinkModel")),
        "scoreLinkPort":  _tel_str(sc.get("scoreLinkPort")),
        "serialPort":     _tel_str(cfg.get("serialPort")),
        "eventType":      _tel_str(cfg.get("eventType")),
        "botNumber":      _tel_str(bot.get("scoreConnectId")),
    }


def _services_down(services: dict, scoreboard: Optional[dict]) -> list:
    """Services that are down AND should be up. vpu.exe only runs during an
    event, so it's never "down"; ScoreConnect only matters when it is the
    score source (an OCR camera makes it optional) and it is installed."""
    down = []
    for name, st in services.items():
        key = name.lower()
        if key == "vpu" or st == "Running":
            continue
        if key.startswith("scoreconnect"):
            if st == "NotFound" or (scoreboard or {}).get("source") == "ocr":
                continue
        down.append(name)
    return down


# Power events (PV-68). Get-RebootHistory already runs on every full pass
# (30 min disk cache). Only labels leave the box: the source Pulse names
# ("Windows Update", "Pulse (Reboot VPU)") and Windows' reason text. The
# process path, the user (VPU\Pixellot carries the computer name), the
# shutdown comment and the raw message stay out.
_POWER_MAX_EVENTS = 20
_POWER_MAX_REASONS = 5


def _is_unexpected(h: dict) -> bool:
    return h.get("category") == "unexpected" or h.get("eventId") in (41, 6008)


def _power_stamp(v) -> Optional[str]:
    """Like _calibration_stamp, and a task that never ran (Windows says
    1999-11-30) is no time at all."""
    t = _calibration_stamp(v)
    return t if t and t >= "2000" else None


def _telemetry_power(raw: dict) -> dict:
    rb = raw.get("reboots") or {}
    hist = [h for h in rb.get("history") or [] if isinstance(h, dict)]
    unexpected = [h for h in hist if _is_unexpected(h)]
    out = {"lastBoot": rb.get("lastBoot") or None,
           # Power cuts and hard crashes, from Get-RebootHistory's 7-day window.
           "unexpectedShutdowns7d": len(unexpected) if rb else None}
    if not rb:
        # Unread: the PV-68 fields stay out, as on an older agent, so a null
        # `deviceInstallRebootLastRun` or an empty `events` is always an answer.
        return out
    ids = _hw_identifiers(raw.get("identity") or {}, {})
    pend = rb.get("pending")
    out["pendingReboot"] = {
        "isPending": bool(pend.get("isPending")),
        "reasons": [r for r in (_hw_str(x, ids) for x in pend.get("reasons") or []) if r][:_POWER_MAX_REASONS],
    } if isinstance(pend, dict) else None
    apl = rb.get("afterPowerLoss")
    if isinstance(apl, dict) and _tel_str(apl.get("status")):
        status = _tel_str(apl.get("status"))[:16]
        # A value only when it was read: unknown never reads as "Power On".
        out["afterPowerLoss"] = {"status": status,
                                 "value": _hw_str(apl.get("value"), ids, 32) if status == "read" else None}
    else:
        out["afterPowerLoss"] = None
    out["deviceInstallRebootLastRun"] = _power_stamp(rb.get("deviceInstallRebootTaskLastRun"))
    rows = sorted(hist, key=lambda h: _calibration_stamp(h.get("time")) or "", reverse=True)
    # Capped at 20, newest first; `unexpectedShutdowns7d` still counts them all.
    out["events"] = [{
        "time":       _calibration_stamp(h.get("time")),
        "category":   "unexpected" if _is_unexpected(h) else "planned",
        "byPulse":    bool(h.get("byPulse")),
        "source":     _hw_str(h.get("source"), ids),
        "reasonText": _hw_str(h.get("reasonText"), ids),
    } for h in rows[:_POWER_MAX_EVENTS]]
    return out


# Calibration (PV-57). Static data, read through the monitor's 6 h disk cache:
# the block is a pure function of that read, ordered deterministically, so an
# unchanged unit fingerprints the same every pass, and a recalibration (a
# sport's time moves, a sport appears) changes the fingerprint and posts on
# the first full pass after the cached read expires, within 6 h. A read that
# could not answer is an error, never cached, so it retries next pass.
CALIBRATION_MAX_SPORTS = 20
CALIBRATION_NAME_MAX = 40
_STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?(Z|[+-]\d\d:\d\d)$")


def _calibration_stamp(v) -> Optional[str]:
    """ISO time with its offset and no fraction, like power.lastBoot. A time
    without an offset is unknown: a local time with no zone misleads."""
    m = _STAMP.match(str(v or "").strip())
    return m.group(1) + m.group(2) if m else None


def _calibration_name(v) -> Optional[str]:
    name = str(v or "").replace("\ufeff", "").strip()[:CALIBRATION_NAME_MAX].strip()
    return name or None


def _calibration_read(section: dict, key: str) -> Optional[dict]:
    """The section's read, or None when it gave no answer. A folder missing
    under a readable Configuration folder IS an answer (nothing calibrated);
    a folder that is there but unreadable, or no readable Configuration
    folder at all, is not."""
    part = section.get(key)
    if not isinstance(part, dict):
        return None
    if part.get("exists"):
        return part if part.get("readable") else None
    return part if section.get("configRootReadable") else None


def _calibration_sports(ms: dict) -> dict:
    rows = ms.get("sports") or []
    if isinstance(rows, dict):   # a one-item array can arrive unrolled
        rows = [rows]
    seen = {}
    for r in rows if isinstance(rows, list) else []:
        name = _calibration_name(r.get("name")) if isinstance(r, dict) else None
        if name and name.lower() not in seen:   # Windows folder names ignore case
            seen[name.lower()] = {"name": name, "at": _calibration_stamp(r.get("at"))}
    sports = sorted(seen.values(), key=lambda s: s["name"].lower())
    sports.sort(key=lambda s: s["at"] or "", reverse=True)   # newest first, undated last
    primary = _calibration_name(ms.get("primary"))
    mine = seen.get((primary or "").lower())
    if mine:
        primary = mine["name"]   # the folder's own spelling
    if len(sports) > CALIBRATION_MAX_SPORTS:
        sports = sports[:CALIBRATION_MAX_SPORTS]
        if mine and mine not in sports:
            sports[-1] = mine
    # A primary.txt naming a sport with no folder is sent as read and not
    # added to `sports`: a name in a text file is not a calibration.
    return {"primary": primary, "sports": sports}


def _telemetry_calibration(raw: dict) -> Optional[dict]:
    """Which sports, and the scoreboard (OCR/PiP) camera, are calibrated.
    Unknown is null: the whole block is null when the sports folder gave no
    answer, and `sports: []` only ever means it was read and holds no sport.
    `ocr` is null when the PiP folder gave no answer; a unit with no OCR
    camera normally reads calibrated false, which is what it is."""
    section = raw.get("calibration")
    if not isinstance(section, dict) or section.get("error"):
        return None
    ms = _calibration_read(section, "multisport")
    if ms is None:
        return None
    out = _calibration_sports(ms)
    pip = _calibration_read(section, "pip")
    if pip is None:
        out["ocr"] = None
    else:
        done = bool(pip.get("hasEnhancedPip")) and bool(pip.get("hasInnerObjects"))
        out["ocr"] = {"calibrated": done, "at": _calibration_stamp(pip.get("at")) if done else None}
    return out


# ── Hardware inventory (PV-64) ──────────────────────────────────────────────
# What the box is: model, CPU, memory, disks, graphics, BIOS. Built from
# collectors the pass already runs: Get-SystemIdentity (every pass, ~0.2 s)
# and Get-Hardware (the monitor serves it from its 6 h disk cache,
# monitor_once.SLOW_COLLECTOR_TTLS), so it adds no collection. It sits in the
# post fingerprint like every other field, so it goes out on the first post
# and again only when something in it changes. A part whose collector failed
# is null (unknown); an empty list means the collector ran and found none.
# Never a serial: the fields are picked one by one, and any string that
# contains the BIOS or a disk serial, the asset tag or the hostname is
# dropped (an odd OEM can put one in a model string).
_HW_MAX_DISKS = 8
_HW_MAX_GPUS = 4
_HW_MAX_STR = 80
# Version strings run 12-17 chars ("32.0.15.7628", "Q01 Ver. 02.07.01"); the
# tighter cap is what keeps a worst-case block under 2 KB.
_HW_MAX_VERSION = 32
# Board makers' unfilled SMBIOS fields: not a model.
_HW_PLACEHOLDERS = {"to be filled by o.e.m.", "system product name", "default string",
                    "not applicable", "none", "n/a", "unknown", "o.e.m."}
# Virtual adapters that come and go with a remote session; listing them would
# post a "change" every time someone connects. Basic Display stays: it means
# the real driver is missing.
_HW_GPU_SKIP = re.compile(r"remote display|mirror|indirect display|virtual display", re.I)
# WMI's InterfaceType, the collector's fallback, reads a SATA disk as IDE and
# an NVMe one as SCSI: not trustworthy on its own.
_HW_UNTRUSTED_BUS = {"IDE", "SCSI"}
# AdapterRAM is 32-bit: a value at its ceiling is "4 GB or more", not a size.
_HW_ADAPTER_RAM_CAP_MB = 4095


def _hw_identifiers(identity: dict, hardware: dict) -> list:
    """Every identifier the collectors return, lower-cased, so no field of the
    hardware block can carry one."""
    vals = []
    if isinstance(identity, dict):
        vals += [(identity.get("bios") or {}).get("serialNumber"),
                 (identity.get("computerSystem") or {}).get("name"),
                 identity.get("assetTag")]
    if isinstance(hardware, dict):
        vals += [d.get("serialNumber") for d in hardware.get("diskDrives") or [] if isinstance(d, dict)]
    return [str(v).strip().lower() for v in vals if v is not None and len(str(v).strip()) >= 4]


def _hw_str(v, ids: list, limit: int = _HW_MAX_STR) -> Optional[str]:
    """Trimmed, whitespace-collapsed, at most `limit` chars; None when empty,
    a placeholder, or carrying an identifier."""
    if v is None or isinstance(v, (dict, list, bool)):
        return None
    s = " ".join(str(v).split())
    low = s.lower()
    if not s or low in _HW_PLACEHOLDERS or any(i in low for i in ids):
        return None
    return s[:limit]


def _hw_int(v) -> Optional[int]:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        return None
    return int(round(v))


def _hw_disk_type(d: dict) -> Optional[str]:
    """NVMe, USB, SSD, HDD, or the bus (SATA, SAS, RAID...) when the media
    type is unknown. Get-PhysicalDisk calls an NVMe drive an SSD, and a USB
    drive is worth naming as one, so the bus wins for those two."""
    bus = str(d.get("interfaceType") or "").strip()
    media = str(d.get("mediaType") or "").strip().upper()
    if bus.upper() == "NVME":
        return "NVMe"
    if bus.upper() == "USB":
        return "USB"
    if media in ("SSD", "HDD", "SCM"):
        return media
    if not bus or bus.upper() in _HW_UNTRUSTED_BUS:
        return None
    return bus[:16]


def _hw_bios_date(v) -> Optional[str]:
    """YYYY-MM-DD in UTC. The collector prints the BIOS date as local time,
    and SMBIOS dates are UTC midnight, so vpu-home's 2019-04-23 BIOS reads
    2019-04-22T20:00:00-04:00: the first ten characters are a day early."""
    from datetime import datetime, timedelta
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?)?",
                 str(v or ""))
    if not m:
        return None
    try:
        dt = datetime(*(int(x or 0) for x in m.groups()[:6]))
    except ValueError:
        return None
    tz = m.group(7)
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        dt -= sign * timedelta(hours=int(tz[1:3]), minutes=int(tz[4:6]))
    return dt.strftime("%Y-%m-%d")


def _hw_vram_mb(g: dict) -> Optional[int]:
    real = _hw_int(g.get("vramMB"))
    if real:
        return real
    wmi = _hw_int(g.get("adapterRAMMB"))
    return wmi if wmi and wmi < _HW_ADAPTER_RAM_CAP_MB else None


def _telemetry_hardware(raw: dict) -> Optional[dict]:
    """The hardware block, or None when none of its collectors answered (a
    build without PV-64 sends no block at all, which Vitals reads the same
    way). Disk space and drive health (PV-70, PV-74) come from Get-DiskHealth,
    which the dashboard pass already runs (1 h disk cache in the monitor)."""
    identity = raw.get("identity")
    hardware = raw.get("hardware")
    disk_health = raw.get("disk_health")
    ident_ok = isinstance(identity, dict) and not identity.get("error")
    hw_ok = isinstance(hardware, dict) and not hardware.get("error")
    dh_ok = isinstance(disk_health, dict) and not disk_health.get("error")
    if not ident_ok and not hw_ok and not dh_ok:
        return None
    ids = _hw_identifiers(identity if ident_ok else {}, hardware if hw_ok else {})
    if dh_ok:
        ids += [str(d.get("serialNumber")).strip().lower() for d in _rows(disk_health.get("physicalDisks"))
                if d.get("serialNumber") is not None and len(str(d.get("serialNumber")).strip()) >= 4]
    out = {"model": None, "cpu": None, "memoryGb": None, "disks": None, "gpus": None, "bios": None}

    if ident_ok:
        out["model"] = _hw_str((identity.get("computerSystem") or {}).get("model"), ids)
        bios = identity.get("bios") or {}
        bios_out = {"version": _hw_str(bios.get("smbiosVersion"), ids, _HW_MAX_VERSION),
                    "date": _hw_bios_date(bios.get("releaseDate"))}
        out["bios"] = bios_out if any(v is not None for v in bios_out.values()) else None

    if hw_ok:
        procs = [p for p in hardware.get("processors") or [] if isinstance(p, dict)]
        if procs:
            cores = [_hw_int(p.get("numberOfCores")) for p in procs]
            threads = [_hw_int(p.get("numberOfLogicalProcessors")) for p in procs]
            out["cpu"] = {"name": _hw_str(procs[0].get("name"), ids),
                          # Summed over sockets; null if any socket didn't say.
                          "cores": sum(cores) if all(cores) else None,
                          "threads": sum(threads) if all(threads) else None}
        # The DIMM sum, the same number the ram-insufficient finding reads.
        # None for no DIMM list: the OS-visible total runs short of it.
        ram = engine._total_ram_gb(hardware, None)
        out["memoryGb"] = int(round(ram)) if ram > 0 else None
        disks = sorted((d for d in hardware.get("diskDrives") or [] if isinstance(d, dict)),
                       key=lambda d: d.get("index") if isinstance(d.get("index"), int) else 1 << 30)
        health = _drive_health_lookup(disk_health if dh_ok else None)
        out["disks"] = [{"model": _hw_str(d.get("model"), ids), "sizeGb": _hw_int(d.get("sizeGB")),
                         "type": _hw_disk_type(d), **health(d)} for d in disks][:_HW_MAX_DISKS]
        gpus = [g for g in hardware.get("gpus") or []
                if isinstance(g, dict) and not _HW_GPU_SKIP.search(str(g.get("name") or ""))]
        out["gpus"] = [{"name": _hw_str(g.get("name"), ids), "driver": _hw_str(g.get("driverVersion"), ids, _HW_MAX_VERSION),
                        "vramMb": _hw_vram_mb(g)} for g in gpus][:_HW_MAX_GPUS]
    out["volumes"] = _telemetry_volumes(disk_health if dh_ok else None)
    pf = disk_health.get("predictFailure") if dh_ok else None
    out["predictFailure"] = pf if isinstance(pf, bool) else None
    return out


def _rows(v) -> list:
    """A collector's list of objects; PowerShell unrolls a one-item array."""
    if isinstance(v, dict):
        v = [v]
    return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []


# ── Disk space per volume (PV-70) ───────────────────────────────────────────
# Fixed local disks only (Get-DiskHealth reads DriveType 3), by letter. The
# letter and two sizes, never the volume label: a tech may have typed a school
# name into it. GiB with one decimal, the unit and precision of the collector's
# usedPercent, so Vitals' percent and the 90% finding agree.
_VOL_MAX = 8
_VOL_LETTER = re.compile(r"^[A-Z]$")


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _telemetry_volumes(disk_health) -> Optional[list]:
    """None when Get-DiskHealth failed or listed no volume: an empty list
    would read as "no disks", which no running VPU has."""
    if not isinstance(disk_health, dict):
        return None
    out = {}
    for d in _rows(disk_health.get("logicalDisks")):
        letter = str(d.get("deviceID") or "").strip().rstrip(":").upper()
        size, free = _num(d.get("sizeGB")), _num(d.get("freeSpaceGB"))
        if not _VOL_LETTER.match(letter) or letter in out or size is None or size <= 0 \
                or free is None or not 0 <= free <= size:
            continue
        out[letter] = {"letter": letter, "sizeGb": round(size, 1), "freeGb": round(free, 1)}
    rows = [out[k] for k in sorted(out)][:_VOL_MAX]
    return rows or None


# ── Drive health (PV-74) ─────────────────────────────────────────────────────
# Per physical drive, from Get-DiskHealth's physicalDisks, matched to
# Get-Hardware's drives by serial (which is used to match and never sent),
# then by model. Unknown is null per field, never 0 or "Healthy": SMART isn't
# readable on every drive (RAID, USB, some NVMe).
_DRIVE_FIELDS = ("health", "wearPercent", "powerOnHours", "uncorrectedErrors")


def _count(v) -> Optional[int]:
    """A non-negative whole number, or None. 0 is a real reading here."""
    n = _num(v)
    return int(round(n)) if n is not None and n >= 0 else None


def _drive_health(pd: Optional[dict]) -> dict:
    if not pd:
        return dict.fromkeys(_DRIVE_FIELDS)
    smart = pd.get("smart") if isinstance(pd.get("smart"), dict) else {}
    health = str(pd.get("healthStatus") or "").strip()
    reads, writes = _count(smart.get("readErrorsUncorrected")), _count(smart.get("writeErrorsUncorrected"))
    return {
        # Windows' HealthStatus: Healthy, Warning or Unhealthy. "Unknown" is null.
        "health":            health[:16] if health and health.lower() != "unknown" else None,
        "wearPercent":       _count(smart.get("wearPercent")),
        "powerOnHours":      _count(smart.get("powerOnHours")),
        # Read plus write, the same sum the disk-smart-prefail finding reads.
        "uncorrectedErrors": None if reads is None and writes is None else (reads or 0) + (writes or 0),
    }


def _drive_health_lookup(disk_health):
    """A function from a Get-Hardware drive to its health fields."""
    physical = _rows((disk_health or {}).get("physicalDisks")) if disk_health else []
    key = lambda v: " ".join(str(v or "").split()).upper()
    by_serial = {key(p.get("serialNumber")): p for p in physical if key(p.get("serialNumber"))}
    by_model = {}
    for p in physical:
        by_model.setdefault(key(p.get("friendlyName")), []).append(p)

    def lookup(d: dict) -> dict:
        pd = by_serial.get(key(d.get("serialNumber"))) if key(d.get("serialNumber")) else None
        if pd is None:
            same = by_model.get(key(d.get("model"))) or []
            pd = same[0] if len(same) == 1 else None   # two of one model: can't tell them apart
        return _drive_health(pd)
    return lookup


# ── Camera card (PV-65) and its PoE power (PV-66) ───────────────────────────
# The card is the adapters on the camera card's PCI bus (main.py's
# _adapter_role: the motherboard port is bus 0 and often the same Intel chip).
# The chip is a fact; the product name is a family, because nothing on the box
# tells a GIE74 from a GIE74P (#239) or a GIE64 from a GIE64+. An unknown chip
# is a null model, never a guess.
_NIC_CHIPS = (("82574l", "82574L"), ("i210", "I210"), ("i211", "I211"), ("i350", "I350"),
              ("i354", "I354"), ("82576", "82576"), ("82580", "82580"))
_NIC_FAMILY = {"82574L": "GIE64 series", "I210": "GIE74 series", "I211": "GIE74 series",
               "I350": "GIE74P-AN", "I354": "GIE74P-AN"}
# Only the I210/I211 cards report PoE; the GIE64 and GIE74P-AN can't.
_NIC_POE = {"I210": True, "I211": True, "82574L": False, "I350": False, "I354": False}
_NIC_MAX_PORTS = 8


def _nic_chip(desc) -> Optional[str]:
    d = str(desc or "").lower()
    return next((chip for needle, chip in _NIC_CHIPS if needle in d), None)


def _camera_card(network_config) -> Optional[dict]:
    """{model, chip, portCount, poeSupported}, or None when the adapters
    couldn't be read or no camera-card port was placed."""
    if not isinstance(network_config, dict) or network_config.get("error"):
        return None
    ports = [a for a in _rows(network_config.get("adapters")) if engine._adapter_role(a) == "camera"]
    if not ports:
        return None
    chips = [_nic_chip(a.get("interfaceDescription")) for a in ports]
    families = {}
    for c in chips:
        if c:
            families.setdefault(_NIC_FAMILY.get(c, c), []).append(c)
    if families:
        # The card is the family most of the camera ports belong to.
        family = max(families.values(), key=len)
        chip, count = family[0], len(family)
    else:
        chip, count = None, len(ports)
    return {"model": _NIC_FAMILY.get(chip), "chip": chip, "portCount": min(count, _NIC_MAX_PORTS),
            "poeSupported": _NIC_POE.get(chip)}


def _round(v, places: int) -> Optional[float]:
    n = _num(v)
    return round(n, places) if n is not None else None


def _telemetry_poe(poe) -> Optional[dict]:
    """What the card reported, or None when it didn't: not a PoE card, no
    SmartPoE driver, the crash sentinel latched, or the read failed. Total is
    what the card says its budget is; it drifts with consumed and remaining on
    real hardware, so it is the card's figure, not its rating."""
    if not isinstance(poe, dict) or poe.get("error") or not poe.get("supported") or not poe.get("available"):
        return None
    b = poe.get("budget") if isinstance(poe.get("budget"), dict) else None
    if b is None:
        return None
    temp = _num(b.get("tempC"))
    ports = []
    for p in _rows(poe.get("ports"))[:_NIC_MAX_PORTS]:
        n = _count(p.get("port"))
        if n is None:
            continue
        read = p.get("readOk") is not False
        ports.append({"port": n, "on": bool(p.get("poeOn")) if read else None,
                      "volts": _round(p.get("voltage"), 1) if read else None,
                      "amps": _round(p.get("current"), 3) if read else None,
                      "watts": _round(p.get("watts"), 1) if read else None})
    return {"budget": {"totalW": _round(b.get("totalW"), 1), "consumedW": _round(b.get("consumedW"), 1),
                       "remainingW": _round(b.get("remainingW"), 1),
                       # The collector writes 0 when the temperature read failed.
                       "tempC": round(temp) if temp and temp > 0 else None},
            # The Molex lead: the same flag the poe-underpowered finding reads.
            "underPowered": bool(b.get("underPowered")),
            "ports": ports}


def _telemetry_nic(raw: dict) -> Optional[dict]:
    card = _camera_card(raw.get("network_config"))
    if card is None:
        return None
    card["poe"] = _telemetry_poe(raw.get("poe")) if card["poeSupported"] else None
    return card


# ── Streaming components and installed applications (PV-71) ─────────────────
# `services` states each component outright, so Vitals stops reading "not in
# servicesDown" as Running. `servicesDown` keeps its v1 meaning beside it.
_SERVICE_ORDER = ("agent", "coordinator", "keepagentup", "vpu", "scoreconnect")
_SERVICE_STATE = {"running": "running", "stopped": "stopped", "notfound": "not-installed"}
_APPS_MAX = 150
_APP_NAME_MAX, _APP_VERSION_MAX, _APP_PUBLISHER_MAX = 80, 32, 40


def _service_key(name: str) -> str:
    k = re.sub(r"[^a-z0-9]", "", str(name).lower())
    return "scoreconnect" if k.startswith("scoreconnect") else k


def _telemetry_services(services: dict) -> Optional[list]:
    """None when Get-Services didn't answer. A component it didn't list is
    "unknown"; LogMeIn (remote support) is added when it is listed."""
    if not services:
        return None
    states = {}
    for name, st in services.items():
        key = _service_key(name)
        st = _SERVICE_STATE.get(str(st or "").lower(), "unknown")
        # A running instance wins (an SC I/II leftover can sit beside SC III).
        if states.get(key) != "running":
            states[key] = st
    out = [{"name": k, "state": states.get(k, "unknown")} for k in _SERVICE_ORDER]
    if "logmein" in states:
        out.append({"name": "logmein", "state": states["logmein"]})
    return out


def _telemetry_applications(raw: dict) -> Optional[list]:
    """Everything installed, Pixellot first, then by name. Names, versions
    and publishers only: no install paths, dates or keys. None when the read
    failed or listed nothing (no Windows box has nothing installed)."""
    sw = raw.get("installed_sw")
    if not isinstance(sw, dict) or sw.get("error"):
        return None
    ids = _hw_identifiers(raw.get("identity") or {}, {})
    seen, out = set(), []
    for a in _rows(sw.get("software")):
        name = _hw_str(a.get("displayName"), ids, _APP_NAME_MAX)
        if not name:
            continue
        row = {"name": name, "version": _hw_str(a.get("displayVersion"), ids, _APP_VERSION_MAX),
               "publisher": _hw_str(a.get("publisher"), ids, _APP_PUBLISHER_MAX)}
        k = (name.lower(), row["version"])
        if k not in seen:
            seen.add(k)
            out.append(row)
    pix = lambda r: "pixellot" in f"{r['name']} {r['publisher'] or ''}".lower()
    out.sort(key=lambda r: (not pix(r), r["name"].lower(), r["version"] or ""))
    # Uncapped here: _build_telemetry caps it, and counts what it left out.
    return out or None


# ── Can Pixellot's programs start (PV-76) ───────────────────────────────────
# Test-PixellotBinaries already runs on every dashboard pass. `canStart` is
# the rule _binary_findings blocks the stream on: a library missing now, or a
# loader-error pop-up within START_ERROR_LIVE_SECONDS (or a VPU.exe stuck on
# one). An older pop-up is the finding's warning or info, not "can't start".
_PROGRAM_MAX_MISSING = 5
_PROGRAM_DLL_MAX = 40


def _telemetry_programs(raw: dict) -> Optional[list]:
    b = raw.get("binaries")
    if not isinstance(b, dict) or b.get("error"):
        return None
    now = engine._ps_time(b.get("now"))
    stuck = any(p.get("stuckOnLoaderError") for p in _rows(b.get("vpuProcesses")))
    popups = [p for p in _rows(b.get("popups")) if p.get("count")]
    out = []
    for e in _rows(b.get("exes")):
        name = _tel_str(e.get("name"))
        if not name:
            continue
        mine = [p for p in popups if str(p.get("exe") or "").lower() == name.lower()]
        lasts = [t for t in (engine._ps_time(p.get("last")) for p in mine) if t]
        last = max(lasts) if lasts else None
        missing = []
        for m in _rows(e.get("missing")):
            dll = _tel_str(m.get("dll"))
            if dll and dll[:_PROGRAM_DLL_MAX] not in missing:
                missing.append(dll[:_PROGRAM_DLL_MAX])
        if not e.get("present") or e.get("readable") is False or not e.get("scanned"):
            can = None   # not there, or couldn't be scanned: unknown, never true
        elif missing:
            can = False
        else:
            live = last is not None and now is not None and (now - last).total_seconds() <= engine.START_ERROR_LIVE_SECONDS
            can = not (live or (stuck and name.lower() == "vpu.exe" and mine))
        out.append({"name": name, "canStart": can, "missing": missing[:_PROGRAM_MAX_MISSING],
                    "loaderErrors": {"count": sum(_count(p.get("count")) or 0 for p in mine),
                                     "last": _calibration_stamp(last.isoformat()) if last else None}
                                    if mine else None})
    return out or None


# ── Windows, time zone and clock (PV-75) ────────────────────────────────────
# The OS and time zone come from Get-SystemIdentity (every pass) and the patch
# level from Get-WindowsUbr (6 h cache); clock drift from Test-NtpDrift (1 h
# cache), the same read the Network page shows. `timeZone.us` is the function
# the tz-non-us blocker uses, so the tab and the verdict can't disagree. No
# hostname, user or domain.
_CLOCK_STATUS = {"ok", "warn", "fail"}


def _telemetry_environment(raw: dict) -> Optional[dict]:
    identity, ubr, ntp = raw.get("identity"), raw.get("ubr"), raw.get("ntp")
    ident_ok = isinstance(identity, dict) and not identity.get("error")
    ubr_ok = isinstance(ubr, dict) and not ubr.get("error")
    ids = _hw_identifiers(identity if ident_ok else {}, {})
    os_ = identity.get("operatingSystem") or {} if ident_ok else {}
    build = re.sub(r"\D", "", str(os_.get("buildNumber") or (ubr.get("currentBuild") if ubr_ok else "") or ""))[:8] or None
    patch = _count(ubr.get("ubr")) if ubr_ok and (not build or str(ubr.get("currentBuild") or build) == build) else None
    name = _hw_str(re.sub(r"^Microsoft\s+", "", str(os_.get("caption") or "")), ids)
    os_out = {"name": name, "build": build, "ubr": patch} if (name or build) else None
    tz_out = None
    if ident_ok:
        tz_id, tz_cap = str(identity.get("timezoneId") or ""), str(identity.get("timezone") or "")
        if tz_id or tz_cap:
            tz_out = {"caption": _tel_str(tz_cap or tz_id), "us": engine._is_us_timezone(tz_id, tz_cap)}
    clock = None
    if isinstance(ntp, dict) and not ntp.get("error"):
        st = str(ntp.get("status") or "").lower()
        synced = ntp.get("networkSynced")
        clock = {"offsetSeconds": _round(ntp.get("offsetSeconds"), 3),
                 "status": st if st in _CLOCK_STATUS else None,
                 "source": _hw_str(ntp.get("source"), ids),
                 "synced": synced if isinstance(synced, bool) else None}
    if os_out is None and tz_out is None and clock is None:
        return None
    return {"os": os_out, "timeZone": tz_out, "clock": clock}


# The check-in Worker drops a telemetry document over 16 KB whole
# (MAX_TELEMETRY_BYTES in tools/checkin-worker/src/ingest.js), and the unit
# then reads as reporting nothing. 15 KB leaves room for the Worker's own
# JSON.stringify, which is never larger than this compact, ASCII-escaped form.
_TELEMETRY_MAX_BYTES = 15 * 1024


def _telemetry_bytes(t: dict) -> int:
    return len(json.dumps(t, separators=(",", ":"), default=str).encode("utf-8"))


def _fit_telemetry(t: dict) -> dict:
    """Keep the document under the Worker's cap by cutting the two long lists
    from their ends: the installed applications (Pixellot's come first, so
    they stay), then the oldest restart rows. `applicationsTotal` still says
    how many there were. Anything else over the cap is left for the Worker
    to refuse, as before."""
    for path in (("applications",), ("power", "events")):
        if _telemetry_bytes(t) <= _TELEMETRY_MAX_BYTES:
            break
        parent = t if len(path) == 1 else t.get(path[0])
        rows = parent.get(path[-1]) if isinstance(parent, dict) else None
        if not isinstance(rows, list) or not rows:
            continue
        lo, hi = 0, len(rows)          # the most rows that fit
        while lo < hi:
            mid = (lo + hi + 1) // 2
            parent[path[-1]] = rows[:mid]
            if _telemetry_bytes(t) <= _TELEMETRY_MAX_BYTES:
                lo = mid
            else:
                hi = mid - 1
        # An application list cut to nothing would read as "none installed".
        parent[path[-1]] = rows[:lo] if lo or path[-1] == "events" else None
    return t


def _build_telemetry(dashboard: dict, raw: dict, status_since: Optional[str] = None,
                     status: Optional[str] = None, open_codes=None) -> dict:
    """The utilitarian payload. Fail-soft: a collector that errored leaves its
    part null rather than guessing. `status` is the monitor's settled verdict
    (a finding counts only after two passes see it) and `open_codes` the
    findings it settled on; headline and blockers follow them, so a PASS
    never carries an unconfirmed problem as its headline."""
    verdict = (dashboard or {}).get("readiness") or {}
    ident = (dashboard or {}).get("identity") or {}
    blockers, risks = verdict.get("blockers") or [], verdict.get("risks") or []
    if open_codes is not None:
        keep = set(open_codes)
        blockers = [b for b in blockers if b.get("code") in keep]
        risks = [r for r in risks if r.get("code") in keep]

    services = {}
    for s in ((dashboard or {}).get("services") or {}).get("services") or []:
        if s.get("name"):
            services[s["name"]] = s.get("status")

    net = (dashboard or {}).get("networkConfig") or {}
    port_tests = raw.get("port_tests")
    ports = _telemetry_ports(port_tests)
    cameras = _telemetry_cameras(raw)
    scoreboard = _telemetry_scoreboard(raw)
    adapters = _telemetry_adapters(raw.get("network_config"),
                                   (net.get("uplinkAdapter") or {}).get("interfaceAlias"))
    apps = _telemetry_applications(raw)
    inet = next((a for a in adapters or [] if a.get("internet")), None)
    if inet:
        inet = {k: inet.get(k) for k in ("adapter", "mac", "ip", "subnetMask", "gateway",
                                         "dns1", "dns2", "dhcp")}
    return _fit_telemetry({
        "schema":          _TELEMETRY_SCHEMA,
        "status":          status or verdict.get("status"),
        "statusSince":     status_since,
        "headline":        (blockers or risks or [{}])[0].get("title"),
        "blockers":        [b.get("title") for b in blockers][:10],
        "checkedAt":       verdict.get("timestamp"),
        "pixellotVersion": ident.get("pixellotVersion"),
        "network": {
            "internetReachable": net.get("internetReachable"),
            "streamingPath":     _telemetry_streaming_path(port_tests),
            "portsFailed":       None if ports is None else
                                 [f"{p['name']} ({p['rule']})" for p in ports if not p["ok"] and not p["optional"]],
            "internet":          inet,
        },
        "cameras": {
            "systemType": cameras.get("systemType"),
            "expected":   cameras.get("expected"),
            "detected":   cameras.get("detected"),
            "slow":       sum(1 for p in cameras.get("ports") or [] if p.get("slow")),
            "ports":      cameras.get("ports"),
            "nic":        _telemetry_nic(raw),
        },
        "servicesDown": _services_down(services, scoreboard) if services else None,
        "services":     _telemetry_services(services),
        "applications": apps[:_APPS_MAX] if apps else None,
        "applicationsTotal": len(apps) if apps else None,
        "programs":     _telemetry_programs(raw),
        "scoreboard":   scoreboard,
        "power":        _telemetry_power(raw),
        "calibration":  _telemetry_calibration(raw),
        "hardware":     _telemetry_hardware(raw),
        "environment":  _telemetry_environment(raw),
    })


def _fingerprint_view(t: dict) -> dict:
    """The payload as the post rules compare it. Readings that move on every
    read are coarsened, or a healthy unit would post in full every pass:
    clock drift to whole seconds, disk space to whole percent used, PoE to each
    port on or off, and a drive's power-on hours not at all. The post itself
    carries the exact values."""
    t = dict(t)
    env = t.get("environment")
    if isinstance(env, dict) and isinstance(env.get("clock"), dict):
        off = env["clock"].get("offsetSeconds")
        t["environment"] = {**env, "clock": {**env["clock"], "offsetSeconds": None if off is None else round(off)}}
    hw = t.get("hardware")
    if isinstance(hw, dict):
        hw = dict(hw)
        if isinstance(hw.get("volumes"), list):
            hw["volumes"] = [[v["letter"], round(100 * (v["sizeGb"] - v["freeGb"]) / v["sizeGb"])]
                             for v in hw["volumes"]]
        if isinstance(hw.get("disks"), list):
            hw["disks"] = [{k: v for k, v in d.items() if k != "powerOnHours"} for d in hw["disks"]]
        t["hardware"] = hw
    cams = t.get("cameras")
    nic = cams.get("nic") if isinstance(cams, dict) else None
    if isinstance(nic, dict) and isinstance(nic.get("poe"), dict):
        poe = nic["poe"]
        t["cameras"] = {**cams, "nic": {**nic, "poe": {
            "underPowered": poe.get("underPowered"),
            "ports": [[p.get("port"), p.get("on")] for p in poe.get("ports") or []]}}}
    return t


def _telemetry_fingerprint(telemetry: dict, open_codes) -> str:
    """What "the data changed" means for the post rules: everything in the
    payload except when it was measured, plus the open blocker/risk codes (a
    risk opening may not move any payload field). A change posts at once."""
    import hashlib
    t = {k: v for k, v in _fingerprint_view(telemetry or {}).items() if k not in ("checkedAt", "statusSince")}
    body = json.dumps({"t": t, "open": sorted(open_codes or [])}, sort_keys=True, default=str)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()
