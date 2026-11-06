"""What a live event is doing, read from the files Pixellot already writes.

The scheduled monitor never runs a check while VPU.exe is running: a pass
starts PowerShell collectors, and nothing may compete with a game encode. This
module is the exception, built to the same rule. It starts no process, opens
no socket to the cameras or the venue network, and imports nothing outside
the standard library (main.py and its FastAPI stack are never loaded during an
event). Each tick it reads:

  * the part of VPU.exe's log written since the last tick (at most
    MAX_READ_BYTES), for the stream's own story: which servers it dialed,
    every failed attempt, failover, the moment it connected, VPU.exe
    restarts, dropped frames, and the event's close reason;
  * the last few KB of Pixellot's AgentBenchmarks CSV (one row per 10 s), for
    camera link speeds, CPU, GPU and free memory;
  * the newest folder name in the recorded-events directory, which carries the
    Pixellot event id. Unity resolves that id to the NFHS game and broadcast
    (GET /v2/pixellots/broadcasts/<id>, no auth), so the id is all Pulse sends.

From that it keeps one record per event (`state["event"]`) and a verdict:
on-air, connecting, stream-failing, restart-loop or camera-link-down. The
caller posts at the event's start, when a verdict is confirmed by two reads in
a row, and at its end with a summary: did it go on air, for how long, and if
not, why.

Not every VPU.exe run is an event. Head setup (a tech pressing "start recorder
in manual mode" in the Agent GUI) runs VPU.exe with no event and no stream.
Its start reason says so, and the record is then a setup run: kind "setup",
verdict "setup", no event id (PV-48).

Line shapes (VPU.exe 5.27-5.37; "Level | yyyy-MM-dd HH:mm:ss.fff |Module
|File(line) |Function |Message", tab-separated), from Get-VpuStreamLog.ps1:
  urlToStreamWriter for urls zixi://...|zixi://...|rtmp://...   the chain
  Failed connecting to <url>, because ... return value: -11     one failed try
  onStreamDisconnect: <url> failed, move to <url>               failover
  Created Zixi stream: HD_Writer0_Stream0                       on air (Zixi)
  Video Connection rtmp://... Created Successfuly               on air (RTMP)
  START NEW LOG SESSION >>> VPU.exe - Version: x                (re)started
  Agent Start Reason:  event command. Event: Name[...] _id[...]  an event run
  Agent Start Reason: start recorder in manual mode was pressed  head setup
  CloseUnit ... Reason: "stopStreaming event command"           event ended
  LEAKY BUCKET Debayer dropping queueSize ...                   frames dropped
"""

import csv
import io
import os
import re
import time
from typing import Optional

LOG_DIR = r"C:\Pixellot\Data\Log"
EVENTS_DIR = r"D:\recordedEvents"
MAX_READ_BYTES = 4 * 1024 * 1024    # per tick; a busier log is skipped to its tail
CATCH_UP_BYTES = 96 * 1024 * 1024   # once, when the monitor starts mid-event
BENCH_TAIL_BYTES = 16 * 1024        # ~40 rows of AgentBenchmarks
FAILING_AFTER_SECONDS = 120         # failed tries for this long with no connect
RESTART_LOOP_COUNT = 2              # VPU.exe restarts within one event
CAMERA_SLOW_FPS = 15.0              # a camera below this is degrading the picture
SCHEMA = "pulse.event/v1"
SC3_SETTINGS = r"C:\ProgramData\Sportzcast LLC\ScoreConnectIII\Files\settings.json"
ENDED_EARLY_SECONDS = 600           # closed this long before the scheduled end
SCOREBUG_STALE_SECONDS = 600        # scorebug unchanged this long, with no data
SPORT_WORDS = ("baseball", "basketball", "football", "hockey", "lacrosse", "soccer", "softball",
               "volleyball", "wrestling", "swimming", "waterpolo", "rodeo")

