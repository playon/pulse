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
  2. If that slot is new (on probation): the first safe update window is
     a forced full pass, and three clean ticks commit it ("applied"). A tick
     that fails, crashes or never finishes switches back to the previous slot
     ("rolled-back"), and that version and hash are never tried again until
     fleet control names another target.
  3. Otherwise, if fleet control (the check-in reply, kept in the monitor's
     queue file) names another build, and the update window is safe: download it from
     the fixed URL below, check its SHA-256 against the pin, unpack it into
     the other slot and switch. The next tick starts its probation.

The URL is built here, from the version alone: fleet control can only pick
among published agent-v* releases of playon/pulse, and a zip that doesn't
match the pinned hash is refused.

A failed update leaves the unit on the build it runs and says why in
agent-update.json. A zip that fails a check, and a build that was rolled back,
are not tried again until fleet control names a different target (clearing
it counts). A download that fails for another reason (the network, a full
disk, a slot in use) is retried after about an hour, then two, four and
eight; the fifth try gives the target up the same way. Each try is counted
before it starts, so one the task's time limit kills still counts.

A new target isn't fetched at once: each unit waits a random part of an hour
first, and retries wait a random extra part of their gap, so a fleet pin
doesn't pull the zip on every unit in the same five minutes.

Updates (including rollback switches and probation's forced full pass) wait
while VPU.exe runs, during a scheduled event, or in the 30 minutes before it.
The UTC schedule is C:\\Pixellot\\Data\\Configuration\\dashboardEvents.json;
missing, unreadable, malformed or over-three-hour-old schedules hold updates. Holds
are logged without consuming an update try. Regular monitor passes still run.

Nothing an update does outlives it: the download, a half-unpacked slot and
the slot being replaced are swept at the start of every tick (a killed runner
leaves them), a tick that runs over is killed with everything it started, and
the state file only keeps entries for the current target.
"""

from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
import zlib

# This file's own version: what the monitor's posts report as
# telemetry.runnerVersion (it reads PULSE_RUNNER_VERSION). An update never
# replaces the runner, so this says which units need enrolling again for a
# runner fix. Bump it with any change to this file. None reported: a runner
# from before PV-85's review fixes.
RUNNER_VERSION = "3"

RELEASE_URL = "https://github.com/playon/pulse/releases/download/agent-v{version}/pulse-agent-{version}.zip"
SLOTS_FILE = "agent-slots.json"
UPDATE_FILE = "agent-update.json"          # pulse_agent.UPDATE_FILE
QUEUE_FILE = "pulse-monitor-checkin-queue.json"
MARKER_FILE = "agent-tick.running"
LOG_FILE = "agent-runner.log"
DOWNLOAD_FILE = "agent-download.tmp"
STDERR_FILE = "agent-tick.stderr"           # the last tick's stderr, read for its last line
SLOT_NAMES = ("a", "b")

SCHEDULE_FILE = r"C:\Pixellot\Data\Configuration\dashboardEvents.json"
EVENT_LOOKAHEAD_SECONDS = 30 * 60
# Empty lab schedule rewritten after 60m08s (PV-82, 2026-10-22); allow three
# hourly refreshes. Not yet verified on a unit with real upcoming events.
SCHEDULE_MAX_AGE_SECONDS = 3 * 60 * 60
VERSION_RE = re.compile(r"^\d{1,4}\.\d{1,4}\.\d{1,6}$")   # the Worker's TARGET_VERSION_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROBATION_CLEAN_TICKS = 3
TASK_LIMIT_SECONDS = 300                    # Install-PulseMonitor.ps1: ExecutionTimeLimit PT5M
TICK_TIMEOUT_SECONDS = 240                  # the task kills everything at 300
# An update after a tick that took longer than this waits for a quicker
# tick, so the download and unpack fit inside the task's 300 s.
UPDATE_AFTER_TICK_MAX_SECONDS = 120
# What an update needs after the download, inside the task's limit: unpack,
# two renames, and the event check before the switch (tasklist, up to 20 s).
STAGE_RESERVE_SECONDS = 60
DOWNLOAD_TIMEOUT_SECONDS = 30              # per read: a read can block this long past the deadline
DOWNLOAD_DEADLINE_SECONDS = 120            # the whole download, at most
MIN_DOWNLOAD_SECONDS = 30                  # less time left than this: try on a later tick
FIRST_SPREAD_SECONDS = 3600                # a new target waits a random part of this
RETRY_JITTER = 0.5                         # a retry waits up to this much of its gap more
MAX_ZIP_BYTES = 64 * 1024 * 1024
MAX_UNPACKED_BYTES = 128 * 1024 * 1024
RETRY_AFTER_SECONDS = 3600                 # doubles per failure: 1, 2, 4, 8 h
MAX_TRIES = 5                              # then the target is given up, like a refused one
ERROR_MAX = 200
LOG_MAX_BYTES = 512 * 1024
REQUIRED_FILES = ("app/monitor_once.py", "app/main.py", "app/pulse_agent/VERSION", "app/requirements.txt")

_CREATE_NO_WINDOW = 0x08000000


class Rejected(Exception):
    """A zip that fails a check: never retried for this version and hash."""


def _jitter() -> float:
    """0 <= x < 1; tests replace it."""
    return random.random()


def _retry_gap(tries: int) -> float:
    return RETRY_AFTER_SECONDS * 2 ** (tries - 1) * (1 + RETRY_JITTER * _jitter())


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


_PATH_RE = re.compile(r"""(?<![A-Za-z])[A-Za-z]:[\\/][^\s'"]*|\\\\[^\s'"]+|(?<![\w:/.])/[^\s'"]+""")


def short_error(text: str) -> str:
    """An error fit to post: one line, no file paths, no computer name."""
    text = _PATH_RE.sub("<path>", str(text))
    for var in ("COMPUTERNAME", "USERNAME"):
        name = os.environ.get(var) or ""
        if len(name) >= 3:
            text = re.sub(re.escape(name), "<host>" if var == "COMPUTERNAME" else "<user>", text, flags=re.I)
    return " ".join(text.split())[:ERROR_MAX]


def report(root: str, status: str, version: str, error: str = "", from_version: str = "") -> None:
    """The outcome the monitor's posts carry as agentUpdate (for a day)."""
    rec = {"status": status, "version": version, "from": from_version or None, "at": time.time()}
    error = short_error(error) if error else ""
    if error:
        rec["error"] = error
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
    return r.returncode != 0 or "vpu.exe" in (r.stdout or "").lower()


def schedule_hold() -> str:
    """Read the whole upcoming-events list; absent Z also means UTC."""
    now = time.time()
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8-sig") as fh:
            if now - os.fstat(fh.fileno()).st_mtime > SCHEDULE_MAX_AGE_SECONDS:
                return "schedule unknown"
            events = json.load(fh)
        if not isinstance(events, list):
            return "schedule unknown"
        upcoming = []
        for event in events:
            times = []
            for field in ("start", "end"):
                value = event[field]["$date"]
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                times.append(parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp())
            start, end = times
            if end < start:
                return "schedule unknown"
            if start <= now <= end or now <= start <= now + EVENT_LOOKAHEAD_SECONDS:
                upcoming.append(start)
        if upcoming:
            at = datetime.fromtimestamp(min(upcoming), timezone.utc).isoformat().replace("+00:00", "Z")
            return "event at " + at
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return "schedule unknown"
    return ""


def update_allowed(root: str, is_event_live) -> bool:
    reason = "event live" if is_event_live() else schedule_hold()
    if reason:
        log(root, "held: " + reason)
        return False
    return True


def _kill_tree(proc) -> None:
    """Kill a tick and everything it started (PowerShell collectors)."""
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                           timeout=30, creationflags=_CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(proc.pid, 9)
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


def _last_line(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 4096))
            tail = fh.read().decode("utf-8", "replace").strip().splitlines()
    except OSError:
        return ""
    return tail[-1] if tail else ""


