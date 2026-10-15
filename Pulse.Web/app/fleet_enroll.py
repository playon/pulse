"""Opt a unit in to (or out of) the fleet monitor from the Pulse UI.

The monitor runs from its own copy of Pulse in C:\\PulseFleetMonitor, not
from C:\\Pulse. Other people launch Pulse on these units with the production
launcher, which copies its build over C:\\Pulse: a monitor running from there
would end up with half its files from another build and fail every tick,
quietly. Its own folder is never touched by a launcher, so it keeps running
whatever channel the interactive Pulse is on.

  enroll()        copy this Pulse build into the monitor folder and register
                  the task there (deploy/Install-PulseMonitor.ps1), then run
                  the first tick, so the unit shows in Vitals within a minute
  unenroll()      remove the task and the copied files
  refresh()       at a dev-channel launch: if the copy is from another build,
                  copy this one over it (never during an event)
  status()        what the Settings card shows

Copying is robocopy /MIR, which skips unchanged files, so the 50 MB Python
runtime is only copied the first time. The task is disabled and stopped
before a copy, so no tick runs on half-copied files, and the installer
re-registers it enabled. The folder is locked to SYSTEM and Administrators:
the task runs its code as SYSTEM.

Dev channel only for now (the card and the endpoints): the monitor is a
pilot, and only Ian runs dev.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from typing import Optional

TASK_NAME = "Pulse Fleet Monitor"
MONITOR_ROOT = r"C:\PulseFleetMonitor"
BUILD_FILE = "pulse-monitor-build.json"
VITALS_URL = "https://pulse-vitals.pulse-checkin-worker.workers.dev/"
COPY_DIRS = ("app", "scripts", "deploy")
COPY_FILES = ("VERSION", "CHANNEL")
# The monitor's own files (Install-PulseMonitor.ps1 $MonitorFiles). On the
# first enroll they are carried over from a task that ran from another folder,
# so the unit keeps its open findings and post history.
STATE_FILES = ("pulse-monitor-state.json", "pulse-monitor-checkin-queue.json",
               "pulse-monitor-posts.json", "pulse-monitor-cache.json",
               "pulse-monitor-event.json")
# A tick every 5 minutes; past this the task isn't running.
STALE_AFTER_SECONDS = 20 * 60

_CREATE_NO_WINDOW = 0x08000000
_TASK_NS = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"


def _run(args, timeout=60):
    kw = {"capture_output": True, "text": True, "timeout": timeout}
    if sys.platform == "win32":
        kw["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.run(args, **kw)


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def vpu_running() -> bool:
    """Is an event live (vpu.exe running)? One tasklist call, as the tick does."""
    if sys.platform != "win32":
        return False
    try:
        r = _run(["tasklist", "/FI", "IMAGENAME eq vpu.exe", "/FO", "CSV", "/NH"], timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return '"vpu.exe"' in (r.stdout or "").lower()


def fingerprint(root: str) -> Optional[str]:
    """Which build a folder holds: a hash of the monitor's code (app\\*.py,
    scripts, deploy, VERSION). The Python runtime and static UI don't change
    what the monitor does, so they're left out, which keeps this fast. Dev
    builds all say 1.5.0-dev in VERSION, so the version alone can't tell."""
    files = []
    app = os.path.join(root, "app")
    if not os.path.isfile(os.path.join(app, "monitor_once.py")):
        return None
    for name in os.listdir(app):
        if name.endswith(".py"):
            files.append(os.path.join("app", name))
    for d in ("scripts", "deploy"):
        base = os.path.join(root, d)
        for dirpath, dirnames, names in os.walk(base):
            dirnames[:] = [x for x in dirnames if x != "__pycache__"]
            for name in names:
                files.append(os.path.relpath(os.path.join(dirpath, name), root))
    files.extend(f for f in COPY_FILES if os.path.isfile(os.path.join(root, f)))
    h = hashlib.sha1()
    for rel in sorted(files, key=lambda p: p.replace("\\", "/").lower()):
        h.update(rel.replace("\\", "/").lower().encode())
        h.update(b"\0")
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                h.update(fh.read())
        except OSError:
            h.update(b"?")
        h.update(b"\0")
    return h.hexdigest()


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def parse_task_xml(text: str) -> Optional[dict]:
    """The registered task's command and whether it's enabled, from
    `schtasks /Query /XML`. XML, not the CSV list: those headers are localized."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    cmd = root.find(f"./{_TASK_NS}Actions/{_TASK_NS}Exec/{_TASK_NS}Command")
    arg = root.find(f"./{_TASK_NS}Actions/{_TASK_NS}Exec/{_TASK_NS}Arguments")
    en = root.find(f"./{_TASK_NS}Settings/{_TASK_NS}Enabled")
    ver = root.find(f"./{_TASK_NS}RegistrationInfo/{_TASK_NS}Version")
    command = (cmd.text or "").strip() if cmd is not None else ""
    arguments = (arg.text or "").strip().strip('"') if arg is not None else ""
    # <Enabled> is omitted when true.
    enabled = en is None or (en.text or "").strip().lower() != "false"
    # C:\X\app\python\python.exe -> C:\X
    tail = "\\app\\python\\python.exe"
    norm = command.replace("/", "\\")
    install_dir = norm[: -len(tail)] if norm.lower().endswith(tail) else None
    return {"command": command, "arguments": arguments, "enabled": enabled,
            "installDir": install_dir, "definition": (ver.text or "").strip() if ver is not None else None}


def query_task() -> Optional[dict]:
    if sys.platform != "win32":
        return None
    try:
        r = _run(["schtasks", "/Query", "/TN", TASK_NAME, "/XML", "ONE"], timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return parse_task_xml(r.stdout)


def _last_tick(root: str) -> dict:
    """The last line of the tick log: when the task last ran and what it did."""
    path = os.path.join(root, "pulse-monitor-ticks.log")
    try:
        mtime = os.path.getmtime(path)
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 2048))
            tail = fh.read().decode("utf-8", "replace").strip().splitlines()
        line = tail[-1] if tail else ""
    except OSError:
        return {}
    outcome = line.rsplit(" ", 1)[-1] if line else None
    return {"at": mtime, "outcome": outcome, "line": line}


def unit_link(posts: dict) -> str:
    """The unit's drawer in Vitals: its key is the venue id, else the name
    (the check-in Worker's unit key)."""
    ident = (posts or {}).get("identity") or {}
    key = ident.get("venueId") or ident.get("vpuName")
    if not key:
        return VITALS_URL
    from urllib.parse import quote
    return f"{VITALS_URL}#/unit/{quote(str(key), safe='')}"


def status(source_root: str, channel: str, now: Optional[float] = None) -> dict:
    """What the Settings card shows. `state` is one of:
      unavailable  not the dev channel, or not Windows: no card
      off          no task
      elsewhere    a task runs the monitor from another folder (the old way,
                   from C:\\Pulse): opting in moves it here
      broken       the task points here but its files are gone, it's
                   disabled, or it hasn't ticked in 20 minutes
      paused       running, but fleet control has it switched off
      on           running
    """
    now = time.time() if now is None else now
    out = {"available": channel == "dev" and sys.platform == "win32",
           "channel": channel, "admin": is_admin(), "root": MONITOR_ROOT,
           "vitalsUrl": VITALS_URL}
    if not out["available"]:
        out["state"] = "unavailable"
        return out
    task = query_task()
    out["task"] = task
    src = fingerprint(source_root)
    out["sourceHasMonitor"] = src is not None
    if not task:
        out["state"] = "off"
        return out
    here = (task.get("installDir") or "").rstrip("\\").lower() == MONITOR_ROOT.lower()
    if not here:
        out["state"] = "elsewhere"
        return out
    build = _read_json(os.path.join(MONITOR_ROOT, BUILD_FILE))
    posts = _read_json(os.path.join(MONITOR_ROOT, "pulse-monitor-posts.json"))
    st = _read_json(os.path.join(MONITOR_ROOT, "pulse-monitor-state.json"))
    queue = _read_json(os.path.join(MONITOR_ROOT, "pulse-monitor-checkin-queue.json"))
    tick = _last_tick(MONITOR_ROOT)
    ctl = queue.get("control") if isinstance(queue.get("control"), dict) else {}
    out.update({
        "version": _read_text(os.path.join(MONITOR_ROOT, "VERSION")),
        "copiedAt": build.get("copiedAt"),
        "current": src is not None and build.get("fingerprint") == src,
        "lastTickAt": tick.get("at"),
        "lastTickOutcome": tick.get("outcome"),
        "lastPostAt": posts.get("lastPostAt"),
        "lastPostKind": posts.get("lastKind"),
        "verdict": st.get("status"),
        "control": "off" if ctl.get("mode") == "off" else "on",
        "unitUrl": unit_link(posts),
    })
    problem = None
    if not os.path.isfile(os.path.join(MONITOR_ROOT, "app", "monitor_once.py")):
        problem = "The monitor's files are missing from " + MONITOR_ROOT + "."
    elif not task.get("enabled"):
        problem = "The scheduled task is disabled."
    elif not tick.get("at"):
        # Registered but never ticked: fine for the first few minutes.
        problem = None if (build.get("copiedAt") or 0) > now - STALE_AFTER_SECONDS else \
            "The task has never run."
    elif now - tick["at"] > STALE_AFTER_SECONDS:
        problem = "The task hasn't run for " + str(int((now - tick["at"]) // 60)) + " minutes."
    if problem:
        out["state"], out["problem"] = "broken", problem
    elif out["control"] == "off":
        out["state"] = "paused"
    else:
        out["state"] = "on"
    return out


def _stop_task() -> None:
    """Disable, then end any running tick, so nothing runs while files change."""
    _run(["schtasks", "/Change", "/TN", TASK_NAME, "/DISABLE"], timeout=20)
    _run(["schtasks", "/End", "/TN", TASK_NAME], timeout=20)
    time.sleep(1.0)


def _robocopy(src: str, dst: str) -> Optional[str]:
    r = _run(["robocopy", src, dst, "/MIR", "/XD", "__pycache__", "/R:3", "/W:2",
              "/NP", "/NFL", "/NDL", "/NJH", "/NJS"], timeout=300)
    # robocopy: 0-7 = success (bits for copied / extra / mismatched), 8+ = failure.
    if r.returncode >= 8:
        return f"Copying {os.path.basename(src)} failed (robocopy {r.returncode}): " + \
            (r.stdout or r.stderr or "").strip()[-300:]
    return None


def _readable(root: str) -> bool:
    for rel in (os.path.join("app", "monitor_once.py"),
                os.path.join("deploy", "Install-PulseMonitor.ps1")) + STATE_FILES:
        p = os.path.join(root, rel)
        if os.path.exists(p):
            try:
                with open(p, "rb") as fh:
                    fh.read(1)
            except OSError:
                return False
    return True


def _lock_down(root: str) -> Optional[str]:
    """SYSTEM and Administrators can change the folder; everyone else can read
    it. The task runs this code as SYSTEM.

    The grant goes on the folder only, and everything inside is reset to
    inherit it. Granting with /T instead strips each file's inherited entries
    and adds none (the (OI)(CI) flags don't apply to a file), which left every
    file unreadable, even to admins, on 6493. A file nobody can open (from that,
    or written by SYSTEM with no entries) is taken over by Administrators first."""
    r = _run(["icacls", root, "/inheritance:r",
              "/grant:r", "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F",
              "*S-1-5-32-545:(OI)(CI)RX", "/Q"], timeout=60)
    if r.returncode != 0:
        return "Setting folder permissions failed: " + (r.stdout or r.stderr or "").strip()[-300:]
    reset = ["icacls", os.path.join(root, "*"), "/reset", "/T", "/C", "/Q"]
    r = _run(reset, timeout=300)
    # icacls /C exits 0 even when files failed, and its messages are localized:
    # check by opening the files that matter.
    if r.returncode != 0 or not _readable(root):
        _run(["takeown", "/F", root, "/R", "/A", "/D", "Y"], timeout=300)
        r = _run(reset, timeout=300)
        if r.returncode != 0 or not _readable(root):
            return "Resetting file permissions failed: " + (r.stdout or r.stderr or "").strip()[-300:]
    return None


def _run_installer(args) -> tuple:
    script = os.path.join(MONITOR_ROOT, "deploy", "Install-PulseMonitor.ps1")
    r = _run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
              "-InstallDir", MONITOR_ROOT] + list(args), timeout=120)
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    if r.returncode != 0:
        lines += [ln.strip() for ln in (r.stderr or "").splitlines() if ln.strip()][:3]
    return r.returncode, lines


def _carry_state(old_root: Optional[str]) -> int:
    """First enroll on a unit that ran the monitor from another folder: bring
    its state across, so findings stay open and nothing reposts as new."""
    if not old_root or old_root.rstrip("\\").lower() == MONITOR_ROOT.lower():
        return 0
    if os.path.exists(os.path.join(MONITOR_ROOT, "pulse-monitor-state.json")):
        return 0
    n = 0
    for name in STATE_FILES:
        src = os.path.join(old_root, name)
        if os.path.isfile(src):
            try:
                with open(src, "rb") as a, open(os.path.join(MONITOR_ROOT, name), "wb") as b:
                    b.write(a.read())
                n += 1
            except OSError:
                pass
    return n


def _guard(source_root: str, channel: str) -> Optional[str]:
    if sys.platform != "win32":
        return "The fleet monitor runs on Windows VPUs only."
    if channel != "dev":
        return "Opting in is only available on the dev channel for now."
    if not is_admin():
        return "Pulse isn't running as administrator. Restart Pulse and choose Yes when Windows asks."
    if fingerprint(source_root) is None:
        return "This Pulse build has no fleet monitor."
    if not os.path.isfile(os.path.join(source_root, "app", "python", "python.exe")):
        return "This Pulse install has no embedded Python. Launch Pulse from the launcher once."
    return None


def enroll(source_root: str, channel: str) -> dict:
    """Copy this build into the monitor folder, register the task there and run
    the first tick. Safe to repeat: it's also how the copy is refreshed."""
    err = _guard(source_root, channel)
    if err:
        return {"ok": False, "error": err}
    if vpu_running():
        return {"ok": False, "error": "An event is live on this VPU (vpu.exe is running). Try again after it ends."}
    old = query_task()
    steps = []
    try:
        if old:
            _stop_task()
            steps.append("Paused the monitor task.")
        os.makedirs(MONITOR_ROOT, exist_ok=True)
        for d in COPY_DIRS:
            err = _robocopy(os.path.join(source_root, d), os.path.join(MONITOR_ROOT, d))
            if err:
                raise RuntimeError(err)
        for f in COPY_FILES:
            src = os.path.join(source_root, f)
            if os.path.isfile(src):
                with open(src, "rb") as a, open(os.path.join(MONITOR_ROOT, f), "wb") as b:
                    b.write(a.read())
        steps.append("Copied this Pulse build to " + MONITOR_ROOT + ".")
        carried = _carry_state(old.get("installDir") if old else None)
        if carried:
            steps.append(f"Kept the monitor's history from {old['installDir']} ({carried} files).")
        build = {"fingerprint": fingerprint(MONITOR_ROOT), "version": _read_text(os.path.join(source_root, "VERSION")),
                 "copiedAt": time.time(), "source": source_root}
        with open(os.path.join(MONITOR_ROOT, BUILD_FILE), "w", encoding="utf-8") as fh:
            json.dump(build, fh, indent=2)
        err = _lock_down(MONITOR_ROOT)
        if err:
            raise RuntimeError(err)
        code, lines = _run_installer(["-Force", "-RunNow"])
        steps.extend(lines)
        if code != 0:
            raise RuntimeError("The installer failed: " + (" ".join(lines[-2:]) or f"exit {code}"))
    except Exception as e:
        # The installer re-enables the task; if it never ran, leave the old one
        # running rather than disabled.
        if old:
            _run(["schtasks", "/Change", "/TN", TASK_NAME, "/ENABLE"], timeout=20)
        return {"ok": False, "error": str(e), "steps": steps}
    return {"ok": True, "steps": steps}


def unenroll() -> dict:
    """Remove the task and what enroll copied. Anything else in the folder
    (someone's files) is left, and so is the folder then."""
    if sys.platform != "win32":
        return {"ok": False, "error": "The fleet monitor runs on Windows VPUs only."}
    if not is_admin():
        return {"ok": False, "error": "Pulse isn't running as administrator. Restart Pulse and choose Yes when Windows asks."}
    task = query_task()
    steps = []
    if task:
        _stop_task()
    script = os.path.join(MONITOR_ROOT, "deploy", "Install-PulseMonitor.ps1")
    if os.path.isfile(script):
        code, lines = _run_installer(["-Uninstall", "-Purge"])
        steps.extend(lines)
        if code != 0:
            return {"ok": False, "error": "The installer failed: " + " ".join(lines[-2:]), "steps": steps}
    elif task:
        _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], timeout=20)
        steps.append(f"Removed {TASK_NAME}.")
    import shutil
    for d in COPY_DIRS:
        shutil.rmtree(os.path.join(MONITOR_ROOT, d), ignore_errors=True)
    for f in COPY_FILES + (BUILD_FILE, "pulse-monitor-event.json", "pulse-monitor-event.json.tmp"):
        try:
            os.remove(os.path.join(MONITOR_ROOT, f))
        except OSError:
            pass
    try:
        left = os.listdir(MONITOR_ROOT)
    except OSError:
        left = []
    if left:
        steps.append(f"Left {len(left)} other item(s) in {MONITOR_ROOT}.")
    else:
        try:
            os.rmdir(MONITOR_ROOT)
            steps.append(f"Removed {MONITOR_ROOT}.")
        except OSError:
            pass
    if task and task.get("installDir") and task["installDir"].rstrip("\\").lower() != MONITOR_ROOT.lower():
        steps.append(f"The task had been running from {task['installDir']}; its files there were left alone.")
    return {"ok": True, "steps": steps}


def refresh(source_root: str, channel: str) -> Optional[dict]:
    """At a launch: bring an enrolled unit's copy up to this build. Does
    nothing unless the monitor runs from its folder and holds another build.
    Never during an event: the copy is a burst of disk work."""
    if channel != "dev" or sys.platform != "win32" or not is_admin():
        return None
    task = query_task()
    if not task or (task.get("installDir") or "").rstrip("\\").lower() != MONITOR_ROOT.lower():
        return None
    src = fingerprint(source_root)
    if src is None or _read_json(os.path.join(MONITOR_ROOT, BUILD_FILE)).get("fingerprint") == src:
        return None
    if vpu_running():
        return {"ok": False, "error": "Skipped: an event is live."}
    return enroll(source_root, channel)
