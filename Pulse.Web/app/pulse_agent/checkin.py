"""The fleet agent's check-in: the on-disk queue, the beacon, the fallback
sheet and the entry itself. Moved out of main.py (PV-49) so it versions with
the agent (pulse_agent/VERSION), not with Pulse Diagnostics. Diagnostics still
sends its launch check-in through it.

The collectors and verdicts it reports still live in main.py: see engine.py.
"""

import asyncio
import json
import os as _os
import urllib.error
import urllib.request
from typing import Optional

from pulse_agent import WEB_ROOT
from pulse_agent.engine import engine


# Fire-and-forget "Pulse ran on this VPU" beacon for fleet tracking. The sink is
# the pulse-checkin Cloudflare Worker (tools/checkin-worker/), which appends one
# row per check-in to D1. There is no write key: Pulse ships from a public repo,
# so a key in it was readable by anyone (Snyk flagged it on PR #229). The
# Worker's rate limit and validation are the protection; real per-unit auth
# comes with the Unity/DevOps transport. The env var PULSE_CHECKIN_URL
# overrides the URL.
#
# Every check-in is queued on disk first and leaves the queue only when the
# Worker acknowledges it. The previous sink (an Apps Script sheet) lost four days
# of check-ins because nothing checked the reply; now a dead sink only delays
# them, and they replay with their original sentAt on a later launch. The queue
# lives in the web root beside pulse-settings.json, which the launcher's xcopy
# update never removes.
#
# If the Worker can't be reached (a school filter that blocks workers.dev, a
# Cloudflare outage), the new launch check-in also goes to the old Apps Script
# sheet, which school filters are less likely to block. It stays queued for the
# Worker either way, so D1 still ends up complete; the sheet is only a safety
# net for seeing the unit at all. Only that one check-in goes, never the
# backlog, so an outage can't flood the sheet. The sheet keys a unit on serial,
# then venue id; check-ins no longer carry the serial, so a unit gets a new
# sheet row keyed on its venue id at the switch. PULSE_CHECKIN_FALLBACK_URL /
# PULSE_CHECKIN_FALLBACK_SECRET override; an empty URL turns the fallback off.
#
# Check-ins carry no hostname or BIOS serial (Ian, 2026-10-13): a unit is its
# Pixellot venue id and VPU name.
#
# Never sends in demo/dev (DEMO_MODE), so a developer's machine can't pollute the
# list. Fail-open in every branch: a blocked network or unreachable sink must
# never slow or break launch. Stdlib urllib on purpose (no httpx): the beacon has
# to work on any installed build, even one missing an optional pip dependency.
# The address lives in checkin_lite.py, the one place to change it (the
# monitor's event-time sender can't import this file: it needs main.py).
from pulse_agent.checkin_lite import CHECKIN_URL as _CHECKIN_URL
_CHECKIN_FALLBACK_URL    = "https://script.google.com/macros/s/AKfycbworYEcINtNfd1R6sTvHFDFqOHzYVA1XxHZRStB54T2GcTgQ8JvE0lxnboJ9q_jEFS4/exec"
_CHECKIN_FALLBACK_SECRET = "7a161bad7765fc5078b8375007999160c5687bf5da52ae1ca717ebbad628e648"
_CHECKIN_STATE_PATH = _os.path.join(WEB_ROOT, "pulse-checkin-queue.json")
_CHECKIN_BATCH = 50
# The Worker refuses a body over 64 KB with a 413 for the whole batch, so a
# batch is cut by size as well as count. Launch check-ins (~0.5 KB) fit 50 at a
# time; the fleet monitor's full reports (~2 KB) don't, and without this cut the
# same oversized batch went back on every flush and the queue never drained.
_CHECKIN_MAX_BODY_BYTES = 64 * 1024
_CHECKIN_MAX_QUEUED = 200
_CHECKIN_MAX_AGE_DAYS = 30
# A failure younger than this is a blip; older is worth a notice on the About page.
_CHECKIN_NOTICE_AFTER_HOURS = 24
_CHECKIN_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_checkin_lock = asyncio.Lock()


