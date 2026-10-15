"""One scheduled tick of the Pulse fleet monitor.

Task Scheduler runs this every 5 minutes as SYSTEM (see
deploy/Install-PulseMonitor.ps1):

    C:\\Pulse\\app\\python\\python.exe C:\\Pulse\\app\\monitor_once.py

Resource budget, in the order a tick spends it:

  1. One `tasklist` call: is vpu.exe running (an event is live)? If so,
     nothing else happens. No PowerShell.
  2. `monitor.plan_tick` decides from the state file whether a pass is due.
     Most ticks stop here and exit without importing main.py (FastAPI).
  3. A due pass imports main and runs the collectors in one powershell.exe at
     below-normal priority, with slow-changing collectors served from a disk
     cache (powershell.configure_background). Then diff.
  4. `monitor.plan_post` decides whether to post: in full when anything
     changed or an unchanged FAIL/WARN is due again, the one-line heartbeat
     for an unchanged PASS once an hour, otherwise nothing.

It holds no port, so it never collides with an interactive Pulse (run.bat
kills whatever is listening on 8765), and it writes its own log, state, queue
and cache files, so the two never race on a file.

    --force   run a pass now and post it in full, whatever the cadence or a live event
    --dry-run run the pass but print the check-in instead of sending it
"""

import asyncio
import json
import os
import sys
import time

_app_dir = os.path.dirname(os.path.abspath(__file__))
_web_root = os.path.dirname(_app_dir)
# Where the monitor keeps its state, queue, cache and logs. The agent's runner
# (pulse_agent/runner.py) runs this file from a slot it replaces on an update,
# so it passes the folder that outlives the slots. Without it (the older
# install, or a hand run), they live beside the code, as before.
_data_root = os.environ.get("PULSE_MONITOR_DATA") or _web_root
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from pulse_agent import AGENT_VERSION, UPDATE_FILE, last_update  # noqa: E402  (light: stdlib only)
from pulse_agent import monitor, event_watch, checkin_lite  # noqa: E402  (light: stdlib only)
from typing import Optional  # noqa: E402

STATE_PATH = os.path.join(_data_root, "pulse-monitor-state.json")
QUEUE_PATH = os.path.join(_data_root, "pulse-monitor-checkin-queue.json")
CACHE_PATH = os.path.join(_data_root, "pulse-monitor-cache.json")
LOG_NAME = "pulse-monitor.log"
TICKS_PATH = os.path.join(_data_root, "pulse-monitor-ticks.log")
POSTS_PATH = os.path.join(_data_root, "pulse-monitor-posts.json")
EVENT_PATH = os.path.join(_data_root, "pulse-monitor-event.json")
UPDATE_PATH = os.path.join(_data_root, UPDATE_FILE)
LOG_MAX_BYTES = 2 * 1024 * 1024

# Collectors whose answer moves over hours, not minutes. Everything else runs
# fresh each pass, including Test-NetworkPorts (venue firewalls are the top
# cause of missed events) and the GPU and service checks. Not
# Get-SystemIdentity: a read that came back without its Pixellot part was
# cached for 6 h on lab-z2 and every post went out nameless. It costs ~0.2 s.
SLOW_COLLECTOR_TTLS = {
    "Get-InstalledSoftware.ps1": 6 * 3600,
    "Get-Hardware.ps1": 6 * 3600,
    "Get-GraphicsDelivery.ps1": 2 * 3600,
    "Get-LmiGatewayLog.ps1": 2 * 3600,
    "Test-PixellotInstallState.ps1": 3600,
    "Test-TlsInspection.ps1": 3600,
    "Get-DiskHealth.ps1": 3600,
    "Get-WifiAdapters.ps1": 3600,
    "Get-RebootHistory.ps1": 1800,
}

_BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
_CREATE_NO_WINDOW = 0x08000000


