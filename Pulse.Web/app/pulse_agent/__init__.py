"""The Pulse fleet agent: the scheduled monitor, its check-in and its report.

It versions on its own (VERSION beside this file, CHANGELOG.md, agent-v* tags),
apart from Pulse Diagnostics (Pulse.Web/VERSION), so the fleet can be pinned to
an agent build without pinning the app (PV-49).

Stdlib only and cheap to import: the monitor imports this on every tick,
including the ones during an event that must not load main.py.
"""

import os as _os

_PKG_DIR = _os.path.dirname(_os.path.abspath(__file__))
# The Pulse.Web tree this copy of the agent is in: Pulse.Web, or one of the
# runner's slots. The monitor keeps its state elsewhere when the runner gives
# it a data folder (monitor_once.py, PULSE_MONITOR_DATA).
WEB_ROOT = _os.path.dirname(_os.path.dirname(_PKG_DIR))


def _read_version() -> str:
    try:
        with open(_os.path.join(_PKG_DIR, "VERSION"), "r", encoding="utf-8") as fh:
            return fh.read().strip()[:64]
    except OSError:
        return ""


AGENT_VERSION = _read_version()

# The runner's record of its last update attempt (runner.py writes it in the
# monitor's data folder). Posts carry it as agentUpdate for a day after.
UPDATE_FILE = "agent-update.json"
UPDATE_STATUSES = ("applied", "failed", "rolled-back")
UPDATE_REPORT_SECONDS = 24 * 3600


def last_update(path: str, now=None):
    """agentUpdate for a post: {status, version, error} from the runner's last
    attempt, or None when there's none, it's unreadable or over a day old."""
    import json
    import time
    try:
        with open(path, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or rec.get("status") not in UPDATE_STATUSES:
        return None
    at = rec.get("at")
    now = time.time() if now is None else now
    if not isinstance(at, (int, float)) or not 0 <= now - at <= UPDATE_REPORT_SECONDS:
        return None
    out = {"status": rec["status"], "version": rec.get("version")}
    if rec.get("error"):
        out["error"] = str(rec["error"])[:256]
    return out
