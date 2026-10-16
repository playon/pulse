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
    os.makedirs(os.path.join(root, "app", "pulse_agent"), exist_ok=True)
    for rel, text in (("app/monitor_once.py", body), ("app/main.py", "m = 1\n"),
                      ("scripts/Get-X.ps1", "1"), ("deploy/Install-PulseMonitor.ps1", "1"),
                      ("VERSION", "web-dev-v1.5.0-dev"), ("app/python/python.exe", "bin"),
                      ("app/requirements.txt", "fastapi\n"), ("app/pulse_agent/VERSION", "0.2.0\n"),
                      ("app/pulse_agent/runner.py", "# runner\n")):
        with open(os.path.join(root, rel), "w") as fh:
            fh.write(text)


RUNNER_TASK_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Version>3</Version></RegistrationInfo>
  <Actions Context="Author"><Exec>
    <Command>C:\\PulseFleetMonitor\\runtime\\python\\python.exe</Command>
    <Arguments>"C:\\PulseFleetMonitor\\agent_runner.py"</Arguments>
  </Exec></Actions>
</Task>"""


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

    def test_runner_layout(self):
        t = fe.parse_task_xml(RUNNER_TASK_XML)
        self.assertEqual(t["installDir"], "C:\\PulseFleetMonitor")
        self.assertTrue(t["runner"])
        self.assertFalse(fe.parse_task_xml(TASK_XML.format(enabled="", root="C:\\X"))["runner"])

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

    def test_changes_with_the_agent_package(self):
        with tempfile.TemporaryDirectory() as d:
            _build(d)
            os.makedirs(os.path.join(d, "app", "pulse_agent"), exist_ok=True)
            with open(os.path.join(d, "app", "pulse_agent", "checkin.py"), "w") as fh:
                fh.write("x = 1\n")
            a = fe.fingerprint(d)
            with open(os.path.join(d, "app", "pulse_agent", "checkin.py"), "w") as fh:
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



class RunnerLayout(unittest.TestCase):
    """PV-49: the task runs the agent's runner; the code is in slots."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "Pulse")
        self.root = os.path.join(self.tmp.name, "PulseFleetMonitor")
        _build(self.src)
        for p in (mock.patch.object(fe, "MONITOR_ROOT", self.root),
                  mock.patch.object(fe.sys, "platform", "win32"),
                  mock.patch.object(fe, "is_admin", return_value=True),
                  mock.patch.object(fe, "vpu_running", return_value=False)):
            p.start()
            self.addCleanup(p.stop)
        self.calls = []

    def _fake_run(self, args, timeout=60):
        """robocopy as a real copy (honouring /XD); the rest succeed."""
        import shutil
        import subprocess
        self.calls.append(args)
        if args[0] == "robocopy":
            src, dst = args[1], args[2]
            skip = set(args[args.index("/XD") + 1:args.index("/R:3")])
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if n in skip])
            return subprocess.CompletedProcess(args, 1, "", "")
        return subprocess.CompletedProcess(args, 0, "  Installed Pulse Fleet Monitor.", "")

    def _runner_task(self):
        return {"installDir": self.root, "enabled": True, "runner": True, "command": "", "arguments": "",
                "definition": "3"}

    def test_enroll_moves_an_older_layout_to_the_runner_and_keeps_state(self):
        _build(self.root)                                       # the older layout, code in the folder
        with open(os.path.join(self.root, "pulse-monitor-state.json"), "w") as fh:
            json.dump({"status": "WARN"}, fh)
        old = {"installDir": self.root, "enabled": True, "runner": False}
        with mock.patch.object(fe, "_run", side_effect=self._fake_run), \
                mock.patch.object(fe, "query_task", return_value=old):
            res = fe.enroll(self.src, "dev")
        self.assertTrue(res["ok"], res)
        r = self.root
        self.assertTrue(os.path.isfile(os.path.join(r, "runtime", "python", "python.exe")))
        self.assertEqual(open(os.path.join(r, "runtime", "requirements.txt")).read(), "fastapi\n")
        self.assertTrue(os.path.isfile(os.path.join(r, "slots", "a", "app", "monitor_once.py")))
        self.assertFalse(os.path.exists(os.path.join(r, "slots", "a", "app", "python")))   # the runtime is shared
        self.assertEqual(open(os.path.join(r, "agent_runner.py")).read(), "# runner\n")
        slots = json.load(open(os.path.join(r, fe.SLOTS_FILE)))
        self.assertEqual((slots["active"], slots["slots"]["a"]["version"], slots["slots"]["a"]["sha256"]),
                         ("a", "0.2.0", None))
        self.assertFalse(os.path.exists(os.path.join(r, "app")))                         # older layout gone
        self.assertEqual(json.load(open(os.path.join(r, "pulse-monitor-state.json"))), {"status": "WARN"})
        installer = [c for c in self.calls if c[0] == "powershell.exe"][-1]
        self.assertIn("-Runner", installer)
        self.assertEqual(installer[installer.index("-File") + 1],
                         os.path.join(r, "slots", "a", "deploy", "Install-PulseMonitor.ps1"))
        self.assertTrue(any("older layout" in s for s in res["steps"]))

    def test_enroll_refuses_a_build_without_the_runner(self):
        os.remove(os.path.join(self.src, "app", "pulse_agent", "runner.py"))
        self.assertIn("no agent runner", fe.enroll(self.src, "dev")["error"])

    def test_status_reads_the_active_slot(self):
        with mock.patch.object(fe, "_run", side_effect=self._fake_run), \
                mock.patch.object(fe, "query_task", return_value=None):
            self.assertTrue(fe.enroll(self.src, "dev")["ok"])
        with open(os.path.join(self.root, fe.UPDATE_FILE), "w") as fh:
            json.dump({"status": "applied", "version": "0.2.0"}, fh)
        ticks = os.path.join(self.root, "pulse-monitor-ticks.log")
        with open(ticks, "w") as fh:
            fh.write("2026-10-16 00:05:00 plan=none ok\n")
        with mock.patch.object(fe, "query_task", return_value=self._runner_task()):
            st = fe.status(self.src, "dev")
        self.assertEqual(st["state"], "on")
        self.assertEqual(st["version"], "agent 0.2.0 (Pulse web-dev-v1.5.0-dev)")
        self.assertIsNone(st["current"])            # fleet control picks the build, not this launch
        self.assertEqual(st["agentUpdate"]["status"], "applied")
        os.remove(os.path.join(self.root, "agent_runner.py"))
        with mock.patch.object(fe, "query_task", return_value=self._runner_task()):
            self.assertEqual(fe.status(self.src, "dev")["state"], "broken")

    def test_says_whether_the_running_slot_holds_this_build(self):
        # A dev launch never copies its build into a runner-layout monitor, so
        # the card offers "Reinstall this build" when the slot runs other code.
        with mock.patch.object(fe, "_run", side_effect=self._fake_run), \
                mock.patch.object(fe, "query_task", return_value=None):
            self.assertTrue(fe.enroll(self.src, "dev")["ok"])
        with open(os.path.join(self.root, "pulse-monitor-ticks.log"), "w") as fh:
            fh.write("2026-10-16 00:05:00 plan=none ok\n")
        with mock.patch.object(fe, "query_task", return_value=self._runner_task()):
            st = fe.status(self.src, "dev")
            self.assertTrue(st["runner"])
            self.assertTrue(st["slotMatchesThisBuild"])
            self.assertEqual(st["thisBuild"], "agent 0.2.0 (Pulse web-dev-v1.5.0-dev)")
            with open(os.path.join(self.src, "app", "monitor_once.py"), "w") as fh:
                fh.write("x = 2  # a fix in this build\n")
            st = fe.status(self.src, "dev")
        self.assertFalse(st["slotMatchesThisBuild"])
        self.assertIsNone(st["current"])                # still no "older than this Pulse"

    def test_older_layout_has_no_slot_to_compare(self):
        _build(self.root)
        with open(os.path.join(self.root, "pulse-monitor-ticks.log"), "w") as fh:
            fh.write("2026-10-16 00:05:00 plan=none ok\n")
        old = {"installDir": self.root, "enabled": True, "runner": False}
        with mock.patch.object(fe, "query_task", return_value=old):
            st = fe.status(self.src, "dev")
        self.assertFalse(st["runner"])
        self.assertIsNone(st["slotMatchesThisBuild"])

    def test_refresh_leaves_the_runner_layout_alone(self):
        with mock.patch.object(fe, "query_task", return_value=self._runner_task()), \
                mock.patch.object(fe, "enroll") as en:
            self.assertIsNone(fe.refresh(self.src, "dev"))
        en.assert_not_called()


if __name__ == "__main__":
    unittest.main()
