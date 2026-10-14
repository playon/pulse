"""The "Pulse ScoreConnect Guard" task that keeps SC III's crash auto-restart on.

Sportzcast's installer deletes and re-creates the ScoreConnectIII service
(vpu-6493 2026-10-05: installing 1.4.2.2 logged System 7045 and left no
FailureActions), so the restart setting does not survive an update. The task
in Set-Sc3ServiceRecovery.ps1 puts it back. These checks read the task XML out
of the script and hold it to what was measured, so an edit that breaks a
trigger fails here instead of silently on a VPU.
"""

import os
import re
import unittest
import xml.etree.ElementTree as ET

_WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def _task_xml():
    with open(os.path.join(_WEB, "scripts", "Set-Sc3ServiceRecovery.ps1"), encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"\$GuardTaskXml = @'\r?\n(.*?)\r?\n'@", src, re.S)
    assert m, "no $GuardTaskXml here-string in Set-Sc3ServiceRecovery.ps1"
    return ET.fromstring(m.group(1))


class GuardTask(unittest.TestCase):
    def setUp(self):
        self.task = _task_xml()

    def _events(self):
        out = {}
        for trig in self.task.findall("t:Triggers/t:EventTrigger", _NS):
            sub = ET.fromstring(trig.find("t:Subscription", _NS).text)
            select = sub.find("Query/Select").text
            eid = re.search(r"EventID=(\d+)", select).group(1)
            out[eid] = (select, trig.find("t:Delay", _NS).text)
        return out

    def test_install_trigger_matches_the_measured_7045(self):
        select, delay = self._events()["7045"]
        # Measured EventData on vpu-6493: ServiceName = ScoreConnectIII.
        self.assertIn("Data[@Name='ServiceName']='ScoreConnectIII'", select)
        self.assertIn("Service Control Manager", select)
        self.assertEqual(delay, "PT30S")

    def test_crash_trigger_is_7034_only(self):
        ev = self._events()
        select, delay = ev["7034"]
        # Measured EventData: param1 = ScoreConnectIII. 7031 (Windows already
        # restarted it) must not trigger a second restart.
        self.assertIn("Data[@Name='param1']='ScoreConnectIII'", select)
        self.assertNotIn("7031", ev)
        self.assertEqual(delay, "PT10S")

    def test_boot_trigger(self):
        boots = self.task.findall("t:Triggers/t:BootTrigger", _NS)
        self.assertEqual(len(boots), 1)
        self.assertEqual(len(self.task.findall("t:Triggers/*", _NS)), 3)

    def test_runs_as_system_with_windows_tools_only(self):
        self.assertEqual(self.task.find("t:Principals/t:Principal/t:UserId", _NS).text, "S-1-5-18")
        execs = self.task.findall("t:Actions/t:Exec", _NS)
        self.assertEqual(len(execs), 1)
        self.assertEqual(execs[0].find("t:Command", _NS).text, "cmd.exe")
        args = execs[0].find("t:Arguments", _NS).text
        # Same restart actions Pulse applies directly, then a start; nothing
        # under C:\Pulse, so a Pulse update cannot break the task.
        self.assertIn("sc.exe failure ScoreConnectIII reset= 86400 actions= restart/5000/restart/5000/restart/30000", args)
        self.assertIn("& sc.exe start ScoreConnectIII", args)
        self.assertNotIn("Pulse", args)

    def test_same_actions_as_the_direct_apply(self):
        with open(os.path.join(_WEB, "scripts", "Set-Sc3ServiceRecovery.ps1"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("& sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/5000/restart/30000", src)


if __name__ == "__main__":
    unittest.main()
