"""The fleet agent's runner: what the scheduled task runs every 5 minutes (PV-49).

    <root>\\runtime\\python\\python.exe <root>\\agent_runner.py

Enrolling a unit copies this file to <root>\\agent_runner.py (root is
C:\\PulseFleetMonitor). An update never replaces it: it's the part that has to
work for an update to be undone, so it stays small, stdlib only, and changes
only with a new enroll.

    <root>\\agent_runner.py       this file
    <root>\\runtime\\python\\       the embedded Python, shared by both slots
    <root>\\runtime\\requirements.txt   the packages that runtime has
    <root>\\slots\\a, slots\\b      two Pulse.Web trees (a release zip each)
    <root>\\agent-slots.json      which slot runs, and any update on probation
    <root>\\agent-update.json     the last update's outcome; posts report it
    <root>\\pulse-monitor-*       the monitor's state, queue and logs

Each tick:

  1. Run the active slot's app\\monitor_once.py, passing <root> as its data
     folder (PULSE_MONITOR_DATA), so state outlives a slot.
  2. If that slot is new (on probation): the first tick with no event live is
     a forced full pass, and three clean ticks commit it ("applied"). A tick
     that fails, crashes or never finishes switches back to the previous slot
     ("rolled-back"), and that version and hash are never tried again until
     fleet control names another target.
  3. Otherwise, if fleet control (the check-in reply, kept in the monitor's
     queue file) names another build, and no event is live: download it from
     the fixed URL below, check its SHA-256 against the pin, unpack it into
     the other slot and switch. The next tick starts its probation.

The URL is built here, from the version alone: fleet control can only pick
among published agent-v* releases of playon/pulse, and a zip that doesn't
match the pinned hash is refused. A download that fails for a network reason
is retried after an hour; a zip that fails a check is not retried.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

RELEASE_URL = "https://github.com/playon/pulse/releases/download/agent-v{version}/pulse-agent-{version}.zip"
SLOTS_FILE = "agent-slots.json"
UPDATE_FILE = "agent-update.json"          # pulse_agent.UPDATE_FILE
QUEUE_FILE = "pulse-monitor-checkin-queue.json"
MARKER_FILE = "agent-tick.running"
LOG_FILE = "agent-runner.log"
DOWNLOAD_FILE = "agent-download.tmp"
SLOT_NAMES = ("a", "b")

VERSION_RE = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,6}$")   # the Worker's TARGET_VERSION_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROBATION_CLEAN_TICKS = 3
TICK_TIMEOUT_SECONDS = 240                  # the task kills everything at 300
# An update after a tick that took longer than this waits for a quicker
# tick, so the download and unpack fit inside the task's 300 s.
UPDATE_AFTER_TICK_MAX_SECONDS = 120
DOWNLOAD_TIMEOUT_SECONDS = 60
MAX_ZIP_BYTES = 64 * 1024 * 1024
MAX_UNPACKED_BYTES = 128 * 1024 * 1024
RETRY_AFTER_SECONDS = 3600
LOG_MAX_BYTES = 512 * 1024
REQUIRED_FILES = ("app/monitor_once.py", "app/main.py", "app/pulse_agent/VERSION", "app/requirements.txt")

_CREATE_NO_WINDOW = 0x08000000


class Rejected(Exception):
    """A zip that fails a check: never retried for this version and hash."""


# ── Small file helpers ───────────────────────────────────────────────────────

def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def log(root: str, msg: str) -> None:
    path = os.path.join(root, LOG_FILE)
    try:
        if os.path.getsize(path) > LOG_MAX_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + msg + "\n")
    except OSError:
        pass


def slot_dir(root: str, name: str) -> str:
    return os.path.join(root, "slots", name)


def slot_version(root: str, name: str) -> str:
    return _read_text(os.path.join(slot_dir(root, name), "app", "pulse_agent", "VERSION"))


def report(root: str, status: str, version: str, error: str = "", from_version: str = "") -> None:
    """The outcome the monitor's posts carry as agentUpdate (for a day)."""
    rec = {"status": status, "version": version, "from": from_version or None, "at": time.time()}
    if error:
        rec["error"] = error[:256]
    try:
        _write_json(os.path.join(root, UPDATE_FILE), rec)
    except OSError:
        pass
    log(root, f"update {status}: {from_version or '?'} -> {version}" + (f" ({error})" if error else ""))


# ── The environment: an event, a tick, the network ───────────────────────────

def event_live() -> bool:
    """Is VPU.exe running? Never update, or force a pass, during an event."""
    if sys.platform != "win32":
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq vpu.exe", "/NH", "/FO", "CSV"],
                           capture_output=True, text=True, timeout=20, creationflags=_CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return True                        # can't tell: assume live, do nothing risky
    return "vpu.exe" in (r.stdout or "").lower()