_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})")
_EVENT_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_p_([0-9A-Za-z]{8,40})$")
# The event's folder, as VPU.exe logs it when it copies the calibration in:
# "...recordedEvents/2026-10-14_p_6ad018b2ec5d0313d04118a6/..." or, for
# Pixellot's own daily test, "..._p_DAILYTEST20261014/...".
_EVENT_IN_LOG_RE = re.compile(r"recordedEvents[\\/]\d{4}-\d{2}-\d{2}_p_([0-9A-Za-z]{8,40})")
# The per-second status line: the values the reader keeps from its newest one.
_STATUS_KEYS = {
    "CFPS": "Avr", "Camera0AvgFps": "Lst", "Camera1AvgFps": "Lst", "Camera2AvgFps": "Lst",
    "Camera0LowFpsCount": "Lst", "Camera1LowFpsCount": "Lst", "Camera2LowFpsCount": "Lst",
    "HD_Writer0_Stream0_FPS": "Lst", "HD_Writer0_Stream0_Fails": "Lst",
    "HD_Writer0_Stream0_UrlPort": "Lst", "HD_WritersDroppedFrames": "Lst",
    "HD_WritersSkippedFrames": "Lst", "Debayer_Drops": "Lst", "Health": "Lst",
    "CumulativeNetworkIssues": "Lst", "CamerasHardResetCount": "Lst",
    "CamerasSoftResetCount": "Lst",
    # Scorebug: data arriving from the scoreboard, and seconds since the
    # graphics last changed (6493's static test scorebug read 0/s and an
    # ever-growing delta for the whole event).
    "ScoreboardDataFrequencyPerSecond": "Lst", "GraphicsTimestampsDelta": "Avr",
}


def _line_time(line: str) -> Optional[float]:
    m = _TIME_RE.search(line)
    if not m:
        return None
    try:
        return time.mktime(time.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, OverflowError):
        return None


def _newest(dirpath: str, prefix: str, suffix: str):
    """(path, size) of the most recently written matching file, or None.
    One directory listing; no file is opened."""
    best = None
    try:
        with os.scandir(dirpath) as it:
            for e in it:
                n = e.name
                if not (n.startswith(prefix) and n.endswith(suffix)) or not e.is_file():
                    continue
                st = e.stat()
                if best is None or st.st_mtime > best[2]:
                    best = (e.path, st.st_size, st.st_mtime)
    except OSError:
        return None
    return (best[0], best[1]) if best else None


def _read_new(path: str, offset: int, size: int):
    """Text appended since `offset`, at most MAX_READ_BYTES of it, and the new
    offset. Reads with the file shared, so VPU.exe keeps writing."""
    if size < offset:           # truncated or replaced: start over
        offset = 0
    start = max(offset, size - MAX_READ_BYTES)
    skipped = start > offset
    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(size - start)
    except OSError:
        return "", offset, False
    if skipped:                 # landed mid-line: drop the partial first line
        cut = data.find(b"\n")
        data = data[cut + 1:] if cut >= 0 else b""
    # Keep a trailing partial line for the next read.
    end = data.rfind(b"\n")
    if end < 0:
        return "", start, skipped
    return data[:end + 1].decode("utf-8", "replace"), start + end + 1, skipped


def _catch_up(path: str, size: int):
    """For a reader that starts mid-event (the monitor was installed or
    updated during a game): the marker lines of VPU.exe's current session,
    from its START NEW LOG SESSION line to now, without the per-second status
    lines. One pass, at most CATCH_UP_BYTES, done once per such event.
    Returns (text, offset to continue from)."""
    marker = b"START NEW LOG SESSION"
    start = None
    try:
        with open(path, "rb") as fh:
            pos = size
            floor = max(0, size - CATCH_UP_BYTES)
            chunk = 1024 * 1024
            while pos > floor and start is None:
                lo = max(floor, pos - chunk)
                fh.seek(lo)
                buf = fh.read(pos - lo + len(marker))
                i = buf.rfind(marker)
                if i >= 0:
                    start = lo + i
                pos = lo
            fh.seek(start if start is not None else floor)
            keep = []
            for raw in fh:
                if fh.tell() > size:
                    break
                if b"StatusReporter::reportStatus" in raw:
                    continue
                keep.append(raw.decode("utf-8", "replace"))
    except OSError:
        return "", size
    # Back to the line start of the session marker.
    text = "".join(keep)
    j = text.find("START NEW LOG SESSION")
    if j > 0:
        text = text[text.rfind("\n", 0, j) + 1:]
    return text, size


_START_RE = re.compile(r"Event: Name\[\s*(.*?)\s*\]\s*_id\[(\w+)\]\s*venue\[(\w*)\]\s*"
                       r"startDate\[([^\]]*)\]\s*endDate\[([^\]]*)\]")


def sport_word(name) -> Optional[str]:
    """'americanfootball', 'Fairplay Football Code 23', 'Middle School Boys
    Football' -> 'football'. None if no known sport is named."""
    n = (name or "").lower().replace(" ", "")
    for w in SPORT_WORDS:
        if w in n:
            return w
    return None


