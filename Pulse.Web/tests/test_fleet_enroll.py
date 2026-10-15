"""Unit tests for the fleet monitor opt-in (app/fleet_enroll.py).

Standard library only. Windows calls (schtasks, robocopy, icacls) are not run:
status() is tested with query_task and the platform patched, against a temp
folder standing in for C:\\PulseFleetMonitor.

    cd Pulse.Web && .venv/bin/python -m unittest tests.test_fleet_enroll -v
"""

import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import fleet_enroll as fe  # noqa: E402

TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Version>2</Version></RegistrationInfo>
  <Settings>{enabled}</Settings>
  <Actions Context="Author"><Exec>
    <Command>{root}\\app\\python\\python.exe</Command>
    <Arguments>"{root}\\app\\monitor_once.py"</Arguments>
  </Exec></Actions>
</Task>"""


def _build(root, body="x = 1\n"):
    os.makedirs(os.path.join(root, "app", "python"), exist_ok=True)
    os.makedirs(os.path.join(root, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(root, "deploy"), exist_ok=True)
    for rel, text in (("app/monitor_once.py", body), ("app/main.py", "m = 1\n"),
                      ("scripts/Get-X.ps1", "1"), ("deploy/Install-PulseMonitor.ps1", "1"),
                      ("VERSION", "web-dev-v1.5.0-dev"), ("app/python/python.exe", "bin")):
        with open(os.path.join(root, rel), "w") as fh:
            fh.write(text)


class TaskXml(unittest.TestCase):
    def test_reads_folder_and_enabled(self):
        t = fe.parse_task_xml(TASK_XML.format(enabled="", root="C:\\PulseFleetMonitor"))
        self.assertEqual(t["installDir"], "C:\\PulseFleetMonitor")
        self.assertTrue(t["enabled"])           # <Enabled> omitted = true
        self.assertEqual(t["definition"], "2")

    def test_disabled_and_old_folder(self):
        t = fe.parse_task_xml(TASK_XML.format(enabled="<Enabled>false</Enabled>", root="C:\\Pulse"))
        self.assertEqual(t["installDir"], "C:\\Pulse")
        self.assertFalse(t["enabled"])

    def test_garbage(self):
        self.assertIsNone(fe.parse_task_xml("ERROR: The system cannot find the file specified."))


class Fingerprint(unittest.TestCase):
    def test_changes_with_code_not_runtime(self):
        with tempfile.TemporaryDirectory() as d:
            _build(d)
            a = fe.fingerprint(d)
            with open(os.path.join(d, "app", "python", "python.exe"), "w") as fh:
                fh.write("other")
            self.assertEqual(fe.fingerprint(d), a)          # runtime isn't part of it
            with open(os.path.join(d, "app", "monitor_once.py"), "w") as fh:
                fh.write("x = 2\n")
            self.assertNotEqual(fe.fingerprint(d), a)

    def test_no_monitor(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "app"))
            self.assertIsNone(fe.fingerprint(d))


class Status(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "Pulse")
        self.root = os.path.join(self.tmp.name, "PulseFleetMonitor")
        _build(self.src)
        patches = [mock.patch.object(fe, "MONITOR_ROOT", self.root),
                   mock.patch.object(fe.sys, "platform", "win32"),
                   mock.patch.object(fe, "is_admin", return_value=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def _task(self, root=None, enabled=True):
        return mock.patch.object(fe, "query_task", return_value={
            "installDir": root or self.root, "enabled": enabled, "command": "", "arguments": "", "definition": "2"})

    def _enroll_files(self, tick_age=60, control=None, same_build=True):
        _build(self.root)
        fp = fe.fingerprint(self.src) if same_build else "old"
        with open(os.path.join(self.root, fe.BUILD_FILE), "w") as fh:
            json.dump({"fingerprint": fp, "copiedAt": time.time() - 3600}, fh)
        with open(os.path.join(self.root, "pulse-monitor-posts.json"), "w") as fh:
            json.dump({"lastPostAt": time.time() - 300, "lastKind": "heartbeat",
                       "identity": {"venueId": "5d6b/x", "vpuName": "Gym"}}, fh)
        with open(os.path.join(self.root, "pulse-monitor-state.json"), "w") as fh:
            json.dump({"status": "WARN"}, fh)
        if control:
            with open(os.path.join(self.root, "pulse-monitor-checkin-queue.json"), "w") as fh:
                json.dump({"control": control}, fh)
        ticks = os.path.join(self.root, "pulse-monitor-ticks.log")
        with open(ticks, "w") as fh:
            fh.write("2026-10-15 00:05:00 plan=none eventLive=0 took=0.14s ok\n")
        t = time.time() - tick_age
        os.utime(ticks, (t, t))

    def test_not_dev_has_no_card(self):
        st = fe.status(self.src, "production")
        self.assertEqual(st["state"], "unavailable")
        self.assertFalse(st["available"])

    def test_off(self):
        with mock.patch.object(fe, "query_task", return_value=None):
            self.assertEqual(fe.status(self.src, "dev")["state"], "off")

    def test_old_install_in_c_pulse(self):
        with self._task(root="C:\\Pulse"):
            self.assertEqual(fe.status(self.src, "dev")["state"], "elsewhere")

    def test_on(self):
        self._enroll_files()
        with self._task():
            st = fe.status(self.src, "dev")
        self.assertEqual(st["state"], "on")
        self.assertTrue(st["current"])
        self.assertEqual(st["verdict"], "WARN")
        self.assertEqual(st["lastTickOutcome"], "ok")
        self.assertTrue(st["unitUrl"].endswith("#/unit/5d6b%2Fx"))

    def test_older_build_still_on_but_not_current(self):
        self._enroll_files(same_build=False)
        with self._task():
            st = fe.status(self.src, "dev")
        self.assertEqual(st["state"], "on")
        self.assertFalse(st["current"])

    def test_stopped_ticking_is_broken_not_on(self):
        self._enroll_files(tick_age=45 * 60)
        with self._task():
            st = fe.status(self.src, "dev")
        self.assertEqual(st["state"], "broken")
        self.assertIn("45 minutes", st["problem"])

    def test_disabled_is_broken(self):
        self._enroll_files()
        with self._task(enabled=False):
            self.assertEqual(fe.status(self.src, "dev")["state"], "broken")

    def test_files_gone_is_broken(self):
        with self._task():
            st = fe.status(self.src, "dev")
        self.assertEqual(st["state"], "broken")
        self.assertIn("missing", st["problem"])

    def test_paused_from_vitals(self):
        self._enroll_files(control={"mode": "off"})
        with self._task():
            self.assertEqual(fe.status(self.src, "dev")["state"], "paused")


class Guards(unittest.TestCase):
    def test_refuses_off_dev_and_without_admin(self):
        with tempfile.TemporaryDirectory() as d:
            _build(d)
            with mock.patch.object(fe.sys, "platform", "win32"), \
                    mock.patch.object(fe, "is_admin", return_value=True):
                self.assertIn("dev channel", fe.enroll(d, "production")["error"])
            with mock.patch.object(fe.sys, "platform", "win32"), \
                    mock.patch.object(fe, "is_admin", return_value=False):
                self.assertIn("administrator", fe.enroll(d, "dev")["error"])

    def test_refuses_during_an_event(self):
        with tempfile.TemporaryDirectory() as d:
            _build(d)
            with mock.patch.object(fe.sys, "platform", "win32"), \
                    mock.patch.object(fe, "is_admin", return_value=True), \
                    mock.patch.object(fe, "vpu_running", return_value=True), \
                    mock.patch.object(fe, "query_task") as q:
                res = fe.enroll(d, "dev")
            self.assertFalse(res["ok"])
            self.assertIn("event is live", res["error"])
            q.assert_not_called()               # nothing was touched

    def test_refresh_only_when_build_differs(self):
        with tempfile.TemporaryDirectory() as d:
            src, root = os.path.join(d, "Pulse"), os.path.join(d, "Mon")
            _build(src)
            _build(root)
            with open(os.path.join(root, fe.BUILD_FILE), "w") as fh:
                json.dump({"fingerprint": fe.fingerprint(src)}, fh)
            task = {"installDir": root, "enabled": True}
            with mock.patch.object(fe, "MONITOR_ROOT", root), \
                    mock.patch.object(fe.sys, "platform", "win32"), \
                    mock.patch.object(fe, "is_admin", return_value=True), \
                    mock.patch.object(fe, "query_task", return_value=task), \
                    mock.patch.object(fe, "enroll") as en:
                self.assertIsNone(fe.refresh(src, "dev"))
                en.assert_not_called()
                with open(os.path.join(src, "app", "monitor_once.py"), "w") as fh:
                    fh.write("x = 3\n")
                with mock.patch.object(fe, "vpu_running", return_value=False):
                    fe.refresh(src, "dev")
                en.assert_called_once()


if __name__ == "__main__":
    unittest.main()
