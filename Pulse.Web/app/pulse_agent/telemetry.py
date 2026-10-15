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
    power loss, and the scoreboard source. Fills `raw`; each part fails soft.
    `skip_intrusive` is accepted for symmetry; neither collector probes the
    network."""
    del skip_intrusive
    reboots, sc = await asyncio.gather(
        engine.run_ps("Get-RebootHistory.ps1", timeout=30),
        # Straight to the collector, not _run_sc_status: that also appends to
        # the ScoreConnect config history, which is the interactive tab's job.
        engine.run_ps("Get-ScoreConnectStatus.ps1", {"BaseUrl": engine.sc3_base_url()}, timeout=15),
        return_exceptions=True,
    )
    raw.update(reboots=reboots if isinstance(reboots, dict) and not reboots.get("error") else None,
               scoreconnect=sc if isinstance(sc, dict) else None)


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
    return out


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
    }


def _telemetry_fingerprint(telemetry: dict, open_codes) -> str:
    """What "the data changed" means for the post rules: everything in the
    payload except when it was measured, plus the open blocker/risk codes (a
    risk opening may not move any payload field). A change posts at once."""
    import hashlib
    t = {k: v for k, v in (telemetry or {}).items() if k not in ("checkedAt", "statusSince")}
    body = json.dumps({"t": t, "open": sorted(open_codes or [])}, sort_keys=True, default=str)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()