def _iso_time(v) -> Optional[float]:
    if not v:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", v)
    if not m:
        return None
    import calendar
    return float(calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0)))


def read_sc3(path: Optional[str] = None) -> Optional[dict]:
    """ScoreConnect III's saved setup, from its own settings file (a few KB,
    no call to its API): the sport it decodes, whether its ScoreLink is
    online, and its status message."""
    try:
        import json
        with open(path or SC3_SETTINGS, "r", encoding="utf-8-sig", errors="replace") as fh:
            j = json.load(fh)
    except (OSError, ValueError):
        return None
    parms = j.get("parms")
    if isinstance(parms, list):
        slot = j.get("slot") if isinstance(j.get("slot"), int) else 0
        parms = parms[slot] if 0 <= slot < len(parms) and isinstance(parms[slot], dict) else None
    if not isinstance(parms, dict):
        return None
    return {"sport": parms.get("sbvendorname"),
            "botOnline": parms.get("bot_online") if isinstance(parms.get("bot_online"), bool) else None,
            "status": parms.get("ConfigurationStatus"),
            "statusMessage": (parms.get("ConfigurationStatusMessage") or None)}


def parse_status(line: str) -> dict:
    """The kept values from one StatusReporter::reportStatus line."""
    out = {}
    for key, field in _STATUS_KEYS.items():
        m = re.search(r"\|" + key + r":[^|]*?" + field + r"=\s*(-?[0-9.]+)", line)
        if m:
            try:
                out[key] = float(m.group(1))
            except ValueError:
                pass
    return out


def parse_vpu_lines(text: str) -> list:
    """The stream's events, in order, from VPU.exe log text."""
    out = []
    status = None
    for line in text.splitlines():
        if "StatusReporter::reportStatus" in line:
            status = line          # only the newest one is parsed, below
            continue
        if ("urlToStreamWriter" not in line and "calibration" not in line and "Failed connecting to" not in line
                and "failed, move to" not in line and "Created Zixi stream" not in line
                and "Created Successfuly" not in line and "START NEW LOG SESSION" not in line
                and "CloseUnit" not in line and "LEAKY BUCKET" not in line
                and "Request to disable the Poe" not in line and "Camera reset happened" not in line
                and "Couldn't get response from camera rtsp" not in line
                and "Start Reason:" not in line and "ReplayManager::init(" not in line
                and "recordedEvents" not in line):
            continue
        t = _line_time(line)
        if "START NEW LOG SESSION" in line:
            m = re.search(r"Version: ([0-9.]+)", line)
            out.append({"t": t, "kind": "session", "version": m.group(1) if m else None})
        elif "urlToStreamWriter for urls" in line:
            m = re.search(r"urlToStreamWriter for urls (\S+)", line)
            if m and re.search(r"(zixi|rtmp)://", m.group(1)):
                out.append({"t": t, "kind": "chain", "urls": m.group(1).split("|")})
        elif "Failed connecting to" in line:
            m = re.search(r"Failed connecting to (\S+?), because", line)
            rv = re.search(r"return value: (-?\d+)", line)
            out.append({"t": t, "kind": "fail", "url": m.group(1) if m else None,
                        "returnValue": int(rv.group(1)) if rv else None})
        elif "failed, move to" in line:
            m = re.search(r"onStreamDisconnect: (\S+) failed, move to (\S+)", line)
            out.append({"t": t, "kind": "move", "from": m.group(1) if m else None,
                        "to": m.group(2) if m else None})
        elif "Created Zixi stream" in line:
            out.append({"t": t, "kind": "connected", "via": "zixi"})
        elif "Created Successfuly" in line and "rtmp://" in line:
            m = re.search(r"(rtmp://\S+) Created Successfuly", line)
            out.append({"t": t, "kind": "connected", "via": "rtmp", "path": _path_of(m.group(1) if m else None)})
        elif "CloseUnit" in line:
            m = re.search(r'Reason: "([^"]*)"', line)
            out.append({"t": t, "kind": "close", "reason": m.group(1) if m else None})
        elif "LEAKY BUCKET" in line and "dropping" in line:
            out.append({"t": t, "kind": "drop"})
        elif "Request to disable the Poe" in line:
            out.append({"t": t, "kind": "poeReset"})
        elif "Camera reset happened" in line:
            out.append({"t": t, "kind": "cameraReset"})
        elif "Couldn't get response from camera rtsp" in line:
            m = re.search(r"rtsp://([0-9.]+)", line)
            out.append({"t": t, "kind": "cameraUnreachable", "ip": m.group(1) if m else None})
        elif "Start Reason:" in line and "Event: Name[" in line:
            m = _START_RE.search(line)
            if m:
                name = m.group(1)
                g = re.search(r"\b(gam[0-9a-f]{6,})\b", name)
                out.append({"t": t, "kind": "start", "name": name, "id": m.group(2),
                            "gameKey": g.group(1) if g else None,
                            "scheduledStart": m.group(4), "scheduledEnd": m.group(5)})
        elif "Start Reason:" in line and "event command" not in line:
            # Head setup: "Agent Start Reason: start recorder in manual mode
            # was pressed" (lab-workbench-z2, VPU 5.21.8, 2026-05-14). No
            # stream chain, connect or fail line follows.
            m = re.search(r"Start Reason:\s*(.*?)\s*$", line)
            out.append({"t": t, "kind": "setupStart", "reason": (m.group(1) if m else None) or None})
        elif "ReplayManager::init(" in line:
            m = re.search(r"ReplayManager::init\((\w+)\)", line)
            if m:
                out.append({"t": t, "kind": "sport", "sport": m.group(1)})
        elif "cannot find needed calibration for" in line:
            m = re.search(r"cannot find needed calibration for (\S+?)\.", line)
            out.append({"t": t, "kind": "uncalibrated", "sport": m.group(1) if m else None})
        else:
            m = _EVENT_IN_LOG_RE.search(line)
            if m:
                out.append({"t": t, "kind": "eventId", "id": m.group(1)})
    if status:
        out.append({"t": _line_time(status), "kind": "status", "values": parse_status(status)})
    return out


