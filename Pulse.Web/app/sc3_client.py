"""ScoreConnect III setup: read and write SC III's configuration through its
local REST API, plus the scoreboard-chain facts a tech confirms by hand.

Why stdlib HTTP and not PowerShell: SC III serves a swagger-documented API on
localhost:5000 with no auth, and main.py already reads it over urllib
(_fetch_sc3_status). Writes through the same path avoid every PowerShell 5.1
trap, and the service validates each write itself.

What was measured on a real unit (vpu-home, SC III, 2026-09-29):
  - get-devices-list is EMPTY (HTTP 204) until discover-devices runs. SC III
    refuses to be configured without a device, so saving has to find devices
    first. VPU2 was in the same state after a reinstall.
  - discover-devices then lists BOTH a ScoreLink and a ScoreLink II for one
    physical USB device. The list is the two device types SC III supports,
    not what is plugged in, so the tech picks which one this is.
  - v2 set-scoreconnect-configuration answers {isValid, warningMessage,
    requiredFields}. An incomplete wireless setup is refused with HTTP 400 and
    the missing fields named; the saved config is untouched. A valid save
    takes several seconds.
  - botNumber 0 makes SC III assign itself a bot number.
  - Connection-type ids are per vendor, so they are always re-fetched after a
    vendor change.
Saves always send isCloudMode false: local decode, which is how Pixellot reads
the score on port 1402. No venue uses cloud mode (Ian, 2026-09-29).
"""

import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
from datetime import datetime

SC3_SETTINGS_PATH = r"C:\ProgramData\Sportzcast LLC\ScoreConnectIII\Files\settings.json"
GRAPHICS_CFG_PATH = r"C:\Pixellot\Data\Configuration\graphics.cfg"

DEVICE_TYPES = ("ScoreLink", "ScoreLinkII")
_BACKUPS_KEPT = 10


class Sc3Error(Exception):
    """SC III could not be reached, or answered with something unusable."""


# ── Transport ────────────────────────────────────────────────

def http_transport(base_url):
    """A (method, path, body) -> (status, parsed) callable against SC III."""
    base = (base_url or "http://localhost:5000").rstrip("/")

    def call(method, path, body=None, timeout=6):
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            data = b"" if method == "PUT" else None
        req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (urllib.error.URLError, OSError) as e:
            raise Sc3Error("ScoreConnect III is not answering on %s (%s)" % (base, e))
        text = raw.decode("utf-8", "replace").strip()
        if not text:
            return status, None
        try:
            return status, json.loads(text)
        except ValueError:
            return status, text
    return call


# ── Parsing ──────────────────────────────────────────────────

_FIELD_RX = re.compile(r"^\s*([A-Za-z]+)\s*(?:\((.*)\))?\s*$")
_RANGE_RX = re.compile(r"(-?\d+)\s*-\s*(-?\d+)")


def parse_required_field(text):
    """SC III names each extra field as prose: "Group (BCAST, 0 - 8)",
    "Channel (Group #, 0 - 99)", "ExternalAntenna (true - false)" or just
    "ExternalAntenna". Turn one into a form field the editor can draw.
    `raw` keeps SC III's words so a field Pulse cannot parse still shows."""
    m = _FIELD_RX.match(text or "")
    if not m:
        return {"key": None, "label": text, "type": "text", "raw": text}
    name, inner = m.group(1), (m.group(2) or "")
    key = name[0].lower() + name[1:]
    label = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
    if key == "externalAntenna" or "true" in inner.lower():
        return {"key": "externalAntenna", "label": "External antenna", "type": "bool", "raw": text}
    rng = _RANGE_RX.search(inner)
    hint = inner.split(",")[0].strip() if "," in inner else ""
    field = {"key": key, "label": label, "type": "int", "hint": hint, "raw": text}
    if rng:
        field["min"], field["max"] = int(rng.group(1)), int(rng.group(2))
    return field


