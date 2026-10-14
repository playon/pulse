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
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

import monitor  # noqa: E402  (light: stdlib only)

STATE_PATH = os.path.join(_web_root, "pulse-monitor-state.json")
QUEUE_PATH = os.path.join(_web_root, "pulse-monitor-checkin-queue.json")
CACHE_PATH = os.path.join(_web_root, "pulse-monitor-cache.json")
LOG_NAME = "pulse-monitor.log"
TICKS_PATH = os.path.join(_web_root, "pulse-monitor-ticks.log")
POSTS_PATH = os.path.join(_web_root, "pulse-monitor-posts.json")
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
            return {"cpuSeconds": round((info.TotalUserTime + info.TotalKernelTime) / 1e7, 2),
                    "processes": int(info.TotalProcesses)}
        except Exception:
            return None


_CPU = None


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
    names = set()
    for line in out.splitlines():
        if line.startswith('"'):
            names.add(line[1:line.find('"', 1)].lower())
    return names or None


def _rotate(path: str) -> None:
    try:
        if os.path.getsize(path) > LOG_MAX_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass


def _record_tick(started: float, plan, event_live: bool,
                 images, state: dict, outcome: str) -> None:
    """One line per tick, so the cadence and the cost of an idle tick are
    visible (the main log is only written when a pass runs)."""
    last = state.get("lastFullAt")
    age = f"{time.time() - last:.0f}" if isinstance(last, (int, float)) else "-"
    line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} plan={plan or 'none'} "
            f"eventLive={int(event_live)} "
            f"procs={len(images) if images else 0} sinceFull={age}s "
            f"open={len(state.get('open') or {})} took={time.monotonic() - started:.2f}s {outcome}\n")
    try:
        _rotate(TICKS_PATH)
        with open(TICKS_PATH, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


async def _pass(plan: str, dry_run: bool, force: bool, tick_wall: float) -> str:
    """Run one pass; return what was posted (full / heartbeat / none)."""
    os.environ["PULSE_SERVER_LOG_NAME"] = LOG_NAME
    os.environ["PULSE_SERVER_LOG_APPEND"] = "1"
    _rotate(os.path.join(_web_root, LOG_NAME))

    import powershell
    powershell.configure_background(concurrency=1, low_priority=True,
                                    disk_cache_path=CACHE_PATH,
                                    disk_cache_ttls=SLOW_COLLECTOR_TTLS)
    import main
    main._CHECKIN_STATE_PATH = QUEUE_PATH
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
        st = monitor.load_state(state_path)
        status = (delta or {}).get("status")
        open_codes = [c for c, f in (st.get("open") or {}).items()
                      if (f or {}).get("class") in ("blocker", "risk")]
        try:
            telemetry = main._build_telemetry(dashboard, raw, st.get("statusSince"),
                                              status=status, open_codes=open_codes)
        except Exception as e:  # never let the detail block the check-in itself
            main._server_log.warning("Telemetry skipped (%s)", e)
            telemetry = None
        fingerprint = main._telemetry_fingerprint(telemetry, open_codes)
        posts = monitor.load_posts(posts_path)
        # Keep the unit's name if this read lost it; remember it when it didn't.
        ident = (dashboard or {}).get("identity") or {}
        known = dict(posts.get("identity") or {})
        for k in ("venueId", "vpuName"):
            if ident.get(k):
                known[k] = ident[k]
        main._CHECKIN_IDENTITY_FALLBACK = known
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
            entry = await main._build_checkin_entry(
                dashboard, reason, None if heartbeat else delta, None if heartbeat else stats,
                None if heartbeat else telemetry, heartbeat)
            print(json.dumps(entry, indent=2, default=str))
        else:
            await main._send_checkin(
                dashboard=dashboard, reason=reason,
                delta=None if heartbeat else delta, monitor=None if heartbeat else stats,
                telemetry=None if heartbeat else telemetry, heartbeat=heartbeat)
        posts.update(fingerprint=fingerprint, lastPostAt=tick_wall, lastKind=kind)
        monitor.save_posts(posts_path, posts)
        posted["kind"] = kind

    async def _collect(skip):
        dashboard = await main._collect_dashboard(skip_intrusive=skip, raw_out=raw)
        try:
            await main._collect_telemetry_extras(raw, skip_intrusive=skip)
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
    plan = "full" if force else monitor.plan_tick(state, tick_wall, event_live)
    if not plan:
        _record_tick(started, None, event_live, images, state, "ok")
        return 0
    try:
        posted = asyncio.run(_pass(plan, dry_run, force, tick_wall))
    except BaseException as e:
        _record_tick(started, plan, event_live, images, state, f"failed: {type(e).__name__}: {e}")
        raise
    _record_tick(started, plan, event_live, images, state,
                 f"posted={posted}" + (" dry-run" if dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main_entry(sys.argv[1:]))