def run_slot(root: str, name: str, args: list) -> tuple:
    """Run one monitor tick from a slot. (ok, note)."""
    script = os.path.join(slot_dir(root, name), "app", "monitor_once.py")
    if not os.path.isfile(script):
        return False, f"slot {name} has no app/monitor_once.py"
    env = dict(os.environ, PULSE_MONITOR_DATA=root)
    kw = {"env": env, "cwd": os.path.dirname(script), "timeout": TICK_TIMEOUT_SECONDS,
          "capture_output": True, "text": True}
    if sys.platform == "win32":
        kw["creationflags"] = _CREATE_NO_WINDOW
    try:
        r = subprocess.run([sys.executable, script] + list(args), **kw)
    except subprocess.TimeoutExpired:
        return False, f"the tick ran over {TICK_TIMEOUT_SECONDS} s"
    except OSError as e:
        return False, f"couldn't start the tick: {e}"
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()
        return False, f"exit {r.returncode}" + (f": {tail[-1][:200]}" if tail else "")
    return True, "ok"


def fetch(url: str, dest: str) -> str:
    """Download url to dest, returning its SHA-256. Raises OSError on a
    network failure, Rejected when it's too big."""
    h = hashlib.sha256()
    n = 0
    req = urllib.request.Request(url, headers={"User-Agent": "Pulse-agent-runner"})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            n += len(chunk)
            if n > MAX_ZIP_BYTES:
                raise Rejected(f"the download is over {MAX_ZIP_BYTES // (1024 * 1024)} MB")
            h.update(chunk)
            out.write(chunk)
    return h.hexdigest()


# ── Fleet control and the slots ──────────────────────────────────────────────

def target(root: str):
    """The build fleet control names: {version, sha256}, or None."""
    ctl = _read_json(os.path.join(root, QUEUE_FILE)).get("control")
    agent = ctl.get("agent") if isinstance(ctl, dict) else None
    if not isinstance(agent, dict):
        return None
    version, sha = agent.get("version"), agent.get("sha256")
    if not (isinstance(version, str) and VERSION_RE.match(version)
            and isinstance(sha, str) and SHA256_RE.match(sha)):
        return None
    return {"version": version, "sha256": sha}


def load_slots(root: str) -> dict:
    st = _read_json(os.path.join(root, SLOTS_FILE))
    if st.get("active") not in SLOT_NAMES:
        # No record (or a broken one): run whichever slot exists, a first.
        st = {"active": next((n for n in SLOT_NAMES if os.path.isdir(slot_dir(root, n))), "a")}
    st.setdefault("previous", None)
    st.setdefault("probation", None)
    for key in ("slots", "blocked", "retryAt"):
        if not isinstance(st.get(key), dict):
            st[key] = {}
    return st


def save_slots(root: str, st: dict) -> None:
    _write_json(os.path.join(root, SLOTS_FILE), st)


def _requirements(text: str) -> list:
    return sorted(line.strip().lower() for line in text.splitlines()
                  if line.strip() and not line.strip().startswith("#"))


def _safe_members(zf: zipfile.ZipFile) -> list:
    members, total = [], 0
    for info in zf.infolist():
        name = info.filename
        parts = name.replace("\\", "/").split("/")
        if name.startswith(("/", "\\")) or ":" in name or ".." in parts:
            raise Rejected(f"the zip has an unsafe path: {name[:80]}")
        total += info.file_size
        if total > MAX_UNPACKED_BYTES:
            raise Rejected("the zip unpacks to more than 128 MB")
        members.append(info)
    return members


