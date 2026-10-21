"""The fleet agent's runner (app/pulse_agent/runner.py, PV-49).

It runs as SYSTEM on every enrolled VPU and is the one part an update can't
fix, so most of this file is its update rules: what it downloads, what it
refuses, when it switches slots and when it switches back.

The end-to-end cases at the bottom build real agent zips with
tools/agent-release/build_agent_zip.py, serve them over local HTTP, and run
real monitor ticks (demo mode) from the slots.
"""

import hashlib
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import zipfile

_WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP_DIR = os.path.join(_WEB, "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
sys.path.insert(0, os.path.join(os.path.dirname(_WEB), "tools", "agent-release"))

import pulse_agent  # noqa: E402
from pulse_agent import runner  # noqa: E402
import build_agent_zip  # noqa: E402

REQS = "fastapi\nuvicorn[standard]\n"


def _zip_bytes(version, reqs=REQS, extra=None, version_inside=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app/monitor_once.py", "x = 1\n")
        zf.writestr("app/main.py", "m = 1\n")
        zf.writestr("app/requirements.txt", reqs)
        zf.writestr("app/pulse_agent/VERSION", (version_inside or version) + "\n")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


class Fixture(unittest.TestCase):
    """A runner root with slot a holding agent 0.1.0, and fakes for the
    network, the event check and the tick."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self._slot("a", "0.1.0")
        os.makedirs(os.path.join(self.root, "runtime"))
        with open(os.path.join(self.root, "runtime", "requirements.txt"), "w") as fh:
            fh.write(REQS)
        self._write_slots({"active": "a", "previous": None, "probation": None,
                           "slots": {"a": {"version": "0.1.0", "sha256": None}}, "blocked": {}, "retryAt": {}})
        self.event = False
        self.ticks = []             # (slot, args) per tick
        self.tick_ok = {}           # slot -> bool
        self.served = {}            # url -> bytes, or an exception to raise
        self.downloads = []
        self.now = 1_000_000.0

    def _slot(self, name, version):
        d = os.path.join(self.root, "slots", name, "app", "pulse_agent")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "VERSION"), "w") as fh:
            fh.write(version + "\n")
        with open(os.path.join(self.root, "slots", name, "app", "monitor_once.py"), "w") as fh:
            fh.write("x = 1\n")

    def _write_slots(self, st):
        with open(os.path.join(self.root, runner.SLOTS_FILE), "w") as fh:
            json.dump(st, fh)

    def slots(self):
        with open(os.path.join(self.root, runner.SLOTS_FILE)) as fh:
            return json.load(fh)

    def update(self):
        try:
            with open(os.path.join(self.root, runner.UPDATE_FILE)) as fh:
                return json.load(fh)
        except OSError:
            return None

    def pin(self, version, sha):
        with open(os.path.join(self.root, runner.QUEUE_FILE), "w") as fh:
            json.dump({"queue": [], "control": {"mode": "on", "skip": [], "agent": {"version": version, "sha256": sha}}}, fh)

    def serve(self, version, data):
        self.served[runner.RELEASE_URL.format(version=version)] = data
        return hashlib.sha256(data).hexdigest() if isinstance(data, bytes) else None

    def _download(self, url, dest):
        self.downloads.append(url)
        data = self.served.get(url, OSError("HTTP Error 404: Not Found"))
        if isinstance(data, Exception):
            raise data
        with open(dest, "wb") as fh:
            fh.write(data)
        return hashlib.sha256(data).hexdigest()

    def _run(self, root, slot, args):
        self.ticks.append((slot, list(args)))
        ok = self.tick_ok.get(slot, True)
        return ok, "ok" if ok else "exit 1: RuntimeError: broken"

    def tick(self, argv=(), advance=300):
        self.now += advance
        return runner.tick(self.root, list(argv), is_event_live=lambda: self.event, run=self._run,
                           download=self._download, now=self.now)


class Target(Fixture):
    def test_no_pin_runs_the_slot_and_fetches_nothing(self):
        self.assertEqual(self.tick(), 0)
        self.assertEqual(self.ticks, [("a", [])])
        self.assertEqual(self.downloads, [])

    def test_malformed_pins_are_ignored(self):
        for version, sha in (("v0.2.0", "a" * 64), ("0.2.0", "A" * 64), ("0.2.0", "abc"), ("0.2", "a" * 64)):
            self.pin(version, sha)
            self.assertIsNone(runner.target(self.root), (version, sha))
        self.tick()
        self.assertEqual(self.downloads, [])

    def test_the_url_is_built_from_the_version_only(self):
        self.assertEqual(runner.RELEASE_URL.format(version="0.2.0"),
                         "https://github.com/playon/pulse/releases/download/agent-v0.2.0/pulse-agent-0.2.0.zip")

    def test_the_update_file_is_the_one_posts_read(self):
        self.assertEqual(runner.UPDATE_FILE, pulse_agent.UPDATE_FILE)


class Update(Fixture):
    def test_downloads_checks_unpacks_and_switches(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        self.tick()
        st = self.slots()
        self.assertEqual((st["active"], st["previous"]), ("b", "a"))
        self.assertEqual(st["slots"]["b"], {"version": "0.2.0", "sha256": sha, "installedAt": self.now})
        self.assertEqual(st["probation"]["from"], "0.1.0")
        self.assertEqual(runner.slot_version(self.root, "b"), "0.2.0")
        self.assertFalse(os.path.exists(os.path.join(self.root, runner.DOWNLOAD_FILE)))
        self.assertIsNone(self.update())                       # nothing to report until it proves itself

    def test_probation_forces_a_full_pass_then_three_clean_ticks_commit(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        self.tick()
        self.tick()
        self.assertEqual(self.ticks[-1], ("b", ["--force"]))
        self.tick()
        self.assertEqual(self.ticks[-1], ("b", []))
        self.assertIsNotNone(self.slots()["probation"])
        self.tick()
        self.assertIsNone(self.slots()["probation"])
        u = self.update()
        self.assertEqual((u["status"], u["version"], u["from"]), ("applied", "0.2.0", "0.1.0"))
        n = len(self.downloads)
        self.tick()
        self.assertEqual(len(self.downloads), n)               # running the pinned bytes: nothing to do

    def test_a_failing_new_build_rolls_back_and_is_never_retried(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        self.tick()
        self.tick_ok["b"] = False
        self.assertEqual(self.tick(), 1)
        st = self.slots()
        self.assertEqual((st["active"], st["previous"], st["probation"]), ("a", "b", None))
        self.assertIn(f"0.2.0:{sha}", st["blocked"])
        u = self.update()
        self.assertEqual((u["status"], u["version"], u["from"]), ("rolled-back", "0.2.0", "0.1.0"))
        self.assertIn("broken", u["error"])
        n = len(self.downloads)
        for _ in range(3):
            self.tick()
        self.assertEqual(len(self.downloads), n)
        self.assertEqual(self.ticks[-1][0], "a")

    def test_a_tick_that_never_finished_rolls_back(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        self.tick()
        with open(os.path.join(self.root, runner.MARKER_FILE), "w") as fh:
            fh.write("killed")                                 # the task limit killed the last tick
        self.tick()
        self.assertEqual(self.slots()["active"], "a")
        self.assertEqual(self.ticks[-1][0], "a")               # this tick ran the good build
        self.assertIn("never finished", self.update()["error"])

    def test_a_wrong_hash_is_refused_and_not_retried(self):
        self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", "f" * 64)
        self.tick()
        self.assertEqual(self.slots()["active"], "a")
        self.assertFalse(os.path.exists(os.path.join(self.root, "slots", "b")))
        u = self.update()
        self.assertEqual(u["status"], "failed")
        self.assertIn("not the pinned", u["error"])
        self.tick(advance=7200)
        self.assertEqual(len(self.downloads), 1)

    def test_a_network_failure_is_retried_after_an_hour(self):
        self.pin("0.2.0", "a" * 64)                             # nothing served: a 404
        self.tick()
        self.assertEqual(self.update()["status"], "failed")
        self.tick()
        self.assertEqual(len(self.downloads), 1)
        self.tick(advance=3600)
        self.assertEqual(len(self.downloads), 2)

    def test_nothing_happens_during_an_event(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        self.event = True
        self.tick()
        self.assertEqual(self.downloads, [])
        self.event = False
        self.tick()                                            # switch
        self.event = True
        self.tick()
        self.assertEqual(self.ticks[-1], ("b", []))            # no forced pass during an event
        self.assertTrue(self.slots()["probation"]["needsFullPass"])

    def test_pinning_back_uses_the_build_still_in_the_other_slot(self):
        sha1 = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha1)
        for _ in range(4):
            self.tick()                                         # 0.2.0 in b, applied
        sha2 = self.serve("0.3.0", _zip_bytes("0.3.0"))
        self.pin("0.3.0", sha2)
        for _ in range(4):
            self.tick()                                         # 0.3.0 in a, applied
        self.assertEqual(self.slots()["active"], "a")
        n = len(self.downloads)
        self.pin("0.2.0", sha1)
        self.tick()
        self.assertEqual(len(self.downloads), n)                # no download: b still holds it
        self.assertEqual(self.slots()["active"], "b")

    def test_a_slow_tick_leaves_the_update_for_a_quicker_one(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        slow = [True]
        clock = iter(range(0, 10**6, 200))
        real = runner.time.monotonic
        runner.time.monotonic = lambda: next(clock) if slow[0] else real()
        try:
            self.tick()
        finally:
            runner.time.monotonic = real
        self.assertEqual(self.downloads, [])
        slow[0] = False
        self.tick()
        self.assertEqual(len(self.downloads), 1)

    def test_a_dry_run_changes_nothing(self):
        sha = self.serve("0.2.0", _zip_bytes("0.2.0"))
        self.pin("0.2.0", sha)
        self.tick(argv=["--dry-run"])
        self.assertEqual(self.downloads, [])
        self.assertEqual(self.ticks, [("a", ["--dry-run"])])

    def test_a_dry_run_sweeps_nothing(self):
        path = os.path.join(self.root, runner.DOWNLOAD_FILE)
        with open(path, "w") as fh:
            fh.write("half")
        self.tick(argv=["--dry-run"])
        self.assertTrue(os.path.exists(path))


class Refused(Fixture):
    def _refused(self, data, expect):
        sha = self.serve("0.2.0", data)
        self.pin("0.2.0", sha)
        self.tick()
        self.assertEqual(self.slots()["active"], "a")
        self.assertIn(expect, self.update()["error"])
        self.assertIn(f"0.2.0:{sha}", self.slots()["blocked"])

    def test_a_path_outside_the_slot(self):
        self._refused(_zip_bytes("0.2.0", extra={"../../evil.py": "x"}), "unsafe path")
        self.assertFalse(os.path.exists(os.path.join(self.root, "evil.py")))

    def test_an_absolute_path(self):
        self._refused(_zip_bytes("0.2.0", extra={"/etc/evil": "x"}), "unsafe path")

    def test_a_zip_that_says_another_version(self):
        self._refused(_zip_bytes("0.2.0", version_inside="0.9.9"), "says it is 0.9.9")

    def test_packages_the_runtime_doesnt_have(self):
        self._refused(_zip_bytes("0.2.0", reqs=REQS + "numpy\n"), "Python packages")

    def test_not_a_zip(self):
        self._refused(b"<html>a captive portal</html>", "not a zip")

    def test_missing_files(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("app/pulse_agent/VERSION", "0.2.0\n")
        self._refused(buf.getvalue(), "has no")


class UpdateReport(unittest.TestCase):
    def test_last_update_is_reported_for_a_day(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, pulse_agent.UPDATE_FILE)
            self.assertIsNone(pulse_agent.last_update(path))
            runner.report(d, "rolled-back", "0.2.0", "exit 1: boom", "0.1.0")
            u = pulse_agent.last_update(path)
            self.assertEqual(u, {"status": "rolled-back", "version": "0.2.0", "error": "exit 1: boom"})
            self.assertIsNone(pulse_agent.last_update(path, now=time.time() + 25 * 3600))

    def test_posts_carry_it(self):
        import asyncio
        import main  # noqa: F401  (binds the engine)
        from pulse_agent import checkin
        with tempfile.TemporaryDirectory() as d:
            runner.report(d, "applied", "0.2.0", "", "0.1.0")
            saved = (checkin._AGENT_VERSION, checkin._AGENT_UPDATE_PATH)
            try:
                checkin._AGENT_VERSION = "0.2.0"
                checkin._AGENT_UPDATE_PATH = os.path.join(d, pulse_agent.UPDATE_FILE)
                beat = asyncio.run(checkin._build_checkin_entry({"identity": {"venueId": "V1"}}, heartbeat=True))
            finally:
                checkin._AGENT_VERSION, checkin._AGENT_UPDATE_PATH = saved
        self.assertEqual(beat["agentUpdate"], {"status": "applied", "version": "0.2.0"})


# ── Leaks: repeated failed updates leave nothing behind (PV-85) ─────────────

class _Release(http.server.BaseHTTPRequestHandler):
    """Serves /<mode>/<version>.zip: ok, drop (the connection breaks off),
    slow (a trickle) or 404."""
    zips = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        mode, version = self.path.strip("/").split("/")[:2]
        data = self.zips.get(version.replace(".zip", ""), b"")
        try:
            if mode == "missing":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str({"ok": len(data), "drop": len(data), "slow": 40 * 70000}[mode]))
            self.end_headers()
            if mode == "ok":
                self.wfile.write(data)
            elif mode == "drop":
                self.wfile.write(data[:len(data) // 2])
            elif mode == "slow":
                for _ in range(40):
                    self.wfile.write(b"x" * 70000)
                    self.wfile.flush()
                    time.sleep(0.05)
        except OSError:
            pass                                 # the runner hung up: expected


def _open_fds():
    for d in ("/dev/fd", "/proc/self/fd"):
        if os.path.isdir(d):
            return len(os.listdir(d))
    return None


def _corrupt(data):
    """A zip whose directory reads fine but whose blob fails its CRC."""
    i = data.index(b"BLOBBLOB") + 100
    return data[:i] + bytes([data[i] ^ 0xFF]) + data[i + 1:]


class Leaks(Fixture):
    ALLOWED = {"slots", "runtime", runner.SLOTS_FILE, runner.UPDATE_FILE, runner.QUEUE_FILE,
               runner.LOG_FILE, runner.LOG_FILE + ".1"}

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Release)
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def real_tick(self, mode, advance=300):
        """A tick whose download is real HTTP to the local release server."""
        self.now += advance
        return runner.tick(self.root, [], is_event_live=lambda: False, run=self._run,
                           url_template=self.base + "/" + mode + "/{version}.zip", now=self.now)

    def assert_clean(self):
        left = set(os.listdir(self.root)) - self.ALLOWED
        self.assertEqual(left, set(), "left behind in the root")
        self.assertLessEqual(set(os.listdir(os.path.join(self.root, "slots"))), {"a", "b"})
        st = self.slots()
        for field in ("blocked", "retryAt", "tries"):
            self.assertLessEqual(len(st.get(field) or {}), 1, field)
        self.assertEqual(st["active"], "a")
        self.assertEqual(runner.slot_version(self.root, "a"), "0.1.0")

    def failing(self, i):
        """Target i, and how it fails: (mode, sha) per kind."""
        version = f"0.2.{i}"
        good = _zip_bytes(version)
        kind = ("hash", "corrupt", "drop", "missing", "notzip", "probation")[i % 6]
        if kind == "hash":
            _Release.zips[version] = good
            return "ok", "f" * 64, kind
        if kind == "corrupt":
            bad = _corrupt(_zip_bytes(version, extra={"app/blob.bin": b"BLOBBLOB" + os.urandom(4000)}))
            _Release.zips[version] = bad
            return "ok", hashlib.sha256(bad).hexdigest(), kind
        if kind == "notzip":
            bad = b"<html>captive portal</html>" * 50
            _Release.zips[version] = bad
            return "ok", hashlib.sha256(bad).hexdigest(), kind
        if kind == "probation":
            _Release.zips[version] = good
            return "ok", hashlib.sha256(good).hexdigest(), kind
        _Release.zips[version] = good
        return kind, hashlib.sha256(good).hexdigest(), kind

    def one_failed_update(self, i):
        _Release.zips.clear()
        del self.ticks[:], self.downloads[:]
        mode, sha, kind = self.failing(i)
        version = f"0.2.{i}"
        self.pin(version, sha)
        self.tick_ok["b"] = kind != "probation"
        self.real_tick(mode)
        if kind == "probation":
            self.assertEqual(self.slots()["active"], "b")
            self.real_tick(mode)                      # it crashes: back to a
        u = self.update()
        self.assertEqual(u["version"], version, kind)
        self.assertIn(u["status"], ("failed", "rolled-back"), kind)
        self.assertNotIn(self.root, u.get("error", ""), kind)
        self.assertNotIn("\\", u.get("error", ""), kind)
        self.assert_clean()
        return kind

    def test_each_failure_leaves_the_unit_on_its_build_and_nothing_behind(self):
        kinds = [self.one_failed_update(i) for i in range(6)]
        self.assertEqual(len(set(kinds)), 6)

    def test_a_refused_target_is_not_retried_until_the_target_changes(self):
        for i in (0, 1, 4, 5):                      # hash, corrupt, not a zip, crashed in probation
            self.one_failed_update(i)
            n = len(self.downloads), self.update()["at"]
            for _ in range(3):
                self.real_tick("ok", advance=RETRY_DAY)
            self.assertEqual(self.update()["at"], n[1], "tried again")
        mode, sha, _ = self.failing(0)
        self.pin("0.2.0", sha)                      # back to the first one: a change, so it's tried
        before = self.update()["at"]
        self.real_tick(mode)
        self.assertNotEqual(self.update()["at"], before)

    def _drop_until_given_up(self, version):
        _Release.zips[version] = _zip_bytes(version)
        sha = hashlib.sha256(_Release.zips[version]).hexdigest()
        key = f"{version}:{sha}"
        self.pin(version, sha)
        gaps, attempts = [], 0
        for _ in range(5):
            at = (self.update() or {}).get("at")
            self.real_tick("drop", advance=0)
            attempts += self.update()["at"] != at
            st = self.slots()
            if key in st["retryAt"]:
                gaps.append(st["retryAt"][key] - self.now)
                self.now += gaps[-1]
        return key, sha, gaps, attempts

    def test_a_network_failure_backs_off_then_gives_up_after_five(self):
        key, sha, gaps, attempts = self._drop_until_given_up("0.3.0")
        self.assertEqual(gaps, [3600, 7200, 14400, 28800])
        self.assertEqual(attempts, 5)
        st = self.slots()
        self.assertIn(key, st["blocked"])
        self.assertEqual((st["retryAt"], st["tries"]), ({}, {}))
        u = self.update()
        self.assertEqual((u["status"], u["version"]), ("failed", "0.3.0"))
        self.assertIn("gave up after 5 network failures", u["error"])
        self.assertIn("broke off", u["error"])                 # the last cause
        self.assertNotIn(self.root, u["error"])
        at = u["at"]
        for _ in range(3):
            self.real_tick("ok", advance=RETRY_DAY)            # served fine now: still no 6th attempt
        self.assertEqual(self.update()["at"], at)
        self.assertEqual(self.slots()["active"], "a")
        self.assert_clean()

    def test_a_given_up_target_is_tried_again_after_it_changes(self):
        key, sha, _, _ = self._drop_until_given_up("0.3.0")
        self.pin("0.3.1", "b" * 64)                             # another target...
        self.real_tick("missing", advance=1)
        st = self.slots()
        self.assertNotIn(key, st["blocked"])
        self.assertEqual(st["tries"], {"0.3.1:" + "b" * 64: 1})  # ...counted on its own
        self.pin("0.3.0", sha)                                  # ...then back: a fresh start
        self.real_tick("ok", advance=1)
        st = self.slots()
        self.assertEqual(st["active"], "b")
        self.assertEqual((st["blocked"], st["retryAt"], st["tries"]), ({}, {}, {}))

    def test_clearing_the_target_resets_the_count(self):
        key, sha, _, _ = self._drop_until_given_up("0.3.0")
        with open(os.path.join(self.root, runner.QUEUE_FILE), "w") as fh:
            json.dump({"queue": [], "control": {"mode": "on", "skip": []}}, fh)
        self.real_tick("ok", advance=1)
        self.assertEqual(self.slots()["blocked"], {})
        self.pin("0.3.0", sha)
        self.real_tick("ok", advance=1)
        self.assertEqual(self.slots()["active"], "b")

    def test_a_success_resets_the_count(self):
        _Release.zips["0.3.0"] = _zip_bytes("0.3.0")
        sha = hashlib.sha256(_Release.zips["0.3.0"]).hexdigest()
        self.pin("0.3.0", sha)
        for _ in range(3):
            self.real_tick("drop", advance=0)
            self.now = self.slots()["retryAt"]["0.3.0:" + sha]
        self.assertEqual(self.slots()["tries"], {"0.3.0:" + sha: 3})
        self.real_tick("ok", advance=1)
        st = self.slots()
        self.assertEqual(st["active"], "b")
        self.assertEqual((st["retryAt"], st["tries"]), ({}, {}))

    def test_a_download_that_trickles_is_cut_off(self):
        saved = runner.DOWNLOAD_DEADLINE_SECONDS
        runner.DOWNLOAD_DEADLINE_SECONDS = 0.2
        try:
            _Release.zips["0.3.0"] = _zip_bytes("0.3.0")
            self.pin("0.3.0", "a" * 64)
            started = time.monotonic()
            self.real_tick("slow")
        finally:
            runner.DOWNLOAD_DEADLINE_SECONDS = saved
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertIn("took over", self.update()["error"])
        self.assert_clean()

    def test_what_a_killed_runner_leaves_is_swept(self):
        for path in (runner.DOWNLOAD_FILE, runner.SLOTS_FILE + ".tmp", runner.UPDATE_FILE + ".tmp"):
            with open(os.path.join(self.root, path), "wb") as fh:
                fh.write(b"half")
        os.makedirs(os.path.join(self.root, "slots", "b.new", "app"))
        self.tick()
        self.assert_clean()
        self.assertFalse(os.path.exists(os.path.join(self.root, "slots", "b")))

    def test_killed_between_the_two_renames_puts_the_old_slot_back(self):
        self._slot("b", "0.0.9")
        os.replace(os.path.join(self.root, "slots", "b"), os.path.join(self.root, "slots", "b.old"))
        os.makedirs(os.path.join(self.root, "slots", "b.new", "app"))
        self.tick()
        self.assertEqual(runner.slot_version(self.root, "b"), "0.0.9")
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "slots"))), ["a", "b"])

    def test_a_failed_update_keeps_the_build_in_the_other_slot(self):
        self._slot("b", "0.0.9")
        st = self.slots()
        st["slots"]["b"] = {"version": "0.0.9", "sha256": "9" * 64}
        self._write_slots(st)
        self.one_failed_update(1)                    # a damaged zip: refused before any rename
        self.assertEqual(runner.slot_version(self.root, "b"), "0.0.9")
        self.assertEqual(self.slots()["slots"]["b"]["sha256"], "9" * 64)

    def test_many_failed_updates_hold_no_memory_or_handles(self):
        import gc
        import tracemalloc
        import urllib.parse
        only = [tracemalloc.Filter(True, runner.__file__)]

        def settle():
            # urllib.parse caches up to 128 parsed URLs (Python 3.11+), and
            # each target here has its own URL: bounded, and stdlib's.
            urllib.parse.clear_cache()
            gc.collect()
            return tracemalloc.take_snapshot().filter_traces(only) if tracemalloc.is_tracing() else None

        for i in range(240):
            self.one_failed_update(i)                # warm up: imports, the interpreter's own caches
        settle()
        fds = _open_fds()
        tracemalloc.start()
        try:
            snaps, n = [settle()], 240
            for _ in range(3):
                for i in range(n, n + 60):
                    self.one_failed_update(i)
                n += 60
                snaps.append(settle())
        finally:
            tracemalloc.stop()
        # What runner.py still holds after each 60 more failed updates. It
        # keeps nothing between ticks, so a leak of even ~70 B a tick grows
        # every window by 4 KB or more. Python 3.12's own caches still settle
        # here and there (a window grows, the next shrinks), so it's the
        # smallest window that has to stay under that.
        growth, top = [], []
        for a, b in zip(snaps, snaps[1:]):
            diff = b.compare_to(a, "lineno")
            growth.append(sum(d.size_diff for d in diff))
            top.append(", ".join(f"{d.traceback[0].lineno}: {d.size_diff:+d} B" for d in diff[:3] if d.size_diff))
        self.assertLess(min(growth), 4 * 1024, f"runner.py holds memory across ticks: {growth} ({'; '.join(top)})")
        if fds is not None:
            self.assertLessEqual(_open_fds(), fds, "file handles or sockets left open")


RETRY_DAY = 25 * 3600


@unittest.skipIf(sys.platform == "win32", "the process-group check is POSIX; the VPU smoke covers taskkill /T")
class Processes(unittest.TestCase):
    """A tick that runs over is killed with everything it started."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pulse-runner-proc-")
        self.addCleanup(shutil.rmtree, self.root, True)
        app = os.path.join(self.root, "slots", "a", "app")
        os.makedirs(app)
        self.pidfile = os.path.join(self.root, "child.pid")
        with open(os.path.join(app, "monitor_once.py"), "w") as fh:
            fh.write(
                "import subprocess, sys, time\n"
                f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                f"open({self.pidfile!r}, 'w').write(str(p.pid))\n"
                "sys.stderr.write('x' * 100000 + '\\nlast line\\n')\n"
                "sys.stderr.flush()\n"
                "time.sleep(60)\n")

    def _alive(self, pid):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            try:
                done, _ = os.waitpid(pid, os.WNOHANG)    # reap it if it's ours
                if done:
                    return False
            except ChildProcessError:
                pass
            time.sleep(0.05)
        return True

    def test_a_tick_over_time_takes_its_children_with_it(self):
        for _ in range(3):
            fds = _open_fds()
            ok, note = runner.run_slot(self.root, "a", [], timeout=1.5)
            self.assertFalse(ok)
            self.assertIn("ran over", note)
            with open(self.pidfile) as fh:
                child = int(fh.read())
            self.assertFalse(self._alive(child), "the tick's child outlived it")
            if fds is not None:
                self.assertLessEqual(_open_fds(), fds)

    def test_a_tick_still_runs_when_its_stderr_file_cant_be_opened(self):
        with open(os.path.join(self.root, "slots", "a", "app", "monitor_once.py"), "w") as fh:
            fh.write("import sys\nsys.exit(0)\n")
        os.makedirs(os.path.join(self.root, runner.STDERR_FILE))     # a directory: open() fails
        self.assertEqual(runner.run_slot(self.root, "a", []), (True, "ok"))

    def test_a_failed_tick_reports_its_last_stderr_line_without_holding_it(self):
        with open(os.path.join(self.root, "slots", "a", "app", "monitor_once.py"), "w") as fh:
            fh.write("import sys\nsys.stderr.write('y' * 1000000 + '\\nRuntimeError: broken\\n')\nsys.exit(3)\n")
        ok, note = runner.run_slot(self.root, "a", [])
        self.assertEqual((ok, note), (False, "exit 3: RuntimeError: broken"))
        self.assertLessEqual(os.path.getsize(os.path.join(self.root, runner.STDERR_FILE)), 1100000)


# ── End to end: real zips, real HTTP, real monitor ticks ────────────────────

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class EndToEnd(unittest.TestCase):
    """Builds agent zips from this tree, serves them, and lets the runner
    move a unit forward and back with real ticks of the monitor (demo mode)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pulse-runner-e2e-")
        cls.www = os.path.join(cls.tmp, "www")
        cls.shas = {}
        for version, broken in (("9.9.1", False), ("9.9.2", True)):
            web = os.path.join(cls.tmp, "src-" + version)
            shutil.copytree(_WEB, web, ignore=shutil.ignore_patterns("python", "__pycache__", "tests", "*.log",
                                                                     "pulse-*.json"))
            with open(os.path.join(web, "app", "pulse_agent", "VERSION"), "w") as fh:
                fh.write(version + "\n")
            if broken:
                path = os.path.join(web, "app", "monitor_once.py")
                with open(path) as fh:
                    code = fh.read()
                with open(path, "w") as fh:
                    fh.write('raise RuntimeError("9.9.2 is broken")\n' + code)
            out = os.path.join(cls.www, f"agent-v{version}")
            _, cls.shas[version] = build_agent_zip.build(web, version, out)
        handler = lambda *a, **k: _Quiet(*a, directory=cls.www, **k)  # noqa: E731
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}" + "/agent-v{version}/pulse-agent-{version}.zip"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pulse-runner-root-")
        self.addCleanup(shutil.rmtree, self.root, True)
        # What enroll leaves: this tree in slot a, the runtime's requirements.
        shutil.copytree(_WEB, os.path.join(self.root, "slots", "a"),
                        ignore=shutil.ignore_patterns("python", "__pycache__", "tests", "*.log", "pulse-*.json"))
        os.makedirs(os.path.join(self.root, "runtime"))
        shutil.copyfile(os.path.join(_APP_DIR, "requirements.txt"), os.path.join(self.root, "runtime", "requirements.txt"))
        with open(os.path.join(self.root, runner.SLOTS_FILE), "w") as fh:
            json.dump({"active": "a", "slots": {"a": {"version": pulse_agent.AGENT_VERSION, "sha256": None}}}, fh)

    def pin(self, version):
        with open(os.path.join(self.root, runner.QUEUE_FILE), "w") as fh:
            json.dump({"queue": [], "control": {"agent": {"version": version, "sha256": self.shas[version]}}}, fh)

    def tick(self):
        return runner.tick(self.root, [], is_event_live=lambda: False, url_template=self.url)

    def slots(self):
        with open(os.path.join(self.root, runner.SLOTS_FILE)) as fh:
            return json.load(fh)

    def test_forward_to_a_good_build_and_back_from_a_broken_one(self):
        self.pin("9.9.1")
        self.assertEqual(self.tick(), 0)                       # runs a, then fetches 9.9.1 into b
        self.assertEqual(self.slots()["active"], "b")
        for _ in range(3):
            self.assertEqual(self.tick(), 0)                   # forced full pass, then clean ticks
        with open(os.path.join(self.root, runner.UPDATE_FILE)) as fh:
            self.assertEqual(json.load(fh)["status"], "applied")
        # The monitor kept its state in the root, not in the slot it ran from.
        self.assertTrue(os.path.isfile(os.path.join(self.root, "pulse-monitor-state.json")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "slots", "b", "pulse-monitor-state.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "pulse-monitor.log")))

        self.pin("9.9.2")
        self.assertEqual(self.tick(), 0)                       # runs 9.9.1, fetches 9.9.2 into a
        self.assertEqual(self.slots()["active"], "a")
        self.assertEqual(self.tick(), 1)                       # 9.9.2 fails its first tick
        st = self.slots()
        self.assertEqual((st["active"], runner.slot_version(self.root, st["active"])), ("b", "9.9.1"))
        with open(os.path.join(self.root, runner.UPDATE_FILE)) as fh:
            u = json.load(fh)
        self.assertEqual((u["status"], u["version"], u["from"]), ("rolled-back", "9.9.2", "9.9.1"))
        self.assertIn("9.9.2 is broken", u["error"])
        self.assertEqual(self.tick(), 0)                       # back on 9.9.1, and stays there


if __name__ == "__main__":
    unittest.main()
