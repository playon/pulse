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