def read_bench(path: str, header: Optional[list], since: float):
    """(header, summary) from the AgentBenchmarks rows newer than `since`.
    The header is read once per file and kept by the caller."""
    try:
        with open(path, "rb") as fh:
            if header is None:
                header = next(csv.reader(io.StringIO(fh.readline().decode("utf-8", "replace"))), [])
                header = [h.strip() for h in header]
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - BENCH_TAIL_BYTES))
            tail = fh.read().decode("utf-8", "replace")
    except (OSError, StopIteration):
        return header, None
    idx = {name: i for i, name in enumerate(header or [])}

    def col(row, name):
        i = idx.get(name)
        if i is None or i >= len(row):
            return None
        try:
            return float(row[i])
        except ValueError:
            return None

    nics = [n for n in (header or []) if re.match(r"Camera NIC \d+ Speed$", n)]
    rows = 0
    summ = {"cpuMax": None, "vpuCpuMax": None, "gpuMax": None, "gpuVideoMax": None,
            "ramAvailMin": None, "cameraNics": {}}
    for row in csv.reader(io.StringIO(tail.split("\n", 1)[1] if "\n" in tail else "")):
        if len(row) < 7 or not row[0].strip().isdigit():
            continue
        try:
            ts = time.mktime((int(row[0]), int(row[1]), int(row[2]), int(row[3]),
                              int(row[4]), int(float(row[5])), 0, 0, -1))
        except (ValueError, OverflowError):
            continue
        if ts <= since:
            continue
        rows += 1
        for key, name, pick in (("cpuMax", "CPULoad", max), ("vpuCpuMax", "CPU Usage: VPU", max),
                                ("gpuMax", "GPUCoreLoad", max), ("gpuVideoMax", "GPU Video Engine Load", max),
                                ("ramAvailMin", "RAM Available", min)):
            v = col(row, name)
            if v is not None:
                summ[key] = v if summ[key] is None else pick(summ[key], v)
        for n in nics:
            v = col(row, n)
            if v is not None:
                prev = summ["cameraNics"].get(n)
                summ["cameraNics"][n] = v if prev is None else min(prev, v)
    summ["rows"] = rows
    return header, (summ if rows else None)


def _folder_mtime(path: str, own: float) -> float:
    """The newest write in an event folder: VPU.exe keeps writing the
    recordings inside it for the whole event, while the folder's own time
    stays at its creation. One listing of its top level, no file opened."""
    newest = own
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    newest = max(newest, e.stat().st_mtime)
                except OSError:
                    pass
    except OSError:
        pass
    return newest