def run_slot(root: str, name: str, args: list, timeout: float = TICK_TIMEOUT_SECONDS) -> tuple:
    """Run one monitor tick from a slot. (ok, note)."""
    script = os.path.join(slot_dir(root, name), "app", "monitor_once.py")
    if not os.path.isfile(script):
        return False, f"slot {name} has no app/monitor_once.py"
    env = dict(os.environ, PULSE_MONITOR_DATA=root, PULSE_RUNNER_VERSION=RUNNER_VERSION)
    kw = {"env": env, "cwd": os.path.dirname(script), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = _CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True      # its own group, so a kill takes its children too
    err_path = os.path.join(root, STDERR_FILE)
    try:
        # stderr goes to a file, not memory: one file, rewritten each tick.
        # If it can't be opened (something still holds it), the tick runs
        # without it rather than not at all.
        try:
            err = open(err_path, "wb")
        except OSError:
            err, err_path = subprocess.DEVNULL, ""
        try:
            proc = subprocess.Popen([sys.executable, script] + list(args), stderr=err, **kw)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                proc.wait()
                return False, f"the tick ran over {int(timeout)} s"
        finally:
            if err is not subprocess.DEVNULL:
                err.close()
    except OSError as e:
        return False, f"couldn't start the tick: {e.strerror or type(e).__name__}"
    if code != 0:
        tail = _last_line(err_path) if err_path else ""
        return False, f"exit {code}" + (f": {tail}" if tail else "")
    return True, "ok"


def fetch(url: str, dest: str, deadline=None) -> str:
    """Download url to dest, returning its SHA-256. Raises OSError on a
    network failure (an HTTP error, a dropped connection, too slow), Rejected
    when it's too big. `deadline` (time.monotonic()) is when it must stop;
    a read can run DOWNLOAD_TIMEOUT_SECONDS past it, which the caller allows
    for. Every socket and file is closed on every path."""
    h = hashlib.sha256()
    n = 0
    started = time.monotonic()
    cap = started + DOWNLOAD_DEADLINE_SECONDS
    deadline = cap if deadline is None else min(deadline, cap)
    req = urllib.request.Request(url, headers={"User-Agent": "Pulse-agent-runner"})
    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp, open(dest, "wb") as out:
            length = resp.headers.get("Content-Length")
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                n += len(chunk)
                if n > MAX_ZIP_BYTES:
                    raise Rejected(f"the download is over {MAX_ZIP_BYTES // (1024 * 1024)} MB")
                if time.monotonic() > deadline:
                    raise OSError(f"the download took over {int(deadline - started)} s")
                h.update(chunk)
                out.write(chunk)
            # read(n) returns b"" when the connection drops early, as if the
            # file had ended: without this a cut download fails the hash
            # check and is refused for good instead of retried.
            if length is not None and length.isdigit() and n != int(length):
                raise OSError(f"the download broke off at {n} of {length} bytes")
    except urllib.error.HTTPError as e:
        e.close()                           # an HTTPError holds the response open
        raise OSError(f"HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise OSError(f"couldn't reach the release: {getattr(e.reason, 'strerror', None) or e.reason}") from None
    except http.client.HTTPException as e:
        # IncompleteRead and friends: a dropped connection, not an OSError.
        raise OSError(f"the download broke off: {type(e).__name__}") from None
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
    for key in ("slots", "blocked", "retryAt", "tries"):
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
    """Unpack a checked zip into slot `name`, replacing what's there.

    It unpacks beside the slot (<slot>.new), moves the old slot aside
    (<slot>.old), moves the new one in, then deletes the old. Each move is
    one rename, so a failure or a kill leaves either the old slot or the new
    one in place, never half of one; sweep() clears the leftovers."""
    dest = slot_dir(root, name)
    tmp, old = dest + ".new", dest + ".old"
    try:
        zf = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError, EOFError) as e:
        raise Rejected(f"not a zip: {type(e).__name__}")
    try:
        with zf:
            members = _safe_members(zf)
            names = {m.filename for m in members}
            missing = [f for f in REQUIRED_FILES if f not in names]
            if missing:
                raise Rejected("the zip has no " + ", ".join(missing))
            inside = zf.read("app/pulse_agent/VERSION").decode("utf-8", "replace").strip()
            if inside != version:
                raise Rejected(f"the zip says it is {inside[:20]}, not {version}")
            have = _read_text(os.path.join(root, "runtime", "requirements.txt"))
            need = zf.read("app/requirements.txt").decode("utf-8", "replace")
            if not have or _requirements(have) != _requirements(need):
                raise Rejected("it needs Python packages this unit's runtime doesn't have: opt the unit in again from Pulse")
            shutil.rmtree(tmp, ignore_errors=True)
            zf.extractall(tmp, members)
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Rejected(f"the zip is damaged: {type(e).__name__}")
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    shutil.rmtree(old, ignore_errors=True)
    try:
        if os.path.exists(dest):
            os.replace(dest, old)           # fails whole if a file in it is open
        os.replace(tmp, dest)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        if os.path.isdir(old) and not os.path.exists(dest):
            os.replace(old, dest)           # put the old slot back
        raise
    shutil.rmtree(old, ignore_errors=True)


def sweep(root: str) -> None:
    """Clear what a killed update leaves: the download, a half-unpacked slot,
    a slot moved aside, a half-written state file."""
    for path in (os.path.join(root, DOWNLOAD_FILE), os.path.join(root, SLOTS_FILE + ".tmp"),
                 os.path.join(root, UPDATE_FILE + ".tmp")):
        try:
            os.remove(path)
        except OSError:
            pass
    for name in SLOT_NAMES:
        for suffix in (".new", ".old"):
            path = slot_dir(root, name) + suffix
            if os.path.isdir(path):
                if suffix == ".old" and not os.path.exists(slot_dir(root, name)):
                    try:
                        os.replace(path, slot_dir(root, name))   # killed between the two renames
                        continue
                    except OSError:
                        pass
                shutil.rmtree(path, ignore_errors=True)


def _other(name: str) -> str:
    return "b" if name == "a" else "a"


def _switch(root: str, st: dict, new: str, version: str, sha: str) -> None:
    old = st["active"]
    st["previous"], st["active"] = old, new
    st["probation"] = {"version": version, "sha256": sha, "from": slot_version(root, old),
                       "needsFullPass": True, "clean": 0, "since": time.time()}
    save_slots(root, st)
    log(root, f"switched to slot {new} ({version}); on probation")


def rollback(root: str, st: dict, why: str, *, is_event_live=event_live) -> None:
    p = st.get("probation") or {}
    if not update_allowed(root, is_event_live):
        p["rollback"] = why
        save_slots(root, st)
        return
    bad, good = st["active"], st.get("previous")
    key = f"{p.get('version')}:{p.get('sha256')}"
    st["blocked"][key] = short_error("rolled back: " + why)
    st["probation"] = None
    if good and os.path.isfile(os.path.join(slot_dir(root, good), "app", "monitor_once.py")):
        st["active"], st["previous"] = good, bad
        save_slots(root, st)
        report(root, "rolled-back", p.get("version") or "", why, p.get("from") or "")
    else:
        save_slots(root, st)
        report(root, "failed", p.get("version") or "", "couldn't roll back, no previous slot: " + why,
               p.get("from") or "")


def _forget_other_targets(st: dict, key: str) -> bool:
    """Keep refusals and retry times only for the current target: a new
    target (or none) is what lets an old one be tried again, and it keeps
    the state file from growing."""
    changed = False
    for field in ("blocked", "retryAt", "tries"):
        for k in [k for k in st[field] if k != key]:
            del st[field][k]
            changed = True
    return changed


def _give_up(root: str, st: dict, key: str, version: str, current: str, why: str) -> None:
    st["blocked"][key] = short_error(why)
    st["retryAt"].pop(key, None)
    st["tries"].pop(key, None)
    save_slots(root, st)
    report(root, "failed", version, why, current)


def maybe_update(root: str, st: dict, now: float, *, is_event_live=event_live, download=fetch,
                 url_template: str = RELEASE_URL, deadline=None) -> None:
    """`deadline` (time.monotonic()) is when the download and unpack must be
    done for the switch to fit inside the task's time limit."""
    want = target(root)
    key = f"{want['version']}:{want['sha256']}" if want else ""
    if _forget_other_targets(st, key):
        save_slots(root, st)
    if not want:
        return
    version, sha = want["version"], want["sha256"]
    active = st["active"]
    if (st["slots"].get(active) or {}).get("sha256") == sha:
        return                                     # already running the pinned bytes
    if key in st["blocked"]:
        return
    if not update_allowed(root, is_event_live):
        return
    current = slot_version(root, active)
    other = _other(active)
    in_other = (st["slots"].get(other) or {}).get("sha256") == sha and slot_version(root, other) == version
    if key not in st["retryAt"] and key not in st["tries"] and not in_other:
        # A new target: wait a random part of an hour, so a fleet pin doesn't
        # have every unit download in the same five minutes.
        st["retryAt"][key] = now + FIRST_SPREAD_SECONDS * _jitter()
        save_slots(root, st)
    if st["retryAt"].get(key, 0) > now:
        return
    if in_other:
        _switch(root, st, other, version, sha)     # a rollback to the build still in the other slot
        return
    deadline = time.monotonic() + TASK_LIMIT_SECONDS - STAGE_RESERVE_SECONDS if deadline is None else deadline
    until = deadline - DOWNLOAD_TIMEOUT_SECONDS    # a read can block that long past the last check
    if until - time.monotonic() < MIN_DOWNLOAD_SECONDS:
        log(root, f"not enough of the task's time left to download {version}; a later tick will")
        return
    tries = int(st["tries"].get(key) or 0)
    if tries >= MAX_TRIES:
        # The last try was counted but never reported: the task's time limit
        # (or a crash) stopped it part way.
        _give_up(root, st, key, version, current,
                 f"gave up after {tries} failed tries; the last never finished (the task's time limit?)")
        return
    # Count this try before it starts, so one the time limit kills still counts.
    tries += 1
    st["tries"][key] = tries
    st["retryAt"][key] = now + _retry_gap(tries)
    url = url_template.format(version=version)
    tmp = os.path.join(root, DOWNLOAD_FILE)
    log(root, f"downloading {version} from {url} (try {tries} of {MAX_TRIES})")
    # The other slot is about to be replaced: stop vouching for what's in it
    # until it's known whether it was (stage leaves it whole either way).
    kept = st["slots"].pop(other, None)
    save_slots(root, st)
    try:
        got = download(url, tmp, until)
        if got != sha:
            raise Rejected(f"its SHA-256 is {got[:12]}..., not the pinned {sha[:12]}...")
        stage(root, tmp, version, other)
    except Rejected as e:
        _give_up(root, st, key, version, current, str(e))
        return
    except (OSError, ValueError) as e:
        # The network, a full disk, a slot in use: worth another try later
        # (already booked above, backing off so a unit on a bad link doesn't
        # pull 64 MB an hour), giving up after five, until the target changes.
        cause = f"{type(e).__name__}: {e.strerror or e}" if isinstance(e, OSError) else f"{type(e).__name__}: {e}"
        if tries >= MAX_TRIES:
            _give_up(root, st, key, version, current,
                     f"gave up after {tries} failed tries; the last: {short_error(cause)}")
        else:
            report(root, "failed", version, cause, current)
        return
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
        if (kept and st["active"] == active and other not in st["slots"]
                and slot_version(root, other) == kept.get("version")
                and os.path.isfile(os.path.join(slot_dir(root, other), "app", "monitor_once.py"))):
            st["slots"][other] = kept                  # the failed update never touched it
            save_slots(root, st)
    st["slots"][other] = {"version": version, "sha256": sha, "installedAt": now}
    st["retryAt"].pop(key, None)
    st["tries"].pop(key, None)
    if not update_allowed(root, is_event_live):
        # An event started during the download: keep the new build in the
        # other slot and switch to it on the first safe update window.
        save_slots(root, st)
        return
    _switch(root, st, other, version, sha)


# ── One tick ─────────────────────────────────────────────────────────────────

def tick(root: str, argv: list, *, is_event_live=event_live, run=run_slot, download=fetch,
         url_template: str = RELEASE_URL, now=None) -> int:
    began = time.monotonic()                # the task's limit counts from about here
    now = time.time() if now is None else now
    if "--dry-run" not in argv:
        sweep(root)
    st = load_slots(root)
    marker = os.path.join(root, MARKER_FILE)
    if os.path.exists(marker):
        # The last tick was killed at the time limit, or Python itself died.
        try:
            os.remove(marker)
        except OSError:
            pass
        if st.get("probation"):
            rollback(root, st, "the new build's tick never finished", is_event_live=is_event_live)
    elif (st.get("probation") or {}).get("rollback"):
        rollback(root, st, st["probation"]["rollback"], is_event_live=is_event_live)
    p = st.get("probation")
    dry_run = "--dry-run" in argv
    args = list(argv)
    forced = False
    if p and p.get("needsFullPass") and not dry_run and not p.get("rollback"):
        if update_allowed(root, is_event_live):
            if "--force" not in args:
                args.append("--force")      # only probation's safe full pass
            forced = True
        else:
            args = [arg for arg in args if arg != "--force"]
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
            rollback(root, st, note, is_event_live=is_event_live)
            return 1
        if p.get("rollback"):
            return 0                       # keep regular passes running until rollback is safe
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
    maybe_update(root, st, now, is_event_live=is_event_live, download=download, url_template=url_template,
                 deadline=began + TASK_LIMIT_SECONDS - STAGE_RESERVE_SECONDS)
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