def brand_of(vendor_name):
    """SC III's "vendor" list mixes brands and console models ("Fairplay
    MP70", "Daktronics AllSport CG"). The chain draws one controller per
    brand, so fold the model away. Unknown brands are "other", not a guess."""
    v = (vendor_name or "").lower().replace("-", "").replace(" ", "")
    for brand, needle in (("daktronics", "daktronics"), ("fairplay", "fairplay"),
                          ("nevco", "nevco"), ("electromech", "electromech")):
        if v.startswith(needle):
            return brand
    return "other" if v else None


def device_type_of(desc):
    """settings.json names the selected device "USB ScoreLinkII"."""
    d = (desc or "").replace(" ", "").lower()
    if "scorelinkii" in d or "scorelink2" in d:
        return "ScoreLinkII"
    if "scorelink" in d:
        return "ScoreLink"
    return None


def read_sc3_settings(path=SC3_SETTINGS_PATH):
    """The device SC III is set to use, from its own settings file. The REST
    API does not report it. Read-only."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            j = json.load(f)
    except FileNotFoundError:
        return {"error": "ScoreConnect III settings file not found"}
    except (OSError, ValueError) as e:
        return {"error": "Could not read ScoreConnect III settings: %s" % e}
    parms = j.get("parms") or {}
    return {
        "deviceType": device_type_of(parms.get("scorelink_desc")),
        "port": parms.get("port") or None,
        "error": None,
    }


def read_graphics_cfg(path=GRAPHICS_CFG_PATH):
    """Where Pixellot takes the score from, and the bot number it expects.
    graphics.cfg is INI-ish: "KEY, type, value  //comment" under [SECTION]
    headers, and TYPE appears in more than one section, so only [GENERAL]
    counts. Read-only; never edited by Pulse."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return {"error": "Pixellot graphics settings not found"}
    except OSError as e:
        return {"error": "Could not read Pixellot graphics settings: %s" % e}
    section, out = None, {}
    for line in lines:
        s = line.split("//", 1)[0].strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().upper()
            continue
        if section != "GENERAL":
            continue
        parts = [p.strip() for p in s.split(",", 2)]
        if len(parts) == 3 and parts[0] in ("TYPE", "BOT_NUMBER"):
            out[parts[0]] = parts[2]
    return {
        "source": (out.get("TYPE") or "").upper() or None,
        "botNumber": out.get("BOT_NUMBER") or None,
        "error": None,
    }


SC3_LOG_DIR = r"C:\ProgramData\Sportzcast LLC\ScoreConnectIII\Logs"

# SC III's own log is the only place that says whether it can open the
# ScoreLink. Its status API kept answering "No Scoreboard data" through a USB
# unplug on vpu-home (2026-09-29) while the log said:
#   "Local BotServer - Serial thread error:The operation was canceled."
#   "USB/Serial Manager - SER BOT failed to connect"   (every 5s while gone)
#   "Local BotServer - Serial thread started, Baudrate:19200"  (~2s after replug)
# A config save also stops and restarts the serial thread, so "stopped" alone
# is not a fault; repeated failures are.
_SERIAL_OPEN = ("Serial thread started",)
_SERIAL_FAIL = ("SER BOT failed to connect", "Serial thread error")
_LOG_TS_RX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC")


