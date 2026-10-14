"""Proactive monitoring — scheduled readiness pass + finding-state diff.

The engine behind the fleet-monitor pilot. It turns the on-demand readiness
verdict into a background watch:

  * **State diff.** Persist the set of *open* finding codes across runs and diff
    each new verdict against it, so we emit an event only when a finding
    *opens* or *resolves* — never on every pass while it persists.
  * **Severity gate.** Route each transition by its readiness class: blocker →
    alert now, risk → low-urgency/digest, info → log only (info findings are
    chronic and fleet-wide; alerting on them destroys signal).
  * **Scheduled tick (`plan_tick` + `run_once`).** Task Scheduler starts
    `monitor_once.py` every 5 minutes; one tasklist call says whether an event
    is live, and only a due tick runs a readiness pass. Nothing runs during a
    live event, so the collector burst never competes with a game encode.
  * **Post rules (`plan_post`).** A pass posts only when something changed, or
    when an unchanged FAIL/WARN is due again; an unchanged PASS is an hourly
    one-line heartbeat.

Everything that makes a *decision* (`codes_from_verdict`, `compute_delta`,
`route_for`, `should_alert_now`) is a pure function with no I/O, so it is unit-
testable in demo mode on any platform. `main.py` injects its collectors and the
beacon via `MonitorDeps`, so this module never imports `main` (no import cycle)
and carries no FastAPI/PowerShell dependency of its own.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

_log = logging.getLogger("pulse.monitor")

# ── State schema version ─────────────────────────────────────────────────────
# Bumped only if the on-disk shape changes incompatibly; load tolerates a
# mismatch by starting from an empty open-set (first run after an upgrade just
# re-opens whatever is currently failing — no false "resolved" storm).
STATE_VERSION = 1

# Readiness class → alert routing. Mirrors the policy in main.py's
# `_READINESS_POLICY` (blocker/risk/info) but expressed as a *transport* routing
# decision so the relay (PULSEDEV-54) and the beacon (PULSEDEV-53) agree.
_ROUTE = {
    "blocker": "alert",    # page us now — won't stream tonight
    "risk":    "digest",   # low-urgency — a human should eyeball before game time
    "info":    "log",      # chronic/context — never alert
}

# ── Cadence (seconds), env-overridable so the pilot can be tuned per box ──────
def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.environ.get(name, "")).strip())
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


# Checking and posting are separate (Ian, 2026-10-13). The task ticks every 5
# minutes; these set how often a tick runs a readiness pass...
FULL_SECONDS     = _env_int("PULSE_MONITOR_FULL_SECONDS", 1200)     # healthy: every 20 min
INCIDENT_SECONDS = _env_int("PULSE_MONITOR_INCIDENT_SECONDS", 900)  # a blocker or risk open: every 15 min
CONFIRM_SECONDS  = _env_int("PULSE_MONITOR_CONFIRM_SECONDS", 300)   # a finding awaiting its 2nd sighting
# ...and these how often an UNCHANGED verdict is posted again. Any change posts
# at once. A PASS repeat is the one-line heartbeat, not the full payload.
FAIL_REPOST_SECONDS = _env_int("PULSE_MONITOR_FAIL_REPOST_SECONDS", 900)    # 15 min
WARN_REPOST_SECONDS = _env_int("PULSE_MONITOR_WARN_REPOST_SECONDS", 1800)   # 30 min
HEARTBEAT_SECONDS   = _env_int("PULSE_MONITOR_HEARTBEAT_SECONDS", 3600)     # hourly
# Task Scheduler starts ticks a few seconds either side of the 5-minute mark,
# so an interval that is a whole number of ticks needs slack or it slips a
# full tick (measured on vpu-home: 5 min became 10).
TICK_SLACK_SECONDS = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Pure decision functions (no I/O — unit-tested directly) ───────────────────

def codes_from_verdict(verdict: Optional[dict]) -> dict:
    """Flatten a readiness verdict into ``{code: {class,title,category,recommendation}}``.

    The verdict already classifies every code by which bucket it lands in
    (blockers/risks/info), so the readiness *class* is implied by position — no
    second lookup against the policy table needed. This is also why we diff on
    the verdict rather than the raw findings list: the verdict includes the
    readiness-only computed codes (disk-c-critical, cpu-sustained, …) that the
    dashboard findings don't carry.
    """
    out: dict = {}
    for cls, key in (("blocker", "blockers"), ("risk", "risks"), ("info", "info")):
        for f in (verdict or {}).get(key) or []:
            code = (f or {}).get("code")
            if not code:
                continue
            out[code] = {
                "class": cls,
                "title": f.get("title", ""),
                "category": f.get("category", ""),
                "recommendation": f.get("recommendation", ""),
            }
    return out


def route_for(cls: str) -> str:
    """Alert routing for a readiness class (alert / digest / log)."""
    return _ROUTE.get(cls or "", "log")


def status_from_open(open_map: dict) -> str:
    """Roll the open finding set into one verdict — same rule as the readiness
    engine (any blocker → FAIL, any risk → WARN, else PASS).

    Derived from the open set rather than the raw verdict on purpose: while
    recording we skip the port probe and carry its blocker forward, so the raw
    verdict would read WARN while a blocker is still open. Keying status on the
    open set keeps it honest and stops a FAIL↔WARN flap at recording boundaries.
    """
    classes = {info.get("class") for info in open_map.values()}
    if "blocker" in classes:
        return "FAIL"
    if "risk" in classes:
        return "WARN"
    return "PASS"


def _fingerprint(serial: Optional[str], code: str) -> str:
    """Cross-fleet identity for one open finding: ``serial:code``.

    Locally we key state by ``code`` alone (state is per-box), but every emitted
    event carries the fingerprint so the Sheet/relay can dedup across the fleet.
    """
    return f"{serial}:{code}" if serial else code


def compute_delta(prev_open: dict, current: dict, prev_status: Optional[str],
                  serial: Optional[str], out_of_scope: frozenset = frozenset(),
                  now: Optional[str] = None):
    """Diff the prior open-set against the current verdict.

    Returns ``(new_open, delta)`` where:

      * ``new_open`` is the open-set to persist — current findings plus any
        ``out_of_scope`` codes carried forward unevaluated.
      * ``delta`` is the structured transition record the beacon sends:
        ``opened`` / ``resolved`` lists (each entry tagged with its class +
        fingerprint + routing), ``persisting`` codes, the status flip
        (``status`` derived from the resulting open set), and an ``alert`` flag
        set when any *blocker* opened or resolved.

    ``out_of_scope`` codes (e.g. the port probe was skipped while recording) are
    never resolved — a check we didn't run can't have "cleared". They carry
    forward from ``prev_open`` so the next full run reconciles them.
    """
    now = now or _now_iso()
    opened, resolved, persisting = [], [], []
    new_open: dict = {}

    for code, info in current.items():
        if code in prev_open:
            persisting.append(code)
            # Preserve the original open time so "open for N hours" stays true.
            since = prev_open[code].get("since") or now
            new_open[code] = {**info, "since": since}
        else:
            new_open[code] = {**info, "since": now}
            opened.append(_event(code, info, serial, since=now))

    for code, info in prev_open.items():
        if code in current:
            continue
        if code in out_of_scope:
            # Not evaluated this run — carry forward, do NOT resolve.
            new_open[code] = info
            continue
        resolved.append(_event(code, info, serial, since=info.get("since")))

    alert = any(e["class"] == "blocker" for e in opened) or \
            any(e["class"] == "blocker" for e in resolved)

    status = status_from_open(new_open)
    delta = {
        "opened": opened,
        "resolved": resolved,
        "persisting": sorted(persisting),
        "status": status,
        "prevStatus": prev_status,
        "statusChanged": status != prev_status,
        "alert": alert,
    }
    return new_open, delta


def debounce(prev_open: dict, current: dict, pending: dict,
             out_of_scope: frozenset = frozenset(), now: Optional[str] = None):
    """Two-pass confirmation, run before `compute_delta`.

    A finding opens only when two passes in a row see it, and resolves only
    when two in a row don't. A camera link renegotiating its speed, or one
    lost probe packet, otherwise opens and resolves a finding every pass
    (nic-slow on vpu-home, 2026-10-13: open/resolved every 5 minutes).

    `pending` is ``{"open": {code: info+firstSeen}, "resolve": {code: firstMissing}}``
    from the state file. Returns ``(effective_current, new_pending)``: feed
    `effective_current` to compute_delta in place of the raw verdict codes.
    A pending entry makes `plan_tick` re-check on the next tick, so the
    confirmation costs one tick, not one full interval.
    """
    now = now or _now_iso()
    pend_open = dict((pending or {}).get("open") or {})
    pend_resolve = dict((pending or {}).get("resolve") or {})
    effective, new_open_p, new_resolve_p = {}, {}, {}

    for code, info in current.items():
        if code in prev_open or code in pend_open:
            effective[code] = info               # persisting, or its second sighting
        else:
            new_open_p[code] = {**info, "firstSeen": now}

    for code, info in prev_open.items():
        if code in current:
            continue
        if code in out_of_scope:
            continue                             # compute_delta carries it forward
        if code in pend_resolve:
            continue                             # second miss: let it resolve
        effective[code] = {k: v for k, v in info.items() if k != "since"}
        new_resolve_p[code] = pend_resolve.get(code) or now
    return effective, {"open": new_open_p, "resolve": new_resolve_p}


def _event(code: str, info: dict, serial: Optional[str], since: Optional[str]) -> dict:
    cls = info.get("class", "info")
    return {
        "code": code,
        "fingerprint": _fingerprint(serial, code),
        "class": cls,
        "route": route_for(cls),
        "title": info.get("title", ""),
        "category": info.get("category", ""),
        "recommendation": info.get("recommendation", ""),
        "since": since,
    }


def should_alert_now(delta: dict) -> bool:
    """Whether a delta warrants an *immediate*, off-cadence beacon.

    Fires for any blocker/risk transition or an overall status flip. Info-only
    changes ride the next periodic beacon instead — they're reported, but they
    never trigger an off-cycle alert (severity gate: info → log only).
    """
    transitions = (delta.get("opened") or []) + (delta.get("resolved") or [])
    if any(e.get("class") in ("blocker", "risk") for e in transitions):
        return True
    return bool(delta.get("statusChanged"))


def summarize_delta(delta: dict) -> str:
    """One-line human summary for the server log."""
    o, r = delta.get("opened") or [], delta.get("resolved") or []
    parts = [f"status={delta.get('status')}"]
    if o:
        parts.append("opened=" + ",".join(e["code"] for e in o))
    if r:
        parts.append("resolved=" + ",".join(e["code"] for e in r))
    if not o and not r:
        parts.append(f"steady ({len(delta.get('persisting') or [])} open)")
    return " ".join(parts)


# ── File-backed state (survives restart, resets on reinstall) ─────────────────
# Lives alongside pulse-settings.json in the install tree, so a reinstall (which
# re-downloads C:\Pulse) clears it — a fresh box re-opens whatever is currently
# failing rather than inheriting a stale ledger.

def load_state(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
            return _empty_state()
        data.setdefault("open", {})
        data.setdefault("status", None)
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _empty_state()


def save_state(path: str, open_map: dict, status: Optional[str],
               serial: Optional[str], last_full_at: Optional[float] = None,
               status_since: Optional[str] = None,
               pending: Optional[dict] = None) -> None:
    payload = {
        "version": STATE_VERSION,
        "serial": serial,
        "status": status,
        "open": open_map,
        "updatedAt": _now_iso(),
    }
    if last_full_at is not None:
        payload["lastFullAt"] = last_full_at
    if status_since is not None:
        payload["statusSince"] = status_since
    if pending and (pending.get("open") or pending.get("resolve")):
        payload["pending"] = pending
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp, path)  # atomic — a torn write can't corrupt the ledger
    except OSError as e:
        _log.warning("Monitor state save failed (%s) — continuing in memory", e)


def _empty_state() -> dict:
    return {"version": STATE_VERSION, "serial": None, "status": None, "open": {}}


# ── Dependency injection for the async loop ───────────────────────────────────
# main.py supplies the collectors + beacon; this keeps monitor.py free of any
# import of main (no cycle) and trivially mockable in tests.

class MonitorDeps:
    def __init__(
        self,
        collect_dashboard: Callable[[bool], Awaitable[dict]],   # (skip_intrusive) -> dashboard
        send_checkin: Callable[..., Awaitable[None]],           # (dashboard, delta, reason)
        get_serial: Callable[[dict], Optional[str]],            # dashboard -> serial
        clear_cache: Callable[[], object],
    ):
        self.collect_dashboard = collect_dashboard
        self.send_checkin = send_checkin
        self.get_serial = get_serial
        self.clear_cache = clear_cache


async def run_full_recompute(deps: MonitorDeps, state_path: str,
                             recording: bool, wall_now: Optional[float] = None) -> dict:
    """One authoritative pass: collect → diff → persist → beacon.

    When ``recording`` we skip the intrusive port probe, so the pass is partial:
    it may open findings but resolves none (every previously open code carries
    forward). A check that did not run cannot have cleared, and the port probe
    feeds several findings, so a hand-kept list of its codes would drift.
    Returns the delta (for logging/tests)."""
    if not recording:
        # Force genuinely fresh data; the 25 s result cache is far shorter than
        # our cadence, but clearing makes the "this is the authoritative read"
        # intent explicit and avoids reusing a stale heartbeat-era entry.
        deps.clear_cache()

    dashboard = await deps.collect_dashboard(recording)
    verdict = (dashboard or {}).get("readiness") or {}
    serial = deps.get_serial(dashboard or {})
    state = load_state(state_path)
    out_of_scope = frozenset(state.get("open", {})) if recording else frozenset()
    current = codes_from_verdict(verdict)
    effective, pending = debounce(state.get("open", {}), current, state.get("pending"),
                                  out_of_scope=out_of_scope)
    new_open, delta = compute_delta(
        state.get("open", {}), effective, state.get("status"),
        serial, out_of_scope=out_of_scope,
    )
    # An opened finding was first seen a pass earlier; date it from then.
    for e in delta["opened"]:
        first = ((state.get("pending") or {}).get("open") or {}).get(e["code"], {}).get("firstSeen")
        if first:
            e["since"] = first
            new_open[e["code"]]["since"] = first
    delta["pending"] = sorted(set(pending["open"]) | set(pending["resolve"]))
    # When the verdict last changed, so a fleet view can say "FAIL for 3 h".
    since = state.get("statusSince") if not delta["statusChanged"] else None
    since = since or _now_iso()
    save_state(state_path, new_open, delta["status"], serial,
               last_full_at=wall_now if wall_now is not None else time.time(),
               status_since=since, pending=pending)

    reason = "state-change" if should_alert_now(delta) else "periodic"
    _log.info("Monitor recompute: %s (reason=%s, recording=%s)",
              summarize_delta(delta), reason, recording)
    try:
        await deps.send_checkin(dashboard=dashboard, delta=delta, reason=reason)
    except Exception as e:  # fail-open: a beacon error must never stall the loop
        _log.warning("Monitor beacon failed (%s)", e)
    return delta


def plan_tick(state: dict, wall_now: float, event_live: bool) -> Optional[str]:
    """Decide whether this tick runs a readiness pass: "full" or None.

    Pure, and cheap enough to run before main.py is even imported, which is
    what keeps an idle tick near zero cost. While an event is live (vpu.exe
    running) nothing runs at all: a pass starts ~18 collectors and must never
    compete with a game encode. Otherwise the interval depends on what is
    open: a finding awaiting confirmation, a blocker or risk, or nothing
    (info-only findings never speed checks up)."""
    if event_live:
        return None
    last = state.get("lastFullAt")
    since = wall_now - last if isinstance(last, (int, float)) else None
    if since is None or since < 0:   # never run, or the clock stepped backwards
        return "full"
    pend = state.get("pending") or {}
    if pend.get("open") or pend.get("resolve"):
        interval = CONFIRM_SECONDS
    elif any((f or {}).get("class") in ("blocker", "risk") for f in (state.get("open") or {}).values()):
        interval = INCIDENT_SECONDS
    else:
        interval = FULL_SECONDS
    return "full" if since >= interval - TICK_SLACK_SECONDS else None


def read_control(queue_state) -> dict:
    """The fleet control the Worker last sent (main._flush_checkin_queue keeps
    it in the monitor's queue file): {"mode": "on" | "off", "skip": [script]}.

    The remote off switch from the Leaf lessons (#leaf-deploy-coordination):
    finding Leaf's memory leak took four months of editing cron jobs by hand,
    so here one D1 row can stop the monitor, or one collector, on a unit or
    the whole fleet. Anything unreadable means "on, skip nothing": a garbled
    reply must not silence the fleet, and the last good one stays in force
    while the Worker is unreachable."""
    ctl = (queue_state or {}).get("control") if isinstance(queue_state, dict) else None
    if not isinstance(ctl, dict):
        return {"mode": "on", "skip": []}
    mode = "off" if ctl.get("mode") == "off" else "on"
    skip = ctl.get("skip")
    skip = [str(x) for x in skip if isinstance(x, str) and x][:50] if isinstance(skip, list) else []
    return {"mode": mode, "skip": skip}


def plan_paused(posts: dict, wall_now: float, event_live: bool) -> bool:
    """While switched off: send the hourly "paused" line (identity only), or
    not. It's what lets a paused unit hear that it's back on, and it shows
    the unit is still reachable. Nothing during an event."""
    if event_live:
        return False
    last = posts.get("lastPausedAt")
    age = wall_now - last if isinstance(last, (int, float)) and wall_now >= last else float("inf")
    return age >= HEARTBEAT_SECONDS - TICK_SLACK_SECONDS


def plan_post(posts: dict, fingerprint: str, status: Optional[str], wall_now: float) -> Optional[str]:
    """After a pass: post "full", post the one-line "heartbeat", or nothing.

    Any change to the payload (or to the open blocker/risk codes) posts in
    full at once. An unchanged verdict is posted again only on its own
    schedule: FAIL every 15 min, WARN every 30, PASS as an hourly heartbeat.
    Everything else is the same data posted twice, which Unity writes can't
    afford fleet-wide."""
    if fingerprint != posts.get("fingerprint"):
        return "full"
    last = posts.get("lastPostAt")
    age = wall_now - last if isinstance(last, (int, float)) and wall_now >= last else float("inf")
    if status == "FAIL":
        return "full" if age >= FAIL_REPOST_SECONDS - TICK_SLACK_SECONDS else None
    if status == "WARN":
        return "full" if age >= WARN_REPOST_SECONDS - TICK_SLACK_SECONDS else None
    return "heartbeat" if age >= HEARTBEAT_SECONDS - TICK_SLACK_SECONDS else None


def load_posts(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_posts(path: str, posts: dict) -> None:
    try:
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(posts, f)
        os.replace(tmp, path)
    except OSError as e:
        _log.warning("Monitor post record save failed (%s)", e)


async def run_once(deps: MonitorDeps, state_path: str, plan: str,
                   wall_now: Optional[float] = None) -> dict:
    """Run the pass `plan_tick` chose. Returns the delta."""
    return await run_full_recompute(deps, state_path, plan == "partial", wall_now)