def newest_event_id(events_dir: str = EVENTS_DIR, since: Optional[float] = None) -> Optional[str]:
    """The newest event folder's id, only if it was written after `since`
    (minus a margin): an older folder belongs to an earlier event."""
    best = None
    try:
        with os.scandir(events_dir) as it:
            for e in it:
                m = _EVENT_DIR_RE.match(e.name)
                if m and e.is_dir():
                    mt = _folder_mtime(e.path, e.stat().st_mtime)
                    if since is not None and mt < since - 900:
                        continue
                    if best is None or mt > best[1]:
                        best = (m.group(1), mt)
    except OSError:
        return None
    return best[0] if best else None


def _path_of(url) -> Optional[str]:
    """zixi://host:2088/... -> "zixi-2088", the streamingPath vocabulary of
    the pre-event check (pulse.telemetry/v1)."""
    m = re.match(r"(zixi|rtmp)://[^/:]+(?::(\d+))?", url or "")
    if not m:
        return None
    port = m.group(2) or ("1935" if m.group(1) == "rtmp" else "2088")
    return f"{m.group(1)}-{port}"


def _round(v):
    return None if v is None else round(v, 1)


def slow_cameras(ev: dict) -> list:
    """Indexes of cameras below CAMERA_SLOW_FPS in the newest status line."""
    st = ev.get("status") or {}
    return [i for i in range(3)
            if f"Camera{i}AvgFps" in st and st[f"Camera{i}AvgFps"] < CAMERA_SLOW_FPS]


def verdict(ev: dict, now: float) -> str:
    """One word for what the event is doing now."""
    if ev.get("setup"):
        return "setup"              # no stream to judge
    if (ev.get("restarts") or 0) >= RESTART_LOOP_COUNT:
        return "restart-loop"
    down = ev.get("nicsDown") or []
    if down:
        return "camera-link-down"
    if slow_cameras(ev):
        # On 6493 a camera link forced to 100 Mbps took that camera from 25
        # to 0 fps while the stream itself kept encoding at 25 (2026-10-14).
        return "camera-degraded"
    st = ev.get("status") or {}
    # On air = the log's newest connect line has no failed attempt after it.
    # The status line's stream FPS is NOT proof: it counts frames leaving the
    # encoder, and read 25 fps through a 2.5-minute outage on 6493 with every
    # UDP path blocked (2026-10-14). Its Fails counter does veto.
    conn = ev.get("connectedAt")
    last_fail = ev.get("lastFailAt")
    if conn and (not last_fail or last_fail <= conn) and not (st.get("HD_Writer0_Stream0_Fails") or 0):
        return "on-air"
    first_fail = ev.get("failingSince")
    if first_fail and now - first_fail >= FAILING_AFTER_SECONDS:
        return "stream-failing"
    return "connecting"


# What a record keeps when VPU.exe switches between head setup and an event:
# where the reader is in the files and which VPU.exe, nothing about the run.
_READER_KEYS = ("logFile", "offset", "vpuPid", "vpuVersion", "benchFile", "benchHeader", "benchSince",
                "caughtUp")


def _switch_run(ev: dict, t: float, setup: bool) -> None:
    """VPU.exe restarted into the other kind of run (head setup, then the
    scheduled event; or an event, then head setup) faster than the monitor
    saw it stop. Keep the old run's summary in `endedRun` for the caller to
    post as its end, and start the record again from this session."""
    ended = summary(ev, t, ended=True)
    keep = {k: ev[k] for k in _READER_KEYS if k in ev}
    ev.clear()
    ev.update(keep, startedAt=t, sessions=1, setup=setup, endedRun=ended)


