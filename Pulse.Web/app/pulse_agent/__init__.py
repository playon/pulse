"""The Pulse fleet agent: the scheduled monitor, its check-in and its report.

It versions on its own (VERSION beside this file, CHANGELOG.md, agent-v* tags),
apart from Pulse Diagnostics (Pulse.Web/VERSION), so the fleet can be pinned to
an agent build without pinning the app (PV-49).

Stdlib only and cheap to import: the monitor imports this on every tick,
including the ones during an event that must not load main.py.
"""

import os as _os

_PKG_DIR = _os.path.dirname(_os.path.abspath(__file__))
# Pulse.Web, or the monitor's own copy of it (C:\PulseFleetMonitor): where the
# state, queue and log files live.
WEB_ROOT = _os.path.dirname(_os.path.dirname(_PKG_DIR))


def _read_version() -> str:
    try:
        with open(_os.path.join(_PKG_DIR, "VERSION"), "r", encoding="utf-8") as fh:
            return fh.read().strip()[:64]
    except OSError:
        return ""


AGENT_VERSION = _read_version()