def read_sc3_serial_state(log_dir=SC3_LOG_DIR, tail=400, now_utc=None):
    """{state: open|failing|unknown, at, failures} from the newest SC III log.
    `failures` counts consecutive failures since the last open. Timestamps
    in the log are UTC."""
    try:
        names = sorted(n for n in os.listdir(log_dir) if n.startswith("Log_") and n.endswith(".txt"))
    except OSError:
        return {"state": "unknown", "error": "ScoreConnect III log not found"}
    if not names:
        return {"state": "unknown", "error": "ScoreConnect III log is empty"}
    try:
        with open(os.path.join(log_dir, names[-1]), "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()[-tail:]
    except OSError as e:
        return {"state": "unknown", "error": "Could not read ScoreConnect III log: %s" % e}
    state, at, failures = "unknown", None, 0
    for line in lines:
        if any(k in line for k in _SERIAL_OPEN):
            state, failures = "open", 0
        elif any(k in line for k in _SERIAL_FAIL):
            state, failures = "failing", failures + 1
        else:
            continue
        m = _LOG_TS_RX.match(line)
        at = m.group(1).replace(" ", "T") + "Z" if m else None
    return {"state": state, "at": at, "failures": failures, "error": None}


# ── Reads ────────────────────────────────────────────────────

def _ok_list(status, body):
    if status == 204 or body is None:
        return []
    if status != 200 or not isinstance(body, list):
        raise Sc3Error("ScoreConnect III answered %s" % status)
    return body


def catalog(call):
    vendors = _ok_list(*call("GET", "/api/configuration/get-vendor-list"))
    vendors = [{"id": v.get("id"), "name": v.get("description"), "brand": brand_of(v.get("description"))}
               for v in vendors if isinstance(v, dict)]
    vendors.sort(key=lambda v: (v["name"] or "").lower())
    return {"vendors": vendors}


def vendor_detail(call, vendor_id):
    vid = int(vendor_id)
    sports = _ok_list(*call("GET", "/api/configuration/get-vendor-sports/%d" % vid))
    confs = _ok_list(*call("GET", "/api/v2/configuration/get-vendor-configurations/%d" % vid))
    return {
        "vendorId": vid,
        "sports": [{"id": s.get("id"), "name": s.get("description")} for s in sports if isinstance(s, dict)],
        "connections": [{
            "id": c.get("id"),
            "name": c.get("description"),
            "fields": [parse_required_field(t) for t in (c.get("requiredAdditionalFields") or [])],
            "instructions": list(c.get("specialInstructions") or []),
        } for c in confs if isinstance(c, dict)],
    }


def current(call, settings=None):
    """SC III's setup as the editor needs it: ids, names, bot, device."""
    st, cfg = call("GET", "/api/v2/configuration/get-current-configuration")
    if st not in (200, 204):
        raise Sc3Error("ScoreConnect III answered %s for its configuration" % st)
    cfg = cfg if isinstance(cfg, dict) else {}
    bst, bot = call("GET", "/api/configuration/get-bot-number")
    devices = _ok_list(*call("GET", "/api/configuration/get-devices-list"))
    settings = settings if settings is not None else {}
    return {
        "configured": bool(cfg.get("vendorSportId")),
        "vendorId": cfg.get("vendorId"),
        "vendorName": cfg.get("vendorName"),
        "brand": brand_of(cfg.get("vendorName")),
        "vendorSportId": cfg.get("vendorSportId"),
        "vendorSportName": cfg.get("vendorSportName"),
        "vendorConfigurationId": cfg.get("vendorConfigurationId"),
        "vendorConfigurationName": cfg.get("vendorConfigurationName"),
        "additionalConfiguration": cfg.get("additionalConfiguration"),
        "botNumber": bot if bst == 200 and isinstance(bot, int) else None,
        "deviceType": settings.get("deviceType"),
        "devicesFound": [d.get("type") for d in devices if isinstance(d, dict)],
    }


def discover(call, wait_s=20.0, sleep=time.sleep):
    """Ask SC III to look for its USB device, then wait for the list to fill.
    Measured: the list is populated within 15s on vpu-home."""
    call("PUT", "/api/configuration/discover-devices", timeout=60)
    deadline = time.monotonic() + wait_s
    while True:
        devices = _ok_list(*call("GET", "/api/configuration/get-devices-list"))
        if devices or time.monotonic() >= deadline:
            return devices
        sleep(2)


# ── Writes ───────────────────────────────────────────────────

def backup_settings(backup_dir, src=SC3_SETTINGS_PATH, now=None):
    """Copy SC III's settings file aside before any write, keeping the last
    ten. A write without a backup is refused, so this raises on failure."""
    os.makedirs(backup_dir, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backup_dir, "settings-%s.json" % stamp)
    try:
        shutil.copy2(src, dest)
    except OSError as e:
        raise Sc3Error("Could not back up ScoreConnect III's settings (%s)" % e)
    old = sorted(n for n in os.listdir(backup_dir) if n.startswith("settings-") and n.endswith(".json"))
    for n in old[:-_BACKUPS_KEPT]:
        try:
            os.remove(os.path.join(backup_dir, n))
        except OSError:
            pass
    return dest


def _int(v, name):
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ValueError("%s must be a whole number" % name)


def validate_request(req):
    """Normalise the editor's request. Raises ValueError with the tech-facing
    reason. Values SC III itself checks (sport belongs to vendor, fields in
    range) are left to SC III, which answers with its own message."""
    if not isinstance(req, dict):
        raise ValueError("Missing setup")
    dt = req.get("deviceType")
    if dt not in DEVICE_TYPES:
        raise ValueError("Pick which ScoreLink is plugged in")
    bot = _int(req.get("botNumber", 0), "Bot number")
    if bot < 0 or bot > 99999:
        raise ValueError("Bot number must be 0 to 99999")
    add = req.get("additionalConfiguration")
    if add is not None:
        if not isinstance(add, dict):
            raise ValueError("Wireless settings are malformed")
        clean = {}
        for k in ("group", "channel"):
            if add.get(k) is not None and add.get(k) != "":
                clean[k] = _int(add[k], k.capitalize())
        if "externalAntenna" in add:
            clean["externalAntenna"] = bool(add["externalAntenna"])
        add = clean or None
    return {
        "vendorSportId": _int(req.get("vendorSportId"), "Sport"),
        "vendorConfigurationId": _int(req.get("vendorConfigurationId"), "Connection type"),
        "botNumber": bot,
        "deviceType": dt,
        "additionalConfiguration": add,
    }


def configure(call, req, backup_dir, previous_path, settings_path=SC3_SETTINGS_PATH,
              read_settings=read_sc3_settings, backup=backup_settings, sleep=time.sleep):
    """Save a new SC III setup. Order matters:
      1. read the current setup (it becomes "Restore previous"),
      2. back up settings.json (no backup, no write),
      3. find devices if SC III has none yet,
      4. PUT the v2 configuration and pass SC III's verdict through,
      5. read back what SC III now reports.
    Returns {ok, before, after, warningMessage, requiredFields, discovered}."""
    want = validate_request(req)
    before = current(call, read_settings(settings_path) if read_settings else None)
    backup_path = backup(backup_dir, settings_path)

    st, devices = call("GET", "/api/configuration/get-devices-list")
    devices = _ok_list(st, devices)
    discovered = False
    if not devices:
        devices = discover(call, sleep=sleep)
        discovered = True
    dev = next((d for d in devices if isinstance(d, dict) and d.get("type") == want["deviceType"]), None)
    if dev is None:
        return {"ok": False, "discovered": discovered, "before": before, "backup": backup_path,
                "warningMessage": "ScoreConnect III did not find a %s device. Check it is plugged into the VPU's USB."
                                  % ("ScoreLink II" if want["deviceType"] == "ScoreLinkII" else "ScoreLink"),
                "requiredFields": []}

    body = {
        "deviceId": dev.get("id"),
        "vendorSportId": want["vendorSportId"],
        "botNumber": want["botNumber"],
        "isCloudMode": False,
        "vendorConfigurationId": want["vendorConfigurationId"],
        "additionalConfiguration": want["additionalConfiguration"],
    }
    st, resp = call("PUT", "/api/v2/configuration/set-scoreconnect-configuration", body, timeout=45)
    resp = resp if isinstance(resp, dict) else {}
    if st != 200 or resp.get("isValid") is False:
        return {"ok": False, "discovered": discovered, "before": before, "backup": backup_path,
                "warningMessage": resp.get("warningMessage") or ("ScoreConnect III refused the setup (HTTP %s)" % st),
                "requiredFields": [parse_required_field(t) for t in (resp.get("requiredFields") or [])]}

    # Only a setup that was actually configured is worth restoring to.
    if before.get("configured"):
        try:
            with open(previous_path, "w", encoding="utf-8") as f:
                json.dump({"savedAt": datetime.now().isoformat(timespec="seconds"), "setup": before}, f)
        except OSError:
            pass
    sleep(2)
    after = current(call, read_settings(settings_path) if read_settings else None)
    return {"ok": True, "discovered": discovered, "before": before, "after": after,
            "backup": backup_path, "warningMessage": resp.get("warningMessage"), "requiredFields": []}


def load_previous(previous_path):
    try:
        with open(previous_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def restore_request(previous):
    """The configure() request that puts a recorded setup back."""
    s = (previous or {}).get("setup") or {}
    return {
        "vendorSportId": s.get("vendorSportId"),
        "vendorConfigurationId": s.get("vendorConfigurationId"),
        "botNumber": s.get("botNumber") or 0,
        "deviceType": s.get("deviceType") or "ScoreLinkII",
        "additionalConfiguration": s.get("additionalConfiguration"),
    }


# ── Tech-confirmed chain ─────────────────────────────────────
# What Pulse cannot measure (cable, extension, console brand, and the
# ScoreLink model when Windows gives the USB device no name), as the school
# confirmed it. The ScoreLink II comes black with a yellow or a blue label;
# same hardware, so colour is not recorded. Saved on the VPU so the next call starts from it.

CHAIN_FIELDS = {
    "device": ("ScoreLink", "ScoreLinkII"),
    # Which tip of the multi-tip cable is in the console, or a custom cable.
    "cable": ("gray", "red", "bnc", "custom"),
    "extension": ("none", "yes"),
    "controller": ("daktronics", "fairplay", "nevco", "electromech", "other"),
    # Console model ids come from main.SC_CONSOLES and are passed in `allowed`.
    "model": (),
}


def load_chain(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_chain(path, current_chain, update, basis, now=None, allowed=None):
    """Merge one confirmation into the saved chain. Each part carries when it
    was confirmed and what SC III was set to at the time (basis), so a later
    vendor change can mark the console and cable as needing a fresh check.
    A value of None clears that part."""
    chain = dict(current_chain or {})
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    fields = dict(CHAIN_FIELDS, **(allowed or {}))
    for k, v in (update or {}).items():
        if k not in fields:
            raise ValueError("Unknown part: %s" % k)
        if v is None:
            chain.pop(k, None)
            continue
        if v not in fields[k]:
            raise ValueError("Unknown %s: %s" % (k, v))
        chain[k] = {"value": v, "at": stamp, "basis": dict(basis or {})}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chain, f, indent=1)
    return chain


def chain_with_staleness(chain, basis):
    """Flag each confirmed part whose basis no longer holds. Console, cable
    and extension depend on the vendor SC III is set to; the device on the
    ScoreLink model Windows reports (when it reports one)."""
    out = {}
    for k, entry in (chain or {}).items():
        if not isinstance(entry, dict):
            continue
        b = entry.get("basis") or {}
        stale = False
        if k in ("controller", "model", "cable", "extension"):
            stale = bool(basis.get("vendorName") and b.get("vendorName")
                         and basis["vendorName"] != b["vendorName"])
        elif k == "device":
            stale = bool(basis.get("scoreLinkModel") and b.get("scoreLinkModel")
                         and basis["scoreLinkModel"] != b["scoreLinkModel"])
        out[k] = dict(entry, stale=stale)
    return out


# ── Demo SC III ──────────────────────────────────────────────

class DemoSc3:
    """In-memory SC III for demo mode, answering the same paths with the
    shapes measured on vpu-home. Starts configured the way the demo status
    payload describes (Daktronics, wired, ScoreLink II)."""

    def __init__(self, catalog_data):
        self.cat = catalog_data
        self.devices = []
        self.bot = 54025
        self.cfg = {"vendorId": 1, "vendorName": "Daktronics", "vendorSportId": 180,
                    "vendorSportName": "Daktronics 3000 Football", "vendorSportCode": None,
                    "vendorConfigurationId": 11, "vendorConfigurationName": "Wired",
                    "additionalConfiguration": None}
        self.device_type = "ScoreLinkII"

    def _vendor(self, vid):
        return next((v for v in self.cat["vendors"] if v["id"] == vid), None)

    def settings(self):
        return {"deviceType": self.device_type, "port": "COM7", "error": None}

    def __call__(self, method, path, body=None, timeout=6):
        p = path
        if method == "GET" and p == "/api/configuration/get-vendor-list":
            return 200, self.cat["vendors"]
        m = re.match(r"^/api/configuration/get-vendor-sports/(\d+)$", p)
        if method == "GET" and m:
            return 200, self.cat["sports"].get(m.group(1), [])
        m = re.match(r"^/api/v2/configuration/get-vendor-configurations/(\d+)$", p)
        if method == "GET" and m:
            return 200, self.cat["configurations"].get(
                m.group(1), [{"id": 900 + int(m.group(1)), "description": "Wired",
                              "requiredAdditionalFields": [], "specialInstructions": []}])
        if method == "GET" and p == "/api/v2/configuration/get-current-configuration":
            return 200, dict(self.cfg)
        if method == "GET" and p == "/api/configuration/get-bot-number":
            return 200, self.bot
        if method == "GET" and p == "/api/configuration/get-devices-list":
            return (200, list(self.devices)) if self.devices else (204, None)
        if method == "PUT" and p == "/api/configuration/discover-devices":
            self.devices = [{"id": 0, "type": "ScoreLink", "description": "USB ScoreLink"},
                            {"id": 1, "type": "ScoreLinkII", "description": "USB ScoreLinkII"}]
            return 200, None
        if method == "PUT" and p == "/api/v2/configuration/set-scoreconnect-configuration":
            return self._set(body or {})
        return 404, None

    def _set(self, body):
        sport_id, conf_id = body.get("vendorSportId"), body.get("vendorConfigurationId")
        vendor_id = sport = None
        for vid, sports in self.cat["sports"].items():
            hit = next((s for s in sports if s["id"] == sport_id), None)
            if hit:
                vendor_id, sport = int(vid), hit
                break
        if sport is None:
            return 400, {"isValid": False, "warningMessage": "Unknown vendor sport", "requiredFields": []}
        confs = self.cat["configurations"].get(str(vendor_id), [])
        conf = next((c for c in confs if c["id"] == conf_id), None)
        if conf is None:
            return 400, {"isValid": False, "warningMessage": "This connection type does not belong to the vendor",
                         "requiredFields": []}
        need = conf.get("requiredAdditionalFields") or []
        add = body.get("additionalConfiguration") or {}
        if need and not all(parse_required_field(t)["key"] in add for t in need):
            return 400, {"isValid": False,
                         "warningMessage": "This vendor requires additional properties and were not provided",
                         "requiredFields": need}
        dev = next((d for d in self.devices if d["id"] == body.get("deviceId")), None)
        if dev:
            self.device_type = dev["type"]
        self.bot = body.get("botNumber") or 51244
        self.cfg = {"vendorId": vendor_id, "vendorName": self._vendor(vendor_id)["description"],
                    "vendorSportId": sport_id, "vendorSportName": sport["description"],
                    "vendorSportCode": None, "vendorConfigurationId": conf_id,
                    "vendorConfigurationName": conf["description"],
                    "additionalConfiguration": add or None}
        return 200, {"isValid": True, "warningMessage": None, "requiredFields": []}