def _lower_own_priority() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetPriorityClass(k32.GetCurrentProcess(), _BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass


class _CpuMeter:
    """Exact CPU time of this tick and every process it starts.

    The tick puts itself in a Windows job object; PowerShell children join it
    automatically, and the job's accounting keeps the CPU time of processes
    that have already exited. So `cpu_seconds()` is the whole cost of the
    pass, which a sample of machine-wide CPU can't separate from whatever else
    the VPU is doing. Off Windows (demo), or if the job can't be created,
    every reading is None."""

    def __init__(self):
        self.job = None
        self.k32 = None
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes as w
            # Declare every signature: without argtypes ctypes passes a 64-bit
            # HANDLE as a C int and overflows (caught on vpu-home).
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
            k32.CreateJobObjectW.restype = w.HANDLE
            k32.GetCurrentProcess.argtypes = []
            k32.GetCurrentProcess.restype = w.HANDLE
            k32.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
            k32.AssignProcessToJobObject.restype = w.BOOL
            k32.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                      w.DWORD, ctypes.POINTER(w.DWORD)]
            k32.QueryInformationJobObject.restype = w.BOOL
            job = k32.CreateJobObjectW(None, None)
            if job and k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
                self.job, self.k32 = job, k32
        except Exception:
            self.job = None

    def read(self):
        if not self.job:
            return None
        try:
            import ctypes

            class _Acct(ctypes.Structure):
                _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                            ("ThisPeriodTotalUserTime", ctypes.c_int64),
                            ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                            ("TotalPageFaultCount", ctypes.c_uint32), ("TotalProcesses", ctypes.c_uint32),
                            ("ActiveProcesses", ctypes.c_uint32),
                            ("TotalTerminatedProcesses", ctypes.c_uint32)]
            info = _Acct()
            ok = self.k32.QueryInformationJobObject(
                self.job, 1, ctypes.byref(info), ctypes.sizeof(info), None)  # 1 = basic accounting
            if not ok:
                return None
            out = {"cpuSeconds": round((info.TotalUserTime + info.TotalKernelTime) / 1e7, 2),
                   "processes": int(info.TotalProcesses)}
            peak = self._peak_memory_mb()
            if peak is not None:
                out["memoryPeakMb"] = peak
            return out
        except Exception:
            return None

    def _peak_memory_mb(self):
        """Peak memory committed by the whole job at once (this tick and its
        PowerShell children), in MB. Canopy's Leaf agent leaked memory on
        VPUs for months before anyone noticed (#leaf-deploy-coordination,
        2025-09 to 2026-01), so every pass reports what it held, not just
        its CPU. A tick is a fresh process each time, so a leak can't build
        up across ticks; a rising peak here would mean one pass got heavier."""
        import ctypes

        class _Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                        ("SchedulingClass", ctypes.c_uint32)]

        class _Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", _Basic), ("IoInfo", ctypes.c_uint64 * 6),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        info = _Extended()
        ok = self.k32.QueryInformationJobObject(
            self.job, 9, ctypes.byref(info), ctypes.sizeof(info), None)  # 9 = extended limit info
        if not ok:
            return None
        return round(info.PeakJobMemoryUsed / (1024 * 1024), 1)


_CPU = None


_VPU_PID = None   # set by _running_images; a change mid-event is a VPU.exe restart
_IMAGES = None    # the tick's process names, reused by the event reader


def _running_images():
    """Lower-cased image names of running processes, or None if unreadable."""
    if sys.platform != "win32":
        return None
    import subprocess
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
            timeout=20, creationflags=_CREATE_NO_WINDOW,
        ).stdout or ""
    except Exception:
        return None
    global _VPU_PID, _IMAGES
    names = set()
    _VPU_PID = None
    for line in out.splitlines():
        if line.startswith('"'):
            name = line[1:line.find('"', 1)].lower()
            names.add(name)
            if name == "vpu.exe" and _VPU_PID is None:
                parts = line.split('","')
                _VPU_PID = parts[1] if len(parts) > 1 else None
    _IMAGES = names or None
    return names or None


