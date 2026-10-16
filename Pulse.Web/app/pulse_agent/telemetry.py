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
# this carries what Pixellot can't see from outside the box. Troubleshooting
# detail (full findings copy, every adapter, clock drift, PoE, GPUs, disks,
# recordings) comes later. Kept small on purpose: Unity writes must be. D1
# stores it as the proof of concept. Leaves out hostname, BIOS serial and
# camera serials.
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
    power loss, the scoreboard source, and calibration. Fills `raw`; each part
    fails soft.
    `skip_intrusive` is accepted for symmetry; none of them probes the
    network."""
    del skip_intrusive
    reboots, sc, calib = await asyncio.gather(
        engine.run_ps("Get-RebootHistory.ps1", timeout=30),
        # Straight to the collector, not _run_sc_status: that also appends to
        # the ScoreConnect config history, which is the interactive tab's job.
        engine.run_ps("Get-ScoreConnectStatus.ps1", {"BaseUrl": engine.sc3_base_url()}, timeout=15),
        # Two folders and a few file times. Not Get-PixellotConfig: that also
        # probes every camera over CGI. The monitor serves it from its 6 h disk
        # cache (monitor_once.SLOW_COLLECTOR_TTLS), so most passes start no
        # PowerShell for it; no args, or the cache would not apply.
        engine.run_ps("Get-CalibrationStatus.ps1", timeout=15),
        return_exceptions=True,
    )
    raw.update(reboots=reboots if isinstance(reboots, dict) and not reboots.get("error") else None,
               scoreconnect=sc if isinstance(sc, dict) else None,
               calibration=calib if isinstance(calib, dict) and not calib.get("error") else None)


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


def _telemetry_power(raw: dict) -> dict:
    rb = raw.get("reboots") or {}
    hist = rb.get("history") or []
    unexpected = [h for h in hist if h.get("category") == "unexpected" or h.get("eventId") in (41, 6008)]
    return {"lastBoot": rb.get("lastBoot") or None,
            # Power cuts and hard crashes, from Get-RebootHistory's 7-day window.
            "unexpectedShutdowns7d": len(unexpected) if rb else None}


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
    inet = next((a for a in adapters or [] if a.get("internet")), None)
    if inet:
        inet = {k: inet.get(k) for k in ("adapter", "mac", "ip", "subnetMask", "gateway",
                                         "dns1", "dns2", "dhcp")}
    return {
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
        },
        "servicesDown": _services_down(services, scoreboard) if services else None,
        "scoreboard":   scoreboard,
        "power":        _telemetry_power(raw),
        "calibration":  _telemetry_calibration(raw),
    }


def _telemetry_fingerprint(telemetry: dict, open_codes) -> str:
    """What "the data changed" means for the post rules: everything in the
    payload except when it was measured, plus the open blocker/risk codes (a
    risk opening may not move any payload field). A change posts at once."""
    import hashlib
    t = {k: v for k, v in (telemetry or {}).items() if k not in ("checkedAt", "statusSince")}
    body = json.dumps({"t": t, "open": sorted(open_codes or [])}, sort_keys=True, default=str)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()
