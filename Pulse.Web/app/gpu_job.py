"""The graphics driver repair, run as a detached job with a status file.

Swapping the NVIDIA driver blacks out the screen of a VPU whose display hangs
off that card, can crash the browser's GPU process, and can drop the LogMeIn
session. The repair used to be one HTTP request held open for the whole
10-20 minutes, so any of those lost its result, and a reload let a second
install start on top of the first.

Now POST /api/gpu-driver/repair calls start(), which launches
Repair-GpuDriver.ps1 as its own process (it survives a reload, a browser crash
and Pulse closing) and returns at once. The script writes
C:\\ProgramData\\Pulse\\gpu-driver-status.json at every stage and heartbeats
it during every long wait. status() reads that file and adds what only Pulse
can judge: whether the process is still alive and whether its heartbeat is
stale. The Hardware tab's modal polls status() and reopens itself after a
reload until the technician acknowledges the result (ack()).

Demo mode (not Windows) runs a timed stand-in built from demo_data's repair
result, so the modal can be clicked through end to end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from typing import Optional

DEMO = sys.platform != "win32"

STATUS_NAME = "gpu-driver-status.json"
LOG_NAME = "gpu-driver-run.log"
KINDS = ("install", "reinstall", "rescan", "enable")

# The script heartbeats at least every few seconds. Hashing a ~700 MB
# installer for its signature is the longest silent step (tens of seconds), so
# 3 minutes without a heartbeat means a hung process, not a slow one.
STALE_SECS = 180
# Before the script's first write the file holds only what start() wrote.
# powershell.exe can take a while to start on a loaded VPU.
FIRST_WRITE_GRACE_SECS = 90
# A run whose heartbeat stopped this long ago no longer blocks a new one, even
# if its pid now belongs to some other process.
ABANDONED_SECS = 3600

_SCRIPTS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

_lock = threading.Lock()
_last_spawn: dict = {}          # runId -> pid of the process start() launched
_procs: list = []               # keep Popen objects referenced (no ResourceWarning)
_demo: dict = {"run": None}


def status_path() -> str:
    base = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(base, "Pulse", STATUS_NAME)


# ── process + file helpers ──────────────────────────────────────

def _pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        # Access denied means the process exists; anything else means it doesn't.
        return ctypes.get_last_error() == 5
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return True
        return code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def _read_file() -> Optional[dict]:
    """The status file as a dict, None when there is none, or
    {"_unreadable": True} when it can't be parsed (the script swaps the file
    in atomically, so this should be rare; one retry covers the swap)."""
    path = status_path()
    for attempt in (0, 1):
        try:
            with open(path, encoding="utf-8-sig") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {"_unreadable": True}
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            if attempt == 0:
                time.sleep(0.15)
    return {"_unreadable": True}


def _write_file(data: dict) -> None:
    path = status_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".pulse.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)


# ── status ──────────────────────────────────────────────────────

def _judge(st: dict, now: float) -> dict:
    """Adds live / stale / died / ageSec to a raw status record."""
    out = dict(st)
    done = st.get("stage") == "done"
    updated = st.get("updatedEpoch") or st.get("startedEpoch") or 0
    try:
        age = max(0.0, now - float(updated))
    except (TypeError, ValueError):
        age = 0.0
    pid = st.get("pid") or _last_spawn.get(st.get("runId"))
    alive = (not done) and _pid_alive(pid)
    stale = died = False
    if not done:
        if pid and not alive:
            died = True           # the process ended without writing a result
        elif not pid:
            died = age > FIRST_WRITE_GRACE_SECS
        elif age > STALE_SECS:
            stale = True          # alive but silent: hung, or a reused pid
    out.update(ageSec=int(age), live=bool(alive and not stale), stale=stale, died=died,
               finished=bool(done or died))
    return out


def status() -> dict:
    if DEMO:
        return _demo_status()
    st = _read_file()
    if st is None:
        return {"stage": "idle", "live": False, "finished": False}
    if st.get("_unreadable"):
        return {"stage": "unknown", "live": False, "finished": False, "transient": True,
                "message": "Could not read the install status file."}
    return _judge(st, time.time())


def install_live() -> bool:
    """True while a repair is running or may still be running (alive but
    silent). Pulse's auto-close paths stay up while this is true, so the
    result is still on screen when the technician looks again."""
    try:
        s = status()
    except Exception:
        return False
    return bool(s.get("live") or (s.get("stale") and s.get("ageSec", 0) < ABANDONED_SECS))


# ── start / ack ─────────────────────────────────────────────────

def _busy_reply(cur: dict) -> dict:
    return {"ok": False, "status": "already-running", "runId": cur.get("runId"),
            "message": "A graphics driver install is already running on this VPU. "
                       "Pulse is showing its progress."}


def start(kind: str, reinstall: bool) -> dict:
    """Launch a repair unless one is already running. Returns at once."""
    kind = kind if kind in KINDS else ("reinstall" if reinstall else "install")
    with _lock:
        cur = status()
        if cur.get("live") or (cur.get("stale") and cur.get("ageSec", 0) < ABANDONED_SECS):
            return _busy_reply(cur)
        run_id = uuid.uuid4().hex[:12]
        if DEMO:
            return _demo_start(run_id, kind, reinstall)
        now = int(time.time())
        record = {"runId": run_id, "kind": kind, "pid": None, "reinstall": bool(reinstall),
                  "stage": "starting", "message": "Starting the driver repair.",
                  "stagesSeen": [], "steps": [], "bytesDone": None, "bytesTotal": None,
                  "startedEpoch": now, "updatedEpoch": now, "result": None}
        try:
            _write_file(record)
        except OSError as e:
            return {"ok": False, "status": "no-status-file",
                    "message": f"Pulse could not write its status file ({e}), so it did not start the install."}
        path = status_path()
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", os.path.join(_SCRIPTS_DIR, "Repair-GpuDriver.ps1"),
               "-StatusPath", path, "-RunId", run_id, "-Kind", kind]
        if reinstall:
            cmd += ["-Reinstall", "1"]
        log_path = os.path.join(os.path.dirname(path), LOG_NAME)
        CREATE_NO_WINDOW = 0x08000000
        CREATE_NEW_PROCESS_GROUP = 0x00000200   # Pulse's own Ctrl+C never reaches it
        CREATE_BREAKAWAY_FROM_JOB = 0x01000000  # outlive a job object Pulse may run in
        base = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        proc = None
        err = None
        try:
            log = open(log_path, "w", encoding="utf-8")
        except OSError:
            log = subprocess.DEVNULL
        try:
            for flags in (base | CREATE_BREAKAWAY_FROM_JOB, base):
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
                                            stderr=subprocess.STDOUT, creationflags=flags,
                                            close_fds=True)
                    break
                except OSError as e:   # a job that forbids breakaway refuses the first form
                    err = e
        finally:
            if log is not subprocess.DEVNULL:
                log.close()
        if proc is None:
            record.update(stage="done", updatedEpoch=int(time.time()),
                          message=f"Pulse could not start the driver repair: {err}",
                          result={"error": True, "message": f"Pulse could not start the driver repair: {err}",
                                  "script": "Repair-GpuDriver.ps1", "steps": []})
            try:
                _write_file(record)
            except OSError:
                pass
            return {"ok": False, "status": "spawn-failed", "runId": run_id, "message": record["message"]}
        _last_spawn[run_id] = proc.pid
        _procs.append(proc)
        return {"ok": True, "runId": run_id, "kind": kind}


def ack(run_id: str) -> dict:
    """The technician closed the finished result: stop reopening it."""
    if DEMO:
        run = _demo.get("run")
        if run and run["runId"] == run_id:
            run["acknowledged"] = True
        return {"ok": True}
    with _lock:
        st = _read_file()
        if not st or st.get("_unreadable") or st.get("runId") != run_id:
            return {"ok": False, "message": "That run is no longer the latest one."}
        if not _judge(st, time.time()).get("finished"):
            return {"ok": False, "message": "The install is still running."}
        st["acknowledged"] = True
        try:
            _write_file(st)
        except OSError as e:
            return {"ok": False, "message": str(e)}
        return {"ok": True}


# ── demo stand-in ───────────────────────────────────────────────

_DEMO_TIMELINE = (  # (stage, seconds it lasts, message)
    ("checking", 2, "Checking the graphics card."),
    ("preparing", 1, "Choosing the approved driver and checking disk space."),
    ("downloading", 12, "Downloading the driver."),
    ("verifying", 2, "Checking the installer is signed by NVIDIA."),
    ("installing", 14, "Installing the driver. The screen goes black for a few seconds, "
                       "maybe more than once, while Windows swaps the driver."),
    ("confirming", 3, "Checking the card works with the new driver."),
)
_DEMO_BYTES = 709_000_000


def _demo_start(run_id: str, kind: str, reinstall: bool) -> dict:
    import demo_data
    result = demo_data._demo_gpu_driver_repair(reinstall=reinstall)
    names = [s.get("step") for s in result.get("steps", [])]
    if "run installer" in names:
        timeline = list(_DEMO_TIMELINE)
    else:
        timeline = [("checking", 2, "Checking the graphics card.")]
        if "rescan for hardware" in names:
            timeline.append(("rescanning", 3, "Asking Windows to rescan for the graphics card."))
        if "turn the card on" in names:
            timeline.append(("enabling", 3, "Turning the graphics card on."))
        if "choose driver" in names:
            timeline.append(("preparing", 1, "Choosing the approved driver and checking disk space."))
    _demo["run"] = {"runId": run_id, "kind": kind, "reinstall": bool(reinstall),
                    "t0": time.time(), "timeline": timeline, "result": result, "acknowledged": False}
    return {"ok": True, "runId": run_id, "kind": kind}


def _demo_status() -> dict:
    run = _demo.get("run")
    if not run:
        return {"stage": "idle", "live": False, "finished": False}
    now = time.time()
    el = now - run["t0"]
    seen, t, stage, msg = [], 0.0, "done", run["result"].get("message", "")
    bytes_done = bytes_total = None
    for name, dur, m in run["timeline"]:
        seen.append(name)
        if el < t + dur:
            stage, msg = name, m
            if name == "downloading":
                bytes_total = _DEMO_BYTES
                bytes_done = int(_DEMO_BYTES * (el - t) / dur)
            break
        t += dur
    done = stage == "done"
    return {"runId": run["runId"], "kind": run["kind"], "reinstall": run["reinstall"],
            "stage": stage, "message": msg, "stagesSeen": seen,
            "bytesDone": bytes_done if not done else None,
            "bytesTotal": bytes_total if not done else None,
            "steps": run["result"].get("steps", []) if done else [],
            "startedEpoch": int(run["t0"]), "updatedEpoch": int(now),
            "result": run["result"] if done else None,
            "acknowledged": run["acknowledged"], "ageSec": 0,
            "live": not done, "stale": False, "died": False, "finished": done}