def observe(ev: dict, vpu_pid: Optional[str], now: float,
            log_dir: str = LOG_DIR, events_dir: str = EVENTS_DIR,
            images: Optional[set] = None) -> dict:
    """Advance one event record by one tick. Returns the cost of the read.
    `images` is the tick's tasklist (already collected), for ScoreConnect."""
    cost = {"bytes": 0, "skipped": False}
    pid_changed = bool(vpu_pid and ev.get("vpuPid") and vpu_pid != ev["vpuPid"])
    if vpu_pid:
        ev["vpuPid"] = vpu_pid
    sessions_before = ev.get("sessions") or 0

    newest = _newest(log_dir, "VPU_", ".log")
    if newest:
        path, size = newest
        if path != ev.get("logFile"):
            # A new VPU log is a new VPU.exe start. Read it from the top, unless
            # this is the first look at an event that was already running when
            # the monitor noticed it: then only the last MAX_READ_BYTES count.
            first_look = ev.get("logFile") is None
            ev["logFile"], ev["offset"] = path, (max(0, size - MAX_READ_BYTES) if first_look else 0)
            if first_look:
                ev["midEventStart"] = True
        caught = ""
        if ev.get("midEventStart") and not ev.get("caughtUp"):
            ev["caughtUp"] = True                 # once per event, found or not
            caught, _ = _catch_up(path, max(0, size - MAX_READ_BYTES))
            cost["catchUp"] = len(caught)
            if caught:
                ev.pop("midEventStart", None)    # its session line was found
        text, ev["offset"], skipped = _read_new(path, ev.get("offset") or 0, size)
        cost["bytes"], cost["skipped"] = len(text), skipped
        text = caught + text
        for e in parse_vpu_lines(text):
            k, t = e["kind"], e.get("t") or now
            if k == "chain":
                ev["chain"] = e["urls"]
                ev["pendingPath"] = _path_of(e["urls"][0] if e["urls"] else None)
            elif k == "fail":
                ev["fails"] = (ev.get("fails") or 0) + 1
                if ev.get("connectedAt") and not ev.get("downSince"):
                    ev["downSince"] = t          # an outage starts at the first failed try after a connect
                ev["lastFailAt"] = t
                ev["lastFailUrl"] = e.get("url")
                ev["lastFailCode"] = e.get("returnValue")
                if not ev.get("connectedAt") or (ev.get("lastFailAt") or 0) > ev["connectedAt"]:
                    ev.setdefault("failingSince", t)
            elif k == "move":
                ev["failovers"] = (ev.get("failovers") or 0) + 1
                ev["pendingPath"] = _path_of(e.get("to"))
            elif k == "connected":
                if ev.get("downSince"):
                    ev["offAirSeconds"] = (ev.get("offAirSeconds") or 0) + max(0, t - ev.pop("downSince"))
                ev["connectedAt"] = t
                ev["via"] = e["via"]
                ev["path"] = e.get("path") or ev.get("pendingPath")
                ev.setdefault("firstConnectedAt", t)
                ev.pop("failingSince", None)
            elif k == "close":
                ev["closeReason"] = e.get("reason")
                ev["closedAt"] = t
            elif k == "drop":
                ev["drops"] = (ev.get("drops") or 0) + 1
            elif k == "session":
                ev["sessions"] = (ev.get("sessions") or 0) + 1
                if ev.get("connectedAt") and not ev.get("downSince"):
                    ev["downSince"] = t          # VPU.exe restarted while on air
                ev["vpuVersion"] = e.get("version")
            elif k == "poeReset":
                ev["poeResets"] = (ev.get("poeResets") or 0) + 1
            elif k == "cameraReset":
                ev["cameraResets"] = (ev.get("cameraResets") or 0) + 1
            elif k == "cameraUnreachable" and e.get("ip"):
                ev.setdefault("unreachable", {})[e["ip"]] = t
            elif k == "start":
                if ev.get("setup"):
                    _switch_run(ev, t, setup=False)
                    sessions_before = 1
                ev["setup"] = False
                ev["eventName"] = e["name"]
                ev["nfhsGameKey"] = e.get("gameKey")
                ev["scheduledStart"] = e.get("scheduledStart")
                ev["scheduledEnd"] = e.get("scheduledEnd")
                ev["eventId"] = e["id"]
            elif k == "setupStart":
                if ev.get("setup") is False:
                    _switch_run(ev, t, setup=True)
                    sessions_before = 1
                ev["setup"] = True
                ev["startReason"] = e.get("reason")
                # Head setup still logs the last event's folder (a stale
                # metadata path), so a folder id read before this line isn't
                # this run's.
                ev["eventId"] = None
            elif k == "sport":
                ev["sport"] = e["sport"]
            elif k == "uncalibrated":
                ev["calibrated"] = False
                ev.setdefault("sport", e.get("sport"))
            elif k == "eventId" and not ev.get("setup"):
                # The newest session's folder names the event. A restart
                # mid-event logs the same id again.
                ev["eventId"] = e["id"]
            elif k == "status":
                ev["status"] = e["values"]
                ev["statusAt"] = t
    if ev.pop("midEventStart", False) and not ev.get("sessions"):
        # Started reading mid-event, past the session line: VPU.exe is in a
        # session we didn't see begin, so the next one is a restart.
        ev["sessions"] = 1
        sessions_before = 1
    # A VPU.exe restart: a new log session after the first one this event
    # saw, or (when the log can't be read) a new process id.
    new_sessions = (ev.get("sessions") or 0) - sessions_before
    restarts_now = max(new_sessions - (1 if sessions_before == 0 else 0), 0)
    if restarts_now == 0 and pid_changed and not newest:
        restarts_now = 1
    if restarts_now:
        ev["restarts"] = (ev.get("restarts") or 0) + restarts_now
    if not ev.get("eventId") and not ev.get("setup"):
        ev["eventId"] = newest_event_id(events_dir, since=ev.get("startedAt"))

    bench = _newest(log_dir, "AgentBenchmarks_", ".csv")
    if bench:
        if bench[0] != ev.get("benchFile"):
            ev["benchFile"], ev["benchHeader"] = bench[0], None
        ev["benchHeader"], summ = read_bench(bench[0], ev.get("benchHeader"),
                                             ev.get("benchSince") or (now - 300))
        ev["benchSince"] = now
        if summ:
            peak = ev.setdefault("peak", {})
            for k in ("cpuMax", "vpuCpuMax", "gpuMax", "gpuVideoMax"):
                if summ.get(k) is not None:
                    peak[k] = max(peak.get(k) or 0, summ[k])
            if summ.get("ramAvailMin") is not None:
                peak["ramAvailMin"] = min(peak.get("ramAvailMin", summ["ramAvailMin"]), summ["ramAvailMin"])
            # A camera NIC that had link at the event's first read and reads 0
            # now has lost its camera (unplugged, or the PoE port dropped it).
            nics = summ.get("cameraNics") or {}
            linked = ev.setdefault("nicsLinked", [n for n, v in nics.items() if v and v > 0])
            ev["nicsDown"] = [n for n in linked if nics.get(n) == 0]
    sc3 = read_sc3()
    if sc3:
        ev["sc3"] = sc3
    if images is not None:
        sc = any(n.startswith("scoreconnect") for n in images)
        ev["scoreConnectRunning"] = sc
        if not sc:
            ev["scoreConnectDownSeen"] = True
    ev["lastReadAt"] = now
    return cost


