"""The check-in address, and a sender light enough to run during an event.

checkin.py's client is the real one (queue, batching, About page status) but
it runs on main.py's engine, and importing main loads FastAPI and the whole
app, about a second of CPU, which the monitor never
spends while VPU.exe is running. This sends one small event check-in with the
standard library only, into the same queue file checkin.py's client uses: if
the post fails, the entry stays queued and the next full pass after the event
sends it.

CHECKIN_URL is the one place the address lives; checkin.py reads it from here.
"""

import json
import os
import time
import urllib.error
import urllib.request

CHECKIN_URL = "https://pulse-checkin.pulse-checkin-worker.workers.dev/checkin"
_MAX_QUEUED = 200
_TIMEOUT_SECONDS = 4


def checkin_url() -> str:
    return (os.environ.get("PULSE_CHECKIN_URL") or CHECKIN_URL).strip()


def _load(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return {"queue": []}
    if not isinstance(state, dict):
        return {"queue": []}
    if not isinstance(state.get("queue"), list):
        state["queue"] = []
    return state


def _save(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, path)


def send(queue_path: str, entry: dict, user_agent: str = "Pulse") -> bool:
    """Queue `entry`, then try to post it alone. True if the Worker answered
    for it. Never raises."""
    try:
        state = _load(queue_path)
        state["queue"] = (state["queue"] + [entry])[-_MAX_QUEUED:]
        _save(queue_path, state)        # queued first, so a crash mid-POST keeps it
        url = checkin_url()
        if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            return False
        body = json.dumps({"checkins": [entry]}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json", "User-Agent": user_agent})
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
                reply = json.loads(resp.read(64 * 1024))
        except (urllib.error.URLError, OSError, ValueError) as e:
            state["lastError"] = str(e) or e.__class__.__name__
            state["lastAttemptAt"] = stamp
            _save(queue_path, state)
            return False
        answered = {r.get("checkinId") for r in (reply.get("results") or [])
                    if isinstance(r, dict) and r.get("status") in ("inserted", "duplicate", "invalid")}
        if reply.get("ok") is not True or entry["checkinId"] not in answered:
            return False
        state = _load(queue_path)       # re-read: keep anything queued meanwhile
        state["queue"] = [e for e in state["queue"] if e.get("checkinId") != entry["checkinId"]]
        state["lastAttemptAt"] = state["lastSentAt"] = stamp
        state.pop("lastError", None)
        if isinstance(reply.get("control"), dict):
            state["control"] = dict(reply["control"], receivedAt=stamp)
        _save(queue_path, state)
        return True
    except Exception:
        return False