def stage(root: str, zip_path: str, version: str, name: str) -> None:
    """Unpack a checked zip into slot `name`, replacing what's there."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        raise Rejected(f"not a zip: {e}")
    with zf:
        members = _safe_members(zf)
        names = {m.filename for m in members}
        missing = [f for f in REQUIRED_FILES if f not in names]
        if missing:
            raise Rejected("the zip has no " + ", ".join(missing))
        inside = zf.read("app/pulse_agent/VERSION").decode("utf-8", "replace").strip()
        if inside != version:
            raise Rejected(f"the zip says it is {inside}, not {version}")
        have = _read_text(os.path.join(root, "runtime", "requirements.txt"))
        need = zf.read("app/requirements.txt").decode("utf-8", "replace")
        if not have or _requirements(have) != _requirements(need):
            raise Rejected("it needs Python packages this unit's runtime doesn't have: opt the unit in again from Pulse")
        dest = slot_dir(root, name)
        tmp = dest + ".new"
        shutil.rmtree(tmp, ignore_errors=True)
        zf.extractall(tmp, members)
    shutil.rmtree(dest, ignore_errors=True)
    if os.path.exists(dest):
        raise OSError(f"couldn't clear slot {name}")
    os.replace(tmp, dest)


def _other(name: str) -> str:
    return "b" if name == "a" else "a"


def _switch(root: str, st: dict, new: str, version: str, sha: str) -> None:
    old = st["active"]
    st["previous"], st["active"] = old, new
    st["probation"] = {"version": version, "sha256": sha, "from": slot_version(root, old),
                       "needsFullPass": True, "clean": 0, "since": time.time()}
    save_slots(root, st)
    log(root, f"switched to slot {new} ({version}); on probation")


def rollback(root: str, st: dict, why: str) -> None:
    p = st.get("probation") or {}
    bad, good = st["active"], st.get("previous")
    key = f"{p.get('version')}:{p.get('sha256')}"
    st["blocked"][key] = "rolled back: " + why
    st["probation"] = None
    if good and os.path.isfile(os.path.join(slot_dir(root, good), "app", "monitor_once.py")):
        st["active"], st["previous"] = good, bad
        save_slots(root, st)
        report(root, "rolled-back", p.get("version") or "", why, p.get("from") or "")
    else:
        save_slots(root, st)
        report(root, "failed", p.get("version") or "", "couldn't roll back, no previous slot: " + why,
               p.get("from") or "")


def maybe_update(root: str, st: dict, now: float, *, is_event_live=event_live, download=fetch,
                 url_template: str = RELEASE_URL) -> None:
    want = target(root)
    if not want:
        return
    version, sha = want["version"], want["sha256"]
    active = st["active"]
    if (st["slots"].get(active) or {}).get("sha256") == sha:
        return                                     # already running the pinned bytes
    key = f"{version}:{sha}"
    if key in st["blocked"]:
        return
    if st["retryAt"].get(key, 0) > now:
        return
    if is_event_live():
        return
    current = slot_version(root, active)
    other = _other(active)
    if (st["slots"].get(other) or {}).get("sha256") == sha and slot_version(root, other) == version:
        _switch(root, st, other, version, sha)     # a rollback to the build still in the other slot
        return
    url = url_template.format(version=version)
    tmp = os.path.join(root, DOWNLOAD_FILE)
    log(root, f"downloading {version} from {url}")
    try:
        got = download(url, tmp)
        if got != sha:
            raise Rejected(f"its SHA-256 is {got[:12]}..., not the pinned {sha[:12]}...")
        stage(root, tmp, version, other)
    except Rejected as e:
        st["blocked"][key] = str(e)
        save_slots(root, st)
        report(root, "failed", version, str(e), current)
        return
    except (OSError, ValueError) as e:
        # The network, a full disk, a slot in use: worth another try later.
        st["retryAt"][key] = now + RETRY_AFTER_SECONDS
        save_slots(root, st)
        report(root, "failed", version, f"{type(e).__name__}: {e}", current)
        return
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    st["slots"][other] = {"version": version, "sha256": sha, "installedAt": now}
    st["retryAt"].pop(key, None)
    _switch(root, st, other, version, sha)


# ── One tick ─────────────────────────────────────────────────────────────────

def tick(root: str, argv: list, *, is_event_live=event_live, run=run_slot, download=fetch,
         url_template: str = RELEASE_URL, now=None) -> int:
    now = time.time() if now is None else now
    st = load_slots(root)
    marker = os.path.join(root, MARKER_FILE)
    if os.path.exists(marker):
        # The last tick was killed at the time limit, or Python itself died.
        try:
            os.remove(marker)
        except OSError:
            pass
        if st.get("probation"):
            rollback(root, st, "the new build's tick never finished")
    p = st.get("probation")
    dry_run = "--dry-run" in argv
    args = list(argv)
    forced = False
    if p and p.get("needsFullPass") and not dry_run and "--force" not in args and not is_event_live():
        args.append("--force")              # the new build reports in full at once
        forced = True
    try:
        with open(marker, "w") as fh:
            fh.write(str(now))
    except OSError:
        pass
    started = time.monotonic()
    ok, note = run(root, st["active"], args)
    took = time.monotonic() - started
    try:
        os.remove(marker)
    except OSError:
        pass
    if dry_run:
        return 0 if ok else 1
    if p:
        if not ok:
            rollback(root, st, note)
            return 1
        if forced:
            p["needsFullPass"] = False
        p["clean"] = int(p.get("clean") or 0) + 1
        if not p["needsFullPass"] and p["clean"] >= PROBATION_CLEAN_TICKS:
            st["probation"] = None
            save_slots(root, st)
            report(root, "applied", p.get("version") or "", "", p.get("from") or "")
        else:
            save_slots(root, st)
        return 0
    if not ok:
        log(root, f"tick failed in slot {st['active']}: {note}")
        return 1
    if took > UPDATE_AFTER_TICK_MAX_SECONDS:
        return 0
    maybe_update(root, st, now, is_event_live=is_event_live, download=download, url_template=url_template)
    return 0


def main(argv) -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    try:
        return tick(root, argv)
    except Exception as e:                  # the runner must never be what breaks a unit
        log(root, f"runner error: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