def summary(ev: dict, now: float, ended: bool) -> dict:
    """The event as posted: `pulse.event/v1`."""
    first = ev.get("firstConnectedAt")
    on_air = None
    off_air = None
    if first:
        end = ev.get("closedAt") or ev.get("lastReadAt") or now
        # Outages (failed tries after a connect, VPU.exe restarts) don't count.
        off_air = (ev.get("offAirSeconds") or 0) + (max(0, end - ev["downSince"]) if ev.get("downSince") else 0)
        on_air = max(0, int(end - first - off_air))
    v = verdict(ev, now)
    eid = ev.get("eventId")
    st = ev.get("status") or {}
    out = {
        "schema": SCHEMA,
        "eventId": eid,
        "kind": "setup" if ev.get("setup") else
                ("daily-test" if eid and eid.upper().startswith("DAILYTEST") else "event") if eid else None,
        # The Agent's reason for starting VPU.exe, on a setup run.
        "startReason": ev.get("startReason"),
        "state": ("ended" if ended else v),
        "startedAt": _iso(ev.get("startedAt")),
        "wentOnAir": bool(first),
        "onAirSeconds": on_air,
        "offAirSeconds": int(off_air) if off_air is not None else None,
        "eventName": ev.get("eventName"),
        "nfhsGameKey": ev.get("nfhsGameKey"),
        "scheduledStart": ev.get("scheduledStart"),
        "scheduledEnd": ev.get("scheduledEnd"),
        "via": ev.get("via"),
        "path": ev.get("path"),
        # On air, but not on the chain's first choice: the venue is blocking
        # the preferred path (UDP 2088 first, then UDP 443, then RTMP 1935).
        "fallback": bool(ev.get("path") and ev.get("chain") and _path_of(ev["chain"][0]) != ev.get("path")),
        "fails": ev.get("fails") or 0,
        "failovers": ev.get("failovers") or 0,
        "lastFailUrl": ev.get("lastFailUrl"),
        "lastFailCode": ev.get("lastFailCode"),
        "restarts": ev.get("restarts") or 0,
        "drops": ev.get("drops") or 0,
        "camerasDown": len(ev.get("nicsDown") or []),
        "camerasSlow": slow_cameras(ev),
        "poeResets": ev.get("poeResets") or 0,
        # Cameras Pixellot couldn't reach in the last 5 minutes (by stream IP),
        # and every one it couldn't reach at some point this event.
        "camerasUnreachable": sorted(ip for ip, t in (ev.get("unreachable") or {}).items()
                                     if t and (ev.get("lastReadAt") or now) - t <= 300),
        "camerasLost": sorted((ev.get("unreachable") or {}).keys()),
        "cameraResets": ev.get("cameraResets") or 0,
        "closeReason": ev.get("closeReason"),
        "scoreConnectRunning": ev.get("scoreConnectRunning"),
        "scoreConnectWasDown": bool(ev.get("scoreConnectDownSeen")),
        "calibrated": ev.get("calibrated", True) if ev.get("sessions") else ev.get("calibrated"),
        "sport": ev.get("sport"),
        "vpuVersion": ev.get("vpuVersion"),
        "peak": {k: _round(val) for k, val in (ev.get("peak") or {}).items()},
        "live": {
            "fps": st.get("HD_Writer0_Stream0_FPS"),
            "cameraFps": [st[k] for k in ("Camera0AvgFps", "Camera1AvgFps", "Camera2AvgFps") if k in st],
            "lowFpsCount": sum(st.get(k) or 0 for k in ("Camera0LowFpsCount", "Camera1LowFpsCount", "Camera2LowFpsCount")) if st else None,
            "streamFails": st.get("HD_Writer0_Stream0_Fails"),
            "port": int(st["HD_Writer0_Stream0_UrlPort"]) if st.get("HD_Writer0_Stream0_UrlPort") else None,
            "droppedFrames": st.get("HD_WritersDroppedFrames"),
            "health": st.get("Health"),
            "networkIssues": st.get("CumulativeNetworkIssues"),
            "cameraResets": (st.get("CamerasHardResetCount") or 0) + (st.get("CamerasSoftResetCount") or 0) if st else None,
            "scoreboardDataPerSecond": st.get("ScoreboardDataFrequencyPerSecond"),
            "scorebugAgeSeconds": int(st["GraphicsTimestampsDelta"]) if st.get("GraphicsTimestampsDelta") is not None else None,
            "at": _iso(ev.get("statusAt")),
        } if st else None,
    }
    sc3 = ev.get("sc3") or {}
    vpu_sport, sc_sport = sport_word(ev.get("sport")), sport_word(sc3.get("sport"))
    out["scoreboard"] = {
        "scoreConnectSport": sc3.get("sport"),
        "sportMatch": (vpu_sport == sc_sport) if (vpu_sport and sc_sport) else None,
        "scoreLinkOnline": sc3.get("botOnline"),
        "scoreConnectMessage": sc3.get("statusMessage"),
    } if sc3 else None
    # Things worth a look even when the event aired, most actionable first.
    warn = []
    if out["scoreboard"] and out["scoreboard"]["sportMatch"] is False:
        warn.append("scoreboard-sport-mismatch")   # e.g. a basketball code on a football game
    if out["scoreboard"] and out["scoreboard"]["scoreLinkOnline"] is False and ev.get("scoreConnectRunning"):
        warn.append("scorelink-offline")
    lv = out.get("live") or {}
    if (lv.get("scorebugAgeSeconds") or 0) >= SCOREBUG_STALE_SECONDS and not lv.get("scoreboardDataPerSecond"):
        warn.append("scorebug-stale")
    if out.get("calibrated") is False:
        warn.append("uncalibrated")
    if out.get("fallback"):
        warn.append("stream-fallback")
    if (out.get("offAirSeconds") or 0) >= 60:
        warn.append("off-air-gaps")
    if out.get("restarts"):
        warn.append("vpu-restarted")
    if out.get("camerasLost"):
        warn.append("camera-lost")
    sched_end = _iso_time(ev.get("scheduledEnd"))
    if ended and sched_end and (ev.get("closedAt") or now) < sched_end - ENDED_EARLY_SECONDS:
        warn.append("ended-early")
    out["warnings"] = warn
    if ended:
        out["endedAt"] = _iso(ev.get("closedAt") or now)
        # Why it never aired, in the order a tech would rule things out.
        # Head setup never streams, so it has no reason.
        if not first and not ev.get("setup"):
            out["reason"] = ("restart-loop" if out["restarts"] >= RESTART_LOOP_COUNT else
                             "camera-link-down" if out["camerasDown"] else
                             "camera-degraded" if out["camerasSlow"] else
                             "stream-failing" if out["fails"] else "never-connected")
        else:
            out["reason"] = None
    return out


def _iso(t) -> Optional[str]:
    if not isinstance(t, (int, float)):
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