def _checkin_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime(_CHECKIN_TS_FORMAT)


def _checkin_age_hours(ts, now: str) -> Optional[float]:
    from datetime import datetime
    try:
        return (datetime.strptime(now, _CHECKIN_TS_FORMAT)
                - datetime.strptime(ts, _CHECKIN_TS_FORMAT)).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def _load_checkin_state() -> dict:
    try:
        with open(_CHECKIN_STATE_PATH, "r", encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return {"queue": []}
    if not isinstance(state, dict):
        return {"queue": []}
    if not isinstance(state.get("queue"), list):
        state["queue"] = []
    state["queue"] = [e for e in state["queue"] if isinstance(e, dict) and e.get("checkinId")]
    return state


def _save_checkin_state(state: dict) -> None:
    tmp = _CHECKIN_STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    _os.replace(tmp, _CHECKIN_STATE_PATH)


def _trim_checkin_queue(queue: list, now: str) -> list:
    keep = []
    for entry in queue:
        age = _checkin_age_hours(entry.get("sentAt"), now)
        if age is None or age <= _CHECKIN_MAX_AGE_DAYS * 24:
            keep.append(entry)
    return keep[-_CHECKIN_MAX_QUEUED:]


def _checkin_body_bytes(batch: list) -> int:
    # Exactly the bytes _post_checkin_sync sends.
    return len(json.dumps({"checkins": batch}).encode("utf-8"))


def _next_checkin_batch(queue: list) -> list:
    """The oldest check-ins that fit one request: at most _CHECKIN_BATCH, and
    under the Worker's body cap. Always at least one, so the caller can see
    an entry too big to send at all."""
    batch = []
    for entry in queue[:_CHECKIN_BATCH]:
        if batch and _checkin_body_bytes(batch + [entry]) > _CHECKIN_MAX_BODY_BYTES:
            break
        batch.append(entry)
    return batch


def _post_checkin_sync(url: str, body: dict) -> dict:
    """POST one batch; return the Worker's JSON reply or raise."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": f"Pulse/{engine.APP_VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = resp.read(256 * 1024)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read(4096) or b"{}").get("error") or ""
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}" + (f": {detail}" if detail else ""))
    try:
        reply = json.loads(raw)
    except ValueError:
        raise RuntimeError("reply was not JSON")
    if not isinstance(reply, dict) or reply.get("ok") is not True or not isinstance(reply.get("results"), list):
        raise RuntimeError("sink did not acknowledge" + (f": {reply['error']}" if isinstance(reply, dict) and reply.get("error") else ""))
    return reply


async def _flush_checkin_queue(state: dict, url: str) -> None:
    """Send queued check-ins oldest first; drop only what the Worker answered for."""
    while state["queue"]:
        batch = _next_checkin_batch(state["queue"])
        if _checkin_body_bytes(batch) > _CHECKIN_MAX_BODY_BYTES:
            # One check-in the Worker can never accept. Drop it, like an
            # "invalid" reply, rather than let it block everything behind it.
            engine._server_log.warning("Check-in %s dropped: %d bytes is over the sink's limit",
                                batch[0].get("checkinId"), _checkin_body_bytes(batch))
            state["queue"] = state["queue"][1:]
            continue
        state["lastAttemptAt"] = _checkin_now()
        try:
            reply = await asyncio.to_thread(_post_checkin_sync, url, {"checkins": batch})
        except Exception as e:
            state["lastError"] = str(e) or e.__class__.__name__
            return
        answered = set()
        for r in reply["results"]:
            if isinstance(r, dict) and r.get("status") in ("inserted", "duplicate", "invalid"):
                answered.add(r.get("checkinId"))
                if r.get("status") == "invalid":
                    engine._server_log.warning("Check-in %s rejected as invalid by the sink", r.get("checkinId"))
        if not answered.intersection(e["checkinId"] for e in batch):
            state["lastError"] = "sink answered for none of the batch"
            return
        state["queue"] = [e for e in state["queue"] if e["checkinId"] not in answered]
        state["lastSentAt"] = state["lastAttemptAt"]
        state.pop("lastError", None)
        # Fleet control for the scheduled monitor (monitor.read_control):
        # whether it runs and which collectors it skips. Kept until the Worker
        # says otherwise, so an unreachable Worker never turns it back on.
        if isinstance(reply.get("control"), dict):
            state["control"] = dict(reply["control"], receivedAt=state["lastAttemptAt"])


# The last venue id / VPU name this unit reported, set by the scheduled monitor
# (monitor_once.py) from its post record. The identity collector can come back
# "ok" without its Pixellot part while Pixellot rewrites its config (lab-z2,
# 2026-10-14 05:10Z), and with no hostname or serial a check-in without those
# two can't be tied to any unit. Empty for an interactive launch.
_CHECKIN_IDENTITY_FALLBACK: dict = {}

# The running agent's version (pulse_agent.AGENT_VERSION), set by the scheduled
# monitor so every post it makes says which agent build made it. Empty for an
# interactive launch: Diagnostics carries a copy of the agent, but that copy
# isn't the one running on the unit.
_AGENT_VERSION = ""


def _agent_stamp(entry: dict) -> dict:
    if _AGENT_VERSION:
        entry["agentVersion"] = _AGENT_VERSION
    return entry


async def _build_checkin_entry(dashboard: Optional[dict] = None, reason: str = "startup",
                               delta: Optional[dict] = None,
                               monitor: Optional[dict] = None,
                               telemetry: Optional[dict] = None,
                               heartbeat: bool = False, paused: bool = False) -> Optional[dict]:
    """One check-in. `reason` is startup (an interactive launch) or, from the
    scheduled monitor, periodic / state-change, which also carry the finding
    transitions (`delta`) and the pass's own cost (`monitor`). `dashboard`
    lets the monitor reuse the pass it already ran. `heartbeat` is the
    monitor's hourly "still PASS, nothing changed" line: identity and status
    only, built from that pass with no further collection.

    No hostname or BIOS serial (Ian, 2026-10-13): units are identified by
    their Pixellot venue id and VPU name."""
    import uuid
    if paused:
        # Fleet control has the monitor switched off: identity only, hourly,
        # so the unit still shows as reachable and hears when it's back on.
        known = _CHECKIN_IDENTITY_FALLBACK
        return _agent_stamp({"checkinId": str(uuid.uuid4()), "sentAt": _checkin_now(), "reason": "paused",
                             "venueId": known.get("venueId"), "vpuName": known.get("vpuName"),
                             "pulseVersion": engine.APP_VERSION})
    if heartbeat:
        ident = (dashboard or {}).get("identity") or {}
        return _agent_stamp({"checkinId": str(uuid.uuid4()), "sentAt": _checkin_now(), "reason": "heartbeat",
                             "venueId": ident.get("venueId") or _CHECKIN_IDENTITY_FALLBACK.get("venueId"),
                             "vpuName": ident.get("vpuName") or _CHECKIN_IDENTITY_FALLBACK.get("vpuName"),
                             "status": "PASS"})
    ident = await engine.run_ps("Get-SystemIdentity.ps1")
    if not isinstance(ident, dict) or ident.get("error"):
        return None
    cs   = ident.get("computerSystem") or {}
    px   = ident.get("pixellot") or {}
    os_  = ident.get("operatingSystem") or {}
    entry = {
        "checkinId":    str(uuid.uuid4()),
        "sentAt":       _checkin_now(),
        "venueId":      px.get("venueId") or _CHECKIN_IDENTITY_FALLBACK.get("venueId"),
        "vpuName":      px.get("vpuName") or _CHECKIN_IDENTITY_FALLBACK.get("vpuName"),
        "model":        cs.get("model"),
        "pulseVersion": engine.APP_VERSION,
        "reason":       reason,
    }
    if telemetry:
        # A monitor check-in is the utilitarian payload: the verdict lives in
        # `telemetry`, and channel / OS build wait for the troubleshooting tier.
        if delta is not None:
            entry["delta"] = _checkin_delta(delta)
        if monitor:
            entry["monitor"] = monitor
        entry["telemetry"] = telemetry
        return _agent_stamp(entry)
    entry["channel"] = engine._update_channel()
    entry["osBuild"] = os_.get("buildNumber")
    # UBR tells an unpatched 17763.253 unit from a patched one; the build
    # number alone can't. Fail-open: the check-in goes out without it.
    try:
        ubr = await engine.run_ps("Get-WindowsUbr.ps1", timeout=10)
        if isinstance(ubr, dict) and not ubr.get("error"):
            entry["ubr"] = ubr.get("ubr")
            entry["osBuild"] = entry["osBuild"] or ubr.get("currentBuild")
    except Exception as e:
        engine._server_log.info("Check-in UBR skipped (%s)", e)
    # Stream Readiness verdict on the beacon: a pre-game-readiness time series at
    # ~zero marginal cost. A readiness error never blocks the check-in.
    try:
        dash = dashboard if dashboard is not None else await engine._collect_dashboard()
        verdict = (dash or {}).get("readiness") or {}
        if verdict:
            entry["readiness"] = {
                "status":        verdict.get("status"),
                "policyVersion": verdict.get("policyVersion"),
                "blockers":      [b.get("code") for b in verdict.get("blockers", [])],
                "risks":         [r.get("code") for r in verdict.get("risks", [])],
            }
    except Exception as e:
        engine._server_log.info("Check-in readiness skipped (%s)", e)
    if delta is not None:
        entry["delta"] = _checkin_delta(delta)
    if monitor:
        entry["monitor"] = monitor
    return _agent_stamp(entry)


def _checkin_delta(delta: dict) -> dict:
    """The monitor's transitions, trimmed for the wire: codes and classes, not
    the full finding copy (the sink caps a batch at 64 KB)."""
    def slim(events):
        return [{"code": e.get("code"), "class": e.get("class"), "title": e.get("title"),
                 "since": e.get("since")} for e in (events or [])][:25]
    return {
        "status":     delta.get("status"),
        "prevStatus": delta.get("prevStatus"),
        "opened":     slim(delta.get("opened")),
        "resolved":   slim(delta.get("resolved")),
        "persisting": list(delta.get("persisting") or [])[:50],
    }




def _post_fallback_sync(url: str, body: dict) -> None:
    """POST one check-in to the Apps Script sheet; raise unless it says ok.

    Apps Script answers a POST with a 302 to a result URL; urllib follows it as
    a GET and reads the JSON ack. The reply is checked because the script
    returns 200 with {"ok": false} on failure (the sheet's old trap: Pulse
    logged "sent" without reading it)."""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={
        "Content-Type": "application/json",
        "User-Agent": f"Pulse/{engine.APP_VERSION}",
    })
    # 15s: the script serializes writes behind a lock and the round trip is
    # POST -> 302 -> GET.
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read(64 * 1024)
    try:
        reply = json.loads(raw)
    except ValueError:
        raise RuntimeError("fallback reply was not JSON")
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        raise RuntimeError("fallback did not acknowledge"
                           + (f": {reply.get('error')}" if isinstance(reply, dict) and reply.get("error") else ""))


async def _send_fallback(entry: dict, state: dict) -> None:
    """The new check-in to the sheet, after the Worker failed. Records the
    outcome in `state` (shown on the About page); never raises."""
    url = (_os.environ.get("PULSE_CHECKIN_FALLBACK_URL", _CHECKIN_FALLBACK_URL) or "").strip()
    secret = (_os.environ.get("PULSE_CHECKIN_FALLBACK_SECRET") or _CHECKIN_FALLBACK_SECRET).strip()
    if not url.startswith("https://") or not secret:
        return
    # The sheet takes one flat check-in with the secret inside it.
    body = dict(entry, secret=secret)
    try:
        await asyncio.to_thread(_post_fallback_sync, url, body)
        state["lastFallbackAt"] = _checkin_now()
        state.pop("lastFallbackError", None)
        engine._server_log.info("Check-in sent to the fallback sheet (the Worker failed: %s)", state.get("lastError"))
    except Exception as e:
        state["lastFallbackError"] = str(e) or e.__class__.__name__
        engine._server_log.info("Fallback check-in failed too (%s)", state["lastFallbackError"])


def _checkin_configured(url: str) -> bool:
    return bool(url and url.startswith("https://") and "PASTE_" not in url)


async def _send_checkin(dashboard: Optional[dict] = None, delta: Optional[dict] = None,
                        reason: str = "startup", monitor: Optional[dict] = None,
                        telemetry: Optional[dict] = None, heartbeat: bool = False,
                        paused: bool = False) -> None:
    if engine.DEMO_MODE:
        return  # a dev/demo machine never reports
    url = (_os.environ.get("PULSE_CHECKIN_URL") or _CHECKIN_URL).strip()
    try:
        async with _checkin_lock:
            entry = await _build_checkin_entry(dashboard, reason, delta, monitor, telemetry,
                                               heartbeat, paused)
            state = _load_checkin_state()
            if entry:
                state["queue"].append(entry)
            state["queue"] = _trim_checkin_queue(state["queue"], _checkin_now())
            # Persist before sending, so a crash mid-POST still leaves it queued.
            _save_checkin_state(state)
            if not _checkin_configured(url):
                return
            await _flush_checkin_queue(state, url)
            # Launches only: the monitor posts every few minutes, and the sheet
            # keeps one row per unit with a run count, so monitor posts there
            # would flood it and inflate the count.
            if state.get("lastError") and entry and entry.get("reason") == "startup" and any(
                    e.get("checkinId") == entry["checkinId"] for e in state["queue"]):
                await _send_fallback(entry, state)
            _save_checkin_state(state)
        if state.get("lastError"):
            engine._server_log.info("Check-in queued (%d waiting): %s", len(state["queue"]), state["lastError"])
        else:
            engine._server_log.info("Check-in sent for %s", (entry or {}).get("vpuName") or "unknown VPU")
    except Exception as e:
        try:
            engine._server_log.info("Check-in skipped (%s)", e)
        except Exception:
            pass


def _checkin_status() -> dict:
    """What the About page shows. Read-only: never sends, never runs PowerShell."""
    url = (_os.environ.get("PULSE_CHECKIN_URL") or _CHECKIN_URL).strip()
    state = _load_checkin_state()
    queue = state["queue"]
    oldest = min((e.get("sentAt") for e in queue if e.get("sentAt")), default=None)
    age = _checkin_age_hours(oldest, _checkin_now()) if oldest else None
    # A build with no sink never tried to reach one, so it must not claim it failed to.
    unconfigured = not engine.DEMO_MODE and not _checkin_configured(url)
    if unconfigured:
        status = "not-configured"
    elif queue:
        status = "queued"
    elif state.get("lastSentAt"):
        status = "sent"
    elif engine.DEMO_MODE:
        status = "demo"
    else:
        status = "never"
    return {
        "status":        status,
        "queued":        len(queue),
        "oldestQueued":  oldest,
        "lastSentAt":    state.get("lastSentAt"),
        "lastAttemptAt": state.get("lastAttemptAt"),
        "lastError":     state.get("lastError"),
        "notice":        (not unconfigured and bool(queue) and age is not None
                          and age >= _CHECKIN_NOTICE_AFTER_HOURS),
    }