def _rotate(path: str) -> None:
    try:
        if os.path.getsize(path) > LOG_MAX_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass


def _cost_note() -> str:
    """'cpu=4.4s mem=61MB ' for the tick log, or '' where it can't be measured."""
    cost = _CPU.read() if _CPU else None
    if not cost:
        return ""
    mem = f" mem={cost['memoryPeakMb']:.0f}MB" if cost.get("memoryPeakMb") is not None else ""
    return f"cpu={cost['cpuSeconds']:.1f}s{mem} "


def _record_tick(started: float, plan, event_live: bool,
                 images, state: dict, outcome: str) -> None:
    """One line per tick, so the cadence and the cost of an idle tick are
    visible (the main log is only written when a pass runs)."""
    last = state.get("lastFullAt")
    age = f"{time.time() - last:.0f}" if isinstance(last, (int, float)) else "-"
    line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} plan={plan or 'none'} "
            f"eventLive={int(event_live)} "
            f"procs={len(images) if images else 0} sinceFull={age}s "
            f"open={len(state.get('open') or {})} took={time.monotonic() - started:.2f}s "
            f"{_cost_note()}{outcome}\n")
    try:
        _rotate(TICKS_PATH)
        with open(TICKS_PATH, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_json(path: str, data: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def _app_version() -> str:
    try:
        with open(os.path.join(_web_root, "VERSION"), "r", encoding="utf-8") as fh:
            return fh.read().strip()[:64]
    except OSError:
        return ""


def _log_to_data_root() -> None:
    """main.py's log goes to the data folder: main joins PULSE_SERVER_LOG_NAME
    onto its own folder, and an absolute name wins that join."""
    path = os.path.join(_data_root, LOG_NAME)
    os.environ["PULSE_SERVER_LOG_NAME"] = path
    os.environ["PULSE_SERVER_LOG_APPEND"] = "1"
    _rotate(path)


def _agent_checkin():
    """The check-in module, pointed at the monitor's own queue and stamping
    this agent's version on every post. Import main first: it binds the engine."""
    from pulse_agent import checkin
    checkin._CHECKIN_STATE_PATH = QUEUE_PATH
    checkin._AGENT_VERSION = AGENT_VERSION
    checkin._AGENT_UPDATE_PATH = UPDATE_PATH
    return checkin


def _event_entry(reason: str, ev: dict, tick_wall: float, ended: bool) -> dict:
    import uuid
    posts = monitor.load_posts(POSTS_PATH)
    ident = posts.get("identity") or {}
    entry = {"checkinId": str(uuid.uuid4()),
             "sentAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(tick_wall)),
             "reason": reason, "venueId": ident.get("venueId"), "vpuName": ident.get("vpuName"),
             "pulseVersion": _app_version(), "agentVersion": AGENT_VERSION,
             "event": event_watch.summary(ev, tick_wall, ended)}
    update = last_update(UPDATE_PATH)
    if update:
        entry["agentUpdate"] = update
    return entry


def _event_tick(tick_wall: float) -> str:
    """One tick while VPU.exe runs: read what Pixellot wrote since the last
    tick (event_watch, files only), and post only at the event's start, when
    a new verdict holds for two reads in a row, or never otherwise."""
    rec = _load_json(EVENT_PATH)
    ev = rec.get("event")
    if isinstance(ev, dict):
        ev.pop("goneAt", None)        # VPU.exe is back: it was a restart, not the end
    new_event = not isinstance(ev, dict)
    if new_event:
        ev = {"startedAt": tick_wall}
        mark = rec.get("logMark") or {}
        # Start where VPU.exe started writing: the log's size at the last
        # tick before the event, when it's the same file.
        if mark.get("path"):
            ev["logFile"], ev["offset"] = mark["path"], int(mark.get("size") or 0)
    cost = event_watch.observe(ev, _VPU_PID, tick_wall, images=_IMAGES)
    v = event_watch.verdict(ev, tick_wall)
    posted = "none"
    if new_event:
        reason = "event-start"
    elif v != ev.get("postedVerdict") and v == ev.get("lastVerdict"):
        reason = "event-update"
    elif tick_wall - (ev.get("lastPostAt") or tick_wall) >= monitor.HEARTBEAT_SECONDS - monitor.TICK_SLACK_SECONDS:
        # Hourly while nothing changes: Vitals reads a unit not heard from in
        # 70 minutes as Silent, and a steady game lasts longer than that.
        reason = "event-update"
    else:
        reason = None
    ev["lastVerdict"] = v
    if reason and (ev.get("eventId") or not new_event):
        entry = _event_entry(reason, ev, tick_wall, ended=False)
        ok = checkin_lite.send(QUEUE_PATH, entry, user_agent=f"Pulse/{_app_version()}")
        ev["postedVerdict"] = v
        ev["lastPostAt"] = tick_wall
        posted = f"{reason}{'' if ok else '(queued)'}"
    elif reason == "event-start":
        ev["startPending"] = True   # no event id yet; post once it shows up
    if ev.pop("startPending", False) and ev.get("eventId") and posted == "none":
        ok = checkin_lite.send(QUEUE_PATH, _event_entry("event-start", ev, tick_wall, False),
                               user_agent=f"Pulse/{_app_version()}")
        ev["postedVerdict"] = v
        ev["lastPostAt"] = tick_wall
        posted = f"event-start{'' if ok else '(queued)'}"
    rec["event"] = ev
    _save_json(EVENT_PATH, rec)
    return f"event={v} read={cost['bytes'] // 1024}KB{' skipped' if cost['skipped'] else ''} posted={posted}"


def _event_end(tick_wall: float) -> Optional[str]:
    """VPU.exe has stopped: post the event's summary once, and forget it.

    Only on the second tick in a row without VPU.exe. Pixellot relaunched a
    killed VPU.exe in 5 s on 6493 (2026-10-14); a tick landing in that gap
    must neither end the event nor start a full pass (port tests, PowerShell)
    while VPU.exe is coming back. Returns "pending" for that first tick."""
    rec = _load_json(EVENT_PATH)
    ev = rec.get("event")
    if not isinstance(ev, dict):
        return None
    if not ev.get("goneAt"):
        ev["goneAt"] = tick_wall
        rec["event"] = ev
        _save_json(EVENT_PATH, rec)
        return "pending"
    event_watch.observe(ev, None, tick_wall)     # the close reason, the last lines
    ok = checkin_lite.send(QUEUE_PATH, _event_entry("event-end", ev, tick_wall, ended=True),
                           user_agent=f"Pulse/{_app_version()}")
    rec["last"] = event_watch.summary(ev, tick_wall, ended=True)
    rec.pop("event", None)
    _save_json(EVENT_PATH, rec)
    return f"event-end{'' if ok else '(queued)'}"


def _mark_vpu_log() -> None:
    """Between events: remember the VPU log's name and size (one directory
    listing), so the next event is read from where VPU.exe starts writing."""
    newest = event_watch._newest(event_watch.LOG_DIR, "VPU_", ".log")
    if not newest:
        return
    rec = _load_json(EVENT_PATH)
    if rec.get("event"):
        return
    rec["logMark"] = {"path": newest[0], "size": newest[1]}
    _save_json(EVENT_PATH, rec)


def _read_control() -> dict:
    """Fleet control from the monitor's queue file, read without importing
    main (so a paused unit's idle tick stays as cheap as any other)."""
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8") as fh:
            return monitor.read_control(json.load(fh))
    except (OSError, ValueError):
        return monitor.read_control(None)


async def _paused_post(tick_wall: float) -> str:
    """The hourly identity-only line while fleet control has the monitor off.
    Its reply carries the control, so this is how a unit learns it's back on."""
    _log_to_data_root()
    import main  # noqa: F401  (binds the engine the check-in runs on)
    checkin = _agent_checkin()
    posts = monitor.load_posts(POSTS_PATH)
    known = dict(posts.get("identity") or {})
    if not (known.get("venueId") or known.get("vpuName")):
        # Never posted, so it can't have been told to pause; nothing to name it by.
        return "none"
    checkin._CHECKIN_IDENTITY_FALLBACK = known
    await checkin._send_checkin(reason="paused", paused=True)
    posts["lastPausedAt"] = tick_wall
    monitor.save_posts(POSTS_PATH, posts)
    return "paused"


async def _pass(plan: str, dry_run: bool, force: bool, tick_wall: float,
                skip=()) -> str:
    """Run one pass; return what was posted (full / heartbeat / none)."""
    _log_to_data_root()

    import powershell
    powershell.configure_background(concurrency=1, low_priority=True,
                                    disk_cache_path=CACHE_PATH,
                                    disk_cache_ttls=SLOW_COLLECTOR_TTLS,
                                    skip_scripts=skip)
    import main
    checkin = _agent_checkin()
    from pulse_agent import telemetry as agent_telemetry
    # No batch override: the client cuts each request at the Worker's 64 KB
    # body cap as well as by count (#236), so a replayed backlog of full
    # reports (~2-8 KB each) drains a few per request on its own.

    started = time.monotonic()
    raw = {}

    posted = {"kind": "none"}

    async def send(dashboard=None, delta=None, reason=None):
        wall = time.monotonic() - started
        stats = {"pass": plan, "seconds": round(wall, 1), "psRuns": len(powershell.LOG_BUFFER)}
        cpu = _CPU.read() if _CPU else None
        if cpu:
            # Share of the whole machine over the pass, the number to hold
            # against "must not compete with the encoder".
            cores = os.cpu_count() or 1
            stats.update(cpuSeconds=cpu["cpuSeconds"], processes=cpu["processes"],
                         cpuPercent=round(100 * cpu["cpuSeconds"] / max(wall, 0.1) / cores, 1))
            if cpu.get("memoryPeakMb") is not None:
                stats["memoryPeakMb"] = cpu["memoryPeakMb"]
        st = monitor.load_state(state_path)
        status = (delta or {}).get("status")
        open_codes = [c for c, f in (st.get("open") or {}).items()
                      if (f or {}).get("class") in ("blocker", "risk")]
        try:
            telemetry = agent_telemetry._build_telemetry(dashboard, raw, st.get("statusSince"),
                                              status=status, open_codes=open_codes)
        except Exception as e:  # never let the detail block the check-in itself
            main._server_log.warning("Telemetry skipped (%s)", e)
            telemetry = None
        fingerprint = agent_telemetry._telemetry_fingerprint(telemetry, open_codes)
        posts = monitor.load_posts(posts_path)
        # Keep the unit's name if this read lost it; remember it when it didn't.
        ident = (dashboard or {}).get("identity") or {}
        known = dict(posts.get("identity") or {})
        for k in ("venueId", "vpuName"):
            if ident.get(k):
                known[k] = ident[k]
        checkin._CHECKIN_IDENTITY_FALLBACK = known
        if known:
            posts["identity"] = known
        kind = "full" if force else monitor.plan_post(posts, fingerprint, status, tick_wall)
        if not kind:
            return
        # A change (the delta, or drift in any payload field) vs an unchanged
        # FAIL/WARN posted again on schedule.
        reason = "state-change" if fingerprint != posts.get("fingerprint") else "periodic"
        heartbeat = kind == "heartbeat"
        if dry_run:
            entry = await checkin._build_checkin_entry(
                dashboard, reason, None if heartbeat else delta, None if heartbeat else stats,
                None if heartbeat else telemetry, heartbeat)
            print(json.dumps(entry, indent=2, default=str))
        else:
            await checkin._send_checkin(
                dashboard=dashboard, reason=reason,
                delta=None if heartbeat else delta, monitor=None if heartbeat else stats,
                telemetry=None if heartbeat else telemetry, heartbeat=heartbeat)
        posts.update(fingerprint=fingerprint, lastPostAt=tick_wall, lastKind=kind)
        monitor.save_posts(posts_path, posts)
        posted["kind"] = kind

    async def _collect(skip):
        dashboard = await main._collect_dashboard(skip_intrusive=skip, raw_out=raw)
        try:
            await agent_telemetry._collect_telemetry_extras(raw, skip_intrusive=skip)
        except Exception as e:
            main._server_log.warning("Telemetry extras skipped (%s)", e)
        return dashboard

    deps = monitor.MonitorDeps(
        collect_dashboard=lambda skip: _collect(skip),
        send_checkin=send,
        # Fingerprints are local; the venue id, not the BIOS serial, names the unit.
        get_serial=lambda d: (d.get("identity") or {}).get("venueId"),
        clear_cache=lambda: None,  # a fresh process has nothing cached in memory
    )
    # Stamp the pass with the tick's start, not its end, so the next tick
    # measures a whole interval. A dry run works on a throwaway copy of the
    # state: it sends nothing, so it must not record a pass or move findings
    # along (that hid changes from the next real pass).
    state_path, posts_path = STATE_PATH, POSTS_PATH
    if dry_run:
        import shutil
        import tempfile
        scratch = tempfile.mkdtemp(prefix="pulse-dry-")
        state_path = os.path.join(scratch, "state.json")
        posts_path = os.path.join(scratch, "posts.json")
        for src, dst in ((STATE_PATH, state_path), (POSTS_PATH, posts_path)):
            if os.path.exists(src):
                shutil.copyfile(src, dst)
    await monitor.run_once(deps, state_path, plan, wall_now=tick_wall)
    return posted["kind"]


def main_entry(argv) -> int:
    global _CPU
    started = time.monotonic()
    _CPU = _CpuMeter()
    force = "--force" in argv
    dry_run = "--dry-run" in argv
    _lower_own_priority()

    images = _running_images()
    event_live = bool(images and "vpu.exe" in images)

    state = monitor.load_state(STATE_PATH)
    tick_wall = time.time()
    control = _read_control()
    if control["mode"] == "off" and not force:
        # Switched off by fleet control: no checks, only the hourly line.
        if dry_run or not monitor.plan_paused(monitor.load_posts(POSTS_PATH), tick_wall, event_live):
            _record_tick(started, None, event_live, images, state, "paused")
            return 0
        try:
            posted = asyncio.run(_paused_post(tick_wall))
        except BaseException as e:
            _record_tick(started, "paused", event_live, images, state, f"failed: {type(e).__name__}: {e}")
            raise
        _record_tick(started, "paused", event_live, images, state, f"posted={posted}")
        return 0
    if event_live and not force and not dry_run:
        try:
            note = _event_tick(tick_wall)
        except Exception as e:  # the reader must never break the tick
            note = f"event read failed: {type(e).__name__}: {e}"
        _record_tick(started, "event", event_live, images, state, note)
        return 0
    end_note = None
    if images is not None and not event_live:
        try:
            end_note = _event_end(tick_wall)
            if end_note is None:
                _mark_vpu_log()
        except Exception as e:
            end_note = f"event end failed: {type(e).__name__}: {e}"
        if end_note == "pending" and not force:
            # VPU.exe just disappeared: could be a restart. No pass this tick.
            _record_tick(started, None, event_live, images, state, "vpu.exe gone, event end pending")
            return 0
    plan = "full" if force else monitor.plan_tick(state, tick_wall, event_live)
    if not plan:
        _record_tick(started, None, event_live, images, state, end_note or "ok")
        return 0
    try:
        posted = asyncio.run(_pass(plan, dry_run, force, tick_wall, skip=control["skip"]))
    except BaseException as e:
        _record_tick(started, plan, event_live, images, state, f"failed: {type(e).__name__}: {e}")
        raise
    _record_tick(started, plan, event_live, images, state,
                 f"posted={posted}" + (" dry-run" if dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry(sys.argv[1:]))
